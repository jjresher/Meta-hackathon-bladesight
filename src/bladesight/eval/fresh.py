"""The fresh evaluation set of issue #22: dev tiles no earlier work has touched, and its run guard.

The dev sample of the detection evaluation (`runner.sample_tiles`, seed 7, 300 tiles) is the set
we tuned on; the v2 detector is chosen on it too. To compare v1 and v2 without that bias, this
module draws ~300 *other* dev tiles whose source photos (`DJI_xxxx`) appear in none of:

- the seed-7 dev sample (300 tiles);
- the SAM spike of #3 (`detect.spike.select_tiles`, seed 3; the first 25 damaged and 25 clean
  tiles of its order are excluded, a superset of every n the spike scripts accept);
- the severity gold set (`eval/gold/severity.csv`);
- the synthetic farm (`replay/layout.json`);
- any `DJI_xxxx` id written in a committed text file (docs, eval, replay, tests, web fixtures),
  a conservative catch-all for photos shown in evidence or the UI.

The draw is stratified like the dev sample (two thirds labeled tiles, one third clean) with its
own seed. The manifest (`eval/fresh_v2_manifest.sha256`) lists the sha256 of every tile file;
`eval/preregistration_v2.md` records the manifest's own hash.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import random
import re
import statistics
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ..data import TileLabel, image_path
from ..detect.spike import select_tiles as spike_select
from .heldout import git_sha, sha256_of
from .matching import iou, match
from .metrics import (
    PRIMARY_IOU,
    Counts,
    TileResult,
    aggregate,
    bootstrap,
    image_level,
    tile_counts,
)
from .runner import sample_tiles

REPO_ROOT = Path(__file__).resolve().parents[3]
FRESH_SEED = 20261122
N_FRESH = 300
MANIFEST = REPO_ROOT / "eval/fresh_v2_manifest.sha256"
PREREGISTRATION = REPO_ROOT / "eval/preregistration_v2.md"
EVIDENCE_STEM = "eval_fresh_v2"
EVIDENCE = REPO_ROOT / f"docs/evidence/{EVIDENCE_STEM}.md"
GOLD = REPO_ROOT / "eval/gold/severity.csv"
LAYOUT = REPO_ROOT / "replay/layout.json"
SPIKE_MAX = 25
_PHOTO = re.compile(r"DJI_\d{4}")
_SCAN_SUFFIXES = {".md", ".json", ".jsonl", ".csv", ".py", ".ts", ".tsx", ".txt", ".html"}
_SCAN_SKIP = (
    "eval/fresh_v2_manifest.sha256",
    "eval/preregistration_v2.md",
    "eval/heldout_",
    "docs/evidence/eval_fresh_v2",
)


def photo_of(tile_id: str) -> str:
    return TileLabel.parse_tile_id(tile_id)[0]


def committed_photo_ids(root: Path = REPO_ROOT) -> set[str]:
    """Every `DJI_xxxx` written in a git-tracked text file (except this set's own files)."""
    listed = subprocess.run(
        ["git", "ls-files"], capture_output=True, text=True, cwd=root, check=True
    ).stdout.splitlines()
    found: set[str] = set()
    for name in listed:
        if Path(name).suffix not in _SCAN_SUFFIXES or name.startswith(_SCAN_SKIP):
            continue
        try:
            found |= set(_PHOTO.findall((root / name).read_text(encoding="utf-8")))
        except (OSError, UnicodeDecodeError):
            continue
    return found


def excluded_photos(tiles: list[TileLabel], root: Path = REPO_ROOT) -> dict[str, set[str]]:
    """Source photos to keep out of the fresh set, by reason."""
    reasons: dict[str, set[str]] = {
        "dev_sample_seed7": {photo_of(t.tile_id) for t in sample_tiles(tiles, 300)},
        "spike_seed3": {photo_of(t.tile_id) for t in spike_select(tiles, SPIKE_MAX, SPIKE_MAX)},
    }
    gold = root / "eval/gold/severity.csv"
    with gold.open(encoding="utf-8") as handle:
        reasons["gold_set"] = {photo_of(row["tile_id"]) for row in csv.DictReader(handle)}
    layout = json.loads((root / "replay/layout.json").read_text(encoding="utf-8"))
    reasons["synthetic_farm"] = {
        photo_of(tile_id)
        for years in layout["turbines"].values()
        for ids in years.values()
        for tile_id in ids
    }
    reasons["committed_files"] = committed_photo_ids(root)
    return reasons


def build_fresh(
    tiles: list[TileLabel], excluded: set[str], n: int = N_FRESH, seed: int = FRESH_SEED
) -> list[TileLabel]:
    """Two thirds labeled, one third clean, from tiles of photos outside `excluded`."""
    allowed = [t for t in tiles if t.source_photo not in excluded]
    chosen = sample_tiles(allowed, n, seed=seed)
    return sorted(chosen, key=lambda t: t.tile_id)


def manifest_text(tiles: list[TileLabel], data_dir: Path) -> str:
    lines = [
        f"{hashlib.sha256(image_path(t, 'dev', data_dir).read_bytes()).hexdigest()}  {t.tile_id}"
        for t in tiles
    ]
    return "\n".join(lines) + "\n"


def read_manifest(path: Path = MANIFEST) -> list[tuple[str, str]]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        digest, _, tile_id = line.partition("  ")
        out.append((digest, tile_id))
    return out


class FreshError(RuntimeError):
    pass


def verify_fresh(tiles: list[TileLabel], data_dir: Path, path: Path = MANIFEST) -> list[TileLabel]:
    """The manifest's tiles, in its order, after checking every file's sha256."""
    by_id = {t.tile_id: t for t in tiles}
    out = []
    for digest, tile_id in read_manifest(path):
        if tile_id not in by_id:
            raise FreshError(f"{tile_id} of {path.name} is not in the dev split")
        actual = hashlib.sha256(image_path(tile_id, "dev", data_dir).read_bytes()).hexdigest()
        if actual != digest:
            raise FreshError(f"{tile_id} does not match {path.name}")
        out.append(by_id[tile_id])
    return out


def evidence_path(detector: str, out_dir: Path) -> Path:
    return out_dir / f"{EVIDENCE_STEM}_{detector}.json"


# ---------------------------------------------------------------------------------------------
# The single v1-vs-v2 run (preregistration_v2.md)

DETECTORS = ("v1", "v2")
FA_MARGIN = 0.05  # v2's clean-tile false-alarm rate may exceed v1's by at most 5 points
GUARDED_PATHS = (
    "src",
    "pyproject.toml",
    "uv.lock",
    "eval/preregistration_v2.md",
    "eval/fresh_v2_manifest.sha256",
)
RERUN_ENV = "ALLOW_FRESH_RERUN"
DEV_TABLE_LINK = (
    "## How v2 was chosen\n\nOn the 300-tile seed-7 dev sample only, from cached model answers "
    "(0 USD): see [eval_fresh_v2_dev.md](eval_fresh_v2_dev.md)."
)
BOOT_N = 1000
BOOT_SEED = 20261029


def false_alarm_rate(results: Sequence[TileResult], label: str = "damage") -> float:
    return float(image_level(results, label)["clean_false_alarm_rate"])


def paired_differences(
    first: Sequence[TileResult],
    second: Sequence[TileResult],
    n_boot: int = BOOT_N,
    seed: int = BOOT_SEED,
) -> dict[str, dict[str, float]]:
    """Bootstrap 95% intervals of second - first (damage F1 at IoU 0.3, clean false-alarm rate).

    Paired: the same resampled tiles for both detectors; stratified like `metrics.bootstrap`
    (labeled and clean tiles resampled separately).
    """
    if [r.tile_id for r in first] != [r.tile_id for r in second]:
        raise ValueError("paired results must cover the same tiles in the same order")
    a = [tile_counts(r, "damage", PRIMARY_IOU) for r in first]
    b = [tile_counts(r, "damage", PRIMARY_IOU) for r in second]

    def alarm(r: TileResult) -> int:
        return int(any(lab == "damage" for lab, _, _ in r.preds))

    fa_a = [alarm(r) for r in first]
    fa_b = [alarm(r) for r in second]
    labeled = [i for i, r in enumerate(first) if r.has_label]
    clean = [i for i, r in enumerate(first) if not r.has_label]
    rng = random.Random(seed)
    f1_diffs: list[float] = []
    fa_diffs: list[float] = []
    for _ in range(n_boot):
        picks = [labeled[rng.randrange(len(labeled))] for _ in labeled] if labeled else []
        picks_clean = [clean[rng.randrange(len(clean))] for _ in clean] if clean else []
        ca, cb = Counts(), Counts()
        for i in picks + picks_clean:
            ca, cb = ca + a[i], cb + b[i]
        f1_diffs.append(cb.f1 - ca.f1)
        if picks_clean:
            fa_diffs.append(
                (sum(fa_b[i] for i in picks_clean) - sum(fa_a[i] for i in picks_clean))
                / len(picks_clean)
            )

    def interval(values: list[float]) -> dict[str, float]:
        if not values:
            return {"low": 0.0, "high": 0.0}
        values = sorted(values)
        n = len(values) - 1
        return {"low": values[int(0.025 * n)], "high": values[int(0.975 * n)]}

    ta, tb = aggregate(first, "damage"), aggregate(second, "damage")
    return {
        "f1_iou30": {"diff": tb.f1 - ta.f1, **interval(f1_diffs)},
        "false_alarm_rate": {
            "diff": false_alarm_rate(second) - false_alarm_rate(first),
            **interval(fa_diffs),
        },
    }


def verdict(v1: Sequence[TileResult], v2: Sequence[TileResult]) -> dict[str, object]:
    """The preregistered rule: higher damage F1 at IoU 0.3, false alarms within +5 points."""
    f1_v1, f1_v2 = aggregate(v1, "damage").f1, aggregate(v2, "damage").f1
    fa_v1, fa_v2 = false_alarm_rate(v1), false_alarm_rate(v2)
    f1_ok = f1_v2 > f1_v1
    fa_ok = fa_v2 - fa_v1 <= FA_MARGIN + 1e-12
    return {
        "f1_v1": f1_v1,
        "f1_v2": f1_v2,
        "false_alarm_v1": fa_v1,
        "false_alarm_v2": fa_v2,
        "f1_higher": f1_ok,
        "false_alarms_within_margin": fa_ok,
        "v2_wins": f1_ok and fa_ok,
    }


def dirty_files(root: Path = REPO_ROOT) -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", *GUARDED_PATHS],
        capture_output=True,
        text=True,
        cwd=root,
        check=False,
    )
    if result.returncode != 0:
        return ["(git status failed)"]
    return [line[3:] for line in result.stdout.splitlines()]


