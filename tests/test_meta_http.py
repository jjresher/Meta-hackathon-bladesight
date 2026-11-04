import json

import httpx
import pytest
import respx
from conftest import SAM_FIRST_MASK_AREA, SAM_TEXT, chat_request, make_image_bytes, segment_request
from pydantic import SecretStr

from bladesight.meta import (
    ChatMessage,
    ChatRequest,
    DiskCache,
    HttpProvider,
    ImagePart,
    MetaAuthError,
    MetaClient,
    MetaConfigError,
    MetaConnectionError,
    MetaInvalidResponseError,
    MetaModelNotFoundError,
    MetaPaymentRequiredError,
    MetaRequestError,
    MetaServerError,
    RetryPolicy,
    SpendTracker,
    ToolCall,
    ToolSpec,
)
from bladesight.meta.http_provider import join_url

BASE = "https://api.example.test"
KEY = "sk-test-DO-NOT-LEAK-123"
RESPONSES_URL = f"{BASE}/v1/responses"
BASETEN = "https://inference.baseten.co/v1"


def message_item(text: str) -> dict:
    return {
        "type": "message",
        "role": "assistant",
        "content": [{"type": "output_text", "text": text, "annotations": []}],
    }


def responses_body(text: str = "ok", **extra: object) -> dict:
    """A Responses reply as documented: a reasoning item, then the message, then usage."""
    return {
        "id": "resp-1",
        "status": "completed",
        "model": "muse-spark-1.3",
        "output": [{"type": "reasoning", "summary": []}, message_item(text)],
        "usage": {
            "input_tokens": 11,
            "input_tokens_details": {"cached_tokens": 4},
            "output_tokens": 7,
            "output_tokens_details": {"reasoning_tokens": 3},
            "total_tokens": 18,
        },
        **extra,
    }


def sam_body(text: str = SAM_TEXT) -> dict:
    return {
        "id": "sam-1",
        "status": "completed",
        "model": "sam-3.1",
        "output": [message_item(text)],
    }


def completions_body(text: str = "ok") -> dict:
    return {
        "id": "cc-1",
        "model": "meta-models/muse-spark-open",
        "choices": [{"message": {"content": text}}],
        "usage": {
            "prompt_tokens": 11,
            "prompt_tokens_details": {"cached_tokens": 2},
            "completion_tokens": 7,
        },
    }


def provider(**kwargs: object) -> HttpProvider:
    return HttpProvider("meta", BASE, SecretStr(KEY), **kwargs)  # type: ignore[arg-type]


def baseten_provider() -> HttpProvider:
    return HttpProvider(
        "baseten",
        BASETEN,
        SecretStr("bt-key"),
        chat_format="chat_completions",
        supports_segment=False,
    )


def client_for(
    p: HttpProvider, sleeps: list[float] | None = None, cache: DiskCache | None = None
) -> MetaClient:
    sleeps = [] if sleeps is None else sleeps
    return MetaClient(
        p,
        spend=SpendTracker(10.0, provider=p.name),
        cache=cache,
        sleep=sleeps.append,
        rng=lambda: 1.0,
    )


# --- Muse Spark on /v1/responses -----------------------------------------------------------


@respx.mock
def test_chat_request_shape_and_parsing(image: ImagePart) -> None:
    route = respx.post(RESPONSES_URL).respond(
        200, json=responses_body("hi"), headers={"x-request-id": "r1"}
    )
    request = chat_request("what is this?", image)
    request.tools = [ToolSpec(name="rank", description="rank turbines")]

    result = client_for(provider()).chat(request)

    sent = route.calls.last.request
    assert sent.url == RESPONSES_URL
    assert sent.headers["authorization"] == f"Bearer {KEY}"
    body = json.loads(sent.content)
    assert body["model"] == "muse-spark-1.3"
    assert body["stream"] is False
    assert body["max_output_tokens"] == 256
    assert "temperature" not in body and "reasoning" not in body  # only when asked for
    (item,) = body["input"]
    assert item["type"] == "message"
    assert item["role"] == "user"
    assert item["content"][0] == {"type": "input_text", "text": "what is this?"}
    assert item["content"][1]["type"] == "input_image"
    assert item["content"][1]["image_url"].startswith("data:image/png;base64,")
    assert body["tools"][0]["name"] == "rank"
    assert result.text == "hi"  # the reasoning item is skipped
    assert result.usage.input_tokens == 11
    assert result.usage.cached_input_tokens == 4
    assert result.usage.output_tokens == 7  # reasoning tokens are already inside this number
    assert result.request_id == "r1"


