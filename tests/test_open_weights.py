"""Open-weights path (#15) and the agent's autonomy fields, all on the stub (0 USD).

The chat provider selector, the Baseten rate limiter (fake clock), re-grading a stored farm on
another chat model, model provenance on every stage, the replay selector of the API, the rule ids
of tool rejections and the trace backfill.
"""

from __future__ import annotations

import io
import json
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fleet_fixtures import make_store
from PIL import Image

from bladesight.api import Settings, create_app
from bladesight.chat import OPEN_WEIGHTS_MIN_OUTPUT_TOKENS, chat_provider_from_env, chat_target
from bladesight.contracts import AgentRun, AgentStep, ReplaySet
from bladesight.fleet.agent import run_agent
from bladesight.fleet.backfill import backfill
from bladesight.fleet.process import regrade_farm
from bladesight.fleet.rules import RULES, error_of, rule_for_error
from bladesight.fleet.store import Store
from bladesight.fleet.tools import FleetTools
from bladesight.fleet.trace import annotate_steps
from bladesight.meta import (
    MUSE_SPARK_OPEN_MODEL,
    ChatMessage,
    ChatRequest,
    ChatResult,
    MetaConfigError,
    MetaRateLimitError,
    MetaSettings,
    RetryPolicy,
    StubProvider,
    ToolCall,
    Usage,
    build_client,
)
from bladesight.meta.ratelimit import RateLimitedProvider, RateLimiter, limiter_for

VERIFIED = "T01-2018/DJI_0001_01_01/d1"
PENDING = "T01-2018/DJI_0001_01_01/d2"


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0
        self.sleeps: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


# --- rate limiter ------------------------------------------------------------------------------


def test_the_limiter_lets_15_requests_through_then_waits_for_the_window() -> None:
    clock = FakeClock()
    limiter = RateLimiter(15, 60.0, clock=clock, sleep=clock.sleep)
    for _ in range(15):
        assert limiter.acquire() == 0.0
    clock.now = 10.0
    assert limiter.acquire() == pytest.approx(50.0)  # the first start leaves the window at t=60
    assert clock.now == pytest.approx(60.0)
    starts = [clock.now]
    for _ in range(14):  # the other 14 starts of t=0 all expired at t=60
        limiter.acquire()
        starts.append(clock.now)
    assert starts == [60.0] * 15


def test_the_limiter_never_allows_more_than_its_rate_in_any_window() -> None:
    clock = FakeClock()
    limiter = RateLimiter(3, 60.0, clock=clock, sleep=clock.sleep)
    starts = []
    for _ in range(10):
        limiter.acquire()
        starts.append(clock.now)
        clock.now += 1.0
    for s in starts:
        assert sum(s <= t < s + 60.0 for t in starts) <= 3


