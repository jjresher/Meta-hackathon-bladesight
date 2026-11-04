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
import re
import subprocess
from pathlib import Path

from ..data import TileLabel, image_path
from ..detect.spike import select_tiles as spike_select
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
_SCAN_SKIP = ("eval/fresh_v2_manifest.sha256", "eval/preregistration_v2.md", "eval/heldout_")


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


def main(argv: list[str] | None = None) -> int:
    """`python -m bladesight.eval.fresh [--write]`: print the exclusions; write the manifest."""
    import argparse

    from ..data import load_split

    parser = argparse.ArgumentParser(prog="python -m bladesight.eval.fresh")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--write", action="store_true", help="write eval/fresh_v2_manifest.sha256")
    args = parser.parse_args(argv)
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
