"""Internal label format: one `TileLabel` per 586x371 tile, boxes in tile pixels."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field, model_validator

Split = Literal["dev", "heldout"]
LabelClass = Literal["damage", "dirt"]

# DJI_0004_01_04: source photo DJI_0004, tile row 01, column 04 of that photo.
TILE_ID = re.compile(r"^(DJI_\d{4})_(\d{2})_(\d{2})$")


class Box(BaseModel):
    """Axis-aligned box in tile pixels, as given by the annotators (Supervisely rectangle)."""

    label: LabelClass
    x1: float
    y1: float
    x2: float
    y2: float

    @model_validator(mode="after")
    def _ordered(self) -> Box:
        if self.x2 < self.x1 or self.y2 < self.y1:
            raise ValueError("box corners are not ordered")
        return self

    @property
    def area(self) -> float:
        return (self.x2 - self.x1) * (self.y2 - self.y1)


class TileLabel(BaseModel):
    tile_id: str
    source_photo: str
    row: int
    col: int
    width: int
    height: int
    # The YOLO derivative does not say which inspection (2017 or 2018) a tile comes from, and the
    # original DTU file names (DJI_xxxx) do not either: year stays unknown (docs/decision_ledger.md).
    year: int | None = None
    boxes: list[Box] = Field(default_factory=list)

    @property
    def has_damage(self) -> bool:
        return any(b.label == "damage" for b in self.boxes)

    @property
    def has_label(self) -> bool:
        return bool(self.boxes)

    @classmethod
    def parse_tile_id(cls, tile_id: str) -> tuple[str, int, int]:
        match = TILE_ID.match(tile_id)
        if match is None:
            raise ValueError(f"unexpected tile id {tile_id!r}")
        return match.group(1), int(match.group(2)), int(match.group(3))
