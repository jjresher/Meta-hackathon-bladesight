"""Second-audit follow-ups: interrupts, hostile usage values, uncacheable statuses, NaN caps and
the store / reasoning-effort plumbing."""

import json
from pathlib import Path

import pytest
import respx
from conftest import chat_request, segment_request
from pydantic import SecretStr, ValidationError

from bladesight.meta import (
    ChatDefaults,
    ChatMessage,
    ChatRequest,
    DiskCache,
    HttpProvider,
    ImagePart,
    MetaClient,
    MetaConfigError,
    MetaSettings,
    SpendTracker,
    StubProvider,
    Usage,
    build_client,
)
from bladesight.meta.__main__ import main

BASE = "https://api.example.test"
URL = f"{BASE}/v1/responses"


def reply(usage: dict | None, status: str | None = "completed", text: str = "hi") -> dict:
    body: dict = {
        "id": "r",
        "model": "muse-spark-1.3",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
    }
    if status is not None:
        body["status"] = status
    if usage is not None:
        body["usage"] = usage
    return body


def sam_reply(text: str = "", status: str = "completed", images: object = 1) -> dict:
    return {
        "id": "s",
        "status": status,
        "model": "sam-3.1",
        "output": [
            {
                "type": "message",
                "role": "assistant",
                "content": [{"type": "output_text", "text": text}],
            }
        ],
        "usage": {"input_tokens": 0, "output_tokens": 0, "images_processed": images},
    }


def live_client(tmp_path: Path | None = None, **kwargs: object) -> MetaClient:
    return MetaClient(
        HttpProvider("meta", BASE, SecretStr("k")),
        spend=SpendTracker(
            1.0, provider="meta", log_path=tmp_path / "log.jsonl" if tmp_path else None
        ),
        cache=DiskCache(tmp_path / "cache") if tmp_path else None,
        sleep=lambda _s: None,
        **kwargs,  # type: ignore[arg-type]
    )


# --- 1. an interrupt keeps the reservation ---------------------------------------------------


@pytest.mark.parametrize("interrupt", [KeyboardInterrupt, SystemExit])
def test_an_interrupt_mid_request_keeps_the_reservation_counted(
    interrupt: type[BaseException], tmp_path: Path
) -> None:
    log = tmp_path / "log.jsonl"
    stub = StubProvider(failures=[interrupt()])
    client = MetaClient(stub, spend=SpendTracker(1.0, provider="meta", log_path=log))

    with pytest.raises(interrupt):
        client.chat(chat_request(max_tokens=1000))

    kinds = [json.loads(line)["kind"] for line in log.read_text().splitlines()]
    assert kinds == ["reserve"]  # no release: the request may already have been billed
    assert client.spend.spent_usd > 0
    assert SpendTracker(1.0, provider="meta", log_path=log).spent_usd == client.spend.spent_usd


def test_an_ordinary_failure_still_releases_the_reservation(tmp_path: Path) -> None:
    from bladesight.meta import MetaServerError

    log = tmp_path / "log.jsonl"
    client = MetaClient(
        StubProvider(failures=[MetaServerError("x", status_code=500)] * 9),
        spend=SpendTracker(1.0, provider="meta", log_path=log),
        sleep=lambda _s: None,
    )
    with pytest.raises(MetaServerError):
        client.chat(chat_request())
    assert client.spend.spent_usd == 0


# --- 2. hostile or odd usage values ----------------------------------------------------------


@respx.mock
@pytest.mark.parametrize(
    "usage",
    [
        {"input_tokens": -5, "output_tokens": 10},
        {"input_tokens": 10, "output_tokens": -1},
        {"input_tokens": "12", "output_tokens": 3},
        {"input_tokens": 12.5, "output_tokens": 3},
        {"input_tokens": True, "output_tokens": 3},
        {"input_tokens": 10, "output_tokens": 3, "input_tokens_details": {"cached_tokens": -2}},
    ],
    ids=["neg-in", "neg-out", "string", "fraction", "bool", "neg-cached"],
)
def test_odd_usage_values_settle_at_the_estimate_and_keep_the_log_valid(
    usage: dict, tmp_path: Path
) -> None:
    respx.post(URL).respond(200, json=reply(usage))
    client = live_client(tmp_path)

    client.chat(chat_request(max_tokens=1000))

    assert client.records[0].cost_from_estimate is True
    assert client.records[0].cost_usd >= 1000 * 4.25 / 1e6
    # the log is still readable: no negative amount was written
    assert SpendTracker(1.0, provider="meta", log_path=tmp_path / "log.jsonl").spent_usd > 0
    client.chat(chat_request("again", max_tokens=1000))  # and the next call works


