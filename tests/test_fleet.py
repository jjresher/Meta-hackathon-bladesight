"""Fleet: layout, ranking, store, the seven tools (evidence rule), the agent loop and replay."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fleet_fixtures import make_store

from bladesight.data import TileLabel
from bladesight.fleet.agent import run_agent
from bladesight.fleet.build import build_layout
from bladesight.fleet.rank import build_fleet, score, status_of, trend_of
from bladesight.fleet.store import Store
from bladesight.fleet.tools import FleetTools
from bladesight.meta import ChatResult, MetaSettings, StubProvider, ToolCall, Usage, build_client


@pytest.fixture
def store(tmp_path: Path) -> Store:
    return make_store(tmp_path)


# --- layout ------------------------------------------------------------------------------------


def _tiles(n: int = 400) -> list[TileLabel]:
    out = []
    for i in range(n):
        boxes = [{"label": "damage", "x1": 0, "y1": 0, "x2": 5, "y2": 5}] if i % 4 == 0 else []
        out.append(
            TileLabel.model_validate(
                {
                    "tile_id": f"DJI_{i:04d}_01_01",
                    "source_photo": f"DJI_{i:04d}",
                    "row": 1,
                    "col": 1,
                    "width": 586,
                    "height": 371,
                    "boxes": boxes,
                }
            )
        )
    return out


def test_layout_is_a_reproducible_synthetic_farm_without_reused_tiles() -> None:
    layout = build_layout(_tiles())
    assert layout == build_layout(_tiles()) and layout["synthetic"] is True
    assert len(layout["turbines"]) == 12
    used = [t for years in layout["turbines"].values() for tiles in years.values() for t in tiles]
    assert len(used) == 12 * 2 * 4 == len(set(used))
    assert "invented grouping" in layout["note"]
    with pytest.raises(ValueError):
        build_layout(_tiles(20))


# --- ranking -----------------------------------------------------------------------------------


def test_only_verified_defects_drive_score_status_and_trend(store: Store) -> None:
    t1 = store.inspection("T01-2018")
    assert (
        score(t1) == 10.0 + 4.0 * 0.25
    )  # severity 4 verified, severity 3 pending counts a quarter
    assert status_of(t1) == "critical"
    assert status_of(store.inspection("T03-2018")) == "needs_review"  # reinspect adds no score
    assert score(store.inspection("T03-2018")) == 0.0
    assert trend_of(store.inspection("T01-2017"), t1) == "worse"
    assert trend_of(None, t1) == "new"
    assert trend_of(store.inspection("T02-2017"), store.inspection("T02-2018")) == "same"


def test_fleet_is_ranked_and_labelled_synthetic(store: Store) -> None:
    fleet = build_fleet(store.inspections(), [])
    assert [t.id for t in fleet.turbines] == ["T01", "T02", "T03"] or fleet.turbines[0].id == "T01"
    assert [t.rank for t in fleet.turbines] == [1, 2, 3]
    assert "Synthetic farm" in fleet.note and fleet.synthetic is True


def test_store_round_trip_and_unsafe_ids(store: Store) -> None:
    assert store.inspection("T01-2018").summary.max_severity == 4
    with pytest.raises(KeyError):
        store.inspection("../layout")
    with pytest.raises(KeyError):
        store.inspection("T99-2018")
    store.save_work_orders([])
    assert store.work_orders() == []


# --- tools -------------------------------------------------------------------------------------

VERIFIED = "T01-2018/DJI_0001_01_01/d1"
PENDING = "T01-2018/DJI_0001_01_01/d2"
UNGRADED = "T01-2018/DJI_0001_01_01/d3"


def _call(tools: FleetTools, name: str, **args: object) -> dict:
    return json.loads(tools.call(name, dict(args)))


def test_work_order_needs_verified_defects_and_writes_its_own_evidence(store: Store) -> None:
    tools = FleetTools(store, "run-x")
    base = {"inspection_id": "T01-2018", "action": "repair", "rationale": "crack"}
    rejected = _call(tools, "create_work_order", defect_ids=[VERIFIED, PENDING], **base)
    assert "no work order without a verified assessment" in rejected["error"] and not tools.orders
    ungraded = _call(tools, "create_work_order", defect_ids=[UNGRADED], **base)
    assert "not graded" in ungraded["error"]
    ok = _call(tools, "create_work_order", defect_ids=[VERIFIED], priority="P1", **base)
    assert ok["created"] == "WO-001" and "severity 4" in ok["evidence"][0]
    order = tools.orders[0]
    assert order.defect_ids == [VERIFIED] and order.priority == "P1" and order.run_id == "run-x"


def test_unknown_defects_and_bad_arguments_are_reported_not_raised(store: Store) -> None:
    tools = FleetTools(store, "r")
    args = {"inspection_id": "T01-2018", "action": "a", "rationale": "r"}
    missing = _call(tools, "create_work_order", defect_ids=["T01-2018/nope/d9"], **args)
    assert "not in" in missing["error"]
    assert "error" in _call(tools, "create_work_order", inspection_id="T01-2018")
    assert "unknown tool" in _call(tools, "delete_everything")["error"]
    wrong_kind = _call(tools, "create_work_order", kind="reinspect", defect_ids=[VERIFIED], **args)
    assert "kind" in wrong_kind["error"]


def test_reinspection_is_for_unverified_defects_and_cites_the_reasons(store: Store) -> None:
    tools = FleetTools(store, "r")
    done = _call(
        tools,
        "request_reinspection",
        inspection_id="T01-2018",
        defect_ids=[PENDING],
        reason="the looks differ",
    )
    assert done["created"] == "WO-001" and "not verified" in done["evidence"][0]
    assert tools.orders[0].kind == "reinspect"


def test_report_may_only_cite_existing_orders_and_assessed_defects(store: Store) -> None:
    tools = FleetTools(store, "r")
    _call(tools, "request_reinspection", inspection_id="T01-2018", defect_ids=[PENDING], reason="r")
    assert "do not exist" in _call(tools, "write_report", markdown="see WO-007")["error"]
    unknown = _call(tools, "write_report", markdown="T09-2018/DJI_0001_01_01/d1")
    assert "not assessed" in unknown["error"]
    ok = _call(tools, "write_report", markdown=f"WO-001 for {PENDING}")
    assert ok["report_saved"] is True and tools.report is not None and tools.report.id == "report-r"


def test_read_tools(store: Store) -> None:
    tools = FleetTools(store, "r")
    ranking = _call(tools, "list_turbines")
    assert ranking[0]["turbine_id"] == "T01" and ranking[0]["rank"] == 1
    insp = _call(tools, "get_inspection", inspection_id="T01-2018")
    assert insp["summary"]["max_severity"] == 4 and len(insp["images"][0]["defects"]) == 3
    cmp = _call(tools, "compare_inspections", turbine_id="T01")
    assert cmp["synthetic_years"] is True and cmp["inspections"][1]["verified_severities"] == [4]
    assert "fewer than two" in _call(tools, "compare_inspections", turbine_id="T77")["error"]
    image = _call(tools, "assess_image", image_id="T01-2018/DJI_0001_01_01")
    assert image["defects"][0]["verdict"] == "ok"
    assert (
        "unknown image" in _call(tools, "assess_image", image_id="T01-2018/DJI_9999_01_01")["error"]
    )


# --- agent -------------------------------------------------------------------------------------


def _calls(*calls: tuple[str, dict]) -> ChatResult:
    return ChatResult(
        text="",
        tool_calls=[ToolCall(id=f"c{i}", name=n, arguments=a) for i, (n, a) in enumerate(calls)],
        usage=Usage(input_tokens=100, output_tokens=20),
        model="stub-model",
    )


def _final(text: str = "Done. 1 repair, 1 re-inspection.") -> ChatResult:
    return ChatResult(
        text=text, usage=Usage(input_tokens=100, output_tokens=20), model="stub-model"
    )


def _script() -> list[ChatResult]:
    base = {"inspection_id": "T01-2018", "action": "repair now", "rationale": "verified crack"}
    return [
        _calls(("list_turbines", {})),
        _calls(("create_work_order", {"defect_ids": [PENDING], **base})),  # rejected by the tool
        _calls(
            ("create_work_order", {"defect_ids": [VERIFIED], "priority": "P1", **base}),
            (
                "request_reinspection",
                {"inspection_id": "T01-2018", "defect_ids": [PENDING], "reason": "looks differ"},
            ),
        ),
        _calls(("write_report", {"title": "Farm", "markdown": f"WO-001 {VERIFIED}; WO-002"})),
        _final(),
    ]


def test_agent_run_end_to_end_with_a_trace_and_saved_results(store: Store) -> None:
    stub = StubProvider(chat_responses=_script())
    client = build_client(MetaSettings(), provider="stub", stub=stub)
    run = run_agent(client, MetaSettings(), store, run_id="run-test", provider="stub")
    assert run.status == "completed" and run.work_order_ids == ["WO-001", "WO-002"]
    kinds = [s.kind for s in run.steps]
    assert kinds[0] == "tool_call" and kinds[-1] == "final" and "tool_result" in kinds
    rejected = [s for s in run.steps if s.kind == "tool_result" and "no work order" in s.content]
    assert len(rejected) == 1  # the agent was told no and carried on
    assert [s.index for s in run.steps] == list(range(len(run.steps)))
    assert [o.kind for o in store.work_orders()] == ["repair", "reinspect"]
    assert (
        store.latest_report() is not None and store.run("run-test").report_id == "report-run-test"
    )
    assert all(VERIFIED in o.evidence[0] or PENDING in o.evidence[0] for o in store.work_orders())
    # the tool result went back to the model as a tool message
    last_request = stub.chat_calls[-1]
    assert [m.role for m in last_request.messages][-2:] == ["assistant", "tool"]
    assert last_request.tools and len(last_request.tools) == 7


def test_step_limit_and_budget_are_enforced(store: Store) -> None:
    endless = [_calls(("list_turbines", {})) for _ in range(10)]
    client = build_client(
        MetaSettings(), provider="stub", stub=StubProvider(chat_responses=endless)
    )
    run = run_agent(client, MetaSettings(), store, max_steps=3, run_id="run-limit", provider="stub")
    assert run.status == "step_limit" and sum(s.kind == "tool_call" for s in run.steps) == 3
    client2 = build_client(MetaSettings(), provider="stub", stub=StubProvider())
    broke = run_agent(
        client2, MetaSettings(), store, max_cost_usd=0.0, run_id="run-b", provider="stub"
    )
    assert broke.status == "budget_exceeded" and broke.steps[-1].kind == "error"


def test_a_recorded_run_replays_from_the_cache_without_a_call(store: Store, tmp_path: Path) -> None:
    settings = MetaSettings(cache_dir=tmp_path / "cache")
    first = StubProvider(chat_responses=_script())
    run1 = run_agent(
        build_client(settings, provider="stub", stub=first, use_cache=True),
        settings,
        store,
        run_id="run-1",
        provider="stub",
    )
    assert run1.replay is False and len(first.chat_calls) == 5
    second = StubProvider()
    run2 = run_agent(
        build_client(settings, provider="stub", stub=second, use_cache=True),
        settings,
        store,
        run_id="run-2",
        provider="stub",
    )
    assert second.call_count == 0 and run2.replay is True
    assert run2.work_order_ids == run1.work_order_ids
