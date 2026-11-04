"""The API contract: fixtures validate, the committed fixtures match the code, no drift."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from bladesight.contract_examples import FIXTURE_DIR, fixtures, schema
from bladesight.contracts import (
    EXPORTED,
    AgentRun,
    EvalReport,
    Fleet,
    Health,
    Inspection,
    ReplaySet,
    Report,
    Verification,
    WorkOrder,
)

ROOT = Path(__file__).resolve().parents[1]
RESPONSE_TYPES: dict[str, Any] = {
    "health.json": Health,
    "fleet.json": Fleet,
    "inspection_T03-2018.json": Inspection,
    "work_orders.json": list[WorkOrder],
    "report_latest.json": Report,
    "runs.json": list[AgentRun],
    "run_run-example-001.json": AgentRun,
    "eval.json": list[EvalReport],
    "replays.json": list[ReplaySet],
}


@pytest.mark.parametrize("name", sorted(RESPONSE_TYPES))
def test_each_fixture_validates_against_its_response_type(name: str) -> None:
    TypeAdapter(RESPONSE_TYPES[name]).validate_python(fixtures()[name])


def test_committed_fixtures_match_the_code() -> None:
    files = {**fixtures(), "schema.json": schema()}
    for name, payload in files.items():
        committed = json.loads((ROOT / FIXTURE_DIR / name).read_text(encoding="utf-8"))
        assert committed == payload, f"{name} is stale: run `uv run poe contract`"


def test_schema_has_every_exported_model() -> None:
    assert set(EXPORTED) <= set(schema()["$defs"])


def test_contract_rejects_unknown_fields_and_empty_evidence() -> None:
    order = fixtures()["work_orders.json"][0]
    with pytest.raises(ValidationError):
        WorkOrder.model_validate({**order, "surprise": 1})
    with pytest.raises(ValidationError):
        WorkOrder.model_validate({**order, "evidence": []})
    with pytest.raises(ValidationError):
        WorkOrder.model_validate({**order, "defect_ids": []})


def test_verdicts_are_closed() -> None:
    with pytest.raises(ValidationError):
        Verification.model_validate(
            {"defect_id": "x", "verdict": "probably_fine", "agreement": 1, "reasons": ["r"]}
        )


def test_verification_reasons_cannot_be_empty() -> None:
    with pytest.raises(ValidationError):
        Verification.model_validate(
            {"defect_id": "x", "verdict": "ok", "agreement": 1, "reasons": []}
        )


def test_fixtures_agree_with_each_other() -> None:
    data = fixtures()
    fleet = Fleet.model_validate(data["fleet.json"])
    inspection = Inspection.model_validate(data["inspection_T03-2018.json"])
    orders = TypeAdapter(list[WorkOrder]).validate_python(data["work_orders.json"])
    run = AgentRun.model_validate(data["run_run-example-001.json"])
    report = Report.model_validate(data["report_latest.json"])

    defect_ids = {d.defect.id for img in inspection.images for d in img.defects}
    assert all(set(o.defect_ids) <= defect_ids for o in orders)
    assert run.work_order_ids == [o.id for o in orders] == report.work_order_ids
    assert report.run_id == run.id == fleet.run_id
    assert [t.rank for t in fleet.turbines] == list(range(1, len(fleet.turbines) + 1))
    t03 = next(t for t in fleet.turbines if t.id == "T03")
    assert t03.rank == 1 and t03.inspections[-1] == inspection.summary
    assert t03.open_work_orders == len(orders)
    assert sum(t.open_work_orders for t in fleet.turbines) == len(orders)
    summary = inspection.summary
    assert summary.n_defects == len(defect_ids)
    verdicts = [
        d.verification.verdict for i in inspection.images for d in i.defects if d.verification
    ]
    assert summary.n_needs_review == verdicts.count("needs_review")
    assert summary.n_reinspect == verdicts.count("reinspect")
    for turbine in fleet.turbines:
        for s in turbine.inspections:
            assert s.n_needs_review + s.n_reinspect <= s.n_defects
            assert (s.max_severity is None) == (s.n_defects == 0)
