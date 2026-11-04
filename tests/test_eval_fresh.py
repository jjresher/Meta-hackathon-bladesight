"""The fresh v1-vs-v2 set (#22): construction, manifest, criterion, single run. Stub only, 0 USD."""

from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from bladesight.data import TileLabel
from bladesight.detect.pipeline import (
    V1,
    V2,
    Candidate,
    PostConfig,
    _parts,
    finalize,
    postprocess,
)
from bladesight.eval import fresh
from bladesight.eval.__main__ import main as eval_main
from bladesight.eval.metrics import TileResult


def _tile(i: int, photo: int, labeled: bool) -> TileLabel:
    boxes = [{"label": "damage", "x1": 10, "y1": 10, "x2": 30, "y2": 30}] if labeled else []
    return TileLabel.model_validate(
        {
            "tile_id": f"DJI_{photo:04d}_01_{i:02d}",
            "source_photo": f"DJI_{photo:04d}",
            "row": 1,
            "col": i,
            "width": 64,
            "height": 48,
            "boxes": boxes,
        }
    )


def _tiles() -> list[TileLabel]:
    return [_tile(i, p, labeled=i % 3 == 0) for p in range(10) for i in range(1, 13)]


def test_fresh_set_avoids_excluded_photos_and_keeps_the_two_thirds_design() -> None:
    tiles = _tiles()
    chosen = fresh.build_fresh(tiles, {"DJI_0000", "DJI_0001"}, n=30, seed=5)
    assert len(chosen) == 30
    assert not {t.source_photo for t in chosen} & {"DJI_0000", "DJI_0001"}
    assert sum(t.has_label for t in chosen) == 20
    assert chosen == fresh.build_fresh(tiles, {"DJI_0000", "DJI_0001"}, n=30, seed=5)


def test_the_committed_fresh_set_avoids_gold_and_farm_photos_and_matches_the_prereg() -> None:
    ids = [tile_id for _, tile_id in fresh.read_manifest()]
    assert len(ids) == len(set(ids)) == 300
    photos = {fresh.photo_of(t) for t in ids}
    gold = fresh.GOLD.read_text(encoding="utf-8")
    layout = fresh.LAYOUT.read_text(encoding="utf-8")
    assert not any(photo in gold or photo in layout for photo in photos)
    digest = hashlib.sha256(fresh.MANIFEST.read_bytes()).hexdigest()
    assert digest in fresh.PREREGISTRATION.read_text(encoding="utf-8")


def _write_dev(root: Path, tiles: list[TileLabel]) -> Path:
    img = root / "dev" / "img"
    img.mkdir(parents=True)
    for n, tile in enumerate(tiles):
        Image.new("RGB", (64, 48), (n * 7 % 255, 90, 90)).save(img / f"{tile.tile_id}.png")
    (root / "dev" / "labels.jsonl").write_text(
        "".join(t.model_dump_json() + "\n" for t in tiles), encoding="utf-8"
    )
    manifest = root / "manifest.sha256"
    manifest.write_text(fresh.manifest_text(tiles, root), encoding="utf-8")
    return manifest


def test_manifest_verification_detects_a_changed_tile(tmp_path: Path) -> None:
    tiles = _tiles()[:6]
    manifest = _write_dev(tmp_path, tiles)
    assert fresh.verify_fresh(tiles, tmp_path, manifest) == tiles
    (tmp_path / "dev" / "img" / f"{tiles[2].tile_id}.png").write_bytes(b"tampered")
    with pytest.raises(fresh.FreshError):
        fresh.verify_fresh(tiles, tmp_path, manifest)


def _result(tile_id: str, truths: int, preds: int) -> TileResult:
    box = (0.0, 0.0, 10.0, 10.0)
    return TileResult(tile_id, [("damage", box)] * truths, [("damage", 0.9, box)] * preds)


def test_verdict_needs_higher_f1_and_false_alarms_within_five_points() -> None:
    labeled_v1 = [_result(f"L{i}", 1, i % 2) for i in range(20)]  # half found
    labeled_v2 = [_result(f"L{i}", 1, 1) for i in range(20)]  # all found
    clean_v1 = [_result(f"C{i}", 0, int(i < 2)) for i in range(20)]  # 0.10 false alarms
    ok = [_result(f"C{i}", 0, int(i < 3)) for i in range(20)]  # 0.15: +5 points, allowed
    bad = [_result(f"C{i}", 0, int(i < 4)) for i in range(20)]  # 0.20: +10 points
    assert fresh.verdict(labeled_v1 + clean_v1, labeled_v2 + ok)["v2_wins"] is True
    lost = fresh.verdict(labeled_v1 + clean_v1, labeled_v2 + bad)
    assert lost["f1_higher"] is True and lost["v2_wins"] is False
    same = fresh.verdict(labeled_v1 + clean_v1, labeled_v1 + clean_v1)
    assert same["v2_wins"] is False  # a tie is not a win


