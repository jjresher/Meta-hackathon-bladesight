"""Replies modelled on the first real Meta responses (docs/evidence/meta-api-step1.md).

The `usage` numbers and the overall structure come from the real calls (the raw replies were not
kept, so the envelope fields are reconstructed from the observed shape); ids and text are made up.
They pin the parser to what the API was seen to return, not to what the docs suggest.
"""

import httpx
import pytest
import respx
from conftest import segment_request
from pydantic import SecretStr

from bladesight.meta import (
    ChatMessage,
    ChatRequest,
    HttpProvider,
    ImagePart,
    MetaClient,
    SpendTracker,
)

BASE = "https://api.meta.ai"
RESPONSES_URL = f"{BASE}/v1/responses"
BLADE_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/4/44/blade.jpg/1280px-blade.jpg"


def envelope(**fields: object) -> dict:
    """The fields both real replies shared."""
    return {
        "id": "resp_123",
        "object": "response",
        "status": "completed",
        "created_at": 1.0,
        "completed_at": 2.0,
        "error": None,
        "incomplete_details": None,
        "instructions": None,
        "tools": [],
        "tool_choice": "auto",
        "truncation": "disabled",
        "service_tier": "auto",
        "parallel_tool_calls": True,
        "background": False,
        "store": True,
        "temperature": 1.0,
        "top_p": 1.0,
        "top_logprobs": 0,
        **fields,
    }


REAL_MUSE_SPARK_REPLY = envelope(
    model="muse-spark-1.3",
    reasoning={"effort": "high"},
    max_output_tokens=800,
    output=[
        {"type": "reasoning", "id": "rs_1", "summary": [], "status": "completed"},
        {
            "type": "message",
            "id": "msg_1",
            "role": "assistant",
            "content": [
                {
                    "type": "output_text",
                    "text": "A short description.",
                    "annotations": [],
                    "logprobs": [],
                }
            ],
            "status": "completed",
        },
    ],
    usage={
        "input_tokens": 1143,
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens": 711,
        "output_tokens_details": {"reasoning_tokens": 686},
        "total_tokens": 1854,
    },
)


def sam_reply(text: str, images_processed: int = 1) -> dict:
    return envelope(
        model="sam-3.1",
        metadata={"include_confidence": "true", "mask_encoding": "one_bit"},
        output=[
            {
                "type": "message",
                "id": "msg_2",
                "role": "assistant",
                "content": [
                    {"type": "output_text", "text": text, "annotations": [], "logprobs": []}
                ],
                "status": "completed",
            }
        ],
        usage={
            "input_tokens": 0,
            "input_tokens_details": {"cached_tokens": 0},
            "output_tokens": 0,
            "output_tokens_details": {"reasoning_tokens": 0},
            "total_tokens": 0,
            "images_processed": images_processed,
        },
    )


def client() -> MetaClient:
    return MetaClient(
        HttpProvider("meta", BASE, SecretStr("k")), spend=SpendTracker(0.10, provider="meta")
    )


@respx.mock
def test_real_muse_spark_reply_is_parsed_and_priced() -> None:
    respx.post(RESPONSES_URL).respond(200, json=REAL_MUSE_SPARK_REPLY)
    request = ChatRequest(
        model="muse-spark-1.3",
        messages=[ChatMessage.user("Describe this image.", ImagePart(url=BLADE_URL))],
        max_tokens=800,
    )

    c = client()
    result = c.chat(request)

    assert result.text == "A short description."
    assert (result.usage.input_tokens, result.usage.output_tokens) == (1143, 711)
    assert result.usage.cached_input_tokens == 0
    assert result.model == "muse-spark-1.3"
    # 1143 x $1.25/M + 711 x $4.25/M, the cost logged for the real call
    assert c.records[0].cost_usd == pytest.approx(0.004451, abs=1e-6)
    assert c.records[0].cost_from_estimate is False


@respx.mock
def test_real_sam_zero_match_reply_is_an_empty_result_billed_per_image(image: ImagePart) -> None:
    respx.post(RESPONSES_URL).respond(200, json=sam_reply(""))

    c = client()
    result = c.segment(segment_request(ImagePart(url=BLADE_URL), "wind turbine blade"))

    assert result.masks == []
    assert result.usage.calls == 1
    assert result.model == "sam-3.1"
    assert c.records[0].cost_usd == pytest.approx(0.0025)


@respx.mock
def test_sam_is_billed_by_images_processed_not_by_tokens() -> None:
    respx.post(RESPONSES_URL).respond(200, json=sam_reply("", images_processed=2))
    c = client()
    c.segment(segment_request(ImagePart(url=BLADE_URL)))
    assert c.records[0].cost_usd == pytest.approx(0.005)


@respx.mock
@pytest.mark.parametrize("images", [0, None, "1", True])
def test_a_missing_or_odd_images_processed_falls_back_to_one_image(images: object) -> None:
    body = sam_reply("")
    body["usage"]["images_processed"] = images
    respx.post(RESPONSES_URL).respond(200, json=body)
    c = client()
    c.segment(segment_request(ImagePart(url=BLADE_URL)))
    assert c.records[0].cost_usd == pytest.approx(0.0025)


@respx.mock
def test_a_reply_cut_off_by_max_output_tokens_keeps_its_billed_usage() -> None:
    """Reasoning can eat the whole output budget: status incomplete, no message item."""
    body = REAL_MUSE_SPARK_REPLY | {
        "status": "incomplete",
        "incomplete_details": {"reason": "max_output_tokens"},
        "output": [REAL_MUSE_SPARK_REPLY["output"][0]],
    }
    respx.post(RESPONSES_URL).mock(return_value=httpx.Response(200, json=body))
    c = client()
    result = c.chat(
        ChatRequest(model="muse-spark-1.3", messages=[ChatMessage.user("x")], max_tokens=800)
    )
    assert result.text == ""
    assert c.records[0].cost_usd > 0
