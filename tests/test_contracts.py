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
