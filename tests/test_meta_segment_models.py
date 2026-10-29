import numpy as np
import pytest

from bladesight.meta import SegmentMask


def test_from_frame_array_crops_to_the_bounding_box_and_round_trips() -> None:
    frame = np.zeros((20, 30), dtype=bool)
    frame[5:9, 10:16] = True
    frame[7, 12] = False

    mask = SegmentMask.from_frame_array("crack", 0.8, frame)

    assert mask.box == (10, 5, 16, 9)
    assert (mask.width, mask.height) == (6, 4)
    assert mask.area == 6 * 4 - 1
    assert (mask.frame_width, mask.frame_height) == (30, 20)
    assert np.array_equal(mask.frame_array(), frame)


def test_an_empty_frame_has_no_box() -> None:
    with pytest.raises(ValueError, match="empty"):
        SegmentMask.from_frame_array("crack", 0.8, np.zeros((4, 4), dtype=bool))


def test_raster_must_match_the_box() -> None:
    with pytest.raises(ValueError, match="does not match"):
        SegmentMask.from_raster("c", 1.0, np.ones((2, 3), dtype=bool), (0, 0, 2, 3))


def test_frame_array_needs_a_known_frame_size() -> None:
    mask = SegmentMask.from_raster("c", None, np.ones((2, 2), dtype=bool), (1, 1, 3, 3))
    assert mask.score is None
    assert mask.area == 4
    with pytest.raises(ValueError, match="frame size"):
        mask.frame_array()