def preflight(evidence: Path = EVIDENCE, enforce_clean: bool = True) -> None:
    """Refuse a second run (the evidence exists) and a run on uncommitted code."""
    if evidence.exists() and os.environ.get(RERUN_ENV) != "1":
        raise FreshError(
            f"{evidence} exists: the fresh-set run was already done (once only; "
            f"{RERUN_ENV}=1 forces a rerun, which must be listed as a deviation)"
        )
    if not PREREGISTRATION.exists() or not MANIFEST.exists():
        raise FreshError("eval/preregistration_v2.md and the manifest must be committed first")
    if enforce_clean and (dirty := dirty_files()):
        raise FreshError(f"uncommitted changes in frozen code: {dirty}")


def run_fresh(
    data_dir: Path,
    out_dir: Path,
    provider: str = "meta",
    *,
    enforce: bool = True,
    manifest: Path = MANIFEST,
    dev_table: str = "",
) -> dict[str, object]:
    """v1 then v2, once each, on the manifest's tiles; writes the evidence and returns its JSON.

    The v2 pass reuses v1's model answers from the cache wherever its calls are the same (v2
    only changes post-processing), so it costs nothing extra.
    """
    from ..data import load_split
    from ..meta import MetaSettings, build_client
    from .report import build_report, write_outputs
    from .runner import evaluate_tiles

    evidence = out_dir / f"{EVIDENCE_STEM}.md"
    preflight(evidence, enforce_clean=enforce)
    tiles = verify_fresh(load_split("dev", data_dir), data_dir, manifest)
    settings = MetaSettings.from_env()
    client = build_client(settings, provider=provider)  # type: ignore[arg-type]
    commit = git_sha()
    started = datetime.now(UTC)
    results: dict[str, list[TileResult]] = {}
    costs: dict[str, float] = {}
    calls: dict[str, dict[str, int]] = {}
    for detector in DETECTORS:
        before = len(client.records)
        results[detector] = evaluate_tiles(
            client, settings, tiles, "dev", data_dir, detector=detector
        )
        records = client.records[before:]
        costs[detector] = sum(r.cost_usd for r in records)
        calls[detector] = {
            "live": sum(r.source == "live" for r in records),
            "cache": sum(r.source == "cache" for r in records),
        }
    finished = datetime.now(UTC)
    note = (
        f"Fresh dev set of issue #22 (eval/preregistration_v2.md): {len(tiles)} tiles from "
        f"`eval/fresh_v2_manifest.sha256` (sha256 {sha256_of(manifest)}), every file verified; "
        f"seed {FRESH_SEED}, two thirds labeled, photos disjoint from the tuned dev sample. "
        f"Code commit {commit}; run {started.isoformat(timespec='seconds')} to "
        f"{finished.isoformat(timespec='seconds')}."
    )
    reports = {}
    for detector in DETECTORS:
        stem = f"{EVIDENCE_STEM}_{detector}"
        reports[detector] = build_report(
            "dev",
            results[detector],
            cost_usd=costs[detector],
            evidence_path=f"docs/evidence/{stem}.md",
            sample_note=note,
            detector=detector,
        )
        write_outputs(
            reports[detector],
            results[detector],
            out_dir,
            stem,
            title=f"Detection {detector} on the fresh dev set (#22)",
            command="uv run poe eval --split fresh",
            notes=[note, f"Calls: {calls[detector]}."],
        )
    decision = verdict(results["v1"], results["v2"])
    diffs = paired_differences(results["v1"], results["v2"])
    summary: dict[str, object] = {
        "issue": 22,
        "preregistration_sha256": sha256_of(PREREGISTRATION),
        "manifest_sha256": sha256_of(manifest),
        "commit": commit,
        "started_at": started.isoformat(timespec="seconds"),
        "finished_at": finished.isoformat(timespec="seconds"),
        "provider": provider,
        "n_tiles": len(tiles),
        "cost_usd": costs,
        "calls": calls,
        "metrics": {d: _headline(results[d]) for d in DETECTORS},
        "differences_v2_minus_v1": diffs,
        "verdict": decision,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{EVIDENCE_STEM}.json").write_text(
        json.dumps(summary, indent=1) + "\n", encoding="utf-8"
    )
    evidence.write_text(render_fresh(summary, dev_table), encoding="utf-8")
    return summary


