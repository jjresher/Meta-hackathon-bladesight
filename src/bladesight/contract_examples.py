"""Example payloads for every API response, built from the contract models.

`python -m bladesight.contract_examples` (`uv run poe contract`) writes them, plus the JSON Schema,
to `web/src/fixtures/`. They are **fixtures for UI development, not results**: every number here
is made up and must never be quoted. The real values come from the pipeline (#5-#11).
"""

from __future__ import annotations

import json
import random
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter

from .contracts import (
    EXPORTED,
    SCHEMA_VERSION,
    AgentRun,
    AgentStep,
    Assessment,
    BBox,
    Check,
    ClassMetrics,
    Defect,
    EvalReport,
    Fleet,
    Health,
    InspectedDefect,
    Inspection,
    InspectionImage,
    InspectionSummary,
    Interval,
    Measurement,
    Report,
    SweepPoint,
    Turbine,
    Verification,
    WorkOrder,
)

FIXTURE_DIR = Path("web/src/fixtures")
NOTE = "EXAMPLE FIXTURE for UI development: made-up values, not results"
T0 = datetime(2026, 11, 3, 12, 0, tzinfo=UTC)
RUN_ID = "run-example-001"
TILE_W, TILE_H = 586, 371


def _box_outline(b: BBox) -> list[list[tuple[float, float]]]:
    return [[(b.x1, b.y1), (b.x2, b.y1), (b.x2, b.y2), (b.x1, b.y2)]]


def _defect(
    image_id: str,
    n: int,
    concept: str,
    box: BBox,
    *,
    severity: int,
    second: int,
    verdict: str,
    defect_type: str,
    reasons: list[str],
) -> InspectedDefect:
    defect_id = f"{image_id}/d{n}"
    area = (box.x2 - box.x1) * (box.y2 - box.y1) * 0.7
    length, width = max(box.x2 - box.x1, box.y2 - box.y1), min(box.x2 - box.x1, box.y2 - box.y1)
    return InspectedDefect.model_validate(
        {
            "defect": Defect(
                id=defect_id,
                image_id=image_id,
                concept=concept,
                label="dirt" if concept == "dirt" else "damage",
                score=0.81 if verdict == "ok" else 0.52,
                bbox=box,
                outline=_box_outline(box),
                mask_area_px=area,
            ),
            "measurement": Measurement(
                defect_id=defect_id,
                area_px=area,
                tile_area_ratio=round(area / (TILE_W * TILE_H), 5),
                blade_area_ratio=round(area / 90_000, 4),
                length_px=length,
                width_px=width,
                elongation=round(1 - width / length, 3),
                inside_blade=0.98,
                position="tip",
                position_t=0.82,
            ),
            "assessment": Assessment.model_validate(
                {
                    "defect_id": defect_id,
                    "defect_type": defect_type,
                    "severity": severity,
                    "rationale": "Example rationale: exposed laminate at the leading edge, "
                    "about a fifth of the visible chord.",
                    "confidence": 0.78 if verdict == "ok" else 0.41,
                    "rubric_version": "v1",
                    "prompt_version": "assess/v1",
                    "model": "muse-spark-1.3",
                    "provider": "meta",
                }
            ),
            "verification": Verification.model_validate(
                {
                    "defect_id": defect_id,
                    "verdict": verdict,
                    "agreement": 1.0 if severity == second else 0.5,
                    "second_severity": second,
                    "checks": [
                        Check(
                            name="inside_blade",
                            passed=True,
                            detail="98% of the mask is on the blade",
                        ),
                        Check(
                            name="severity_vs_size",
                            passed=verdict == "ok",
                            detail="severity consistent with relative size"
                            if verdict == "ok"
                            else "severity 4 but the defect covers <0.5% of the blade",
                        ),
                    ],
                    "reasons": reasons,
                }
            ),
        }
    )


def inspection_example() -> Inspection:
    insp = "T03-2018"
    img1, img2 = f"{insp}/DJI_0702_04_05", f"{insp}/DJI_0688_04_03"
    defects1 = [
        _defect(
            img1,
            1,
            "leading edge erosion",
            BBox(x1=210, y1=120, x2=320, y2=190),
            severity=4,
            second=4,
            verdict="ok",
            defect_type="leading_edge_erosion",
            reasons=["both looks agree on severity 4", "all rule checks passed"],
        ),
        _defect(
            img1,
            2,
            "crack",
            BBox(x1=400, y1=60, x2=412, y2=140),
            severity=3,
            second=2,
            verdict="needs_review",
            defect_type="crack",
            reasons=["second look graded 2, first 3", "confidence 0.41 below 0.6"],
        ),
    ]
    defects2 = [
        _defect(
            img2,
            1,
            "dirt",
            BBox(x1=50, y1=40, x2=240, y2=310),
            severity=1,
            second=1,
            verdict="ok",
            defect_type="dirt",
            reasons=["both looks agree on severity 1"],
        ),
        _defect(
            img2,
            2,
            "surface damage",
            BBox(x1=500, y1=300, x2=530, y2=330),
            severity=4,
            second=2,
            verdict="reinspect",
            defect_type="surface_damage",
            reasons=["looks disagree by 2 levels", "severity 4 but small relative size"],
        ),
    ]
    blade = [[(0.0, 90.0), (586.0, 40.0), (586.0, 360.0), (0.0, 371.0)]]
    images = [
        InspectionImage(
            id=img,
            tile_id=img.split("/")[1],
            image_url=f"/images/{img.split('/')[1]}.png",
            width=TILE_W,
            height=TILE_H,
            blade_outline=blade,
            defects=d,
        )
        for img, d in ((img1, defects1), (img2, defects2))
    ]
    summary = InspectionSummary(
        id=insp,
        turbine_id="T03",
        year=2018,
        n_images=2,
        n_defects=4,
        max_severity=4,
        n_needs_review=1,
        n_reinspect=1,
    )
    return Inspection(summary=summary, images=images)


