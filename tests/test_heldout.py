"""The held-out run machinery on synthetic data: sampling, weights, manifest, refusals, seal."""

from __future__ import annotations

import hashlib
import io
import json
import stat
from pathlib import Path

import pytest
from PIL import Image

from bladesight.data import TileLabel
from bladesight.data.build import seal
from bladesight.eval import heldout
from bladesight.eval.__main__ import main as eval_main
from bladesight.eval.metrics import TileResult, aggregate, bootstrap, image_level, sweep

A = (0.0, 0.0, 10.0, 10.0)


def _tiles(n_labeled: int = 20, n_clean: int = 50) -> list[TileLabel]:
    out = []
    for i in range(n_labeled + n_clean):
        boxes = [{"label": "damage", "x1": 0, "y1": 0, "x2": 10, "y2": 10}] if i < n_labeled else []
        out.append(
            TileLabel.model_validate(
                {
                    "tile_id": f"DJI_{i:04d}_01_01",
                    "source_photo": f"DJI_{i:04d}",
                    "row": 1,
                    "col": 1,
                    "width": 586,
                    "height": 371,
                    "boxes": boxes,
                }
            )
        )
    return out


def test_sampling_keeps_every_labeled_tile_and_weights_the_clean_ones(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(heldout, "N_CLEAN", 10)
    tiles, weights = heldout.sample_heldout(_tiles())
    again, _ = heldout.sample_heldout(_tiles())
    assert [t.tile_id for t in tiles] == [t.tile_id for t in again]
    assert sum(t.has_label for t in tiles) == 20 and len(tiles) == 30
    assert all(weights[t.tile_id] == 1.0 for t in tiles if t.has_label)
    assert all(weights[t.tile_id] == 5.0 for t in tiles if not t.has_label)  # 50 clean / 10 drawn


def test_weights_scale_false_positives_and_rates_but_not_recall() -> None:
    labeled = TileResult("a", [("damage", A)], [("damage", 0.9, A)])  # tp
    clean_fp = TileResult("b", [], [("damage", 0.8, A)], weight=5.0)  # fp standing for 5 tiles
    clean_ok = TileResult("c", [], [], weight=5.0)
    results = [labeled, clean_fp, clean_ok]
    c = aggregate(results, "damage")
    assert (c.tp, c.fp, c.fn) == (1, 5, 0)
    assert c.precision == pytest.approx(1 / 6) and c.recall == 1.0
    assert image_level(results)["clean_false_alarm_rate"] == pytest.approx(0.5)
    assert sweep(results, thresholds=(0.0,))[0]["false_alarms_per_image"] == pytest.approx(5 / 11)


def test_stratified_bootstrap_keeps_the_design_and_is_reproducible() -> None:
    results = [TileResult(f"l{i}", [("damage", A)], [("damage", 0.9, A)]) for i in range(10)]
    results += [TileResult(f"c{i}", [], [("damage", 0.7, A)], weight=4.0) for i in range(5)]
    one = bootstrap(results, "damage", n_boot=100, seed=3)
    assert one.recall.low == one.recall.high == 1.0  # every labeled tile is a hit
    assert one.precision.low > 0 and one == bootstrap(results, "damage", n_boot=100, seed=3)


def _write_heldout(root: Path) -> None:
    ho = root / "heldout"
    (ho / "img").mkdir(parents=True)
    lines, manifest = [], []
    for i in range(4):
        tid = f"DJI_{i:04d}_01_01"
        buffer = io.BytesIO()
        Image.new("RGB", (200, 120), (90, 90, 90)).save(buffer, format="PNG")
        (ho / "img" / f"{tid}.png").write_bytes(buffer.getvalue())
        manifest.append(f"{hashlib.sha256(buffer.getvalue()).hexdigest()}  heldout/img/{tid}.png")
        boxes = [{"label": "damage", "x1": 50, "y1": 30, "x2": 150, "y2": 90}] if i < 2 else []
        lines.append(
            json.dumps(
                {
                    "tile_id": tid,
                    "source_photo": f"DJI_{i:04d}",
                    "row": 1,
                    "col": 1,
                    "width": 200,
                    "height": 120,
                    "year": None,
                    "boxes": boxes,
                }
            )
        )
    text = "\n".join(lines) + "\n"
    (ho / "labels.jsonl").write_text(text, encoding="utf-8")
    manifest.append(f"{hashlib.sha256(text.encode()).hexdigest()}  heldout/labels.jsonl")
    (root / "manifest.sha256").write_text("\n".join(manifest) + "\n", encoding="utf-8")


def test_manifest_verification_detects_a_changed_file(tmp_path: Path) -> None:
    _write_heldout(tmp_path)
    assert heldout.verify_manifest(tmp_path, tmp_path / "manifest.sha256") == 5
    (tmp_path / "heldout" / "img" / "DJI_0000_01_01.png").write_bytes(b"tampered")
    with pytest.raises(heldout.HeldoutError):
        heldout.verify_manifest(tmp_path, tmp_path / "manifest.sha256")


def test_cli_refuses_without_the_flag_and_without_a_preregistration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ALLOW_HELDOUT", raising=False)
    assert eval_main(["--split", "heldout", "--data-dir", str(tmp_path / "data")]) == 2
    monkeypatch.setenv("ALLOW_HELDOUT", "1")
    assert eval_main(["--split", "heldout", "--data-dir", str(tmp_path / "data")]) == 2
    assert "preregistration" in capsys.readouterr().err


def test_cli_single_run_reseals_and_writes_the_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ALLOW_HELDOUT", "1")
    monkeypatch.setenv("BLADESIGHT_MODE", "replay")
    monkeypatch.setattr(heldout, "N_CLEAN", 1)
    data = tmp_path / "data"
    _write_heldout(data)
    monkeypatch.setattr("bladesight.eval.heldout.MANIFEST", data / "manifest.sha256")
    monkeypatch.setattr(
        "bladesight.eval.__main__.verify_manifest",
        lambda d: heldout.verify_manifest(d, data / "manifest.sha256"),
    )
    seal(data / "heldout")
    monkeypatch.setattr(heldout, "EVIDENCE", tmp_path / "docs" / "evidence" / "eval_heldout.md")
    (tmp_path / "eval").mkdir()
    (tmp_path / "eval" / "preregistration.md").write_text("frozen\n", encoding="utf-8")
    argv = [
        "--split",
        "heldout",
        "--provider",
        "stub",
        "--data-dir",
        str(data),
        "--out",
        str(tmp_path / "docs" / "evidence"),
    ]
    assert eval_main(argv) == 0
    assert stat.S_IMODE((data / "heldout").stat().st_mode) == 0  # sealed again
    text = (tmp_path / "docs" / "evidence" / "eval_heldout.md").read_text(encoding="utf-8")
    assert "Preregistered sample" in text and "sha256" in text
    assert "Unweighted damage counts at IoU 0.3: TP" in text
    # the evidence file now exists: a second run is refused
    (data / "heldout").chmod(0o700)
    assert eval_main(argv) == 2
    (data / "heldout").chmod(0o700)