def _headline(results: Sequence[TileResult]) -> dict[str, float]:
    c, c5 = aggregate(results, "damage"), aggregate(results, "damage", 0.5)
    dirt = aggregate(results, "dirt")
    il = image_level(results, "damage")
    boot = bootstrap(results, "damage")
    return {
        "damage_tp": c.tp,
        "damage_fp": c.fp,
        "damage_fn": c.fn,
        "damage_precision": c.precision,
        "damage_recall": c.recall,
        "damage_f1": c.f1,
        "damage_precision_ci_low": boot.precision.low,
        "damage_precision_ci_high": boot.precision.high,
        "damage_recall_ci_low": boot.recall.low,
        "damage_recall_ci_high": boot.recall.high,
        "damage_f1_ci_low": boot.f1.low,
        "damage_f1_ci_high": boot.f1.high,
        "damage_recall_iou50": c5.recall,
        "damage_f1_iou50": c5.f1,
        "dirt_precision": dirt.precision,
        "dirt_recall": dirt.recall,
        "dirt_f1": dirt.f1,
        "image_recall": float(il["image_recall"]),
        "clean_false_alarm_rate": float(il["clean_false_alarm_rate"]),
        "touch_recall": float(il["touch_recall"]),
        "tiles_with_damage": float(il["tiles_with_truth"]),
        "clean_tiles": float(il["clean_tiles"]),
        "damage_truth_boxes": float(il["truth_boxes"]),
    }


