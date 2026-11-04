"""Severity assessment on the stub: valid output, the single retry, and the failure path."""

from __future__ import annotations

import io
import json

import pytest
from PIL import Image

from bladesight.assess import AssessError, assess_defect, parse_assessment
from bladesight.assess.assess import build_prompt
from bladesight.assess.crops import SIZE, close_and_context
from bladesight.contracts import BBox, Defect, Measurement
from bladesight.meta import ChatResult, MetaSettings, StubProvider, Usage, build_client

GOOD = {
    "defect_type": "crack",
    "severity": 4,
    "rationale": "A thin open crack runs across the leading edge.",
    "confidence": 0.7,
}


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (200, 120), (80, 80, 80)).save(buffer, format="PNG")
    return buffer.getvalue()


def _defect() -> Defect:
    return Defect(
        id="T01-2018/DJI_0001_01_01/d1",
        image_id="T01-2018/DJI_0001_01_01",
        concept="crack",
        label="damage",
        score=0.8,
        bbox=BBox(x1=20, y1=20, x2=60, y2=50),
        mask_area_px=900,
    )


def _measurement() -> Measurement:
    return Measurement(
        defect_id=_defect().id,
        area_px=900,
        tile_area_ratio=0.0375,
        length_px=40,
        width_px=10,
        elongation=0.75,
        position="unknown",
    )


def _reply(text: str) -> ChatResult:
    return ChatResult(
        text=text, usage=Usage(input_tokens=100, output_tokens=40), model="stub-model"
    )


def _run(*replies: str):
    stub = StubProvider(chat_responses=[_reply(r) for r in replies])
    client = build_client(MetaSettings(), provider="stub", stub=stub)
    return stub, lambda: assess_defect(
        client, MetaSettings(), _png(), _defect(), _measurement(), provider="stub"
    )


def test_a_valid_reply_becomes_a_versioned_assessment() -> None:
    stub, run = _run("```json\n" + json.dumps(GOOD) + "\n```")
    result = run()
    assert (result.severity, result.defect_type, result.confidence) == (4, "crack", 0.7)
    assert (result.rubric_version, result.prompt_version) == ("v1", "assess/v1")
    assert result.defect_id == _defect().id and result.provider == "stub"
    assert len(stub.chat_calls) == 1
    assert len(stub.chat_calls[0].messages[0].content) == 3  # prompt + close + context crops


def test_invalid_json_is_retried_once_with_the_reason() -> None:
    stub, run = _run("I think it is bad.", json.dumps(GOOD))
    assert run().severity == 4
    assert len(stub.chat_calls) == 2
    retry_text = stub.chat_calls[1].messages[0].content[0].text  # type: ignore[union-attr]
    assert "previous reply was rejected" in retry_text


@pytest.mark.parametrize(
    "bad",
    [
        {**GOOD, "severity": 6},
        {**GOOD, "severity": "4"},
        {**GOOD, "severity": True},
        {**GOOD, "defect_type": "scratch"},
        {**GOOD, "confidence": 1.5},
        {**GOOD, "rationale": "  "},
    ],
)
def test_out_of_contract_values_are_rejected(bad: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        parse_assessment(json.dumps(bad))


def test_two_invalid_replies_raise_instead_of_guessing() -> None:
    stub, run = _run("nope", json.dumps({**GOOD, "severity": 9}))
    with pytest.raises(AssessError):
        run()
    assert len(stub.chat_calls) == 2


def test_prompt_carries_the_measurements_and_the_rubric_version() -> None:
    text = build_prompt(_defect(), _measurement())
    assert "version v1" in text and "3.75%" in text and "elongation 0.75" in text


def test_rubric_document_and_prompt_agree_on_the_version() -> None:
    from pathlib import Path

    rubric = (Path(__file__).resolve().parents[1] / "docs" / "rubric.md").read_text("utf-8")
    assert "(version `v1`)" in rubric and "illustrative rubric, not an industry standard" in rubric
    for level in ("Cosmetic", "Minor wear", "Moderate", "Serious", "Critical"):
        assert level in rubric


def test_crops_are_square_pngs_even_at_the_tile_edge() -> None:
    edge = BBox(x1=0, y1=0, x2=3, y2=3)
    for crop in close_and_context(_png(), edge):
        assert Image.open(io.BytesIO(crop)).size == (SIZE, SIZE)


def _red(image: Image.Image, x: int, y: int) -> int:
    pixel = image.getpixel((x, y))
    assert isinstance(pixel, tuple)
    return pixel[0]


def test_crops_do_not_distort_and_stay_inside_the_tile() -> None:
    from bladesight.assess.crops import crop_png

    # a left-to-right gradient makes any stretch or shift visible
    image = Image.new("RGB", (200, 120))
    for x in range(200):
        for y in range(120):
            image.putpixel((x, y), (x, 0, 0))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    png = buffer.getvalue()
    thin = BBox(x1=40, y1=60, x2=140, y2=66)  # a 100x6 crack
    crop = Image.open(io.BytesIO(crop_png(png, thin, pad=0.5, min_side=64)))
    assert crop.size == (SIZE, SIZE)
    # side = 100 * 2 = 200 px is clamped to the tile height (120): one square, no stretching
    left_value, right_value = _red(crop, 0, 10), _red(crop, SIZE - 1, 10)
    assert right_value - left_value == pytest.approx(119, abs=4)  # 120 px of the tile, 1:1 in x
    edge = BBox(x1=0, y1=0, x2=3, y2=3)  # at the corner the square moves, it is not stretched
    corner = Image.open(io.BytesIO(crop_png(png, edge, pad=0.5, min_side=64)))
    assert _red(corner, 0, 0) == 0