@respx.mock
def test_whole_floats_are_accepted_as_counts() -> None:
    respx.post(URL).respond(200, json=reply({"input_tokens": 12.0, "output_tokens": 3.0}))
    client = live_client()
    result = client.chat(chat_request())
    assert (result.usage.input_tokens, result.usage.output_tokens) == (12, 3)
    assert client.records[0].cost_from_estimate is False


@respx.mock
@pytest.mark.parametrize(
    ("images", "calls"), [(2.0, 2), (3, 3), (-1, 1), (2.5, 1), ("2", 1), (0, 1)]
)
def test_images_processed_must_be_a_positive_whole_number(images: object, calls: int) -> None:
    respx.post(URL).respond(200, json=sam_reply(images=images))
    result = live_client().segment(segment_request(ImagePart(url="https://x.test/a.jpg")))
    assert result.usage.calls == calls


def test_usage_rejects_negative_numbers() -> None:
    for field in ("input_tokens", "cached_input_tokens", "output_tokens", "calls"):
        with pytest.raises(ValidationError):
            Usage(**{field: -1})


def test_a_negative_cost_is_never_written_to_the_log(tmp_path: Path) -> None:
    tracker = SpendTracker(1.0, provider="meta", log_path=tmp_path / "log.jsonl")
    reservation = tracker.reserve(0.01)
    tracker.settle(
        reservation,
        operation="chat",
        model="m",
        usage=Usage(),
        cost=-5.0,
        simulated_cost=0.0,
        source="live",
        attempts=1,
        request_id=None,
    )
    assert tracker.spent_usd == pytest.approx(0.01)  # settled at the estimate


# --- 4. NaN / negative caps ------------------------------------------------------------------


@pytest.mark.parametrize("limit", [float("nan"), -0.01])
def test_a_tracker_rejects_a_nan_or_negative_cap(limit: float) -> None:
    with pytest.raises(MetaConfigError):
        SpendTracker(limit, provider="meta")


def test_zero_and_infinite_caps_are_valid() -> None:
    assert SpendTracker(0.0, provider="meta").limit_usd == 0.0
    assert SpendTracker(float("inf"), provider="stub").limit_usd == float("inf")


# --- 6. only completed replies are cached ----------------------------------------------------


@respx.mock
def test_an_incomplete_reply_is_returned_and_billed_but_not_cached(tmp_path: Path) -> None:
    route = respx.post(URL).respond(
        200, json=reply({"input_tokens": 10, "output_tokens": 800}, status="incomplete", text="")
    )
    client = live_client(tmp_path)

    first = client.chat(chat_request())
    client.chat(chat_request())

    assert first.status == "incomplete"
    assert route.call_count == 2  # not replayed from the cache
    assert [r.source for r in client.records] == ["live", "live"]
    assert client.spend.spent_usd > 0
    assert not list((tmp_path / "cache").rglob("*.json"))


@respx.mock
def test_a_completed_reply_is_cached(tmp_path: Path) -> None:
    route = respx.post(URL).respond(200, json=reply({"input_tokens": 10, "output_tokens": 3}))
    client = live_client(tmp_path)
    client.chat(chat_request())
    client.chat(chat_request())
    assert route.call_count == 1
    assert client.records[1].source == "cache"


@respx.mock
def test_a_reply_without_a_status_field_counts_as_completed(tmp_path: Path) -> None:
    route = respx.post(URL).respond(
        200, json=reply({"input_tokens": 1, "output_tokens": 1}, status=None)
    )
    client = live_client(tmp_path)
    client.chat(chat_request())
    client.chat(chat_request())
    assert route.call_count == 1


@respx.mock
def test_a_sam_zero_match_with_status_completed_is_cached_but_an_incomplete_one_is_not(
    tmp_path: Path,
) -> None:
    image = ImagePart(url="https://x.test/a.jpg")
    route = respx.post(URL).respond(200, json=sam_reply(""))
    client = live_client(tmp_path)
    client.segment(segment_request(image, "car"))
    client.segment(segment_request(image, "car"))
    assert route.call_count == 1
    assert client.records[1].source == "cache"

    route.respond(200, json=sam_reply("", status="incomplete"))
    client.segment(segment_request(image, "tree"))
    client.segment(segment_request(image, "tree"))
    assert route.call_count == 3  # both "tree" calls went to the network


# --- store and reasoning effort ---------------------------------------------------------------


