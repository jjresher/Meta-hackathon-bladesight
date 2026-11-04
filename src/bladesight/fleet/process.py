"""Run the vision pipeline over the farm and store the results (detect -> measure -> assess ->
verify per image). This is where the money is spent (about 0.04 USD per tile); results are
cached by `bladesight.meta`, and the store makes every later step free.

Detection (Muse Spark box proposals + SAM 3.1) always runs on the Meta Model API client; grading
and the second look run on the `ChatTarget` (`bladesight.chat`), Meta or Muse Spark Open.
`regrade_farm` re-grades the defects already stored by another run (the same detections and
measurements, read from its store) with a different chat provider, so a comparison of the two
runs isolates the grading model.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from ..assess import AssessError, assess_defect
from ..assess.assess import MAX_TOKENS as ASSESS_MAX_TOKENS
from ..chat import ChatTarget
from ..contracts import (
    Defect,
    InspectedDefect,
    Inspection,
    InspectionImage,
    InspectionSummary,
    Measurement,
)
from ..data import image_path
from ..detect.pipeline import detect_tile
from ..measure import measure_detection
from ..meta import (
    MetaClient,
    MetaConnectionError,
    MetaRateLimitError,
    MetaServerError,
    MetaSettings,
    MetaTimeoutError,
)
from ..verify import verify_defect
from ..verify.verify import SECOND_MAX_TOKENS
from .build import inspection_id
from .rank import summarize
from .store import Store

log = logging.getLogger(__name__)
MAX_DEFECTS_PER_IMAGE = 4  # the highest-scoring detections are graded; the rest are dropped
_RECORDED = (
    AssessError,
    MetaServerError,
    MetaTimeoutError,
    MetaConnectionError,
    MetaRateLimitError,
)


def grade_defect(
    chat: ChatTarget, settings: MetaSettings, png: bytes, defect: Defect, measurement: Measurement
) -> InspectedDefect:
    """Assess and verify one defect on `chat`. A transient failure is recorded on the defect (it
    stays ungraded: no guessed severity); a cache miss, auth or spend-cap error stops the run."""
    item = InspectedDefect(defect=defect, measurement=measurement)
    try:
        item.assessment = assess_defect(
            chat.client,
            settings,
            png,
            defect,
            measurement,
            provider=chat.provider,
            model=chat.model,
            max_tokens=chat.budget(ASSESS_MAX_TOKENS),
        )
        item.verification = verify_defect(
            chat.client,
            settings,
            png,
            defect,
            measurement,
            item.assessment,
            provider=chat.provider,
            model=chat.model,
            max_tokens=chat.budget(SECOND_MAX_TOKENS),
        )
    except _RECORDED as error:
        item.error = str(error)[:300]
    return item


def process_image(
    client: MetaClient,
    settings: MetaSettings,
    png: bytes,
    tile_id: str,
    image_id: str,
    *,
    provider: str = "meta",
    chat: ChatTarget | None = None,
) -> InspectionImage:
    """`client` runs detection (Meta Model API); `chat` grades (defaults to `client` on Meta)."""
    chat = chat or ChatTarget(client, provider, settings.chat_model)  # type: ignore[arg-type]
    detection = detect_tile(client, settings, tile_id, png, image_id=image_id, with_blade=False)
    measurements = {m.defect_id: m for m in measure_detection(detection)}
    ranked = sorted(detection.defects, key=lambda d: -d.defect.score)[:MAX_DEFECTS_PER_IMAGE]
    defects = [
        grade_defect(chat, settings, png, det.defect, measurements[det.defect.id])
        for det in sorted(ranked, key=lambda d: d.defect.id)
    ]
    return InspectionImage(
        id=image_id,
        tile_id=tile_id,
        image_url=f"/images/{tile_id}.png",
        width=detection.width,
        height=detection.height,
        defects=defects,
    )


def process_farm(
    client: MetaClient,
    settings: MetaSettings,
    store: Store,
    data_dir: Path,
    *,
    only: set[str] | None = None,
    provider: str = "meta",
    chat: ChatTarget | None = None,
) -> list[str]:
    """Process every inspection of the layout not yet in the store (resumable after a failure)."""
    done: list[str] = []
    layout = store.layout()
    for turbine, years in layout["turbines"].items():
        for year, tiles in years.items():
            iid = inspection_id(turbine, int(year))
            if (only and iid not in only) or store.has_inspection(iid):
                continue
            images = []
            for tile_id in tiles:
                png = image_path(tile_id, "dev", data_dir).read_bytes()
                images.append(
                    process_image(
                        client,
                        settings,
                        png,
                        tile_id,
                        f"{iid}/{tile_id}",
                        provider=provider,
                        chat=chat,
                    )
                )
            summary = InspectionSummary(
                id=iid,
                turbine_id=turbine,
                year=int(year),
                n_images=len(images),
                n_defects=0,
                max_severity=None,
                n_needs_review=0,
                n_reinspect=0,
            )
            inspection = Inspection(summary=summary, images=images)
            inspection.summary = summarize(inspection)
            store.save_inspection(inspection)  # saved per inspection: a failure keeps the rest
            log.info("stored %s", iid)
            done.append(iid)
    return done


def regrade_farm(
    chat: ChatTarget,
    settings: MetaSettings,
    source: Store,
    target: Store,
    data_dir: Path,
    *,
    only: set[str] | None = None,
    workers: int = 1,
) -> list[str]:
    """Re-grade and re-verify every defect stored in `source` on `chat`, into `target`.

    The detections and measurements are copied from `source` unchanged (no detection call), so
    the two stores differ only in the grading and verification model. Resumable: inspections
    already in `target` are skipped. `workers` > 1 grades defects of one inspection in parallel
    threads; the provider's rate limiter (`meta.ratelimit`) still bounds the request rate.
    """
    target.save_layout(source.layout())
    target.save_manifest(
        {**source.manifest(), "regraded_from": source.root.as_posix(), "chat_model": chat.model}
    )
    done: list[str] = []
    for old in source.inspections():
        iid = old.summary.id
        if (only and iid not in only) or target.has_inspection(iid):
            continue
        jobs: list[tuple[int, int, bytes, InspectedDefect]] = []
        for i, image in enumerate(old.images):
            png = image_path(image.tile_id, "dev", data_dir).read_bytes()
            jobs += [(i, j, png, d) for j, d in enumerate(image.defects)]

        def run(job: tuple[int, int, bytes, InspectedDefect]) -> InspectedDefect:
            _, _, png, d = job
            if d.measurement is None:  # never graded in the source run either
                return d.model_copy(update={"assessment": None, "verification": None})
            return grade_defect(chat, settings, png, d.defect, d.measurement)

        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            graded = list(pool.map(run, jobs))
        images = [image.model_copy(update={"defects": []}) for image in old.images]
        for (i, _, _, _), item in zip(jobs, graded, strict=True):
            images[i].defects.append(item)
        inspection = Inspection(summary=old.summary, images=images)
        inspection.summary = summarize(inspection)
        target.save_inspection(inspection)
        log.info("stored %s", iid)
        done.append(iid)
    return done