@respx.mock
def test_reasoning_effort_and_temperature_are_sent_only_when_set() -> None:
    route = respx.post(RESPONSES_URL).respond(200, json=responses_body())
    request = chat_request()
    request.reasoning_effort = "high"
    request.temperature = 0.2

    client_for(provider()).chat(request)

    body = json.loads(route.calls.last.request.content)
    assert body["reasoning"] == {"effort": "high"}
    assert body["temperature"] == 0.2


@respx.mock
def test_public_image_url_is_sent_as_is() -> None:
    route = respx.post(RESPONSES_URL).respond(200, json=responses_body())
    url = "https://example.test/blade.jpg"

    client_for(provider()).chat(chat_request("look", ImagePart(url=url)))

    part = json.loads(route.calls.last.request.content)["input"][0]["content"][1]
    assert part == {"type": "input_image", "image_url": url}


@respx.mock
def test_meta_documented_minimal_request() -> None:
    route = respx.post("https://api.meta.ai/v1/responses").respond(200, json=responses_body())
    p = HttpProvider("meta", "https://api.meta.ai/v1", SecretStr(KEY))

    client_for(p).chat(chat_request("Write a haiku", model="muse-spark-1.3"))

    body = json.loads(route.calls.last.request.content)
    assert body["input"] == [
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": "Write a haiku"}],
        }
    ]


@respx.mock
def test_function_calls_are_parsed() -> None:
    output = [{"type": "function_call", "call_id": "t1", "name": "rank", "arguments": '{"top": 3}'}]
    respx.post(RESPONSES_URL).respond(200, json=responses_body() | {"output": output})

    result = client_for(provider()).chat(chat_request())

    assert result.text == ""
    assert result.tool_calls[0].id == "t1"
    assert result.tool_calls[0].arguments == {"top": 3}


@respx.mock
def test_tool_round_trip_is_serialized_as_responses_items() -> None:
    route = respx.post(RESPONSES_URL).respond(200, json=responses_body("done"))
    request = ChatRequest(
        model="muse-spark-1.3",
        messages=[
            ChatMessage.user("rank them"),
            ChatMessage.of(
                "assistant", tool_calls=[ToolCall(id="t1", name="rank", arguments={"n": 2})]
            ),
            ChatMessage.of("tool", '{"ok": true}', tool_call_id="t1"),
            ChatMessage.of("assistant", "earlier answer"),
        ],
    )

    client_for(provider()).chat(request)

    items = json.loads(route.calls.last.request.content)["input"]
    assert items[0]["content"][0]["type"] == "input_text"
    assert items[1] == {
        "type": "function_call",
        "call_id": "t1",
        "name": "rank",
        "arguments": '{"n": 2}',
    }
    assert items[2] == {"type": "function_call_output", "call_id": "t1", "output": '{"ok": true}'}
    assert items[3]["type"] == "message"
    assert items[3]["content"][0] == {"type": "output_text", "text": "earlier answer"}


@respx.mock
def test_incomplete_reasoning_only_reply_is_returned_not_lost() -> None:
    """max_output_tokens spent on reasoning: the call was billed, so its usage must be kept."""
    body = responses_body() | {"status": "incomplete", "output": [{"type": "reasoning"}]}
    respx.post(RESPONSES_URL).respond(200, json=body)

    client = client_for(provider())
    result = client.chat(chat_request())

    assert result.text == ""
    assert result.usage.output_tokens == 7
    assert client.spend.spent_usd > 0