def _summary(rng: random.Random, tid: str, year: int) -> InspectionSummary:
    n_defects = rng.choice([0, 0, 1, 2, 3, 5])
    review = min(n_defects, rng.randint(0, 1))
    return InspectionSummary(
        id=f"{tid}-{year}",
        turbine_id=tid,
        year=year,
        n_images=rng.randint(6, 14),
        n_defects=n_defects,
        max_severity=rng.randint(1, 3) if n_defects else None,
        n_needs_review=review,
        n_reinspect=min(n_defects - review, rng.randint(0, 1)),
    )


def fleet_example() -> Fleet:
    """T03 matches `inspection_example()`, the work orders and the run; the rest are filler."""
    rng = random.Random(3)
    latest = inspection_example().summary
    t03_2017 = latest.model_copy(
        update={
            "id": "T03-2017",
            "year": 2017,
            "n_defects": 2,
            "max_severity": 2,
            "n_needs_review": 0,
            "n_reinspect": 0,
        }
    )
    turbines = [
        Turbine(
            id="T03",
            name="Turbine 03",
            rank=1,
            priority_score=92.5,
            status="critical",
            trend="worse",
            inspections=[t03_2017, latest],
            open_work_orders=len(work_orders_example()),
            reason="Example: verified severity 4 in 2018 (2 in 2017), one re-inspection",
        )
    ]
    for i in [n for n in range(1, 13) if n != 3]:
        tid = f"T{i:02d}"
        before, after = _summary(rng, tid, 2017), _summary(rng, tid, 2018)
        b, a = before.max_severity or 0, after.max_severity or 0
        trend = "worse" if a > b else "better" if a < b else "same"
        status = "needs_review" if after.n_needs_review else "attention" if a == 3 else "ok"
        turbines.append(
            Turbine(
                id=tid,
                name=f"Turbine {i:02d}",
                rank=1,
                priority_score=round(a * 15 + after.n_defects * 2 + rng.random() * 5, 1),
                status=status,
                trend=trend,
                inspections=[before, after],
                open_work_orders=0,
                reason=f"Example: max severity {a or 'none'} in 2018, trend {trend}",
            )
        )
    turbines.sort(key=lambda t: -t.priority_score)
    for rank, t in enumerate(turbines, start=1):
        t.rank = rank
    return Fleet(
        farm="Example farm (fixture)",
        note=f"{NOTE}. Real fleet: synthetic farm of real DTU photos.",
        turbines=turbines,
        run_id=RUN_ID,
        generated_at=T0,
    )


def work_orders_example() -> list[WorkOrder]:
    return [
        WorkOrder(
            id="WO-001",
            kind="repair",
            priority="P1",
            turbine_id="T03",
            inspection_id="T03-2018",
            defect_ids=["T03-2018/DJI_0702_04_05/d1"],
            action="Repair leading edge erosion near the tip before the next storm season",
            rationale="Verified severity 4, larger than in 2017",
            evidence=["T03-2018/DJI_0702_04_05/d1: severity 4, verdict ok, agreement 1.0"],
            due_within_days=30,
            run_id=RUN_ID,
        ),
        WorkOrder(
            id="WO-002",
            kind="reinspect",
            priority="P2",
            turbine_id="T03",
            inspection_id="T03-2018",
            defect_ids=["T03-2018/DJI_0688_04_03/d2"],
            action="Re-inspect with a closer drone pass: the two looks disagree",
            rationale="Verification returned reinspect; no repair claimed without evidence",
            evidence=["T03-2018/DJI_0688_04_03/d2: severity 4 vs 2, verdict reinspect"],
            due_within_days=14,
            run_id=RUN_ID,
        ),
    ]


