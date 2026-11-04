"""Run the detector over a tile sample and compare it with the dataset boxes."""

from __future__ import annotations

import random
from collections.abc import Mapping
from pathlib import Path

from ..data import Split, TileLabel, image_path, load_split
from ..detect.pipeline import detect_tile
from ..meta import MetaClient, MetaSettings
from .metrics import TileResult

SAMPLE_SEED = 7


def sample_tiles(
    tiles: list[TileLabel], n: int, labeled_share: float = 2 / 3, seed: int = SAMPLE_SEED
) -> list[TileLabel]:
    """A reproducible sample: `labeled_share` of it from tiles that have boxes, the rest clean.

    The dev split is about 22% labeled; this over-samples labeled tiles so recall is measurable,
    and the report says so (precision and false alarms on clean tiles are reported separately).
    """
    rng = random.Random(seed)
    labeled = sorted((t for t in tiles if t.has_label), key=lambda t: t.tile_id)
    clean = sorted((t for t in tiles if not t.has_label), key=lambda t: t.tile_id)
    rng.shuffle(labeled)
    rng.shuffle(clean)
    n_labeled = min(len(labeled), round(n * labeled_share))
    return labeled[:n_labeled] + clean[: min(len(clean), n - n_labeled)]


def evaluate_tiles(
    client: MetaClient,
    settings: MetaSettings,
    tiles: list[TileLabel],
    split: Split,
    data_dir: Path,
    *,
    with_blade: bool = False,
    weights: Mapping[str, float] | None = None,
    detector: str = "v1",
) -> list[TileResult]:
    results = []
    for tile in tiles:
        png = image_path(tile, split, data_dir).read_bytes()
        detection = detect_tile(
            client, settings, tile.tile_id, png, with_blade=with_blade, detector=detector
        )
        results.append(
            TileResult(
                tile_id=tile.tile_id,
                truths=[(b.label, (b.x1, b.y1, b.x2, b.y2)) for b in tile.boxes],
                preds=[
                    (
                        d.defect.label,
                        d.defect.score,
                        (d.defect.bbox.x1, d.defect.bbox.y1, d.defect.bbox.x2, d.defect.bbox.y2),
                    )
                    for d in detection.defects
                ],
                weight=(weights or {}).get(tile.tile_id, 1.0),
            )
        )
    return results


def load_tiles(split: Split, data_dir: Path) -> list[TileLabel]:
    """Refuses the held-out split unless ALLOW_HELDOUT=1 (issue #16 only)."""
    try:
        return load_split(split, data_dir)
    except FileNotFoundError as error:
        raise SystemExit(f"{error}: run `uv run poe data` first (see DATA.md)") from None
