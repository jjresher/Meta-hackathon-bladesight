"""Data build on a synthetic Supervisely tar: conversion, grouped split, manifest, seal, guards."""

from __future__ import annotations

import io
import json
import os
import stat
import tarfile
from pathlib import Path

import pytest

from bladesight.data import HeldoutSealedError, TileLabel, image_path, load_split
from bladesight.data.build import (
    DataBuildError,
    build,
    convert_annotation,
    split_by_photo,
)


def _ann(objects: list[dict[str, object]]) -> bytes:
    return json.dumps(
        {"description": "", "tags": [], "size": {"height": 371, "width": 586}, "objects": objects}
    ).encode()


def _rect(label: str, x1: int, y1: int, x2: int, y2: int) -> dict[str, object]:
    return {
        "classTitle": label,
        "geometryType": "rectangle",
        "points": {"exterior": [[x1, y1], [x2, y2]], "interior": []},
    }


def _add(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    archive.addfile(info, io.BytesIO(payload))


def _make_tar(path: Path, photos: int = 40, tiles_per_photo: int = 3) -> Path:
    with tarfile.open(path, "w") as archive:
        _add(archive, "README.md", b"readme")
        for p in range(photos):
            for t in range(tiles_per_photo):
                tile = f"DJI_{p:04d}_{t:02d}_01"
                objects = []
                if p % 4 == 0 and t == 0:
                    objects = [_rect("damage", 10, 20, 50, 60)]
                elif p % 4 == 1:
                    objects = [_rect("dirt", 5, 5, 9, 9)]
                _add(archive, f"ds/ann/{tile}.png.json", _ann(objects))
                _add(archive, f"ds/img/{tile}.png", f"png-{tile}".encode())
    return path


def test_convert_annotation_orders_corners_and_parses_the_tile_id() -> None:
    tile = convert_annotation("DJI_0702_04_05", json.loads(_ann([_rect("damage", 50, 60, 10, 20)])))
    assert (tile.source_photo, tile.row, tile.col) == ("DJI_0702", 4, 5)
    assert (tile.boxes[0].x1, tile.boxes[0].y1, tile.boxes[0].x2, tile.boxes[0].y2) == (
        10,
        20,
        50,
        60,
    )
    assert tile.has_damage and tile.year is None


@pytest.mark.parametrize(
    "objects",
    [
        [_rect("crack", 0, 0, 1, 1)],
        [{**_rect("damage", 0, 0, 1, 1), "geometryType": "polygon"}],
    ],
)
def test_convert_annotation_rejects_unknown_classes_and_geometry(
    objects: list[dict[str, object]],
) -> None:
    with pytest.raises(DataBuildError):
        convert_annotation("DJI_0001_01_01", json.loads(_ann(objects)))


def test_split_is_grouped_by_photo_stratified_and_deterministic() -> None:
    tiles = [
        TileLabel.model_validate(
            {
                "tile_id": f"DJI_{p:04d}_0{t}_01",
                "source_photo": f"DJI_{p:04d}",
                "row": t,
                "col": 1,
                "width": 586,
                "height": 371,
                "boxes": [{"label": "damage", "x1": 0, "y1": 0, "x2": 1, "y2": 1}]
                if p < 20 and t == 0
                else [],
            }
        )
        for p in range(100)
        for t in range(3)
    ]
    first = split_by_photo(tiles, seed=7)
    assert first == split_by_photo(tiles, seed=7)
    assert first != split_by_photo(tiles, seed=8)
    heldout = [p for p, s in first.items() if s == "heldout"]
    assert len([p for p in heldout if int(p[4:]) < 20]) == 3  # 15% of the 20 damaged photos
    assert len([p for p in heldout if int(p[4:]) >= 20]) == 12  # 15% of the 80 clean ones


def test_build_writes_splits_manifest_and_seals_heldout(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("bladesight.data.build.MIN_HELDOUT_LABELED", 1)
    archive = _make_tar(tmp_path / "ds.tar")
    data = tmp_path / "data"
    result = build(archive, data, seed=1)

    dev = load_split("dev", data)
    assert result.counts["dev"]["tiles"] == len(dev)
    assert result.counts["dev"]["tiles"] + result.counts["heldout"]["tiles"] == 120
    assert image_path(dev[0], "dev", data).read_bytes() == f"png-{dev[0].tile_id}".encode()
    assert result.manifest_lines[-1].endswith("  heldout/labels.jsonl")
    assert len(result.manifest_lines) == result.counts["heldout"]["tiles"] + 1
    assert stat.S_IMODE((data / "heldout").stat().st_mode) == 0
    dev_photos = {t.source_photo for t in dev}
    held_photos = {line.split("/")[-1][:8] for line in result.manifest_lines[:-1]}
    assert dev_photos.isdisjoint(held_photos)

    again = build(archive, data, seed=1)  # a rebuild unseals, rewrites and reseals
    assert again.manifest_lines == result.manifest_lines
    assert again.summary["manifest_sha256"] == result.summary["manifest_sha256"]
    (data / "heldout").chmod(0o700)  # let pytest clean up tmp_path


def test_build_refuses_too_small_a_heldout(tmp_path: Path) -> None:
    archive = _make_tar(tmp_path / "ds.tar")
    with pytest.raises(DataBuildError, match="fewer than 300"):
        build(archive, tmp_path / "data", seed=1)
    (tmp_path / "data" / "heldout").chmod(0o700)


def test_build_rejects_path_traversal_members(tmp_path: Path) -> None:
    archive = tmp_path / "evil.tar"
    with tarfile.open(archive, "w") as tar:
        _add(tar, "ds/img/../../evil.png", b"x")
        _add(tar, "ds/img/..", b"x")
    with pytest.raises(DataBuildError, match="unexpected file"):
        build(archive, tmp_path / "data")
    assert not (tmp_path / "evil.png").exists()


def test_heldout_is_refused_without_the_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ALLOW_HELDOUT", raising=False)
    with pytest.raises(HeldoutSealedError):
        load_split("heldout", tmp_path)
    with pytest.raises(HeldoutSealedError):
        image_path("DJI_0001_01_01", "heldout", tmp_path)


def test_image_path_rejects_unexpected_ids(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        image_path("../../etc/passwd", "dev", tmp_path)
    assert os.environ.get("ALLOW_HELDOUT") != "1"