def run_example() -> AgentRun:
    steps = [
        ("thought", None, None, "Rank the turbines by their latest verified defects."),
        ("tool_call", "list_turbines", {}, "list_turbines()"),
        ("tool_result", "list_turbines", None, "12 turbines, 24 inspections"),
        ("tool_call", "compare_inspections", {"turbine_id": "T03"}, "compare T03 2017 vs 2018"),
        ("tool_result", "compare_inspections", None, "max severity 2 -> 4, two new defects"),
        (
            "tool_call",
            "create_work_order",
            {"turbine_id": "T03", "defect_ids": ["T03-2018/DJI_0702_04_05/d1"]},
            "WO-001",
        ),
        ("tool_result", "create_work_order", None, "WO-001 created"),
        (
            "tool_call",
            "request_reinspection",
            {"defect_id": "T03-2018/DJI_0688_04_03/d2"},
            "WO-002",
        ),
        ("tool_result", "request_reinspection", None, "WO-002 created"),
        ("tool_call", "write_report", {}, "write the farm report"),
        ("tool_result", "write_report", None, "report-example-001"),
        ("final", None, None, "2 work orders, 1 re-inspection, report written."),
    ]
    return AgentRun(
        id=RUN_ID,
        status="completed",
        replay=True,
        model="muse-spark-1.3",
        provider="meta",
        started_at=T0,
        finished_at=T0 + timedelta(seconds=48),
        steps=[
            AgentStep(
                index=i,
                kind=kind,  # type: ignore[arg-type]
                tool=tool,
                arguments=args,
                content=content,
                duration_ms=1200 if kind == "tool_call" else 40,
                cost_usd=0.002 if kind in ("thought", "tool_call", "final") else 0.0,
                model="muse-spark-1.3" if kind in ("thought", "tool_call", "final") else None,
            )
            for i, (kind, tool, args, content) in enumerate(steps)
        ],
        total_cost_usd=0.014,
        work_order_ids=["WO-001", "WO-002"],
        report_id="report-example-001",
    )


def report_example() -> Report:
    return Report(
        id="report-example-001",
        run_id=RUN_ID,
        title="Example farm inspection report (fixture)",
        markdown=(
            "# Example farm inspection report\n\n"
            "_Example fixture: made-up values._\n\n"
            "## Priorities\n\n1. **T03**: leading edge erosion, severity 4 (WO-001).\n\n"
            "## Re-inspection\n\n- T03-2018/DJI_0688_04_03/d2: looks disagree (WO-002).\n"
        ),
        work_order_ids=["WO-001", "WO-002"],
        model="muse-spark-1.3",
        provider="meta",
        generated_at=T0,
    )


def eval_example() -> list[EvalReport]:
    def cm(label: str, tp: int, fp: int, fn: int) -> ClassMetrics:
        p, r = tp / (tp + fp), tp / (tp + fn)
        return ClassMetrics.model_validate(
            {
                "label": label,
                "tp": tp,
                "fp": fp,
                "fn": fn,
                "precision": round(p, 3),
                "recall": round(r, 3),
                "f1": round(2 * p * r / (p + r), 3),
                "recall_ci": Interval(low=round(r - 0.05, 3), high=round(r + 0.05, 3)),
            }
        )

    return [
        EvalReport(
            split="dev",
            n_images=300,
            iou_threshold=0.3,
            classes=[cm("damage", 60, 40, 30), cm("dirt", 30, 30, 30)],
            image_recall=0.8,
            sweep=[
                SweepPoint(threshold=t, recall=r, precision=p, false_alarms_per_image=f)
                for t, r, p, f in (
                    (0.3, 0.8, 0.4, 1.2),
                    (0.5, 0.67, 0.6, 0.5),
                    (0.7, 0.4, 0.8, 0.1),
                )
            ],
            needs_review_share=0.22,
            prompt_versions={"assess": "v1", "verify": "v1"},
            cost_usd=0.0,
            evidence_path="fixture: not a result",
            generated_at=T0,
        )
    ]


def fixtures() -> dict[str, Any]:
    """File name -> payload. Each file is one API response (see docs/api.md)."""
    inspection = inspection_example()
    run = run_example()
    payloads: dict[str, BaseModel | list[Any]] = {
        "health.json": Health(status="ok", mode="replay", version="0.1.0"),
        "fleet.json": fleet_example(),
        f"inspection_{inspection.summary.id}.json": inspection,
        "work_orders.json": work_orders_example(),
        "report_latest.json": report_example(),
        "runs.json": [run],
        f"run_{run.id}.json": run,
        "eval.json": eval_example(),
    }
    out: dict[str, Any] = {}
    for name, payload in payloads.items():
        out[name] = TypeAdapter(type(payload)).dump_python(payload, mode="json")
    return out


def schema() -> dict[str, Any]:
    defs: dict[str, Any] = {}
    for name, model in EXPORTED.items():
        model_schema = model.model_json_schema(ref_template="#/$defs/{model}", mode="serialization")
        defs.update(model_schema.pop("$defs", {}))
        defs[name] = model_schema
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"bladesight-api-{SCHEMA_VERSION}",
        "title": "BladeSight API contract",
        "description": "Generated from src/bladesight/contracts.py; do not edit by hand.",
        "$defs": dict(sorted(defs.items())),
    }


def write(directory: Path = FIXTURE_DIR) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    files = {**fixtures(), "schema.json": schema()}
    for name, payload in files.items():
        path = directory / name
        path.write_text(json.dumps(payload, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        written.append(path)
    return written


if __name__ == "__main__":
    for path in write():
        print(path)
