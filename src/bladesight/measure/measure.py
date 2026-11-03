"""Mask -> `Measurement`: pixel size, shape (crack-like or patch-like) and position on the blade.

All sizes are relative (pixels and shares of an area): the tiles carry no scale, so nothing here
is millimetres. Position along the blade needs a blade mask; without one it is `unknown`.
"""

from __future__ import annotations

import numpy as np

from ..contracts import Measurement, Position
from ..detect.pipeline import TileDetection

ROOT_END = 1 / 3
TIP_START = 2 / 3
MIN_BLADE_PX = 200
MIN_INSIDE_FOR_POSITION = 0.5  # a defect mostly off the blade gets no root/mid/tip


def _principal_axis(points: np.ndarray) -> np.ndarray:
    """Unit vector of the largest-variance direction of (x, y) points."""
    if len(points) < 2:
        return np.array([1.0, 0.0])
    centered = points - points.mean(axis=0)
    _, vectors = np.linalg.eigh(np.cov(centered.T))
    return vectors[:, -1]


def _extent(points: np.ndarray, axis: np.ndarray) -> tuple[float, float]:
    """Pixel extent along `axis` and across it (+1: a pixel has width)."""
    along = points @ axis
    across = points @ np.array([-axis[1], axis[0]])
    return float(along.max() - along.min() + 1), float(across.max() - across.min() + 1)


def blade_axis(blade: np.ndarray) -> tuple[np.ndarray, np.ndarray, float, float] | None:
    """(axis pointing root -> tip, centroid, t_min, t_max) of a blade mask, or None if too small.

    Blades taper toward the tip, so the end of the principal axis where the mask is wider is the
    root. This is a heuristic: a tile may show only a part of the blade.
    """
    ys, xs = np.nonzero(blade)
    if len(xs) < MIN_BLADE_PX:
        return None
    points = np.column_stack([xs, ys]).astype(float)
    axis = _principal_axis(points)
    t = points @ axis
    across = points @ np.array([-axis[1], axis[0]])
    cut = np.median(t)
    low, high = across[t <= cut], across[t > cut]
    if high.size == 0 or low.size == 0:
        return None
    wider_low = (low.max() - low.min()) >= (high.max() - high.min())
    if wider_low:  # low end is the root: axis already points root -> tip
        direction = axis
    else:
        direction = -axis
        t = -t
    return direction, points.mean(axis=0), float(t.min()), float(t.max())


def measure_mask(defect_id: str, mask: np.ndarray, blade: np.ndarray | None = None) -> Measurement:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        raise ValueError("an empty mask has no measurement")
    points = np.column_stack([xs, ys]).astype(float)
    area = float(len(xs))
    length, width = _extent(points, _principal_axis(points))
    length, width = max(length, width), min(length, width)

    blade_ratio: float | None = None
    inside: float | None = None
    position: Position = "unknown"
    position_t: float | None = None
    if blade is not None and blade.any():
        blade_ratio = area / float(blade.sum())
        inside = float(np.logical_and(mask, blade).sum()) / area
        found = blade_axis(blade)
        if found is not None:
            direction, _, t_min, t_max = found
            if t_max > t_min and inside >= MIN_INSIDE_FOR_POSITION:
                projection = float(points.mean(axis=0) @ direction)
                position_t = min(max((projection - t_min) / (t_max - t_min), 0.0), 1.0)
                position = (
                    "root" if position_t < ROOT_END else "tip" if position_t >= TIP_START else "mid"
                )
    return Measurement(
        defect_id=defect_id,
        area_px=area,
        tile_area_ratio=area / float(mask.size),
        blade_area_ratio=blade_ratio,
        length_px=length,
        width_px=width,
        elongation=round(1.0 - width / length, 6),
        inside_blade=inside,
        position=position,
        position_t=position_t,
    )


def measure_detection(detection: TileDetection) -> list[Measurement]:
    return [measure_mask(d.defect.id, d.mask, detection.blade_mask) for d in detection.defects]
