"""Metric functions on toy boxes with known answers, the report, and the held-out guard."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from bladesight.contracts import SweepPoint
from bladesight.data import TileLabel
from bladesight.eval.__main__ import main as eval_main
from bladesight.eval.metrics import (
    Counts,
    TileResult,
    aggregate,
    bootstrap,
    error_gallery,
    image_level,
    sweep,
    tile_counts,
)
from bladesight.eval.report import build_report, render_markdown, sweep_svg
from bladesight.eval.runner import sample_tiles

A = (0.0, 0.0, 10.0, 10.0)
B = (50.0, 50.0, 60.0, 60.0)


def _tile(tid: str, truths: list[tuple[str, tuple[float, ...]]], preds: list[tuple]) -> TileResult:
    return TileResult(tid, truths, preds)  # type: ignore[arg-type]


def _results() -> list[TileResult]:
    return [
        _tile("hit", [("damage", A)], [("damage", 0.9, A)]),  # tp
        _tile("miss", [("damage", B)], []),  # fn, no prediction
        _tile("far", [("damage", A)], [("damage", 0.8, B)]),  # fn + fp, prediction elsewhere
        _tile(
            "loose", [("damage", A)], [("damage", 0.7, (5.0, 0.0, 25.0, 10.0))]
        ),  # touches, IoU low
        _tile("clean_fp", [], [("damage", 0.6, A)]),  # fp on a clean tile
        _tile("clean_ok", [], []),
        _tile("dirt", [("dirt", A)], [("dirt", 0.9, A)]),
    ]


def test_counts_precision_recall_f1() -> None:
    c = aggregate(_results(), "damage")
    assert (c.tp, c.fp, c.fn) == (1, 3, 3)
    assert c.precision == pytest.approx(0.25) and c.recall == pytest.approx(0.25)
    assert c.f1 == pytest.approx(0.25)
    assert Counts().precision == 0.0 and Counts().f1 == 0.0
    d = aggregate(_results(), "dirt")
    assert (d.tp, d.fp, d.fn) == (1, 0, 0)


def test_iou_levels_change_the_match() -> None:
    loose = _tile("loose", [("damage", A)], [("damage", 0.7, (5.0, 0.0, 25.0, 10.0))])
    assert tile_counts(loose, "damage", 0.3).tp == 0  # IoU 1/3 < ... see below
    assert tile_counts(loose, "damage", 0.1).tp == 1


def test_min_score_drops_predictions() -> None:
    assert aggregate(_results(), "damage", min_score=0.85).fp == 0
    assert aggregate(_results(), "damage", min_score=0.85).tp == 1


def test_image_level_and_lenient_touch() -> None:
    m = image_level(_results(), "damage")
    assert m["tiles_with_truth"] == 4 and m["clean_tiles"] == 2
    assert m["image_recall"] == pytest.approx(3 / 4)  # miss has no prediction
    assert m["clean_false_alarm_rate"] == pytest.approx(1 / 2)
    assert m["touch_recall"] == pytest.approx(2 / 4)  # hit and loose touch their truth box


def test_sweep_trades_recall_for_false_alarms() -> None:
    points = sweep(_results(), thresholds=(0.0, 0.85))
    assert points[0]["false_alarms_per_image"] > points[1]["false_alarms_per_image"]
    assert points[0]["recall"] >= points[1]["recall"]


def test_error_gallery_causes() -> None:
    g = error_gallery(_results(), "damage")
    assert g["fn_no_prediction"] == ["miss"]
    assert g["fn_prediction_elsewhere"] == ["far"]
    assert g["fn_overlap_too_low"] == ["loose"]
    assert g["fp_clean_tile"] == ["clean_fp"]
    assert "far" in g["fp_unmatched"]


def test_bootstrap_is_reproducible_and_brackets_the_estimate() -> None:
    results = _results() * 5
    one = bootstrap(results, "damage", n_boot=200, seed=1)
    two = bootstrap(results, "damage", n_boot=200, seed=1)
    assert one.recall == two.recall and one.recall.low <= 0.25 <= one.recall.high
    assert bootstrap([], "damage").recall.high == 0.0


def test_report_markdown_and_svg() -> None:
    report = build_report(
        "dev", _results(), cost_usd=0.0, evidence_path="docs/evidence/x.md", n_boot=50
    )
    assert report.n_images == 7 and report.classes[0].precision_ci is not None
    text = render_markdown(report, _results(), title="T", command="cmd")
    assert "Error gallery" in text and "Image-level recall" in text and "fn_no_prediction" in text
    svg = sweep_svg(
        [SweepPoint(threshold=0.5, recall=0.5, precision=0.5, false_alarms_per_image=1)]
    )
    assert svg.startswith("<svg") and "<path" in svg


def test_sample_is_reproducible_and_oversamples_labeled_tiles() -> None:
    def tile(i: int, labeled: bool) -> TileLabel:
        boxes = [{"label": "damage", "x1": 0, "y1": 0, "x2": 5, "y2": 5}] if labeled else []
        return TileLabel.model_validate(
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

    tiles = [tile(i, i % 5 == 0) for i in range(400)]
    first, second = sample_tiles(tiles, 30), sample_tiles(tiles, 30)
    assert [t.tile_id for t in first] == [t.tile_id for t in second] and len(first) == 30
    assert sum(t.has_label for t in first) == 20


def test_heldout_is_refused_by_the_cli_without_the_flag(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.delenv("ALLOW_HELDOUT", raising=False)
    assert eval_main(["--split", "heldout", "--data-dir", str(tmp_path)]) == 2
    assert "sealed" in capsys.readouterr().err


def test_dev_cli_with_the_stub_writes_evidence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import io

    from PIL import Image

    dev = tmp_path / "dev"
    (dev / "img").mkdir(parents=True)
    lines = []
    for i in range(6):
        tid = f"DJI_{i:04d}_01_01"
        buffer = io.BytesIO()
        Image.new("RGB", (200, 120), (90, 90, 90)).save(buffer, format="PNG")
        (dev / "img" / f"{tid}.png").write_bytes(buffer.getvalue())
        boxes = [{"label": "damage", "x1": 50, "y1": 30, "x2": 150, "y2": 90}] if i < 3 else []
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
    (dev / "labels.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    monkeypatch.setenv("BLADESIGHT_MODE", "replay")
    code = eval_main(
        [
            "--provider", "stub", "--n", "6", "--data-dir", str(tmp_path),
            "--out", str(tmp_path / "out"), "--stem", "eval_smoke",
        ]
    )  # fmt: skip
    assert code == 0
    assert (tmp_path / "out" / "eval_smoke.md").exists()
    assert (tmp_path / "out" / "eval_smoke_sweep.svg").read_text().startswith("<svg")