@respx.mock
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, text="<html>gateway</html>"),
        httpx.Response(200, json=[1, 2]),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(200, json={"output": "nope"}),
        httpx.Response(200, json={"status": "completed", "output": [{"type": "reasoning"}]}),
        httpx.Response(200, json={"status": "failed", "output": [message_item("x")]}),
        httpx.Response(200, json={"output": [{"type": "function_call", "name": "x"}]}),
    ],
)
def test_malformed_success_responses_are_invalid_not_retried(response: httpx.Response) -> None:
    route = respx.post(RESPONSES_URL).mock(return_value=response)
    with pytest.raises(MetaInvalidResponseError):
        client_for(provider()).chat(chat_request())
    assert route.call_count == 1


def test_images_are_only_allowed_in_user_messages() -> None:
    image = ImagePart(url="https://example.test/a.jpg")
    with pytest.raises(ValueError, match="only allowed in user messages"):
        ChatMessage(role="assistant", content=[image])


def test_an_image_needs_exactly_one_source() -> None:
    with pytest.raises(ValueError):
        ImagePart()
    with pytest.raises(ValueError):
        ImagePart(data=b"x", url="https://example.test/a.jpg")


@respx.mock
def test_unsupported_image_type_is_refused_before_any_call() -> None:
    route = respx.post(RESPONSES_URL)
    bmp = ImagePart(data=b"BM....", mime_type="image/bmp")
    with pytest.raises(MetaRequestError):
        client_for(provider()).chat(chat_request("x", bmp))
    assert route.call_count == 0


@respx.mock
def test_more_than_fifty_images_are_refused_before_any_call(image: ImagePart) -> None:
    route = respx.post(RESPONSES_URL)
    with pytest.raises(MetaRequestError, match="too many images"):
        client_for(provider()).chat(chat_request("x", *([image] * 51)))
    assert route.call_count == 0


@respx.mock
def test_contributor_models_are_refused_unless_explicitly_allowed() -> None:
    route = respx.post(RESPONSES_URL).respond(200, json=responses_body())
    request = chat_request(model="muse-spark-1.3-contributor")

    with pytest.raises(MetaConfigError, match="train"):
        client_for(provider()).chat(request)
    assert route.call_count == 0

    client_for(provider(allow_contributor=True)).chat(request)
    assert route.call_count == 1


# --- transport errors and retries ----------------------------------------------------------


@respx.mock
def test_5xx_then_success_is_retried_through_the_client() -> None:
    route = respx.post(RESPONSES_URL).mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(500, headers={"retry-after": "2"}),
            httpx.Response(200, json=responses_body()),
        ]
    )
    sleeps: list[float] = []
    client = client_for(provider(), sleeps)

    client.chat(chat_request())

    assert route.call_count == 3
    assert client.records[0].source == "live"
    assert client.records[0].retried_codes == ["503", "500"]
    assert sleeps[1] >= 2.0  # Retry-After honored


@respx.mock
def test_529_overloaded_is_retried() -> None:
    route = respx.post(RESPONSES_URL).mock(
        side_effect=[httpx.Response(529), httpx.Response(200, json=responses_body())]
    )
    client = client_for(provider())
    client.chat(chat_request())
    assert route.call_count == 2
    assert client.records[0].retried_codes == ["529"]


@respx.mock
def test_persistent_5xx_gives_up_with_a_server_error() -> None:
    route = respx.post(RESPONSES_URL).respond(502)
    client = client_for(provider())
    client.retry = RetryPolicy(max_attempts=3)
    with pytest.raises(MetaServerError) as info:
        client.chat(chat_request())
    assert route.call_count == 3
    assert info.value.attempts == 3


