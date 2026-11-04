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
from typing import Literal

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
    return _nms(items, MERGE_IOU, union=True)


@dataclass(frozen=True)
class PostConfig:
    """How raw SAM masks become detections; `V1` is the frozen #16 pipeline, `V2` is #22's.

    - `split_components`: each 8-connected part of a mask becomes its own detection (v1 keeps a
      scattered concept mask as one box spanning all its parts);
    - `min_area_px`: parts (or masks) smaller than this are dropped;
    - `max_area_px`: parts larger than this are dropped (None keeps all);
    - `merge`: `union` ORs same-label masks with IoU >= `merge_iou` (v1), `nms` keeps only the
      higher-scored one, `none` keeps both.
    """

    split_components: bool = False
    min_area_px: int = MIN_MASK_AREA_PX
    max_area_px: int | None = None
    merge: Literal["union", "nms", "none"] = "union"
    merge_iou: float = MERGE_IOU
    min_part_share: float = 0.0  # parts below this share of the mask's largest part are dropped
    max_parts: int | None = None  # keep only the largest parts of one mask
    erode_px: int = 0  # split parts joined by thin bridges: components of the eroded mask


V1 = PostConfig()
# Chosen on the 300-tile seed-7 dev sample only (docs/evidence/eval_fresh_v2.md, dev table):
# split every mask into its connected parts, drop parts under 40 px or under a tenth of the
# mask's largest part, and suppress (not union) overlapping same-label masks.
V2 = PostConfig(split_components=True, min_area_px=40, min_part_share=0.1, merge="nms")
DETECTORS: dict[str, PostConfig] = {"v1": V1, "v2": V2}
DEFAULT_DETECTOR = "v1"  # evaluation default: eval_dev / eval_heldout stay reproducible on v1
# What the product runs (the farm, `poe detect`): v2 won the preregistered fresh-set comparison
# (docs/evidence/eval_fresh_v2.md). The held-out result of #16 measured v1 only.
PRODUCT_DETECTOR = "v2"


@dataclass
class Candidate:
    """One raw SAM mask on the full frame, before post-processing."""

    mask: np.ndarray = field(repr=False)
    label: str
    concept: str
    source: str
    score: float
    prompt_box: tuple[int, int, int, int] | None = (
        None  # the Spark box a box-prompted mask came from
    )


def collect_candidates(
    client: MetaClient, settings: MetaSettings, image: ImagePart, width: int, height: int
) -> tuple[list[Candidate], int]:
    """The model calls of the pipeline (steps 1-3); returns the raw masks and the proposal count."""
    candidates: list[Candidate] = []

    def add(
        mask: SegmentMask,
        label: str,
        concept: str,
        source: str,
        prompt_box: tuple[int, int, int, int] | None = None,
    ) -> None:
        score = min(max(mask.score if mask.score is not None else 0.5, 0), 1)
        candidates.append(Candidate(mask_to_frame(mask), label, concept, source, score, prompt_box))

    proposals = propose_boxes(client, settings.chat_model, image, width, height)
    if proposals:
        refined = refine_with_sam(
            client, settings.sam_model, image, [box for _, box in proposals], (width, height)
        )
        for mask in refined:
            index = int(mask.object_id or 0) - 1
            if 0 <= index < len(proposals):
                label, box = proposals[index]
                add(mask, label, f"{label} (proposed)", "box_prompt", box)
    for concept in TEXT_CONCEPTS:
        for mask in client.segment_concepts(settings.sam_model, image, [concept], 0.5).masks:
            add(mask, "damage", concept, "concept")
    return candidates, len(proposals)


def _parts(mask: np.ndarray) -> list[np.ndarray]:
    """The 8-connected components of a boolean mask, largest first (plain BFS, no scipy)."""
    height, width = mask.shape
    seen = np.zeros_like(mask, dtype=bool)
    parts: list[np.ndarray] = []
    for y0, x0 in np.argwhere(mask):
        if seen[y0, x0]:
            continue
        part = np.zeros_like(mask, dtype=bool)
        stack = [(int(y0), int(x0))]
        seen[y0, x0] = True
        while stack:
            y, x = stack.pop()
            part[y, x] = True
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    ny, nx = y + dy, x + dx
                    if 0 <= ny < height and 0 <= nx < width and mask[ny, nx] and not seen[ny, nx]:
                        seen[ny, nx] = True
                        stack.append((ny, nx))
        parts.append(part)
    return sorted(parts, key=lambda p: -int(p.sum()))


