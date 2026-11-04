"""Box IoU and one-to-one greedy matching of predictions to the dataset boxes (best score first)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

Box = tuple[float, float, float, float]  # x1, y1, x2, y2 (x2/y2 exclusive)


def iou(a: Box, b: Box) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    if inter == 0:
        return 0.0
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return inter / (area_a + area_b - inter)


@dataclass(frozen=True)
class MatchResult:
    tp: int
    fp: int
    fn: int
    pairs: list[tuple[int, int, float]]  # (prediction index, truth index, iou)
    unmatched_predictions: list[int]
    unmatched_truths: list[int]


def match(
    predictions: Sequence[Box],
    scores: Sequence[float],
    truths: Sequence[Box],
    iou_threshold: float = 0.3,
) -> MatchResult:
    """Each prediction (by descending score) takes the free truth with the highest IoU."""
    if len(predictions) != len(scores):
        raise ValueError("one score per prediction")
    order = sorted(range(len(predictions)), key=lambda i: -scores[i])
    free = set(range(len(truths)))
    pairs: list[tuple[int, int, float]] = []
    unmatched: list[int] = []
    for p in order:
        best, best_iou = -1, 0.0
        for t in free:
            value = iou(predictions[p], truths[t])
            if value > best_iou:
                best, best_iou = t, value
        if best >= 0 and best_iou >= iou_threshold:
            free.discard(best)
            pairs.append((p, best, best_iou))
        else:
            unmatched.append(p)
    return MatchResult(
        tp=len(pairs),
        fp=len(unmatched),
        fn=len(free),
        pairs=pairs,
        unmatched_predictions=sorted(unmatched),
        unmatched_truths=sorted(free),
    )
