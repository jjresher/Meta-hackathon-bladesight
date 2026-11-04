"""Close and context crops of a defect for the grading prompts (square PNGs, not distorted).

A crop is a SQUARE region centred on the defect, grown by `pad`, at least `min_side` px wide and
moved (not stretched) to stay inside the tile; it is then resized to `SIZE`. Stretching a thin
crack to a square (the first version) made small defects unreadable.
"""

from __future__ import annotations

import io

from PIL import Image

from ..contracts import BBox

SIZE = 336
CLOSE_MIN_SIDE = 64.0
CONTEXT_MIN_SIDE = 192.0
CLOSE_PAD = 0.5
CONTEXT_PAD = 3.0


def crop_png(png: bytes, box: BBox, pad: float, min_side: float = CLOSE_MIN_SIDE) -> bytes:
    image = Image.open(io.BytesIO(png)).convert("RGB")
    width, height = image.size
    extent = max(box.x2 - box.x1, box.y2 - box.y1, 1.0)
    side = min(max(extent * (1 + 2 * pad), min_side), float(min(width, height)))
    cx, cy = (box.x1 + box.x2) / 2, (box.y1 + box.y2) / 2
    left = min(max(cx - side / 2, 0.0), width - side)
    top = min(max(cy - side / 2, 0.0), height - side)
    region = (int(left), int(top), int(left + side), int(top + side))
    out = io.BytesIO()
    image.crop(region).resize((SIZE, SIZE), Image.Resampling.LANCZOS).save(out, format="PNG")
    return out.getvalue()


def close_and_context(png: bytes, box: BBox) -> tuple[bytes, bytes]:
    return (
        crop_png(png, box, pad=CLOSE_PAD, min_side=CLOSE_MIN_SIDE),
        crop_png(png, box, pad=CONTEXT_PAD, min_side=CONTEXT_MIN_SIDE),
    )
