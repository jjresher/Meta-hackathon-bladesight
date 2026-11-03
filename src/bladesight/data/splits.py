"""Read the dev split; refuse the sealed held-out split unless `ALLOW_HELDOUT=1` (#16 only)."""

from __future__ import annotations

import os
from pathlib import Path

from .models import Split, TileLabel

DATA_DIR = Path("data")
HELDOUT_ENV = "ALLOW_HELDOUT"


class HeldoutSealedError(PermissionError):
    """The held-out split is sealed until issue #16 (AGENTS.md rule 3)."""


def split_dir(split: Split, data_dir: Path = DATA_DIR) -> Path:
    return data_dir / split


def _guard(split: Split) -> None:
    if split == "heldout" and os.environ.get(HELDOUT_ENV) != "1":
        raise HeldoutSealedError(
            "the held-out split is sealed until issue #16 (AGENTS.md rule 3); "
            f"only the preregistered run sets {HELDOUT_ENV}=1"
        )


def load_split(split: Split, data_dir: Path = DATA_DIR) -> list[TileLabel]:
    _guard(split)
    path = split_dir(split, data_dir) / "labels.jsonl"
    with path.open(encoding="utf-8") as handle:
        return [TileLabel.model_validate_json(line) for line in handle if line.strip()]


def image_path(tile: TileLabel | str, split: Split = "dev", data_dir: Path = DATA_DIR) -> Path:
    _guard(split)
    tile_id = tile if isinstance(tile, str) else tile.tile_id
    TileLabel.parse_tile_id(tile_id)  # rejects path tricks such as "../x"
    return split_dir(split, data_dir) / "img" / f"{tile_id}.png"
