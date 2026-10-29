"""Fail-safe behaviour found by the issue #2 audit: replay without a key, zero-usage settlement,
a spend log that fails closed, Retry-After dates and the unlimited-tracker guard."""

import json
from datetime import UTC, datetime, timedelta
from email.utils import format_datetime
from pathlib import Path

import httpx
import pytest
import respx
from conftest import chat_request, segment_request
from pydantic import SecretStr

from bladesight.meta import (
    CacheMissError,
    ChatResult,
    DiskCache,
    HttpProvider,
    ImagePart,
    MetaClient,
    MetaConfigError,
    MetaSettings,
    SpendLogError,
    SpendTracker,
    StubProvider,
    Usage,
    build_client,
)
from bladesight.meta.__main__ import main
from bladesight.meta.http_provider import _parse_retry_after

BASE = "https://api.example.test"
RESPONSES_URL = f"{BASE}/v1/responses"


def reply(usage: dict | None) -> dict:
    body: dict = {
        "id": "r",
        "status": "completed",
        "model": "muse-spark-1.3",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": "hi"}],
            }
        ],
    }
    if usage is not None:
        body["usage"] = usage
    return body


# --- replay mode needs no key, and checks it lazily ---------------------------------------


@respx.mock
def test_replay_client_needs_no_key_and_serves_cached_answers(tmp_path: Path) -> None:
    cache_dir = tmp_path / "cache"
    live = HttpProvider("meta", BASE, SecretStr("k"))
    route = respx.post(RESPONSES_URL).respond(
        200, json=reply({"input_tokens": 5, "output_tokens": 2})
    )
    recorder = MetaClient(
        live, spend=SpendTracker(1.0, provider="meta"), cache=DiskCache(cache_dir / "responses")
    )
    recorder.chat(chat_request("cached question"))
    assert route.call_count == 1

    # The demo machine: no META_API_KEY at all, replay mode (the default).
    settings = MetaSettings.from_env({"BLADESIGHT_CACHE_DIR": str(cache_dir)})
    assert settings.meta_api_key is None and settings.mode == "replay"
    replay = build_client(settings, provider="meta")

    assert replay.chat(chat_request("cached question")).text == "hi"
    assert replay.records[0].source == "cache"
    assert route.call_count == 1  # no network


def test_replay_miss_is_a_cache_miss_not_a_missing_key(tmp_path: Path) -> None:
    settings = MetaSettings.from_env({"BLADESIGHT_CACHE_DIR": str(tmp_path / "empty")})
    for provider in ("meta", "baseten"):
        client = build_client(settings, provider=provider)  # type: ignore[arg-type]
        with pytest.raises(CacheMissError, match="BLADESIGHT_MODE=live"):
            client.chat(chat_request())


@respx.mock
def test_a_key_less_provider_refuses_before_any_network_call() -> None:
    route = respx.post(RESPONSES_URL).respond(200, json=reply(None))
    provider = HttpProvider("meta", BASE, None)
    with pytest.raises(MetaConfigError, match="no API key"):
        provider.chat(chat_request())
    assert route.call_count == 0


# --- a response without usage must not settle at $0 ---------------------------------------


@respx.mock
@pytest.mark.parametrize(
    "usage",
    [None, {}, {"input_tokens": 0, "output_tokens": 0}],
    ids=["missing", "empty", "all-zero"],
)
def test_missing_or_zero_usage_settles_at_the_reservation_estimate(
    usage: dict | None, tmp_path: Path
) -> None:
    respx.post(RESPONSES_URL).respond(200, json=reply(usage))
    log = tmp_path / "log.jsonl"
    client = MetaClient(
        HttpProvider("meta", BASE, SecretStr("k")),
        spend=SpendTracker(1.0, provider="meta", log_path=log),
    )
    request = chat_request(max_tokens=1000)

    client.chat(request)

    record = client.records[0]
    assert record.cost_from_estimate is True
    assert record.cost_usd > 0
    settle = json.loads(log.read_text().splitlines()[-1])
    assert settle["kind"] == "settle"
    assert settle["est_cost_usd"] == pytest.approx(record.cost_usd)
    assert client.spend.spent_usd == pytest.approx(record.cost_usd)
    assert record.cost_usd >= 1000 * 4.25 / 1e6  # at least the full max_tokens of output


