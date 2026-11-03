import json
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest
from conftest import chat_request

from bladesight.meta import (
    ChatResult,
    DiskCache,
    MetaClient,
    MetaServerError,
    SpendCapExceededError,
    SpendTracker,
    StubProvider,
    Usage,
)
from bladesight.meta.spend import PRICING, cost_usd, rate_for


def make_client(
    limit: float,
    stub: StubProvider,
    *,
    provider: str = "meta",
    log: Path | None = None,
    cache: DiskCache | None = None,
) -> MetaClient:
    return MetaClient(
        stub,
        spend=SpendTracker(limit, provider=provider, log_path=log),
        cache=cache,
        sleep=lambda _s: None,
    )


# --- the cap -------------------------------------------------------------------------------


def test_cap_refuses_before_any_network_call() -> None:
    stub = StubProvider()
    client = make_client(0.0, stub)
    with pytest.raises(SpendCapExceededError) as info:
        client.chat(chat_request())
    assert stub.call_count == 0
    assert info.value.limit_usd == 0.0
    assert info.value.provider == "meta"
    assert "human" in str(info.value)


def test_cap_stops_a_sequence_of_calls() -> None:
    stub = StubProvider(
        chat_responses=[
            ChatResult(text="x", usage=Usage(input_tokens=1000, output_tokens=1000), model="m")
        ]
        * 10
    )
    client = make_client(0.02, stub)
    done = 0
    with pytest.raises(SpendCapExceededError):
        for i in range(10):
            client.chat(chat_request(f"p{i}", max_tokens=1000))
            done += 1
    assert 0 < done < 10
    assert client.spend.spent_usd <= 0.02
    assert stub.call_count == done


def test_cache_hits_cost_nothing_and_work_at_the_cap(tmp_path: Path) -> None:
    cache = DiskCache(tmp_path / "c")
    make_client(1.0, StubProvider(), cache=cache).chat(chat_request())

    stub = StubProvider()
    capped = make_client(0.0, stub, cache=cache)
    capped.chat(chat_request())

    assert stub.call_count == 0
    assert capped.spend.spent_usd == 0