def test_paired_bootstrap_of_identical_detectors_is_zero() -> None:
    results = [_result(f"L{i}", 1, i % 2) for i in range(10)] + [
        _result(f"C{i}", 0, i % 3 == 0) for i in range(10)
    ]
    diffs = fresh.paired_differences(results, results, n_boot=50)
    assert diffs["f1_iou30"] == {"diff": 0.0, "low": 0.0, "high": 0.0}
    assert diffs["false_alarm_rate"] == {"diff": 0.0, "low": 0.0, "high": 0.0}
    with pytest.raises(ValueError):
        fresh.paired_differences(results, results[::-1])


def _blobs() -> np.ndarray:
    mask = np.zeros((48, 64), dtype=bool)
    mask[2:12, 2:12] = True  # 100 px
    mask[30:38, 40:48] = True  # 64 px
    mask[44:46, 0:3] = True  # 6 px fragment
    return mask


def test_v2_splits_masks_into_parts_and_drops_tiny_fragments() -> None:
    assert [int(p.sum()) for p in _parts(_blobs())] == [100, 64, 6]
    cand = Candidate(_blobs(), "damage", "surface damage", "concept", 0.8)
    v1 = postprocess([cand], "t", V1)
    assert len(v1) == 1 and v1[0].defect.bbox.x2 == 48  # one box spanning all three parts
    v2 = postprocess([cand], "t", V2)
    assert sorted(int(d.mask.sum()) for d in v2) == [64, 100]
    capped = postprocess([cand], "t", PostConfig(split_components=True, max_parts=1))
    assert [int(d.mask.sum()) for d in capped] == [100]


def test_v2_suppresses_overlaps_instead_of_unioning_them() -> None:
    a = np.zeros((48, 64), dtype=bool)
    a[0:20, 0:20] = True
    b = np.zeros((48, 64), dtype=bool)
    b[0:20, 2:22] = True
    cands = [
        Candidate(a, "damage", "crack", "concept", 0.9),
        Candidate(b, "damage", "crack", "concept", 0.5),
    ]
    assert finalize(postprocess(cands, "t", V1), "t")[0].defect.bbox.x2 == 22  # union
    kept = finalize(postprocess(cands, "t", V2), "t")
    assert len(kept) == 1 and kept[0].defect.bbox.x2 == 20  # the higher score only


def test_fresh_run_writes_both_detectors_once_and_refuses_a_second_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BLADESIGHT_MODE", "replay")
    tiles = _tiles()[:9]
    manifest = _write_dev(tmp_path / "data", tiles)
    out = tmp_path / "evidence"
    summary = fresh.run_fresh(tmp_path / "data", out, "stub", enforce=False, manifest=manifest)
    assert summary["n_tiles"] == 9 and set(summary["metrics"]) == {"v1", "v2"}  # type: ignore[arg-type]
    text = (out / "eval_fresh_v2.md").read_text(encoding="utf-8")
    assert "Verdict" in text and "Paired bootstrap" in text and str(summary["commit"]) in text
    for name in ("eval_fresh_v2.json", "eval_fresh_v2_v1.md", "eval_fresh_v2_v2.json"):
        assert (out / name).exists()
    with pytest.raises(fresh.FreshError):
        fresh.run_fresh(tmp_path / "data", out, "stub", enforce=False, manifest=manifest)
    monkeypatch.setenv(fresh.RERUN_ENV, "1")
    fresh.run_fresh(tmp_path / "data", out, "stub", enforce=False, manifest=manifest)


def test_a_dev_run_may_not_write_the_fresh_evidence() -> None:
    with pytest.raises(SystemExit):
        eval_main(["--split", "dev", "--stem", "eval_fresh_v2", "--provider", "stub"])


def test_a_dev_run_with_detector_v2_needs_its_own_stem() -> None:
    for argv in (
        ["--split", "dev", "--detector", "v2", "--provider", "stub"],
        ["--split", "dev", "--detector", "v2", "--stem", "eval_dev", "--provider", "stub"],
        ["--split", "heldout", "--detector", "v2"],
    ):
        with pytest.raises(SystemExit):
            eval_main(argv)


def test_the_manifest_writer_refuses_to_overwrite_the_frozen_set() -> None:
    assert fresh.MANIFEST.exists()
    assert fresh.main(["--write"]) == 2


def test_a_v2_dev_run_records_its_detector(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BLADESIGHT_MODE", "replay")
    tiles = _tiles()[:6]
    _write_dev(tmp_path / "data", tiles)
    out = tmp_path / "ev"
    argv = [
        "--split",
        "dev",
        "--n",
        "6",
        "--provider",
        "stub",
        "--data-dir",
        str(tmp_path / "data"),
    ]
    assert eval_main([*argv, "--detector", "v2", "--stem", "dev_v2", "--out", str(out)]) == 0
    assert "detect-post/v2" in (out / "dev_v2.json").read_text(encoding="utf-8")
    assert eval_main([*argv, "--stem", "dev_v1", "--out", str(out)]) == 0
    assert "postprocess" not in (out / "dev_v1.json").read_text(encoding="utf-8")