def test_zero_usage_from_the_stub_is_settled_at_the_estimate_too() -> None:
    stub = StubProvider(chat_responses=[ChatResult(text="x", usage=Usage(), model="m")])
    client = MetaClient(stub, spend=SpendTracker.unlimited())
    client.chat(chat_request(max_tokens=1000))
    assert client.records[0].cost_from_estimate is True
    assert client.records[0].cost_usd == 0.0  # the stub spends no real money
    assert client.records[0].simulated_cost_usd > 0


@respx.mock
def test_reported_usage_is_used_as_is_and_not_flagged() -> None:
    respx.post(RESPONSES_URL).respond(200, json=reply({"input_tokens": 1000, "output_tokens": 100}))
    client = MetaClient(
        HttpProvider("meta", BASE, SecretStr("k")), spend=SpendTracker(1.0, provider="meta")
    )
    client.chat(chat_request(max_tokens=1000))
    assert client.records[0].cost_from_estimate is False
    assert client.records[0].cost_usd == pytest.approx(1000 * 1.25 / 1e6 + 100 * 4.25 / 1e6)


def test_segment_is_billed_per_call_even_though_it_reports_no_tokens(image: ImagePart) -> None:
    client = MetaClient(StubProvider(), spend=SpendTracker.unlimited())
    client.segment(segment_request(image))
    assert client.records[0].cost_from_estimate is False
    assert client.records[0].simulated_cost_usd == pytest.approx(0.0025)


# --- "documented", not "confirmed" -------------------------------------------------------


def test_cli_labels_prices_as_documented_or_unconfirmed(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["chat", "--provider", "stub", "--model", "muse-spark-1.3", "--prompt", "hi"]) == 0
    out = capsys.readouterr().out
    assert "price=documented" in out and "price=confirmed" not in out
    assert "simulated_usd=" in out and "est_cost_usd=0.0000" in out

    assert main(["chat", "--provider", "stub", "--prompt", "hi"]) == 0  # unknown model id
    assert "price=UNCONFIRMED" in capsys.readouterr().out


# --- the spend log fails closed ----------------------------------------------------------

GOOD_RESERVE = {
    "ts": "t",
    "provider": "meta",
    "kind": "reserve",
    "id": "a",
    "est_cost_usd": 0.9,
}


def j(**fields: object) -> str:
    """A log line as json.dumps writes it (NaN and Infinity are written literally)."""
    return json.dumps(fields)


NAN, INF = float("nan"), float("inf")
BAD_LINES = {
    "truncated write": '{"ts": "t", "provider": "meta", "kind": "reserve", "id": "b", "est_cost_us',
    "NaN cost": j(provider="meta", kind="settle", id="a", est_cost_usd=NAN, simulated_cost_usd=0),
    "Infinity cost": j(provider="meta", kind="reserve", id="b", est_cost_usd=INF),
    "null cost": j(provider="meta", kind="settle", id="a", est_cost_usd=None, simulated_cost_usd=0),
    "negative cost": j(
        provider="meta", kind="settle", id="a", est_cost_usd=-5, simulated_cost_usd=0
    ),
    "string cost": j(provider="meta", kind="reserve", id="b", est_cost_usd="0.1"),
    "boolean cost": j(provider="meta", kind="reserve", id="b", est_cost_usd=True),
    "missing simulated cost": j(provider="meta", kind="settle", id="a", est_cost_usd=0.1),
    "not an object": "[1, 2]",
    "null line": "null",
    "unknown kind": j(provider="meta", kind="refund", id="a", est_cost_usd=0.1),
    "missing id": j(provider="meta", kind="reserve", est_cost_usd=0.1),
    "missing provider": j(kind="reserve", id="b", est_cost_usd=0.1),
    "another provider's NaN": j(provider="baseten", kind="reserve", id="z", est_cost_usd=NAN),
}


