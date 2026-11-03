"""Gold-set selection and the CSV labelling store (no server, no images)."""

from __future__ import annotations

from pathlib import Path

import pytest

from bladesight.data import TileLabel
from bladesight.eval.gold import (
    FIELDS,
    page,
    read_rows,
    select_gold,
    set_severity,
    write_rows,
)


def _tiles() -> list[TileLabel]:
    tiles = []
    for p in range(200):
        side = 8 + (p % 20) * 3  # box sizes from 64 to 1000+ px^2
        tiles.append(
            TileLabel.model_validate(
                {
                    "tile_id": f"DJI_{p:04d}_01_01",
                    "source_photo": f"DJI_{p:04d}",
                    "row": 1,
                    "col": 1,
                    "width": 586,
                    "height": 371,
                    "boxes": [
                        {"label": "damage", "x1": 10, "y1": 10, "x2": 10 + side, "y2": 10 + side},
                        {"label": "dirt", "x1": 100, "y1": 100, "x2": 200, "y2": 200},
                    ],
                }
            )
        )
    return tiles


def test_select_gold_is_reproducible_blind_and_spread_over_sizes() -> None:
    rows = select_gold(_tiles())
    assert rows == select_gold(_tiles()) and len(rows) == 40
    assert all(r["label"] == "damage" and r["severity"] == "" for r in rows)
    assert len({r["tile_id"][:8] for r in rows}) == 40  # one box per source photo
    sizes = sorted((float(r["x2"]) - float(r["x1"])) for r in rows)
    assert sizes[0] < 20 and sizes[-1] > 40  # small and large crops both present
    assert list(rows[0]) == FIELDS and rows == sorted(rows, key=lambda r: r["crop_id"])


def test_csv_roundtrip_and_labelling(tmp_path: Path) -> None:
    path = tmp_path / "severity.csv"
    write_rows(select_gold(_tiles()), path)
    first = read_rows(path)[0]["crop_id"]
    set_severity(path, first, "4", "open crack")
    assert read_rows(path)[0]["severity"] == "4" and read_rows(path)[0]["note"] == "open crack"
    set_severity(path, first, "0")
    assert read_rows(path)[0]["severity"] == "0"  # unreadable
    set_severity(path, first, "")
    assert read_rows(path)[0]["severity"] == ""
    assert len(read_rows(path)) == 40


@pytest.mark.parametrize("bad", ["6", "x", "-1", "10"])
def test_bad_values_and_unknown_ids_are_rejected(tmp_path: Path, bad: str) -> None:
    path = tmp_path / "severity.csv"
    write_rows(select_gold(_tiles()), path)
    with pytest.raises(ValueError):
        set_severity(path, read_rows(path)[0]["crop_id"], bad)
    with pytest.raises(ValueError):
        set_severity(path, "DJI_9999_01_01#0", "3")


def test_the_page_never_mentions_model_grades() -> None:
    html = page().decode()
    assert "model" in html.lower()  # only to say the grades are hidden
    assert "/api/label" in html and "Backspace" in html