def render_fresh(summary: dict[str, Any], dev_table: str = "") -> str:
    m, d, v = summary["metrics"], summary["differences_v2_minus_v1"], summary["verdict"]
    wins = v["v2_wins"]
    rows = [
        ("Damage precision, IoU 0.3 (95% CI)", "damage_precision", True),
        ("Damage recall, IoU 0.3 (95% CI)", "damage_recall", True),
        ("**Damage F1, IoU 0.3** (95% CI)", "damage_f1", True),
        ("Damage recall, IoU 0.5", "damage_recall_iou50", False),
        ("Damage F1, IoU 0.5", "damage_f1_iou50", False),
        ("Dirt F1, IoU 0.3", "dirt_f1", False),
        ("Image-level damage recall", "image_recall", False),
        ("**False-alarm rate, tiles with no box**", "clean_false_alarm_rate", False),
        ("Truth boxes touched by any prediction", "touch_recall", False),
    ]

    def cell(det: str, key: str, ci: bool) -> str:
        value = f"{m[det][key]:.3f}"
        if ci:
            value += f" ({m[det][key + '_ci_low']:.3f}-{m[det][key + '_ci_high']:.3f})"
        return value

    counts = {
        det: f"TP {m[det]['damage_tp']:.0f}, FP {m[det]['damage_fp']:.0f}, FN "
        f"{m[det]['damage_fn']:.0f}"
        for det in DETECTORS
    }
    lines = [
        "# Detection v1 vs v2 on a fresh dev set (issue #22)",
        "",
        f"Command: `BLADESIGHT_MODE=live uv run poe eval --split fresh`. Commit "
        f"`{summary['commit']}`. Run {summary['started_at']} to {summary['finished_at']} "
        f"(provider `{summary['provider']}`). Preregistration `eval/preregistration_v2.md` "
        f"sha256 `{summary['preregistration_sha256']}`; manifest "
        f"`eval/fresh_v2_manifest.sha256` sha256 `{summary['manifest_sha256']}`.",
        "",
        f"Tiles: {summary['n_tiles']} fresh dev tiles ({m['v1']['tiles_with_damage']:.0f} with "
        f"damage boxes, {m['v1']['clean_tiles']:.0f} with no box, "
        f"{m['v1']['damage_truth_boxes']:.0f} damage boxes), from source photos that share "
        "nothing with the dev sample v2 was tuned on. Unweighted. Each detector ran once.",
        "",
        f"## Verdict: **v2 {'wins' if wins else 'loses'}** (preregistered criterion)",
        "",
        f"- (a) damage F1 at IoU 0.3: v1 {v['f1_v1']:.3f}, v2 {v['f1_v2']:.3f} -> "
        f"{'higher' if v['f1_higher'] else 'not higher'};",
        f"- (b) false-alarm rate on tiles with no box: v1 {v['false_alarm_v1']:.3f}, v2 "
        f"{v['false_alarm_v2']:.3f} -> "
        f"{'within' if v['false_alarms_within_margin'] else 'more than'} +0.05 of v1.",
        "",
        "Paired bootstrap of v2 - v1 (same resampled tiles, labeled and clean tiles resampled "
        f"separately, {BOOT_N} resamples, seed {BOOT_SEED}; reported, not part of the "
        "criterion): damage F1 at IoU 0.3 "
        f"{d['f1_iou30']['diff']:+.3f} (95% CI {d['f1_iou30']['low']:+.3f} to "
        f"{d['f1_iou30']['high']:+.3f}); false-alarm rate {d['false_alarm_rate']['diff']:+.3f} "
        f"(95% CI {d['false_alarm_rate']['low']:+.3f} to {d['false_alarm_rate']['high']:+.3f}). "
        "Tiles of one photo are correlated, so the intervals are probably a little too narrow.",
        "",
        "" if wins else "This is a negative result: the pipeline default stays v1.",
        "",
        "## Both detectors on the fresh set",
        "",
        "| Metric | v1 | v2 |",
        "|---|---|---|",
        *[f"| {name} | {cell('v1', key, ci)} | {cell('v2', key, ci)} |" for name, key, ci in rows],
        f"| Damage counts, IoU 0.3 | {counts['v1']} | {counts['v2']} |",
        f"| Cost USD (calls) | {summary['cost_usd']['v1']:.4f} ({summary['calls']['v1']}) | "
        f"{summary['cost_usd']['v2']:.4f} ({summary['calls']['v2']}) |",
        "",
        "Full reports (sweep, error gallery): "
        "[v1](eval_fresh_v2_v1.md), [v2](eval_fresh_v2_v2.md). Cost: documented prices from the "
        "client's call records, not invoice-checked.",
        "",
        "## What v1 and v2 are",
        "",
        "Same model calls (Muse Spark `detect/v1` proposals, SAM 3.1 box refinement, the "
        "`surface damage` and `crack` concepts, no blade call). They differ only in how masks "
        "become boxes (`bladesight.detect.pipeline.PostConfig`):",
        "",
        "- **v1** (frozen #16 pipeline): masks under 20 px dropped, same-label masks with mask "
        "IoU >= 0.5 merged by union, one box per mask (its tight bounding box).",
        "- **v2**: every mask split into its 8-connected parts; parts under 40 px or under 0.1 "
        "of the mask's largest part dropped; same-label masks with IoU >= 0.5 suppressed "
        "(the lower score is dropped, not unioned); one box per part.",
    ]
    if dev_table:
        lines += ["", dev_table.rstrip()]
    return "\n".join(lines) + "\n"