def write_log(path: Path, *lines: str | dict) -> None:
    path.write_text(
        "".join((json.dumps(line) if isinstance(line, dict) else line) + "\n" for line in lines),
        encoding="utf-8",
    )


@pytest.mark.parametrize("bad", list(BAD_LINES.values()), ids=list(BAD_LINES))
def test_a_damaged_spend_log_refuses_every_call_instead_of_lowering_the_cap(
    bad: str, tmp_path: Path
) -> None:
    log = tmp_path / "log.jsonl"
    write_log(log, GOOD_RESERVE, bad)  # 0.9 of the 1.0 cap is genuinely in flight
    stub = StubProvider()
    client = MetaClient(stub, spend=SpendTracker(1.0, provider="meta", log_path=log))

    with pytest.raises(SpendLogError) as info:
        client.chat(chat_request())

    assert stub.call_count == 0
    assert "line 2" in str(info.value)
    assert str(log) in str(info.value)
    with pytest.raises(SpendLogError):
        _ = client.spend.spent_usd  # never reports a number it cannot trust


def test_a_healthy_log_with_blank_lines_still_counts_the_open_reservation(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    write_log(log, GOOD_RESERVE, "", "   ")
    tracker = SpendTracker(1.0, provider="meta", log_path=log)
    assert tracker.spent_usd == pytest.approx(0.9)


def test_spend_log_errors_are_not_retried_or_swallowed(tmp_path: Path) -> None:
    log = tmp_path / "log.jsonl"
    write_log(log, BAD_LINES["null line"])
    client = MetaClient(StubProvider(), spend=SpendTracker(1.0, provider="meta", log_path=log))
    with pytest.raises(SpendLogError):
        client.chat(chat_request())
    assert client.records == []


def test_the_spend_log_lives_in_a_gitignored_spend_dir_not_in_the_cache() -> None:
    root = Path(__file__).resolve().parents[1]
    ignored = (root / ".gitignore").read_text().splitlines()
    assert ".spend/" in ignored and ".cache/" in ignored
    default = MetaSettings.from_env({}).spend_log_path
    assert default == root / ".spend" / "spend_log.jsonl"
    assert ".cache" not in default.parts


# --- Retry-After as an HTTP date ---------------------------------------------------------


def test_retry_after_accepts_numbers_and_http_dates() -> None:
    now = datetime(2026, 10, 29, 12, 0, 0, tzinfo=UTC)
    assert _parse_retry_after("7") == 7.0
    assert _parse_retry_after("1.5") == 1.5
    assert _parse_retry_after("-3") is None
    assert _parse_retry_after(None) is None
    assert _parse_retry_after("soon") is None
    in_90s = format_datetime(now + timedelta(seconds=90), usegmt=True)
    assert _parse_retry_after(in_90s, now=now) == pytest.approx(90.0)
    in_the_past = format_datetime(now - timedelta(seconds=90), usegmt=True)
    assert _parse_retry_after(in_the_past, now=now) == 0.0


@respx.mock
def test_a_429_with_an_http_date_waits_until_that_date() -> None:
    when = format_datetime(datetime.now(UTC) + timedelta(seconds=45), usegmt=True)
    respx.post(RESPONSES_URL).mock(
        side_effect=[
            httpx.Response(429, headers={"retry-after": when}),
            httpx.Response(200, json=reply({"input_tokens": 1, "output_tokens": 1})),
        ]
    )
    sleeps: list[float] = []
    client = MetaClient(
        HttpProvider("meta", BASE, SecretStr("k")),
        spend=SpendTracker(1.0, provider="meta"),
        sleep=sleeps.append,
        rng=lambda: 0.0,
    )
    client.chat(chat_request())
    assert 40 <= sleeps[0] <= 46  # a floor of ~45 s, not the 0.5 s backoff


# --- a real provider can never run uncapped ----------------------------------------------


def test_a_real_provider_refuses_an_unlimited_tracker() -> None:
    with pytest.raises(MetaConfigError, match="finite spend cap"):
        MetaClient(HttpProvider("meta", BASE, SecretStr("k")), spend=SpendTracker.unlimited())
    MetaClient(StubProvider(), spend=SpendTracker.unlimited())  # the stub is exempt
