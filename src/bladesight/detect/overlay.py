"""Draw detections on a tile (local review images only: never committed, AGENTS.md rule 2)."""

from __future__ import annotations

import io

import numpy as np
from PIL import Image, ImageDraw

from .pipeline import TileDetection

COLORS = {"damage": (255, 60, 60), "dirt": (240, 200, 40)}
BLADE_COLOR = (60, 200, 255)
ALPHA = 90


def render_overlay(png_bytes: bytes, detection: TileDetection) -> bytes:
    base = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
    layer = np.zeros((detection.height, detection.width, 4), dtype=np.uint8)
    if detection.blade_mask is not None:
        layer[detection.blade_mask] = (*BLADE_COLOR, 40)
    for det in detection.defects:
        layer[det.mask] = (*COLORS[det.defect.label], ALPHA)
    out = Image.alpha_composite(base, Image.fromarray(layer, "RGBA"))
    draw = ImageDraw.Draw(out)
    for det in detection.defects:
        box = det.defect.bbox
        color = COLORS[det.defect.label]
        draw.rectangle((box.x1, box.y1, box.x2, box.y2), outline=color, width=1)
        draw.text(
            (box.x1 + 1, max(0, box.y1 - 10)),
            f"{det.defect.id.rsplit('/', 1)[-1]} {det.defect.score:.2f}",
            fill=color,
        )
    buffer = io.BytesIO()
    out.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()
