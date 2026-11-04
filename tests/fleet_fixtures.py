"""Shared builders for fleet and API tests: small inspections with known verdicts."""

from __future__ import annotations

from pathlib import Path

from bladesight.contracts import (
    Assessment,
    BBox,
    Defect,
    InspectedDefect,
    Inspection,
    InspectionImage,
    InspectionSummary,
    Measurement,
    Verification,
)
from bladesight.fleet.rank import summarize
from bladesight.fleet.store import Store


def _defect(image_id: str, n: int, severity: int | None, verdict: str | None) -> InspectedDefect:
    did = f"{image_id}/d{n}"
    item = InspectedDefect(
        defect=Defect(
            id=did,
            image_id=image_id,
            concept="c",
            label="damage",
            score=0.8,
            bbox=BBox(x1=0, y1=0, x2=10, y2=10),
            mask_area_px=100,
        ),
        measurement=Measurement(
            defect_id=did,
            area_px=100,
            tile_area_ratio=0.001,
            length_px=10,
            width_px=5,
            elongation=0.5,
            position="unknown",
        ),
    )
    if severity is not None:
        item.assessment = Assessment(
            defect_id=did,
            defect_type="crack",
            severity=severity,
            rationale="r",
            confidence=0.8,
            rubric_version="v1",
            prompt_version="assess/v1",
            model="m",
            provider="stub",
        )
    if verdict is not None:
        item.verification = Verification(
            defect_id=did,
            verdict=verdict,  # type: ignore[arg-type]
            agreement=1.0,
            reasons=["because"],
        )
    return item


def _inspection(tid: str, year: int, specs: list[tuple[int | None, str | None]]) -> Inspection:
    image_id = f"{tid}-{year}/DJI_0001_01_01"
    image = InspectionImage(
        id=image_id,
        tile_id="DJI_0001_01_01",
        image_url="/images/DJI_0001_01_01.png",
        width=586,
        height=371,
        defects=[_defect(image_id, n, s, v) for n, (s, v) in enumerate(specs, start=1)],
    )
    summary = InspectionSummary(
        id=f"{tid}-{year}",
        turbine_id=tid,
        year=year,
        n_images=1,
        n_defects=0,
        max_severity=None,
        n_needs_review=0,
        n_reinspect=0,
    )
    inspection = Inspection(summary=summary, images=[image])
    inspection.summary = summarize(inspection)
    return inspection


def make_store(tmp_path: Path) -> Store:
    s = Store(tmp_path / "replay")
    s.save_inspection(_inspection("T01", 2017, [(2, "ok")]))
    s.save_inspection(_inspection("T01", 2018, [(4, "ok"), (3, "needs_review"), (None, None)]))
    s.save_inspection(_inspection("T02", 2017, [(1, "ok")]))
    s.save_inspection(_inspection("T02", 2018, [(1, "ok")]))
    s.save_inspection(_inspection("T03", 2017, []))
    s.save_inspection(_inspection("T03", 2018, [(5, "reinspect")]))
    return s