@respx.mock
def test_store_and_reasoning_effort_are_sent_on_meta_responses() -> None:
    route = respx.post(URL).respond(200, json=reply({"input_tokens": 1, "output_tokens": 1}))
    request = chat_request()
    request.store = False
    request.reasoning_effort = "low"

    live_client().chat(request)

    body = json.loads(route.calls.last.request.content)
    assert body["store"] is False
    assert body["reasoning"] == {"effort": "low"}


@respx.mock
def test_neither_field_is_sent_when_unset() -> None:
    route = respx.post(URL).respond(200, json=reply({"input_tokens": 1, "output_tokens": 1}))
    live_client().chat(chat_request())
    body = json.loads(route.calls.last.request.content)
    assert "store" not in body and "reasoning" not in body


@respx.mock
def test_client_defaults_fill_only_the_fields_the_caller_left_unset() -> None:
    route = respx.post(URL).respond(200, json=reply({"input_tokens": 1, "output_tokens": 1}))
    client = live_client(chat_defaults=ChatDefaults(store=False, reasoning_effort="low"))

    client.chat(chat_request("uses the defaults"))
    explicit = chat_request("explicit")
    explicit.reasoning_effort = "high"
    explicit.store = True
    client.chat(explicit)

    first, second = (json.loads(c.request.content) for c in route.calls)
    assert (first["store"], first["reasoning"]) == (False, {"effort": "low"})
    assert (second["store"], second["reasoning"]) == (True, {"effort": "high"})


def test_the_defaults_are_part_of_the_cache_key(tmp_path: Path) -> None:
    stub = StubProvider()
    cache = DiskCache(tmp_path / "c")
    a = MetaClient(stub, spend=SpendTracker.unlimited(), cache=cache)
    b = MetaClient(
        stub,
        spend=SpendTracker.unlimited(),
        cache=cache,
        chat_defaults=ChatDefaults(reasoning_effort="low"),
    )
    a.chat(chat_request())
    b.chat(chat_request())
    assert stub.call_count == 2  # a different effort is a different request


@respx.mock
def test_baseten_chat_completions_never_gets_store_or_reasoning_fields() -> None:
    url = "https://inference.baseten.co/v1/chat/completions"
    route = respx.post(url).respond(
        200,
        json={
            "choices": [{"message": {"content": "ok"}}],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1},
        },
    )
    provider = HttpProvider(
        "baseten",
        "https://inference.baseten.co/v1",
        SecretStr("k"),
        chat_format="chat_completions",
        supports_segment=False,
    )
    request = ChatRequest(
        model="meta-models/muse-spark-open-1026",
        messages=[ChatMessage.user("hi")],
        store=False,
        reasoning_effort="low",
    )
    MetaClient(provider, spend=SpendTracker(1.0, provider="baseten")).chat(request)
    body = json.loads(route.calls.last.request.content)
    assert "store" not in body and "reasoning" not in body


def test_settings_read_the_defaults_and_build_client_applies_them_to_meta_only() -> None:
    settings = MetaSettings.from_env(
        {
            "META_API_KEY": "k",
            "BASETEN_API_KEY": "k",
            "BLADESIGHT_MODE": "live",
            "META_STORE": "false",
            "META_REASONING_EFFORT": "low",
        }
    )
    assert settings.store is False and settings.reasoning_effort == "low"
    assert build_client(settings, provider="meta").chat_defaults == ChatDefaults(False, "low")
    assert build_client(settings, provider="baseten").chat_defaults == ChatDefaults()
    with pytest.raises(MetaConfigError):
        MetaSettings.from_env({"META_STORE": "maybe"})


def test_the_defaults_are_the_values_the_real_api_accepted() -> None:
    settings = MetaSettings.from_env({})
    assert settings.store is False
    assert settings.reasoning_effort == "low"


def test_the_word_default_sends_neither_field() -> None:
    settings = MetaSettings.from_env({"META_STORE": "default", "META_REASONING_EFFORT": "default"})
    assert settings.store is None and settings.reasoning_effort is None
    explicit = MetaSettings.from_env({"META_STORE": "true", "META_REASONING_EFFORT": "high"})
    assert explicit.store is True and explicit.reasoning_effort == "high"


def test_cli_flags_override_the_defaults(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    assert (
        main(
            [
                "chat",
                "--provider",
                "stub",
                "--store",
                "false",
                "--reasoning-effort",
                "low",
                "--prompt",
                "hi",
            ]
        )
        == 0
    )
    assert "source=stub" in capsys.readouterr().out