@respx.mock
def test_auth_error_is_not_retried_and_never_leaks_the_key() -> None:
    route = respx.post(RESPONSES_URL).respond(401, text=f"bad key {KEY}")
    with pytest.raises(MetaAuthError) as info:
        client_for(provider()).chat(chat_request())
    assert route.call_count == 1
    assert KEY not in str(info.value)
    assert KEY not in repr(provider())


@respx.mock
@pytest.mark.parametrize(
    ("status", "error"),
    [
        (400, MetaRequestError),
        (402, MetaPaymentRequiredError),
        (404, MetaModelNotFoundError),
    ],
)
def test_permanent_4xx_errors_are_typed_and_never_retried(
    status: int, error: type[Exception]
) -> None:
    route = respx.post(RESPONSES_URL).respond(status, text="nope")
    with pytest.raises(error) as info:
        client_for(provider()).chat(chat_request())
    assert route.call_count == 1
    assert info.value.status_code == status  # type: ignore[attr-defined]


@respx.mock
def test_429_waits_at_least_retry_after() -> None:
    respx.post(RESPONSES_URL).mock(
        side_effect=[
            httpx.Response(429, headers={"retry-after": "5"}),
            httpx.Response(200, json=responses_body()),
        ]
    )
    sleeps: list[float] = []
    client_for(provider(), sleeps).chat(chat_request())
    assert sleeps == [5.0]


@respx.mock
@pytest.mark.parametrize(("header", "seconds"), [("6", 6.0), ("1m30s", 90.0), ("250ms", 0.5)])
def test_429_without_retry_after_uses_the_rate_limit_reset_header(
    header: str, seconds: float
) -> None:
    respx.post(RESPONSES_URL).mock(
        side_effect=[
            httpx.Response(429, headers={"x-ratelimit-reset-requests": header}),
            httpx.Response(200, json=responses_body()),
        ]
    )
    sleeps: list[float] = []
    client_for(provider(), sleeps).chat(chat_request())
    assert sleeps == [max(seconds, 0.5)]  # backoff (0.5 at max jitter) is the floor


@respx.mock
def test_remaining_rate_limit_headers_are_recorded() -> None:
    headers = {"x-ratelimit-remaining-requests": "14", "x-ratelimit-remaining-tokens": "99000"}
    respx.post(RESPONSES_URL).respond(200, json=responses_body(), headers=headers)
    p = provider()
    client_for(p).chat(chat_request())
    assert p.rate_limit_remaining == {"requests": 14, "tokens": 99000}


@respx.mock
def test_timeout_maps_to_timeout_error_and_is_retried() -> None:
    route = respx.post(RESPONSES_URL).mock(
        side_effect=[httpx.ReadTimeout("slow"), httpx.Response(200, json=responses_body())]
    )
    client = client_for(provider())
    client.chat(chat_request())
    assert route.call_count == 2
    assert client.records[0].retried_codes == ["timeout"]


@respx.mock
def test_connection_error_maps_and_is_retried() -> None:
    respx.post(RESPONSES_URL).mock(side_effect=httpx.ConnectError("down"))
    client = client_for(provider())
    client.retry = RetryPolicy(max_attempts=2)
    with pytest.raises(MetaConnectionError):
        client.chat(chat_request())


# --- SAM 3.1 -------------------------------------------------------------------------------


@respx.mock
def test_sam_request_is_one_concept_plus_image_url_and_never_uploads_a_file(
    image: ImagePart,
) -> None:
    route = respx.post(RESPONSES_URL).respond(200, json=sam_body())  # no /v1/files route exists

    client_for(provider()).segment(segment_request(image, "crack"))

    assert route.call_count == 1
    body = json.loads(route.calls.last.request.content)
    assert body["model"] == "sam-3.1"
    assert body["stream"] is False
    assert body["metadata"] == {"mask_encoding": "one_bit", "include_confidence": "true"}
    (item,) = body["input"]
    assert item["type"] == "message" and item["role"] == "user"
    assert item["content"][0] == {"type": "input_text", "text": "crack"}
    assert item["content"][1]["type"] == "input_image"
    assert item["content"][1]["image_url"].startswith("data:image/png;base64,")
    assert len(item["content"]) == 2


