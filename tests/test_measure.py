"""Measurement on synthetic masks with known answers."""

from __future__ import annotations

import numpy as np
import pytest

from bladesight.measure.measure import blade_axis, measure_mask

H, W = 120, 300


def _rect(x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
    mask = np.zeros((H, W), dtype=bool)
    mask[y1:y2, x1:x2] = True
    return mask


def _blade() -> np.ndarray:
    """A horizontal trapezoid: tall (80 px) at the left, short (20 px) at the right."""
    mask = np.zeros((H, W), dtype=bool)
    for x in range(W):
        half = int(40 - 30 * x / W)
        mask[60 - half : 60 + half, x] = True
    return mask


def test_area_extent_and_elongation_of_a_bar() -> None:
    m = measure_mask("d", _rect(10, 10, 60, 20))  # 50 x 10
    assert m.area_px == 500
    assert m.length_px == pytest.approx(50, abs=1)
    assert m.width_px == pytest.approx(10, abs=1)
    assert m.elongation == pytest.approx(0.8, abs=0.03)
    assert m.tile_area_ratio == pytest.approx(500 / (H * W))
    assert (m.blade_area_ratio, m.inside_blade, m.position_t) == (None, None, None)
    assert m.position == "unknown" and m.units == "pixels"


def test_a_square_patch_is_not_elongated_and_a_diagonal_crack_is() -> None:
    assert measure_mask("d", _rect(10, 10, 40, 40)).elongation < 0.1
    crack = np.zeros((H, W), dtype=bool)
    for i in range(80):
        crack[10 + i // 2, 10 + i] = True
    m = measure_mask("d", crack)
    assert m.elongation > 0.9 and m.length_px > 80


def test_a_single_pixel_has_length_and_width_one() -> None:
    m = measure_mask("d", _rect(5, 5, 6, 6))
    assert (m.length_px, m.width_px, m.elongation) == (1, 1, 0)


def test_empty_mask_is_rejected() -> None:
    with pytest.raises(ValueError):
        measure_mask("d", np.zeros((H, W), dtype=bool))


def test_blade_axis_points_from_the_wide_root_to_the_narrow_tip() -> None:
    found = blade_axis(_blade())
    assert found is not None
    direction, _, _, _ = found
    assert direction[0] > 0.9  # root on the left (wide), tip on the right


@pytest.mark.parametrize(("x1", "expected"), [(5, "root"), (140, "mid"), (270, "tip")])
def test_position_along_the_blade(x1: int, expected: str) -> None:
    m = measure_mask("d", _rect(x1, 55, x1 + 12, 65), _blade())
    assert m.position == expected
    assert m.inside_blade == 1.0
    assert m.blade_area_ratio == pytest.approx(120 / _blade().sum())


def test_position_t_is_monotonic_and_a_defect_off_the_blade_is_reported() -> None:
    near = measure_mask("d", _rect(5, 55, 15, 65), _blade())
    far = measure_mask("d", _rect(250, 55, 260, 65), _blade())
    assert near.position_t is not None and far.position_t is not None
    assert near.position_t < far.position_t
    off = measure_mask("d", _rect(100, 0, 110, 8), _blade())  # above the trapezoid at x=100
    assert off.inside_blade == 0.0


def test_a_tiny_blade_mask_gives_no_position() -> None:
    m = measure_mask("d", _rect(5, 5, 15, 15), _rect(0, 0, 5, 5))
    assert m.position == "unknown" and m.blade_area_ratio is not None


def test_mirrored_blade_puts_the_root_on_the_right() -> None:
    blade = _blade()[:, ::-1]  # wide end on the right
    found = blade_axis(blade)
    assert found is not None and found[0][0] < -0.9  # axis now points right -> left
    assert measure_mask("d", _rect(280, 55, 292, 65), blade).position == "root"
    assert measure_mask("d", _rect(5, 55, 17, 65), blade).position == "tip"


def test_a_vertical_blade_works_the_same() -> None:
    blade = _blade().T  # 300 x 120 -> tall, wide end at the top
    height, width = blade.shape
    top = np.zeros((height, width), dtype=bool)
    top[5:17, 55:65] = True
    m = measure_mask("d", top, blade)
    assert m.position == "root"


def test_a_defect_off_the_blade_has_no_position() -> None:
    m = measure_mask("d", _rect(100, 0, 110, 8), _blade())
    assert m.inside_blade == 0.0 and m.position == "unknown" and m.position_t is None
