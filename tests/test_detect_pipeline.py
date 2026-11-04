"""Detection pipeline on the stub provider: merging, filtering, ids, overlay. Spends nothing."""

from __future__ import annotations

import io
import json

import numpy as np
from PIL import Image

from bladesight.detect.overlay import render_overlay
from bladesight.detect.pipeline import (
    MIN_MASK_AREA_PX,
    Detection,
    detect_tile,
    mask_iou,
    mask_outline,
    merge_overlapping,
)
from bladesight.meta import (
    ChatResult,
    MetaSettings,
    SegmentMask,
    SegmentResult,
    StubProvider,
    Usage,
    build_client,
)

W, H = 200, 120


def _png() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (W, H), (90, 90, 90)).save(buffer, format="PNG")
    return buffer.getvalue()


def _reply(items: list[dict[str, object]]) -> ChatResult:
    return ChatResult(text=json.dumps(items), usage=Usage(input_tokens=100, output_tokens=50))


def _item(label: str, x1: int, y1: int, x2: int, y2: int) -> dict[str, object]:
    return {
        "object_name": label,
        "bbox": [{"x_min": x1, "y_min": y1, "x_max": x2, "y_max": y2}],
    }


def _text_mask(concept: str, x1: int, y1: int, x2: int, y2: int, score: float = 0.8) -> SegmentMask:
    frame = np.zeros((H, W), dtype=bool)
    frame[y1:y2, x1:x2] = True
    return SegmentMask.from_frame_array(concept, score, frame)


def _run(stub: StubProvider, with_blade: bool = True):
    client = build_client(MetaSettings(), provider="stub", stub=stub)
    return detect_tile(client, MetaSettings(), "DJI_0001_01_01", _png(), with_blade=with_blade)


def test_box_prompts_become_defects_with_stable_ids_and_labels() -> None:
    stub = StubProvider(
        chat_responses=[
            _reply([_item("damage", 100, 100, 300, 400), _item("dirt", 600, 100, 900, 500)])
        ]
    )
    result = _run(stub, with_blade=False)
    # two box-prompt masks plus the stub's default centred mask for the "surface damage" concept
    assert [d.defect.id for d in result.defects] == [
        f"DJI_0001_01_01/d{n}" for n in range(1, len(result.defects) + 1)
    ]
    assert len(result.defects) >= 2
    assert {d.defect.label for d in result.defects} == {"damage", "dirt"}
    assert all(d.defect.source in ("box_prompt", "concept") for d in result.defects)
    assert stub.segment_calls[0].boxes  # one box-prompt request, then the text concepts
    assert [c.concept for c in stub.segment_calls[1:]] == ["surface damage", "crack"]


def test_no_proposals_still_runs_text_concepts_and_zero_defects_is_valid() -> None:
    stub = StubProvider(
        chat_responses=[_reply([])],
        segment_responses=[SegmentResult(), SegmentResult()],
    )
    result = _run(stub, with_blade=False)
    assert result.defects == [] and result.n_proposals == 0
    assert len(stub.segment_calls) == 2


def test_overlapping_masks_of_the_same_label_merge_and_tiny_masks_drop() -> None:
    big = _text_mask("surface damage", 20, 20, 60, 60)
    twin = _text_mask("crack", 22, 22, 60, 60, score=0.6)
    tiny = _text_mask("crack", 100, 100, 102, 102)
    assert tiny.area < MIN_MASK_AREA_PX
    stub = StubProvider(
        chat_responses=[_reply([])],
        segment_responses=[SegmentResult(masks=[big, tiny]), SegmentResult(masks=[twin])],
    )
    result = _run(stub, with_blade=False)
    assert len(result.defects) == 1
    assert result.defects[0].defect.score == 0.8  # the higher score is kept


def test_masks_off_the_blade_are_dropped_when_a_blade_is_found() -> None:
    on_blade = _text_mask("surface damage", 20, 20, 60, 60)
    off_blade = _text_mask("surface damage", 150, 80, 190, 110)
    blade = _text_mask("wind turbine blade", 0, 0, 100, 120)
    stub = StubProvider(
        chat_responses=[_reply([])],
        segment_responses=[
            SegmentResult(masks=[on_blade, off_blade]),
            SegmentResult(),
            SegmentResult(masks=[blade]),
        ],
    )
    result = _run(stub)
    assert len(result.defects) == 1 and result.blade_mask is not None
    assert result.defects[0].defect.bbox.x1 == 20


def test_outline_is_a_closed_polygon_and_overlay_is_a_png() -> None:
    frame = np.zeros((H, W), dtype=bool)
    frame[10:30, 20:50] = True
    outline = mask_outline(frame)
    xs = [p[0] for p in outline]
    assert min(xs) == 20 and max(xs) == 50 and mask_outline(np.zeros((5, 5), dtype=bool)) == []
    stub = StubProvider(chat_responses=[_reply([_item("damage", 100, 100, 300, 400)])])
    result = _run(stub, with_blade=False)
    out = Image.open(io.BytesIO(render_overlay(_png(), result)))
    assert out.size == (W, H) and out.format == "PNG"


def test_merge_keeps_different_labels_apart() -> None:
    a = _text_mask("x", 0, 0, 30, 30)
    items = [
        Detection(defect=_defect("damage", 0.9), mask=a.frame_array()),
        Detection(defect=_defect("dirt", 0.8), mask=a.frame_array()),
    ]
    assert len(merge_overlapping(items)) == 2
    assert mask_iou(items[0].mask, items[1].mask) == 1.0


def _defect(label: str, score: float):
    from bladesight.contracts import BBox, Defect

    return Defect(
        id="x",
        image_id="i",
        concept="c",
        label=label,  # type: ignore[arg-type]
        score=score,
        bbox=BBox(x1=0, y1=0, x2=30, y2=30),
        mask_area_px=900,
    )


def test_more_than_16_boxes_are_chunked_and_ids_index_into_the_boxes() -> None:
    from bladesight.detect.propose import refine_with_sam
    from bladesight.meta import ImagePart

    boxes = [(i, i, i + 5, i + 5) for i in range(20)]
    stub = StubProvider()
    client = build_client(MetaSettings(), provider="stub", stub=stub)
    masks = refine_with_sam(
        client, "stub-model", ImagePart(data=_png(), mime_type="image/png"), boxes, (W, H)
    )
    assert len(stub.segment_calls) == 2
    assert sorted(int(m.object_id or 0) for m in masks) == list(range(1, 21))
    by_id = {m.object_id: m for m in masks}
    assert by_id["17"].box[:2] == (16, 16)  # the 17th box starts at (16, 16)
