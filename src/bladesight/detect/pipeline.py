"""Defect and blade detection on one tile (issue #5), the pipeline chosen by the #3 spike.

1. Muse Spark proposes damage and dirt boxes (0-1000 grid).
2. SAM 3.1 turns each box into a mask (box prompts, one request for up to 16 boxes).
3. SAM 3.1 text concepts (`surface damage`, `crack`) add candidates the proposals missed.
4. Post-processing: drop tiny masks, merge overlapping ones, keep masks that sit on the blade
   (only when a blade mask was found: `wind turbine blade` often finds nothing on close-ups).

Every call goes through `MetaClient` (cache, retries, spend cap), so a replayed run is free.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import numpy as np
from PIL import Image

from ..contracts import BBox, Defect
from ..meta import ImagePart, MetaClient, MetaSettings, SegmentMask
from .propose import propose_boxes, refine_with_sam

TEXT_CONCEPTS = ("surface damage", "crack")
BLADE_CONCEPT = "wind turbine blade"
MIN_MASK_AREA_PX = 20
MERGE_IOU = 0.5
MIN_INSIDE_BLADE = 0.5
OUTLINE_STEP = 2


@dataclass
class Detection:
    """A `Defect` (the API object) plus the full-frame mask it was drawn from."""

    defect: Defect
    mask: np.ndarray = field(repr=False)


@dataclass
class TileDetection:
    tile_id: str
    width: int
    height: int
    defects: list[Detection]
    blade_mask: np.ndarray | None
    n_proposals: int


def mask_to_frame(mask: SegmentMask) -> np.ndarray:
    return mask.frame_array()


def mask_iou(a: np.ndarray, b: np.ndarray) -> float:
    union = np.logical_or(a, b).sum()
    return float(np.logical_and(a, b).sum() / union) if union else 0.0


def mask_outline(mask: np.ndarray, step: int = OUTLINE_STEP) -> list[tuple[float, float]]:
    """A closed polygon around the mask: right edge of every row top to bottom, left edge back.

    Approximate (one span per row, so holes and separate parts in one row are filled); it is for
    drawing overlays, not for measurement (measurement uses the mask itself).
    """
    rows = np.flatnonzero(mask.any(axis=1))
    if rows.size == 0:
        return []
    picked = list(rows[::step])
    if picked[-1] != rows[-1]:
        picked.append(rows[-1])
    right, left = [], []
    for y in picked:
        xs = np.flatnonzero(mask[y])
        left.append((float(xs[0]), float(y)))
        right.append((float(xs[-1] + 1), float(y)))
    return right + left[::-1]


def _bbox(mask: np.ndarray) -> BBox:
    rows, cols = np.where(mask)
    return BBox(
        x1=float(cols.min()),
        y1=float(rows.min()),
        x2=float(cols.max() + 1),
        y2=float(rows.max() + 1),
    )


def merge_overlapping(items: list[Detection]) -> list[Detection]:
    """Greedy, highest score first: a mask overlapping a kept one (IoU >= 0.5) is merged into it."""
    kept: list[Detection] = []
    for item in sorted(items, key=lambda d: -d.defect.score):
        for target in kept:
            if (
                target.defect.label == item.defect.label
                and mask_iou(target.mask, item.mask) >= MERGE_IOU
            ):
                target.mask = np.logical_or(target.mask, item.mask)
                break
        else:
            kept.append(item)
    return kept


def detect_tile(
    client: MetaClient,
    settings: MetaSettings,
    tile_id: str,
    png_bytes: bytes,
    *,
    image_id: str | None = None,
    with_blade: bool = True,
) -> TileDetection:
    image_id = image_id or tile_id
    with Image.open(io.BytesIO(png_bytes)) as opened:
        width, height = opened.size
    image = ImagePart(data=png_bytes, mime_type="image/png")

    candidates: list[Detection] = []

    def add(mask: SegmentMask, label: str, concept: str, source: str) -> None:
        frame = mask_to_frame(mask)
        if frame.sum() < MIN_MASK_AREA_PX:
            return
        candidates.append(
            Detection(
                defect=Defect.model_validate(
                    {
                        "id": "pending",
                        "image_id": image_id,
                        "concept": concept,
                        "source": source,
                        "label": label,
                        "score": min(max(mask.score if mask.score is not None else 0.5, 0), 1),
                        "bbox": _bbox(frame),
                        "mask_area_px": float(frame.sum()),
                    }
                ),
                mask=frame,
            )
        )

    proposals = propose_boxes(client, settings.chat_model, image, width, height)
    if proposals:
        refined = refine_with_sam(
            client, settings.sam_model, image, [box for _, box in proposals], (width, height)
        )
        for mask in refined:
            index = int(mask.object_id or 0) - 1
            if 0 <= index < len(proposals):
                label = proposals[index][0]
                add(mask, label, f"{label} (proposed)", "box_prompt")
    for concept in TEXT_CONCEPTS:
        for mask in client.segment_concepts(settings.sam_model, image, [concept], 0.5).masks:
            add(mask, "damage", concept, "concept")

    blade_mask: np.ndarray | None = None
    if with_blade:
        blades = client.segment_concepts(settings.sam_model, image, [BLADE_CONCEPT], 0.5).masks
        if blades:
            blade_mask = np.logical_or.reduce([mask_to_frame(m) for m in blades])

    merged = merge_overlapping(candidates)
    if blade_mask is not None:
        merged = [
            d for d in merged if (d.mask & blade_mask).sum() / d.mask.sum() >= MIN_INSIDE_BLADE
        ]
    merged.sort(key=lambda d: (d.defect.bbox.y1, d.defect.bbox.x1))
    for number, det in enumerate(merged, start=1):
        frame = det.mask
        det.defect = det.defect.model_copy(
            update={
                "id": f"{image_id}/d{number}",
                "bbox": _bbox(frame),
                "outline": [mask_outline(frame)],
                "mask_area_px": float(frame.sum()),
            }
        )
    return TileDetection(tile_id, width, height, merged, blade_mask, len(proposals))
