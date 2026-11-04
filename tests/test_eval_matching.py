"""IoU and greedy one-to-one matching on toy boxes."""

from __future__ import annotations

import pytest

from bladesight.eval.matching import iou, match


def test_iou_known_values() -> None:
    assert iou((0, 0, 10, 10), (0, 0, 10, 10)) == 1.0
    assert iou((0, 0, 10, 10), (10, 0, 20, 10)) == 0.0
    assert iou((0, 0, 10, 10), (5, 0, 15, 10)) == pytest.approx(50 / 150)


def test_each_truth_is_matched_at_most_once_highest_score_first() -> None:
    truths = [(0.0, 0.0, 10.0, 10.0)]
    preds = [(0.0, 0.0, 10.0, 9.0), (0.0, 0.0, 10.0, 10.0)]
    result = match(preds, [0.4, 0.9], truths, 0.3)
    assert (result.tp, result.fp, result.fn) == (1, 1, 0)
    assert result.pairs[0][0] == 1  # the higher-scoring box wins the truth
    assert result.unmatched_predictions == [0]


def test_threshold_and_empty_cases() -> None:
    truths = [(0.0, 0.0, 10.0, 10.0)]
    far = [(8.0, 8.0, 18.0, 18.0)]
    assert match(far, [0.9], truths, 0.3).fn == 1
    assert match([], [], truths).fn == 1
    assert match(far, [0.9], []).fp == 1


def test_scores_must_align_with_predictions() -> None:
    with pytest.raises(ValueError):
        match([(0.0, 0.0, 1.0, 1.0)], [], [])
