"""Close and context crops of a defect for the grading prompt (PNG bytes, 256x256)."""

from __future__ import annotations

import io

from PIL import Image

from ..contracts import BBox

SIZE = 256
MIN_SIDE = 24.0


def crop_png(png: bytes, box: BBox, pad: float, min_side: float = MIN_SIDE) -> bytes:
    """Crop `box` grown by `pad` times its size on every side (at least `min_side` px wide)."""
    image = Image.open(io.BytesIO(png)).convert("RGB")
    width, height = image.size
    bw, bh = max(box.x2 - box.x1, min_side), max(box.y2 - box.y1, min_side)
    cx, cy = (box.x1 + box.x2) / 2, (box.y1 + box.y2) / 2
    half_w, half_h = bw * (0.5 + pad), bh * (0.5 + pad)
    region = (
        max(0, int(cx - half_w)),
        max(0, int(cy - half_h)),
        min(width, int(cx + half_w) + 1),
        min(height, int(cy + half_h) + 1),
    )
    out = io.BytesIO()
    image.crop(region).resize((SIZE, SIZE), Image.Resampling.LANCZOS).save(out, format="PNG")
    return out.getvalue()


def close_and_context(png: bytes, box: BBox) -> tuple[bytes, bytes]:
    return crop_png(png, box, pad=0.4), crop_png(png, box, pad=3.0, min_side=96.0)