def _shift_and(mask: np.ndarray, grow: bool) -> np.ndarray:
    """One step of 3x3 erosion (AND of the 9 shifts) or dilation (OR), zero outside the frame."""
    padded = np.pad(mask, 1, constant_values=False)
    height, width = mask.shape
    shifts = [padded[dy : dy + height, dx : dx + width] for dy in range(3) for dx in range(3)]
    return np.logical_or.reduce(shifts) if grow else np.logical_and.reduce(shifts)


def _split(mask: np.ndarray, config: PostConfig) -> list[np.ndarray]:
    if config.erode_px > 0:
        core = mask
        for _ in range(config.erode_px):
            core = _shift_and(core, grow=False)
        parts = []
        for seed in _parts(core):
            grown = seed
            for _ in range(config.erode_px):
                grown = _shift_and(grown, grow=True)
            parts.append(grown & mask)
        if not parts:  # everything was thinner than the erosion: keep the plain components
            parts = _parts(mask)
    else:
        parts = _parts(mask)
    if parts and config.min_part_share > 0:
        largest = int(parts[0].sum())
        parts = [p for p in parts if p.sum() >= config.min_part_share * largest]
    if config.max_parts is not None:
        parts = parts[: config.max_parts]
    return parts


def _nms(items: list[Detection], threshold: float, union: bool) -> list[Detection]:
    kept: list[Detection] = []
    for item in sorted(items, key=lambda d: -d.defect.score):
        for target in kept:
            if (
                target.defect.label == item.defect.label
                and mask_iou(target.mask, item.mask) >= threshold
            ):
                if union:
                    target.mask = np.logical_or(target.mask, item.mask)
                break
        else:
            kept.append(item)
    return kept


def postprocess(
    candidates: list[Candidate], image_id: str, config: PostConfig = V1
) -> list[Detection]:
    """Masks -> detections (before the blade filter and the final numbering)."""
    items: list[Detection] = []
    for cand in candidates:
        if cand.mask.sum() < config.min_area_px:
            continue  # v1 drops tiny masks before anything else
        parts = _split(cand.mask, config) if config.split_components else [cand.mask]
        for part in parts:
            area = float(part.sum())
            if area < config.min_area_px:
                continue
            if config.max_area_px is not None and area > config.max_area_px:
                continue
            items.append(
                Detection(
                    defect=Defect.model_validate(
                        {
                            "id": "pending",
                            "image_id": image_id,
                            "concept": cand.concept,
                            "source": cand.source,
                            "label": cand.label,
                            "score": cand.score,
                            "bbox": _bbox(part),
                            "mask_area_px": area,
                        }
                    ),
                    mask=part,
                )
            )
    if config.merge == "none":
        return items
    return _nms(items, config.merge_iou, union=config.merge == "union")


def detect_tile(
    client: MetaClient,
    settings: MetaSettings,
    tile_id: str,
    png_bytes: bytes,
    *,
    image_id: str | None = None,
    with_blade: bool = True,
    detector: str = DEFAULT_DETECTOR,
) -> TileDetection:
    image_id = image_id or tile_id
    with Image.open(io.BytesIO(png_bytes)) as opened:
        width, height = opened.size
    image = ImagePart(data=png_bytes, mime_type="image/png")
    config = DETECTORS[detector]

    candidates, n_proposals = collect_candidates(client, settings, image, width, height)

    blade_mask: np.ndarray | None = None
    if with_blade:
        blades = client.segment_concepts(settings.sam_model, image, [BLADE_CONCEPT], 0.5).masks
        if blades:
            blade_mask = np.logical_or.reduce([mask_to_frame(m) for m in blades])

    merged = postprocess(candidates, image_id, config)
    if blade_mask is not None:
        merged = [
            d for d in merged if (d.mask & blade_mask).sum() / d.mask.sum() >= MIN_INSIDE_BLADE
        ]
    return TileDetection(
        tile_id, width, height, finalize(merged, image_id), blade_mask, n_proposals
    )


def finalize(merged: list[Detection], image_id: str) -> list[Detection]:
    """Sort top to bottom, number the detections and attach their final box and outline."""
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
    return merged