@respx.mock
def test_sam_response_is_parsed_with_the_official_parser(image: ImagePart) -> None:
    respx.post(RESPONSES_URL).respond(200, json=sam_body())

    result = client_for(provider()).segment(segment_request(image, "crack", threshold=0.0))

    first, second = result.masks
    assert (first.concept, first.score) == ("crack", 0.96)
    assert first.box == (211, 228, 271, 255)  # inclusive wire x2/y2 become half-open
    assert (first.width, first.height) == (60, 27)
    assert first.area == SAM_FIRST_MASK_AREA
    assert (first.frame_width, first.frame_height) == (320, 334)  # from the box w/h
    assert second.score is None  # no confidence in the record: unknown, not zero
    assert second.box == (155, 228, 203, 255)


@respx.mock
def test_mask_raster_is_placed_on_the_frame_at_the_box(image: ImagePart) -> None:
    respx.post(RESPONSES_URL).respond(200, json=sam_body())
    (first, _) = client_for(provider()).segment(segment_request(image, threshold=0.0)).masks

    frame = first.frame_array()

    assert frame.shape == (334, 320)
    assert int(frame.sum()) == SAM_FIRST_MASK_AREA
    assert not frame[:228].any() and not frame[255:].any()
    assert not frame[:, :211].any() and not frame[:, 271:].any()
    assert (frame[228:255, 211:271] == first.array()).all()


@respx.mock
@pytest.mark.parametrize("output", [[message_item("")], []])
def test_zero_matches_is_normal_not_an_error(image: ImagePart, output: list) -> None:
    respx.post(RESPONSES_URL).respond(200, json=sam_body() | {"output": output})

    result = client_for(provider()).segment(segment_request(image))

    assert result.masks == []
    assert result.usage.calls == 1


@respx.mock
def test_sam_on_a_public_url_takes_the_frame_size_from_the_response() -> None:
    route = respx.post(RESPONSES_URL).respond(200, json=sam_body())
    url = "https://example.test/blade.jpg"

    result = client_for(provider()).segment(segment_request(ImagePart(url=url), threshold=0.0))

    content = json.loads(route.calls.last.request.content)["input"][0]["content"]
    assert content[1] == {"type": "input_image", "image_url": url}
    assert (result.masks[0].frame_width, result.masks[0].frame_height) == (320, 334)


@respx.mock
def test_sam_garbage_in_the_mask_payload_is_an_invalid_response(image: ImagePart) -> None:
    bad = "<0f>0<|box;x1=1;y1=1;x2=2;y2=2;w=10;h=10|><|mask;x=0;y=0;data=2,2,!!!!|>\n"
    respx.post(RESPONSES_URL).respond(200, json=sam_body(bad))
    with pytest.raises(MetaInvalidResponseError):
        client_for(provider()).segment(segment_request(image))


@respx.mock
def test_sam_400_for_a_bad_prompt_is_permanent(image: ImagePart) -> None:
    route = respx.post(RESPONSES_URL).respond(400, json={"error": {"code": "invalid_prompt"}})
    with pytest.raises(MetaRequestError):
        client_for(provider()).segment(segment_request(image))
    assert route.call_count == 1


