"""Fallback of issue #3: Muse Spark proposes boxes (0-1000 grid), SAM 3.1 refines them as masks."""

from __future__ import annotations

import json
import re
from typing import Any

from ..meta import ChatMessage, ChatRequest, ImagePart, MetaClient, SegmentMask, SegmentRequest

PROMPT = (
    "You are an object grounding expert. The image is a small drone photo tile of a wind turbine "
    "blade. Provide the bounding box coordinates of every visible surface defect (cracks, "
    "leading-edge erosion, chips or missing paint, lightning damage, holes) as object_name "
    '"damage", and of every patch of dirt or stains as object_name "dirt". Return only a JSON '
    'array whose items look like {"object_name": "damage", "bbox": [{"x_min": 0, "y_min": 0, '
    '"x_max": 0, "y_max": 0}]}. Coordinates are integers on a 0-1000 grid with (0,0) at the '
    "top-left, relative to this image. If there are none, return []."
)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)


def parse_proposals(
    text: str, width: int, height: int
) -> list[tuple[str, tuple[int, int, int, int]]]:
    """`[(label, (x1, y1, x2, y2))]` in pixels, clamped to the image; bad items are skipped."""
    fenced = _FENCE.search(text)
    body = fenced.group(1) if fenced else text
    start, end = body.find("["), body.rfind("]")
    if start < 0 or end < start:
        return []
    try:
        items: list[Any] = json.loads(body[start : end + 1])
    except ValueError:
        return []
    out: list[tuple[str, tuple[int, int, int, int]]] = []
    for item in items:
        if not isinstance(item, dict) or item.get("object_name") not in ("damage", "dirt"):
            continue
        raw = item.get("bbox")
        boxes: list[Any] = raw if isinstance(raw, list) else [raw]
        for box in boxes:
            try:
                x1, y1, x2, y2 = (float(box[k]) for k in ("x_min", "y_min", "x_max", "y_max"))
            except (KeyError, TypeError, ValueError):
                continue
            left, right = sorted((x1 * width / 1000, x2 * width / 1000))
            top, bottom = sorted((y1 * height / 1000, y2 * height / 1000))
            left, right = (min(max(v, 0), width - 1) for v in (left, right))
            top, bottom = (min(max(v, 0), height - 1) for v in (top, bottom))
            if right - left < 2 or bottom - top < 2:
                continue
            out.append((item["object_name"], (int(left), int(top), int(right), int(bottom))))
    return out


def propose_boxes(
    client: MetaClient, chat_model: str, image: ImagePart, width: int, height: int
) -> list[tuple[str, tuple[int, int, int, int]]]:
    request = ChatRequest(
        model=chat_model, messages=[ChatMessage.user(PROMPT, image)], max_tokens=2000
    )
    return parse_proposals(client.chat(request).text, width, height)


def refine_with_sam(
    client: MetaClient,
    sam_model: str,
    image: ImagePart,
    boxes: list[tuple[int, int, int, int]],
    size: tuple[int, int],
) -> list[SegmentMask]:
    """One SAM request for up to 16 boxes; `object_id` (1-based) points back into `boxes`."""
    masks: list[SegmentMask] = []
    for i in range(0, len(boxes), 16):
        request = SegmentRequest(
            model=sam_model,
            image=image,
            concept="defect candidate",
            threshold=0.0,
            boxes=boxes[i : i + 16],
            frame_size=size,
        )
        masks += client.segment(request).masks
    return masks