# The variants measured on the dev sample (seed 7) to choose v2; names are stable labels.
DEV_VARIANTS: dict[str, dict[str, Any]] = {
    "v1 (frozen #16)": {},
    "v1 merge=nms": {"merge": "nms"},
    "v1 drop masks > 2000 px": {"max_area_px": 2000},
    "split parts": {"split_components": True},
    "split parts, merge=nms": {"split_components": True, "merge": "nms"},
    "split, min 40 px, nms": {"split_components": True, "min_area_px": 40, "merge": "nms"},
    "split, min 80 px, nms": {"split_components": True, "min_area_px": 80, "merge": "nms"},
    "split, min 120 px, nms": {"split_components": True, "min_area_px": 120, "merge": "nms"},
    "split, min 40 px, share 0.1, nms (= v2)": {
        "split_components": True,
        "min_area_px": 40,
        "min_part_share": 0.1,
        "merge": "nms",
    },
    "split, min 40 px, max 3 parts, nms": {
        "split_components": True,
        "min_area_px": 40,
        "max_parts": 3,
        "merge": "nms",
    },
    "split after 3 px erosion, min 40 px, nms": {
        "split_components": True,
        "min_area_px": 40,
        "erode_px": 3,
        "merge": "nms",
    },
    "split, drop parts > 2000 px": {"split_components": True, "max_area_px": 2000},
}