@respx.mock
def test_each_concept_is_its_own_request_cached_and_retried_separately(
    image: ImagePart, tmp_path
) -> None:
    route = respx.post(RESPONSES_URL).mock(
        side_effect=[
            httpx.Response(200, json=sam_body()),  # "crack" ok
            httpx.Response(500),  # "erosion" fails ...
            httpx.Response(500),
            httpx.Response(500),
            httpx.Response(500),
        ]
    )
    cache = DiskCache(tmp_path / "c")
    client = client_for(provider(), cache=cache)

    with pytest.raises(MetaServerError):
        client.segment_concepts("sam-3.1", image, ["crack", "erosion"], threshold=0.0)

    texts = [json.loads(c.request.content)["input"][0]["content"][0]["text"] for c in route.calls]
    assert texts == ["crack", "erosion", "erosion", "erosion", "erosion"]

    # A re-run repeats only the concept that failed: "crack" is served from the cache.
    respx.reset()
    route = respx.post(RESPONSES_URL).respond(200, json=sam_body(""))
    merged = client_for(provider(), cache=cache).segment_concepts(
        "sam-3.1", image, ["crack", "erosion"], threshold=0.0
    )
    assert route.call_count == 1
    assert [m.concept for m in merged.masks] == ["crack", "crack"]


@pytest.mark.parametrize("concept", ["crack, dirt", "crack and dirt", "crack\ndirt", "a; b", "  "])
def test_a_request_carries_exactly_one_short_noun_phrase(concept: str, image: ImagePart) -> None:
    with pytest.raises(ValueError):
        segment_request(image, concept)


def test_attributes_and_multiword_phrases_are_fine(image: ImagePart) -> None:
    assert segment_request(image, "leading edge erosion").concept == "leading edge erosion"
    assert segment_request(image, "red square").concept == "red square"


# --- Baseten (chat completions) ------------------------------------------------------------


@respx.mock
def test_baseten_uses_chat_completions_at_the_documented_base_url() -> None:
    route = respx.post("https://inference.baseten.co/v1/chat/completions").respond(
        200, json=completions_body("open")
    )
    p = baseten_provider()

    client = client_for(p)
    result = client.chat(chat_request(model="meta-models/muse-spark-open"))

    assert result.text == "open"
    assert result.usage.cached_input_tokens == 2
    assert route.calls.last.request.headers["authorization"] == "Bearer bt-key"
    sent = json.loads(route.calls.last.request.content)
    assert sent["messages"][0]["content"][0] == {"type": "text", "text": "hello"}
    assert "input" not in sent and "temperature" not in sent
    assert client.records[0].price_documented is True
    with pytest.raises(MetaConfigError):
        p.segment(segment_request(ImagePart(data=make_image_bytes())))


@respx.mock
def test_baseten_payment_required_is_permanent_and_529_is_retried() -> None:
    url = "https://inference.baseten.co/v1/chat/completions"
    route = respx.post(url).mock(
        side_effect=[httpx.Response(529), httpx.Response(200, json=completions_body())]
    )
    client = client_for(baseten_provider())
    client.chat(chat_request(model="meta-models/muse-spark-open"))
    assert client.records[0].retried_codes == ["529"]

    route.mock(side_effect=[httpx.Response(402)])
    route.reset()
    with pytest.raises(MetaPaymentRequiredError):
        client_for(baseten_provider()).chat(chat_request(model="meta-models/muse-spark-open"))


def test_provider_requires_a_base_url() -> None:
    with pytest.raises(MetaConfigError):
        HttpProvider("meta", "", SecretStr("k"))


# --- URL joining ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "base",
    [
        "https://api.meta.ai",
        "https://api.meta.ai/",
        "https://api.meta.ai/v1",
        "https://api.meta.ai/v1/",
        "  https://api.meta.ai  ",
    ],
)
def test_join_url_never_doubles_the_version_prefix(base: str) -> None:
    assert join_url(base, "/v1/responses") == "https://api.meta.ai/v1/responses"


def test_join_url_for_baseten_and_other_path_prefixes() -> None:
    assert (
        join_url("https://inference.baseten.co/v1", "/v1/chat/completions")
        == "https://inference.baseten.co/v1/chat/completions"
    )
    assert (
        join_url("https://host.test/environments/production/sandbox/v1", "/v1/chat/completions")
        == "https://host.test/environments/production/sandbox/v1/chat/completions"
    )