def test_the_limiter_is_thread_safe() -> None:
    clock = FakeClock()
    lock = threading.Lock()

    def sleep(seconds: float) -> None:
        with lock:
            clock.now += seconds

    limiter = RateLimiter(5, 60.0, clock=clock, sleep=sleep)
    threads = [threading.Thread(target=limiter.acquire) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert clock.now == 0.0 and len(limiter._starts) == 5


def test_every_attempt_including_retries_waits_for_the_limiter() -> None:
    clock = FakeClock()
    limiter = RateLimiter(1, 60.0, clock=clock, sleep=clock.sleep)
    stub = StubProvider(failures=[MetaRateLimitError("slow down")])
    from bladesight.meta import MetaClient, SpendTracker

    client = MetaClient(
        RateLimitedProvider(stub, limiter),
        spend=SpendTracker.unlimited(),
        retry=RetryPolicy(max_attempts=2, base_delay=0.0),
        sleep=lambda _s: None,
    )
    client.chat(ChatRequest(model="m", messages=[ChatMessage.user("hi")]))
    # two attempts reached the provider; the retry waited for the window, the first did not
    assert len(stub.chat_calls) == 2 and clock.sleeps == [pytest.approx(60.0)]


def test_baseten_clients_share_one_process_wide_limiter_at_the_configured_rate(
    tmp_path: Path,
) -> None:
    settings = MetaSettings(cache_dir=tmp_path / "c", spend_log_path=tmp_path / "s.jsonl")
    one = build_client(settings, provider="baseten")
    two = build_client(settings, provider="baseten")
    assert isinstance(one.provider, RateLimitedProvider)
    assert one.provider.limiter is two.provider.limiter is limiter_for("baseten", 15)  # type: ignore[union-attr]
    assert one.provider.name == "baseten" and not one.provider.simulated
    meta = build_client(settings.model_copy(update={"meta_api_key": None}), provider="meta")
    assert not isinstance(meta.provider, RateLimitedProvider)
    rpm = MetaSettings.from_env({"BASETEN_REQUESTS_PER_MINUTE": "7"})
    assert rpm.baseten_requests_per_minute == 7
    with pytest.raises(MetaConfigError):
        MetaSettings.from_env({"BASETEN_REQUESTS_PER_MINUTE": "0"})


# --- chat provider selector --------------------------------------------------------------------


def test_the_chat_provider_comes_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BLADESIGHT_CHAT_PROVIDER", raising=False)
    assert chat_provider_from_env() == "meta"
    assert chat_provider_from_env("stub") == "stub"
    monkeypatch.setenv("BLADESIGHT_CHAT_PROVIDER", "baseten")
    assert chat_provider_from_env() == "baseten"
    monkeypatch.setenv("BLADESIGHT_CHAT_PROVIDER", "openai")
    with pytest.raises(MetaConfigError):
        chat_provider_from_env()


def test_the_open_weights_target_uses_the_listed_model_and_a_reasoning_budget(
    tmp_path: Path,
) -> None:
    settings = MetaSettings(cache_dir=tmp_path / "c", spend_log_path=tmp_path / "s.jsonl")
    target = chat_target(settings, "baseten")
    assert target.model == MUSE_SPARK_OPEN_MODEL == "meta-models/muse-spark-open"
    assert target.budget(1500) == OPEN_WEIGHTS_MIN_OUTPUT_TOKENS and target.budget(9000) == 9000
    meta = chat_target(settings, "stub")
    assert meta.model == settings.chat_model and meta.budget(1500) == 1500


# --- re-grading a stored farm on another chat model --------------------------------------------


def _grade(severity: int = 2) -> ChatResult:
    text = json.dumps(
        {"defect_type": "crack", "severity": severity, "confidence": 0.9, "rationale": "a line"}
    )
    return ChatResult(text=text, usage=Usage(input_tokens=10, output_tokens=5), model="open-m")


def _data_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "data" / "dev" / "img"
    folder.mkdir(parents=True)
    buffer = io.BytesIO()
    Image.new("RGB", (586, 371), (120, 120, 120)).save(buffer, format="PNG")
    (folder / "DJI_0001_01_01.png").write_bytes(buffer.getvalue())
    return tmp_path / "data"


def test_regrade_keeps_the_detections_and_regrades_every_defect_on_the_chat_target(
    tmp_path: Path,
) -> None:
    source = make_store(tmp_path)
    source.save_layout({"turbines": {}})
    source.save_manifest({"detection": [{"stage": "segmentation", "model": "sam-3.1",
                                         "provider": "meta"}]})  # fmt: skip
    before = {p.name: p.read_text() for p in (source.root / "inspections").glob("*.json")}
    stub = StubProvider(chat_responses=[_grade() for _ in range(40)])
    settings = MetaSettings()
    chat = chat_target(settings, "stub", client=build_client(settings, provider="stub", stub=stub))
    target = Store(tmp_path / "open")
    done = regrade_farm(chat, settings, source, target, _data_dir(tmp_path), workers=2)
    assert len(done) == 6
    assert before == {p.name: p.read_text() for p in (source.root / "inspections").glob("*.json")}
    for old, new in zip(source.inspections(), target.inspections(), strict=True):
        assert [d.defect for i in old.images for d in i.defects] == [
            d.defect for i in new.images for d in i.defects
        ]
        assert [d.measurement for i in old.images for d in i.defects] == [
            d.measurement for i in new.images for d in i.defects
        ]
        for d in (d for i in new.images for d in i.defects):
            assert d.assessment and d.assessment.provider == "stub" and d.assessment.severity == 2
            assert d.verification and d.verification.provider == "stub"
            assert d.verification.model == "open-m"
    assert len(stub.chat_calls) == 14  # 7 defects x (grade + second look)
    assert target.manifest()["detection"][0]["model"] == "sam-3.1"
    assert regrade_farm(chat, settings, source, target, _data_dir(tmp_path / "x")) == []


def test_the_open_weights_budget_reaches_both_grading_calls(tmp_path: Path) -> None:
    source = make_store(tmp_path)
    source.save_layout({"turbines": {}})
    stub = StubProvider(chat_responses=[_grade() for _ in range(40)])
    settings = MetaSettings()
    chat = chat_target(settings, "stub", client=build_client(settings, provider="stub", stub=stub))
    chat = type(chat)(chat.client, "baseten", "open-model", OPEN_WEIGHTS_MIN_OUTPUT_TOKENS)
    regrade_farm(
        chat, settings, source, Store(tmp_path / "o"), _data_dir(tmp_path), only={"T02-2017"}
    )
    assert [(r.model, r.max_tokens) for r in stub.chat_calls] == [("open-model", 6000)] * 2
    graded = Store(tmp_path / "o").inspection("T02-2017").images[0].defects[0]
    assert graded.assessment and graded.assessment.provider == "baseten"
    assert graded.verification and graded.verification.provider == "baseten"


# --- agent: model provenance and autonomy fields -----------------------------------------------


def _calls(text: str, *calls: tuple[str, dict]) -> ChatResult:
    return ChatResult(
        text=text,
        tool_calls=[ToolCall(id=f"c{i}", name=n, arguments=a) for i, (n, a) in enumerate(calls)],
        usage=Usage(input_tokens=100, output_tokens=20),
        model="stub-model",
    )


def _script() -> list[ChatResult]:
    base = {"inspection_id": "T01-2018", "action": "repair", "rationale": "verified crack"}
    return [
        _calls("Rank first.", ("list_turbines", {})),
        _calls("", ("create_work_order", {"defect_ids": [PENDING], **base})),
        _calls(
            "Only the verified one gets a repair.",
            ("create_work_order", {"defect_ids": [VERIFIED], "priority": "P1", **base}),
            (
                "request_reinspection",
                {"inspection_id": "T01-2018", "defect_ids": [PENDING], "reason": "looks differ"},
            ),
        ),
        _calls("", ("write_report", {"markdown": f"WO-001 {VERIFIED}; WO-002"})),
        ChatResult(text="Done.", usage=Usage(input_tokens=1, output_tokens=1), model="stub-model"),
    ]


def test_the_agent_records_its_model_rationale_decisions_and_the_rule_that_stopped_it(
    tmp_path: Path,
) -> None:
    store = make_store(tmp_path)
    stub = StubProvider(chat_responses=_script())
    client = build_client(MetaSettings(), provider="stub", stub=stub)
    run = run_agent(
        client, MetaSettings(), store, run_id="run-o", provider="baseten", model="open-m",
        max_tokens=6000,
    )  # fmt: skip
    assert {r.model for r in stub.chat_calls} == {"open-m"}
    assert {r.max_tokens for r in stub.chat_calls} == {6000}
    assert run.model == "open-m" and run.provider == "baseten"
    calls = [s for s in run.steps if s.kind == "tool_call"]
    assert [c.outcome for c in calls] == [
        "accepted",
        "rejected",
        "accepted",
        "accepted",
        "accepted",
    ]
    assert calls[0].rationale == "Rank first." and calls[1].rationale is None
    assert calls[2].rationale == calls[3].rationale == "Only the verified one gets a repair."
    assert calls[1].blocked_by_rule is not None and calls[1].blocked_by_rule.id == "verified_only"
    assert calls[1].decision == "repair work order (P2) for T01-2018: 1 defect"
    assert [c.turn for c in calls] == [1, 2, 3, 3, 4]
    assert all(s.provider == "baseten" for s in run.steps if s.model)
    assert all(s.model is None for s in run.steps if s.kind == "tool_result")
    orders = store.work_orders()
    assert {(o.model, o.provider) for o in orders} == {("open-m", "baseten")}
    report = store.latest_report()
    assert report is not None and (report.model, report.provider) == ("open-m", "baseten")


def _tool_error(tools: FleetTools, name: str, **args: object) -> str:
    error = error_of(tools.call(name, dict(args)))
    assert error is not None
    return error


def test_every_rejection_of_the_tools_maps_to_its_rule(tmp_path: Path) -> None:
    tools = FleetTools(make_store(tmp_path), "r")
    cases = {
        "verified_only": ("create_work_order", {"inspection_id": "T01-2018",
                          "defect_ids": [PENDING], "action": "a", "rationale": "r"}),
        "reinspect_unverified_only": ("request_reinspection", {"inspection_id": "T01-2018",
                                      "defect_ids": [VERIFIED], "reason": "r"}),
        "assessed_before_reinspection": ("request_reinspection", {"inspection_id": "T01-2018",
                                         "defect_ids": ["T01-2018/DJI_0001_01_01/d3"],
                                         "reason": "r"}),
        "defects_in_inspection": ("create_work_order", {"inspection_id": "T01-2018",
                                  "defect_ids": ["x"], "action": "a", "rationale": "r"}),
        "cite_a_defect": ("request_reinspection", {"inspection_id": "T01-2018",
                          "defect_ids": [], "reason": "r"}),
        "order_kind": ("create_work_order", {"kind": "replace"}),
        "order_priority": ("create_work_order", {"priority": "P9"}),
        "report_cites_existing_orders": ("write_report", {"markdown": "WO-007"}),
        "report_cites_assessed_defects": ("write_report",
                                          {"markdown": "T09-2018/DJI_0001_01_01/d9"}),
        "two_inspections_to_compare": ("compare_inspections", {"turbine_id": "T99"}),
        "known_image": ("assess_image", {"image_id": "T01-2018/DJI_9999_01_01"}),
        "known_tool": ("delete_everything", {}),
        "known_ids": ("get_inspection", {"inspection_id": "T99-2018"}),
        "valid_arguments": ("create_work_order", {"inspection_id": "T01-2018",
                            "defect_ids": [VERIFIED], "action": "a", "rationale": "r",
                            "due_within_days": "soon"}),
    }  # fmt: skip
    assert set(cases) == set(RULES)
    for rule_id, (name, args) in cases.items():
        found = rule_for_error(_tool_error(tools, name, **args))
        assert found is not None and found.id == rule_id, rule_id
    assert rule_for_error("something else entirely") is None


def test_error_of_reads_a_cut_result_and_ignores_accepted_ones() -> None:
    cut = '{"error":"no work order without a verified assessment; these defects are not ver'
    assert error_of(cut) == "no work order without a verified assessment; these defects are not ver"
    assert error_of('{"created":"WO-001"}') is None and error_of("[1, 2]") is None


def test_backfill_derives_the_fields_from_a_stored_trace_and_is_idempotent(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    stub = StubProvider(chat_responses=_script())
    run_agent(build_client(MetaSettings(), provider="stub", stub=stub), MetaSettings(), store,
              run_id="run-b", provider="stub")  # fmt: skip
    live = store.run("run-b")
    stripped = [
        s.model_copy(update={"rationale": None, "decision": None, "outcome": None,
                             "blocked_by_rule": None, "turn": None, "provider": None})
        for s in live.steps
    ]  # fmt: skip
    # The loop puts the model call's duration on the first call of a turn: mimic a stored run.
    for i, s in enumerate(stripped):
        first = s.kind == "tool_call" and stripped[i - 1].kind in ("tool_result", "thought")
        if first and s.duration_ms == 0 and stripped[i - 1].kind == "tool_result":
            stripped[i] = s.model_copy(update={"duration_ms": 5})
    assert [s.kind for s in stripped[5:10]] == ["thought"] + ["tool_call", "tool_result"] * 2
    stripped[8] = stripped[8].model_copy(update={"duration_ms": 0})  # 2nd call of turn 3
    store.save_run(live.model_copy(update={"steps": stripped}))
    orders = [o.model_copy(update={"model": None, "provider": None}) for o in store.work_orders()]
    store.save_work_orders(orders)
    counts = backfill(store)
    assert counts["runs"] == 1 and counts["work_orders"] == 2
    again = store.run("run-b")
    fields = ("rationale", "decision", "outcome", "blocked_by_rule", "turn", "provider")
    for a, b in zip(again.steps, live.steps, strict=True):
        assert {f: getattr(a, f) for f in fields} == {f: getattr(b, f) for f in fields}
    assert {(o.model, o.provider) for o in store.work_orders()} == {
        (MetaSettings().chat_model, "stub")
    }
    snapshot = (store.root / "runs" / "run-b.json").read_text()
    backfill(store)
    assert (store.root / "runs" / "run-b.json").read_text() == snapshot


def test_backfill_takes_the_second_look_model_from_the_assessment(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    assert backfill(store)["verifications"] == 6
    for i in store.inspections():
        for d in (d for img in i.images for d in img.defects):
            if d.verification and d.assessment:
                assert (d.verification.model, d.verification.provider) == ("m", "stub")
    assert backfill(store)["verifications"] == 0


def test_annotate_leaves_error_steps_without_a_turn() -> None:
    steps = [
        AgentStep(index=0, kind="tool_call", tool="list_turbines", arguments={}, content="x",
                  duration_ms=3, cost_usd=0.0, model="m"),
        AgentStep(index=1, kind="tool_result", tool="list_turbines", content="[]",
                  duration_ms=0, cost_usd=0.0),
        AgentStep(index=2, kind="error", content="step limit", duration_ms=0, cost_usd=0.0),
    ]  # fmt: skip
    out = annotate_steps(steps, "meta")
    assert [s.turn for s in out] == [1, 1, None] and out[0].outcome == "accepted"
    assert out[0].provider == "meta" and out[1].provider is None


# --- API: replay selector ----------------------------------------------------------------------


def _api(tmp_path: Path, with_open: bool) -> TestClient:
    store = make_store(tmp_path)
    store.save_manifest({"detection": [{"stage": "segmentation", "model": "sam-3.1",
                                        "provider": "meta"}]})  # fmt: skip
    run_agent(
        build_client(MetaSettings(), provider="stub", stub=StubProvider(chat_responses=_script())),
        MetaSettings(), store, run_id="run-meta", provider="meta",
    )  # fmt: skip
    if with_open:
        stub = StubProvider(chat_responses=[_grade(3) for _ in range(40)])
        settings = MetaSettings()
        chat = chat_target(settings, "stub", client=build_client(settings, provider="stub",
                                                                 stub=stub))  # fmt: skip
        chat = type(chat)(chat.client, "baseten", "open-m", 6000)
        open_store = Store(store.root / "open-weights")
        store.save_layout({"turbines": {}})
        regrade_farm(chat, settings, store, open_store, _data_dir(tmp_path))
        run_agent(
            build_client(settings, provider="stub", stub=StubProvider(chat_responses=_script())),
            settings, open_store, run_id="run-open", provider="baseten", model="open-m",
        )  # fmt: skip
    settings = Settings(
        replay_dir=store.root,
        data_dir=tmp_path / "data",
        web_dir=tmp_path / "nodist",
        evidence_dir=tmp_path / "evidence",
        mode="replay",
        admin_key="",
    )
    return TestClient(create_app(settings))


def test_the_api_serves_the_meta_replay_by_default_and_404s_a_missing_open_one(
    tmp_path: Path,
) -> None:
    client = _api(tmp_path, with_open=False)
    replays = [ReplaySet.model_validate(r) for r in client.get("/api/replays").json()]
    assert [r.provider for r in replays] == ["meta"] and replays[0].default
    assert client.get("/api/fleet").status_code == 200
    assert client.get("/api/fleet?provider=baseten").status_code == 404
    assert client.get("/api/runs?provider=baseten").status_code == 404
    assert client.get("/api/fleet?provider=openai").status_code == 422


def test_the_api_selects_the_open_weights_replay_and_says_which_model_ran_each_stage(
    tmp_path: Path,
) -> None:
    client = _api(tmp_path, with_open=True)
    replays = {
        r["provider"]: ReplaySet.model_validate(r) for r in client.get("/api/replays").json()
    }
    assert set(replays) == {"meta", "baseten"} and not replays["baseten"].default
    stages = {s.stage: (s.model, s.provider) for s in replays["baseten"].stages}
    assert stages["segmentation"] == ("sam-3.1", "meta")  # SAM 3.1 stays on the Meta Model API
    assert stages["severity"] == stages["verification"] == stages["agent"] == ("open-m", "baseten")
    assert replays["baseten"].run_id == "run-open" and replays["meta"].run_id == "run-meta"
    inspection = client.get("/api/inspections/T01-2018?provider=baseten").json()
    defect = inspection["images"][0]["defects"][0]
    assert defect["assessment"]["provider"] == defect["verification"]["provider"] == "baseten"
    assert client.get("/api/inspections/T01-2018").json()["images"][0]["defects"][0][
        "assessment"]["provider"] == "stub"  # fmt: skip
    runs = [AgentRun.model_validate(r) for r in client.get("/api/runs?provider=baseten").json()]
    assert [r.id for r in runs] == ["run-open"]
    assert client.get("/api/runs/run-open").status_code == 404  # not in the meta replay
    assert client.get("/api/runs/run-open?provider=baseten").json()["provider"] == "baseten"
    orders = client.get("/api/work-orders?provider=baseten").json()
    assert orders and {o["provider"] for o in orders} == {"baseten"}
    assert client.get("/api/reports/latest?provider=baseten").json()["model"] == "open-m"
    assert client.get("/api/fleet?provider=baseten").json()["run_id"] == "run-open"