def oversize_ratios(results: Sequence[TileResult], label: str = "damage") -> list[float]:
    """Area of the best-overlapping prediction / truth area, for overlapped but unmatched truths."""
    ratios = []
    for r in results:
        preds = [(s, b) for lab, s, b in r.preds if lab == label]
        truths = [b for lab, b in r.truths if lab == label]
        m = match([b for _, b in preds], [s for s, _ in preds], truths, PRIMARY_IOU)
        for t in m.unmatched_truths:
            truth = truths[t]
            best = max(((iou(b, truth), b) for _, b in preds), default=(0.0, None))
            if best[0] > 0 and best[1] is not None:
                b = best[1]
                area = (truth[2] - truth[0]) * (truth[3] - truth[1])
                ratios.append((b[2] - b[0]) * (b[3] - b[1]) / area)
    return ratios


def dev_variant_table(data_dir: Path, out: Path) -> str:
    """Every `DEV_VARIANTS` entry on the seed-7 dev sample, from the cache (replay mode, 0 USD)."""
    import io

    from PIL import Image

    from ..data import load_split
    from ..detect.pipeline import PostConfig, collect_candidates, finalize, postprocess
    from ..meta import ImagePart, MetaSettings, build_client

    settings = MetaSettings.from_env()
    if settings.mode != "replay":
        raise FreshError("the dev variant table runs from the cache only (BLADESIGHT_MODE=replay)")
    client = build_client(settings)
    tiles = sample_tiles(load_split("dev", data_dir), 300)
    raw = []
    for tile in tiles:
        png = image_path(tile, "dev", data_dir).read_bytes()
        with Image.open(io.BytesIO(png)) as opened:
            width, height = opened.size
        image = ImagePart(data=png, mime_type="image/png")
        cands, _ = collect_candidates(client, settings, image, width, height)
        raw.append((tile, cands))
    rows = [
        "| Variant | TP | FP | FN | Precision | Recall | **F1** | Recall IoU 0.5 | "
        "False-alarm rate | Image recall | Touched |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    ratios: list[float] = []
    for name, options in DEV_VARIANTS.items():
        config = PostConfig(**options)
        results = []
        for tile, cands in raw:
            dets = finalize(postprocess(cands, tile.tile_id, config), tile.tile_id)
            results.append(
                TileResult(
                    tile_id=tile.tile_id,
                    truths=[(b.label, (b.x1, b.y1, b.x2, b.y2)) for b in tile.boxes],
                    preds=[
                        (
                            x.defect.label,
                            x.defect.score,
                            (
                                x.defect.bbox.x1,
                                x.defect.bbox.y1,
                                x.defect.bbox.x2,
                                x.defect.bbox.y2,
                            ),
                        )
                        for x in dets
                    ],
                )
            )
        if not ratios:  # the first variant is v1
            ratios = oversize_ratios(results)
        c, c5, il = (
            aggregate(results, "damage"),
            aggregate(results, "damage", 0.5),
            image_level(results, "damage"),
        )
        rows.append(
            f"| {name} | {c.tp:.0f} | {c.fp:.0f} | {c.fn:.0f} | {c.precision:.3f} | "
            f"{c.recall:.3f} | {c.f1:.3f} | {c5.recall:.3f} | "
            f"{il['clean_false_alarm_rate']:.3f} | {il['image_recall']:.3f} | "
            f"{il['touch_recall']:.3f} |"
        )
    live = sum(r.source == "live" for r in client.records)
    cached = sum(r.source == "cache" for r in client.records)
    text = "\n".join(
        [
            "# Choosing detection v2 on the dev sample (issue #22)",
            "",
            "Command: `BLADESIGHT_MODE=replay uv run python -m bladesight.eval.fresh --dev-table`. "
            f"Commit `{git_sha()}`. The 300-tile seed-7 dev sample of `eval_dev.md` (the tiles "
            "v1 was tuned on; 176 with damage boxes, 100 with no box), damage class, IoU 0.3, "
            f"unweighted. Model answers replayed from the cache: {live} live and {cached} cached "
            "calls, 0 USD. The first row reproduces `eval_dev.md` (TP 137, FP 237, FN 482).",
            "",
            "Hypothesis (from `eval_heldout.md`): boxes are too large. On this dev sample, for "
            f"the {len(ratios)} damage truth boxes that some v1 box overlaps without matching "
            "them, the best-overlapping v1 box is a median "
            f"{statistics.median(ratios) if ratios else 0:.1f} times the truth box's area "
            f"({sum(r > 1 for r in ratios) / max(len(ratios), 1):.0%} are larger).",
            "",
            *rows,
            "",
            "Reading: splitting masks into connected parts lifts recall (scattered concept masks "
            "become several boxes), and the fragments it creates are mostly tiny, so a 40 px "
            "floor and a share-of-largest-part floor recover precision; larger floors start to "
            "cost image-level recall, and an area ceiling or erosion hurts. The differences "
            "between the best rows are within noise; v2 was picked as the simplest row near "
            "the top that keeps v1's image recall and false-alarm rate.",
            "",
            "Quadrant zoom, checked once on 2026-11-03 (23:43-23:55 UTC-5) and not adopted: Muse "
            "Spark re-proposed boxes on each 2x-upscaled quadrant of the first 20 labeled tiles "
            "of this sample, SAM refined them on the full tile, the concept masks were kept and "
            "the v2 post-processing applied. Damage at IoU 0.3 on those 20 tiles: whole-tile "
            "proposals TP 12, FP 19, FN 37 (F1 0.300); quadrant proposals TP 15, FP 36, FN 34 "
            "(F1 0.300). Same F1 at about 2.5 times the proposal cost (100 live calls, 0.3475 "
            "USD from the client's call records), so zoom stayed out of v2. The check ran from "
            "an ad-hoc script that is not part of the package (its numbers are recorded only "
            "here).",
        ]
    )
    out.write_text(text + "\n", encoding="utf-8")
    return text


def main(argv: list[str] | None = None) -> int:
    """`python -m bladesight.eval.fresh [--write]`: print the exclusions; write the manifest."""
    import argparse

    from ..data import load_split

    parser = argparse.ArgumentParser(prog="python -m bladesight.eval.fresh")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--write", action="store_true", help="write eval/fresh_v2_manifest.sha256")
    parser.add_argument(
        "--dev-table", action="store_true", help="write docs/evidence/eval_fresh_v2_dev.md"
    )
    args = parser.parse_args(argv)
    if args.dev_table:
        dev_variant_table(args.data_dir, EVIDENCE.parent / f"{EVIDENCE_STEM}_dev.md")
        print(f"wrote {EVIDENCE.parent / f'{EVIDENCE_STEM}_dev.md'}")
        return 0
    tiles = load_split("dev", args.data_dir)
    reasons = excluded_photos(tiles)
    excluded = set().union(*reasons.values())
    for reason, photos in reasons.items():
        print(f"{reason}: {len(photos)} photos")
    allowed = [t for t in tiles if t.source_photo not in excluded]
    print(
        f"excluded {len(excluded)} photos; {len(allowed)} dev tiles remain "
        f"({sum(t.has_label for t in allowed)} labeled, "
        f"{len({t.source_photo for t in allowed})} photos)"
    )
    fresh = build_fresh(tiles, excluded)
    damage_boxes = sum(b.label == "damage" for t in fresh for b in t.boxes)
    print(
        f"fresh set: {len(fresh)} tiles, {sum(t.has_label for t in fresh)} labeled, "
        f"{sum(t.has_damage for t in fresh)} with damage, {damage_boxes} damage boxes, "
        f"{len({t.source_photo for t in fresh})} photos, seed {FRESH_SEED}"
    )
    if args.write:
        text = manifest_text(fresh, args.data_dir)
        MANIFEST.write_text(text, encoding="utf-8")
        print(f"wrote {MANIFEST} sha256 {hashlib.sha256(text.encode()).hexdigest()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
