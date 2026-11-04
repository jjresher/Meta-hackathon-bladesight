"""Detection metrics against the dataset boxes: precision, recall, F1, image-level recall,
a lenient "touch" criterion, a threshold sweep and a bootstrap over tiles.

Why more than IoU: 73% of the truth boxes are under 400 px^2 (docs/evidence/spike.md), so box-level
IoU is harsh for any detector. We report IoU 0.3 (primary), 0.5 and 0.1, image-level recall, and
the share of truth boxes touched by a prediction.
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass, field

from .matching import Box, match

PRIMARY_IOU = 0.3
IOU_LEVELS = (0.1, 0.3, 0.5)
LABELS = ("damage", "dirt")


@dataclass
class TileResult:
    tile_id: str
    truths: list[tuple[str, Box]]  # (label, box)
    preds: list[tuple[str, float, Box]]  # (label, score, box)
    # Sampling weight: a clean tile sampled from N clean tiles stands for N / n of them, so
    # false positives and per-image rates can be scaled back to the full split.
    weight: float = 1.0

    @property
    def has_label(self) -> bool:
        return bool(self.truths)


@dataclass(frozen=True)
class Counts:
    tp: float = 0
    fp: float = 0
    fn: float = 0

    def __add__(self, other: Counts) -> Counts:
        return Counts(self.tp + other.tp, self.fp + other.fp, self.fn + other.fn)

    @property
    def precision(self) -> float:
        return self.tp / (self.tp + self.fp) if self.tp + self.fp else 0.0

    @property
    def recall(self) -> float:
        return self.tp / (self.tp + self.fn) if self.tp + self.fn else 0.0

    @property
    def f1(self) -> float:
        p, r = self.precision, self.recall
        return 2 * p * r / (p + r) if p + r else 0.0


def _select(
    result: TileResult, label: str, min_score: float
) -> tuple[list[Box], list[float], list[Box]]:
    preds = [(s, b) for lab, s, b in result.preds if lab == label and s >= min_score]
    return (
        [b for _, b in preds],
        [s for s, _ in preds],
        [b for lab, b in result.truths if lab == label],
    )


def tile_counts(
    result: TileResult, label: str, iou: float = PRIMARY_IOU, min_score: float = 0.0
) -> Counts:
    boxes, scores, truths = _select(result, label, min_score)
    m = match(boxes, scores, truths, iou)
    w = result.weight
    return Counts(m.tp * w, m.fp * w, m.fn * w)


def aggregate(
    results: Sequence[TileResult], label: str, iou: float = PRIMARY_IOU, min_score: float = 0.0
) -> Counts:
    total = Counts()
    for result in results:
        total = total + tile_counts(result, label, iou, min_score)
    return total


def _overlaps(a: Box, b: Box) -> bool:
    return not (a[2] <= b[0] or a[0] >= b[2] or a[3] <= b[1] or a[1] >= b[3])


def image_level(
    results: Sequence[TileResult], label: str = "damage", min_score: float = 0.0
) -> dict[str, float]:
    """Recall over tiles that have the label, false-alarm rate over tiles with no label at all."""
    with_truth = [r for r in results if any(lab == label for lab, _ in r.truths)]
    clean = [r for r in results if not r.has_label]

    def hit(r: TileResult) -> bool:
        return any(lab == label and s >= min_score for lab, s, _ in r.preds)

    touched = total = 0
    for r in with_truth:
        boxes, _, truths = _select(r, label, min_score)
        for t in truths:
            total += 1
            touched += any(_overlaps(b, t) for b in boxes)
    return {
        "tiles_with_truth": len(with_truth),
        "image_recall": sum(hit(r) for r in with_truth) / len(with_truth) if with_truth else 0.0,
        "clean_tiles": len(clean),
        "clean_false_alarm_rate": sum(hit(r) for r in clean) / len(clean) if clean else 0.0,
        "truth_boxes": total,
        "touch_recall": touched / total if total else 0.0,
    }


def sweep(
    results: Sequence[TileResult],
    label: str = "damage",
    thresholds: Sequence[float] = (0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9),
    iou: float = PRIMARY_IOU,
) -> list[dict[str, float]]:
    """Missed defects vs false alarms as the score threshold moves (per sampling-weighted image)."""
    total_weight = sum(r.weight for r in results)
    points = []
    for threshold in thresholds:
        c = aggregate(results, label, iou, threshold)
        points.append(
            {
                "threshold": threshold,
                "recall": c.recall,
                "precision": c.precision,
                "false_alarms_per_image": c.fp / total_weight if total_weight else 0.0,
                "image_recall": image_level(results, label, threshold)["image_recall"],
            }
        )
    return points


@dataclass
class Interval:
    low: float
    high: float


@dataclass
class Bootstrap:
    precision: Interval
    recall: Interval
    f1: Interval
    n_boot: int = 1000
    seed: int = 20261029
    resamples: list[Counts] = field(default_factory=list, repr=False)


def bootstrap(
    results: Sequence[TileResult],
    label: str,
    iou: float = PRIMARY_IOU,
    n_boot: int = 1000,
    seed: int = 20261029,
) -> Bootstrap:
    """95% percentile intervals, resampling tiles with replacement (counts are summed per tile)."""
    per_tile = [tile_counts(r, label, iou) for r in results]
    rng = random.Random(seed)
    # Resample inside each stratum (tiles with boxes / tiles with none) so the sample design is
    # kept: a plain bootstrap could draw a different number of labeled tiles than the run had.
    strata: dict[bool, list[Counts]] = {True: [], False: []}
    for r, c in zip(results, per_tile, strict=True):
        strata[r.has_label].append(c)
    samples = []
    for _ in range(n_boot):
        total = Counts()
        for group in strata.values():
            for _ in group:
                total = total + group[rng.randrange(len(group))]
        samples.append(total)

    def interval(values: list[float]) -> Interval:
        values = sorted(values)
        return Interval(
            values[int(0.025 * (len(values) - 1))], values[int(0.975 * (len(values) - 1))]
        )

    if not per_tile:
        zero = Interval(0.0, 0.0)
        return Bootstrap(zero, zero, zero, n_boot, seed)
    return Bootstrap(
        interval([c.precision for c in samples]),
        interval([c.recall for c in samples]),
        interval([c.f1 for c in samples]),
        n_boot,
        seed,
    )


def error_gallery(
    results: Sequence[TileResult], label: str = "damage", iou: float = PRIMARY_IOU
) -> dict[str, list[str]]:
    """Tile ids per cause (ids only: crops are never committed).

    - `fn_no_prediction`: truth boxes of this label and no prediction of it on the tile;
    - `fn_prediction_elsewhere`: predictions exist but none matched a truth box;
    - `fn_overlap_too_low`: a prediction touches the truth box but IoU is below the threshold;
    - `fp_clean_tile`: a prediction on a tile with no label at all;
    - `fp_unmatched`: an unmatched prediction on a tile that has labels.
    """
    causes: dict[str, list[str]] = {
        "fn_no_prediction": [],
        "fn_prediction_elsewhere": [],
        "fn_overlap_too_low": [],
        "fp_clean_tile": [],
        "fp_unmatched": [],
    }
    for r in results:
        boxes, scores, truths = _select(r, label, 0.0)
        m = match(boxes, scores, truths, iou)
        if m.fn:
            missed = [truths[i] for i in m.unmatched_truths]
            if not boxes:
                causes["fn_no_prediction"].append(r.tile_id)
            elif any(_overlaps(b, t) for t in missed for b in boxes):
                causes["fn_overlap_too_low"].append(r.tile_id)
            else:
                causes["fn_prediction_elsewhere"].append(r.tile_id)
        if m.fp:
            causes["fp_unmatched" if truths or r.has_label else "fp_clean_tile"].append(r.tile_id)
    return causes