def test_failed_calls_release_their_reservation(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    stub = StubProvider(failures=[MetaServerError("x", status_code=500)] * 9)
    client = make_client(1.0, stub, log=log)
    with pytest.raises(MetaServerError):
        client.chat(chat_request())
    assert client.spend.spent_usd == 0
    kinds = [json.loads(line)["kind"] for line in log.read_text().splitlines()]
    assert kinds == ["reserve", "release"]


# --- cumulative across runs and processes --------------------------------------------------


def test_cap_is_cumulative_across_runs_from_the_spend_log(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    first_run = make_client(0.00045, StubProvider(), log=log)
    first_run.chat(chat_request(max_tokens=16))  # ~0.0002 simulated
    first_run.chat(chat_request("again", max_tokens=16))

    # A brand-new process-like tracker on the same log starts from the history, not from zero.
    second_run = make_client(0.00045, StubProvider(), log=log)
    assert second_run.spend.spent_usd == pytest.approx(first_run.spend.spent_usd)
    assert second_run.spend.spent_usd > 0.0004
    with pytest.raises(SpendCapExceededError):
        second_run.chat(chat_request("third", max_tokens=16))


def test_caps_are_separate_per_provider_in_one_log(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    meta = make_client(0.00045, StubProvider(), provider="meta", log=log)
    baseten = make_client(0.00045, StubProvider(), provider="baseten", log=log)

    meta.chat(chat_request(max_tokens=16))
    meta.chat(chat_request("more", max_tokens=16))
    with pytest.raises(SpendCapExceededError):
        meta.chat(chat_request("over", max_tokens=16))

    baseten.chat(chat_request("fresh", max_tokens=16))  # Meta's spend is not Baseten's
    assert baseten.spend.spent_usd < meta.spend.spent_usd


def test_open_reservations_of_a_crashed_run_still_count(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    crashed = SpendTracker(1.0, provider="meta", log_path=log)
    crashed.reserve(0.9)  # never settled or released

    survivor = SpendTracker(1.0, provider="meta", log_path=log)
    with pytest.raises(SpendCapExceededError):
        survivor.reserve(0.2)


WORKER = textwrap.dedent(
    """
    import json, sys, time
    from bladesight.meta import (ChatMessage, ChatRequest, MetaClient, SpendCapExceededError,
                                 SpendTracker, StubProvider)

    class SlowCheck(SpendTracker):
        # Pause right after the total is read and before the reservation is written, so every
        # process is inside the check at the same time unless the file lock serializes them.
        def _total_locked(self):
            total = super()._total_locked()
            time.sleep(0.05)
            return total

    log, tag, attempts, limit = sys.argv[1], sys.argv[2], int(sys.argv[3]), float(sys.argv[4])
    start_at = float(sys.argv[5])  # every worker enters its first check at the same instant
    time.sleep(max(0.0, start_at - time.time()))
    client = MetaClient(
        StubProvider(delay=0.02),
        spend=SlowCheck(limit, provider="meta", log_path=log),
        sleep=lambda _s: None,
    )
    ok = refused = 0
    for i in range(attempts):
        request = ChatRequest(
            model="muse-spark-1.3", messages=[ChatMessage.user(f"{tag}-{i}")], max_tokens=64
        )
        try:
            client.chat(request)
            ok += 1
        except SpendCapExceededError:
            refused += 1
    print(json.dumps({"ok": ok, "refused": refused}))
    """
)


def test_concurrent_processes_cannot_exceed_the_cap(tmp_path: Path) -> None:
    """Fails if a second process can pass the check while the first is still mid-check or mid-call.

    Six workers start together and pause inside the locked check, so without the file lock or the
    reservation they all read the same total and every one of them gets through the cap.
    """
    log = tmp_path / "spend_log.jsonl"
    limit = 0.0005  # a sequential run fits exactly two stub calls (~0.00021 each, ~0.00027 worst)
    start_at = time.time() + 3.0  # generous: interpreter start-up must finish before this
    workers = [
        subprocess.Popen(
            [sys.executable, "-c", WORKER, str(log), f"w{n}", "3", str(limit), str(start_at)],
            stdout=subprocess.PIPE,
            text=True,
            cwd=tmp_path,
        )
        for n in range(6)
    ]
    results = []
    for worker in workers:
        out, _ = worker.communicate(timeout=180)
        assert worker.returncode == 0
        results.append(json.loads(out.strip().splitlines()[-1]))

    ok = sum(r["ok"] for r in results)
    refused = sum(r["refused"] for r in results)
    entries = [json.loads(line) for line in log.read_text().splitlines()]
    settled = sum(e["simulated_cost_usd"] for e in entries if e["kind"] == "settle")

    assert ok + refused == 18
    assert (
        1 <= ok <= 2
    )  # a sequential run allows exactly 2; concurrency may allow fewer, never more
    assert refused > 0
    assert settled <= limit  # the invariant: never above the cap, whatever the interleaving
    assert ok == sum(1 for e in entries if e["kind"] == "settle")


# --- prices and the stub -------------------------------------------------------------------


def test_prices_are_keyed_by_exact_model_id() -> None:
    spark = rate_for("muse-spark-1.3")
    assert (spark.input_per_mtok, spark.cached_input_per_mtok, spark.output_per_mtok) == (
        1.25,
        0.15,
        4.25,
    )
    assert rate_for("muse-spark-1.2") == rate_for("muse-spark-1.1") == spark
    assert rate_for("muse-spark-1.3-contributor").output_per_mtok == 0.20
    assert rate_for("sam-3.1").per_call == 0.0025
    assert rate_for("meta-models/muse-spark-open-1026").output_per_mtok == 4.25
    assert all(r.documented for r in PRICING.values())


def test_unknown_model_gets_a_conservative_unconfirmed_rate() -> None:
    rate = rate_for("muse-spark-1.3-typo")
    assert rate.documented is False
    assert rate.per_call > 0


def test_cost_bills_cached_input_at_the_cached_rate_and_reasoning_as_output() -> None:
    usage = Usage(input_tokens=1_000_000, cached_input_tokens=400_000, output_tokens=100_000)
    expected = 600_000 * 1.25 / 1e6 + 400_000 * 0.15 / 1e6 + 100_000 * 4.25 / 1e6 + 0
    assert cost_usd("muse-spark-1.3", usage.model_copy(update={"calls": 0})) == pytest.approx(
        expected
    )
    assert cost_usd("sam-3.1", Usage(calls=4)) == pytest.approx(0.01)


def test_stub_reports_zero_real_usd_and_tags_the_simulated_cost(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    client = make_client(10.0, StubProvider(), log=log)
    client.chat(chat_request("a secret-looking prompt"))

    record = client.records[0]
    assert record.source == "stub"
    assert record.cost_usd == 0.0
    assert record.simulated_cost_usd > 0
    assert record.price_documented is True

    (_reserve, settle) = [json.loads(line) for line in log.read_text().splitlines()]
    assert settle["est_cost_usd"] == 0.0
    assert settle["simulated_cost_usd"] > 0
    assert settle["input_tokens"] == 100
    assert "prompt" not in log.read_text()
