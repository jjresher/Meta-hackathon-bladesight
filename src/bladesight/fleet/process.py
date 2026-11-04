"""Run the vision pipeline over the farm and store the results (detect -> measure -> assess ->
verify per image). This is where the money is spent (about 0.04 USD per tile); results are
cached by `bladesight.meta`, and the store makes every later step free.
"""

from __future__ import annotations

import logging
from pathlib import Path

from ..assess import AssessError, assess_defect
from ..contracts import InspectedDefect, Inspection, InspectionImage, InspectionSummary
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
from .build import inspection_id
from .rank import summarize
from .store import Store

log = logging.getLogger(__name__)
MAX_DEFECTS_PER_IMAGE = 4  # the highest-scoring detections are graded; the rest are dropped


def process_image(
    client: MetaClient,
    settings: MetaSettings,
    png: bytes,
    tile_id: str,
    image_id: str,
    *,
    provider: str = "meta",
) -> InspectionImage:
    detection = detect_tile(client, settings, tile_id, png, image_id=image_id, with_blade=False)
    measurements = {m.defect_id: m for m in measure_detection(detection)}
    ranked = sorted(detection.defects, key=lambda d: -d.defect.score)[:MAX_DEFECTS_PER_IMAGE]
    defects: list[InspectedDefect] = []
    for det in sorted(ranked, key=lambda d: d.defect.id):
        measurement = measurements[det.defect.id]
        item = InspectedDefect(defect=det.defect, measurement=measurement)
        try:
            item.assessment = assess_defect(
                client, settings, png, det.defect, measurement, provider=provider
            )
            item.verification = verify_defect(
                client, settings, png, det.defect, measurement, item.assessment, provider=provider
            )
        except (
            AssessError,
            MetaServerError,
            MetaTimeoutError,
            MetaConnectionError,
            MetaRateLimitError,
        ) as error:  # a cache miss, auth or spend-cap error must stop the run, not be recorded
            item.error = str(error)[:300]  # the defect stays ungraded: no guessed severity
        defects.append(item)
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
                        client, settings, png, tile_id, f"{iid}/{tile_id}", provider=provider
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
