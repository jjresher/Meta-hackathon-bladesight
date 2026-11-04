"""Issue #3 spike: do SAM 3.1 text concepts find the dataset's damage and dirt boxes?

`python -m bladesight.detect.spike --data-dir <data> --n-damage 20 --n-clean 5` samples dev tiles
with a fixed seed, asks SAM for each concept (cached, so a re-run is free), and writes per-tile and
per-concept recall / false alarms against the dataset boxes. Dev tiles only (AGENTS.md rule 3).
Real calls follow the `meta-api-check` skill: run with `BLADESIGHT_MODE=live`.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import defaultdict
from pathlib import Path

from ..data import TileLabel, image_path, load_split
from ..eval.matching import Box, match
from ..meta import ImagePart, MetaClient, MetaError, MetaSettings, SegmentMask, build_client

DEFAULT_CONCEPTS = [
    "crack",
    "leading edge erosion",
    "surface damage",
    "dirt",
    "wind turbine blade",
]
# Which dataset class each concept is scored against ("blade" is context, not scored).
CONCEPT_CLASS = {
    "crack": "damage",
    "leading edge erosion": "damage",
    "surface damage": "damage",
    "lightning damage": "damage",
    "dirt": "dirt",
}
IOU_LEVELS = (0.1, 0.3, 0.5)
SEED = 3


def select_tiles(
    tiles: list[TileLabel], n_damage: int, n_clean: int, seed: int = SEED
) -> list[TileLabel]:
    rng = random.Random(seed)
    damaged = sorted((t for t in tiles if t.has_damage), key=lambda t: t.tile_id)
    clean = sorted((t for t in tiles if not t.has_label), key=lambda t: t.tile_id)
    rng.shuffle(damaged)  # shuffle then slice: the first n tiles are the same for every n
    rng.shuffle(clean)
    return damaged[:n_damage] + clean[:n_clean]


def run_concepts(
    client: MetaClient, model: str, data_dir: Path, tiles: list[TileLabel], concepts: list[str]
) -> dict[str, dict[str, list[SegmentMask]]]:
    """tile_id -> concept -> masks at the lowest threshold (0.0: sweeps are free afterwards)."""
    out: dict[str, dict[str, list[SegmentMask]]] = {}
    for tile in tiles:
        image = ImagePart(
            data=image_path(tile, "dev", data_dir).read_bytes(), mime_type="image/png"
        )
        out[tile.tile_id] = {}
        for concept in concepts:
            result = client.segment_concepts(model, image, [concept], threshold=0.0)
            out[tile.tile_id][concept] = result.masks
    return out


def _boxes(masks: list[SegmentMask], threshold: float) -> tuple[list[Box], list[float]]:
    kept = [m for m in masks if m.score is None or m.score >= threshold]
    return [tuple(map(float, m.box)) for m in kept], [m.score or 0.0 for m in kept]  # type: ignore[misc]


def evaluate(
    tiles: list[TileLabel],
    found: dict[str, dict[str, list[SegmentMask]]],
    threshold: float,
) -> dict[str, object]:
    """Recall of dataset boxes per class at several IoU levels, plus false alarms on clean tiles."""
    report: dict[str, object] = {"threshold": threshold, "per_concept": {}, "per_class": {}}
    per_concept: dict[str, dict[str, float]] = {}
    for concept in {c for per_tile in found.values() for c in per_tile}:
        label = CONCEPT_CLASS.get(concept)
        if label is None:
            continue
        stats: dict[str, float] = defaultdict(float)
        for tile in tiles:
            truths = [(b.x1, b.y1, b.x2, b.y2) for b in tile.boxes if b.label == label]
            preds, scores = _boxes(found[tile.tile_id][concept], threshold)
            stats["predictions"] += len(preds)
            stats["truths"] += len(truths)
            if not tile.has_label:
                stats["clean_tiles"] += 1
                stats["clean_tiles_with_prediction"] += bool(preds)
            for level in IOU_LEVELS:
                result = match(preds, scores, truths, level)
                stats[f"tp@{level}"] += result.tp
        per_concept[concept] = dict(stats)
    report["per_concept"] = per_concept

    per_class: dict[str, dict[str, float]] = {}
    for label in ("damage", "dirt"):
        concepts = [c for c, cls in CONCEPT_CLASS.items() if cls == label and c in per_concept]
        stats = defaultdict(float)
        image_hit = image_total = 0
        for tile in tiles:
            truths = [(b.x1, b.y1, b.x2, b.y2) for b in tile.boxes if b.label == label]
            preds: list[Box] = []
            scores: list[float] = []
            for concept in concepts:
                p, s = _boxes(found[tile.tile_id][concept], threshold)
                preds += p
                scores += s
            stats["predictions"] += len(preds)
            stats["truths"] += len(truths)
            for level in IOU_LEVELS:
                result = match(preds, scores, truths, level)
                stats[f"tp@{level}"] += result.tp
                stats[f"fp@{level}"] += result.fp
            if truths:
                image_total += 1
                image_hit += bool(preds)
            elif not tile.has_label:
                stats["clean_tiles"] += 1
                stats["clean_tiles_with_prediction"] += bool(preds)
        stats["images_with_truth"] = image_total
        stats["images_with_any_prediction"] = image_hit
        per_class[label] = dict(stats)
    report["per_class"] = per_class
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bladesight.detect.spike")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--n-damage", type=int, default=20)
    parser.add_argument("--n-clean", type=int, default=5)
    parser.add_argument("--concept", action="append")
    parser.add_argument("--out", type=Path, default=Path("outputs/spike"))
    parser.add_argument("--thresholds", type=float, nargs="+", default=[0.3, 0.5, 0.7])
    args = parser.parse_args(argv)
    if args.n_damage + args.n_clean > 25:
        parser.error("the spike is limited to 25 tiles (sprint rule)")

    settings = MetaSettings.from_env()
    client = build_client(settings, provider="meta")
    concepts = args.concept or DEFAULT_CONCEPTS
    tiles = select_tiles(load_split("dev", args.data_dir), args.n_damage, args.n_clean)
    print(f"tiles={len(tiles)} concepts={concepts} mode={settings.mode}")
    try:
        found = run_concepts(client, settings.sam_model, args.data_dir, tiles, concepts)
    except MetaError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    finally:
        live = sum(r.source == "live" for r in client.records)
        print(
            f"calls: live={live} cached={sum(r.source == 'cache' for r in client.records)} "
            f"cost_usd={sum(r.cost_usd for r in client.records):.4f} "
            f"all_runs_usd={client.spend.spent_usd:.4f} limit_usd={client.spend.limit_usd:.2f}"
        )
    args.out.mkdir(parents=True, exist_ok=True)
    raw = {
        t: {
            c: [{"score": m.score, "box": m.box, "area": m.area} for m in ms] for c, ms in d.items()
        }
        for t, d in found.items()
    }
    (args.out / "raw.json").write_text(json.dumps(raw, indent=1), encoding="utf-8")
    reports = {str(th): evaluate(tiles, found, th) for th in args.thresholds}
    (args.out / "report.json").write_text(json.dumps(reports, indent=1), encoding="utf-8")
    print(json.dumps(reports, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
