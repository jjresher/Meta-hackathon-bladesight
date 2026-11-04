"""Spark box proposals (0-1000 grid) and SAM box-prompt payloads, on the stub / pure functions."""

from __future__ import annotations

from bladesight.detect.propose import parse_proposals
from bladesight.meta import ImagePart, SegmentRequest
from bladesight.meta.http_provider import _segment_payload, box_prompt_text


def test_parse_proposals_scales_clamps_and_skips_bad_items() -> None:
    text = (
        "Here you go:\n```json\n["
        '{"object_name":"damage","bbox":[{"x_min":100,"y_min":200,"x_max":300,"y_max":400}]},'
        '{"object_name":"dirt","bbox":[{"x_min":-5,"y_min":0,"x_max":1001,"y_max":500}]},'
        '{"object_name":"cat","bbox":[{"x_min":0,"y_min":0,"x_max":9,"y_max":9}]},'
        '{"object_name":"damage","bbox":[{"x_min":10,"y_min":10}]}'
        "]\n```"
    )
    got = parse_proposals(text, 1000, 500)
    assert got == [("damage", (100, 100, 300, 200)), ("dirt", (0, 0, 999, 250))]


def test_parse_proposals_tolerates_garbage() -> None:
    assert parse_proposals("no boxes here", 586, 371) == []
    assert parse_proposals("[not json]", 586, 371) == []
    assert parse_proposals("[]", 586, 371) == []


def test_box_prompt_text_and_payload() -> None:
    request = SegmentRequest(
        model="sam-3.1",
        image=ImagePart(url="https://example.com/a.png"),
        concept="defect candidate",
        boxes=[(10, 20, 30, 40), (-5, 0, 9999, 9999)],
        frame_size=(586, 371),
    )
    assert box_prompt_text(request) == (
        "<0f>1<|box;x1=10;y1=20;x2=30;y2=40;w=586;h=371|>,"
        "2<|box;x1=0;y1=0;x2=585;y2=370;w=586;h=371|>"
    )
    content = _segment_payload(request)["input"][0]["content"]
    assert content[0]["text"].startswith("<0f>1<|box;")


def test_text_requests_keep_their_cache_key_and_boxes_change_it() -> None:
    image = ImagePart(url="https://example.com/a.png")
    text = SegmentRequest(model="sam-3.1", image=image, concept="crack")
    boxed = SegmentRequest(model="sam-3.1", image=image, concept="crack", boxes=[(1, 2, 3, 4)])
    assert set(text.cache_payload()) == {"image", "concept"}
    assert text.cache_payload() != boxed.cache_payload()
