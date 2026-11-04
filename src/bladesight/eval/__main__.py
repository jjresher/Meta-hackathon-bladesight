"""`uv run poe eval --split dev --n 300`: detection metrics on a dev sample, written as evidence.

Refuses `--split heldout` unless `ALLOW_HELDOUT=1` (only the single preregistered run of #16).
Real calls follow `meta-api-check` (`BLADESIGHT_MODE=live`, a cap sized for the run); the default
replay mode only reads the cache. `--provider stub` spends nothing (smoke test, not a result).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from ..data import HeldoutSealedError
from ..data.splits import HELDOUT_ENV
from ..meta import MetaError, MetaSettings, build_client
from .heldout import SAMPLE_SEED, HeldoutError, preflight, reseal, sample_heldout, verify_manifest
from .report import build_report, write_outputs
from .runner import evaluate_tiles, load_tiles, sample_tiles


def _git_sha() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bladesight.eval")
    parser.add_argument("--split", choices=["dev", "heldout"], default="dev")
    parser.add_argument("--n", type=int, default=300, help="tiles to evaluate (dev: at most 300)")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("docs/evidence"))
    parser.add_argument("--provider", choices=["meta", "stub"], default="meta")
    parser.add_argument("--stem", help="output file stem (default eval_<split>)")
    parser.add_argument(
        "--cost-usd", type=float, help="cost of the live run when this is a cached re-render"
    )
    args = parser.parse_args(argv)
    if args.split == "dev" and args.n > 300:
        parser.error("the dev evaluation is limited to 300 tiles (sprint rule)")

    heldout = args.split == "heldout"
    prereg_hash = ""
    if heldout:
        if os.environ.get(HELDOUT_ENV) != "1":
            print(
                f"refused: the held-out split is sealed until the preregistered run (#16); "
                f"it needs {HELDOUT_ENV}=1",
                file=sys.stderr,
            )
            return 2
        try:
            prereg_hash = preflight(args.data_dir)
        except HeldoutError as error:
            print(f"refused: {error}", file=sys.stderr)
            return 2
    try:
        try:
            tiles = load_tiles(args.split, args.data_dir)
        except HeldoutSealedError as error:
            print(f"refused: {error}", file=sys.stderr)
            return 2
        weights: dict[str, float] = {}
        if heldout:
            print(f"manifest ok: {verify_manifest(args.data_dir)} held-out files match")
            chosen, weights = sample_heldout(tiles)
        else:
            chosen = sample_tiles(tiles, args.n)
        settings = MetaSettings.from_env()
        client = build_client(settings, provider=args.provider)
        try:
            results = evaluate_tiles(
                client, settings, chosen, args.split, args.data_dir, weights=weights
            )
        except MetaError as error:
            print(f"error: {error}", file=sys.stderr)
            return 1
    except HeldoutError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    finally:
        if heldout:
            reseal(args.data_dir)
    cost = args.cost_usd if args.cost_usd is not None else sum(r.cost_usd for r in client.records)
    stem = args.stem or f"eval_{args.split}"
    if heldout:
        n_clean = sum(not r.has_label for r in results)
        clean_total = round(n_clean * max((r.weight for r in results), default=1.0))
        sample_note = (
            f"Preregistered sample of the held-out split: all {len(results) - n_clean} labeled "
            f"tiles plus {n_clean} of its {clean_total} clean tiles (seed {SAMPLE_SEED}); each "
            f"clean tile weighs {clean_total / max(n_clean, 1):.2f}, so precision, false positives "
            "and false alarms per image are scaled to the whole split. Recall and image-level "
            f"rates are not affected. Preregistration sha256 {prereg_hash}. "
            f"Code commit {_git_sha()}."
        )
    else:
        sample_note = (
            "Dev sample: two thirds of the tiles have dataset boxes, one third none (seeded, "
            "`eval/runner.py`); the dev split is about 22% labeled, so recall is measurable but "
            "per-image false-alarm rates are not those of a real inspection (unweighted)."
        )
    report = build_report(
        args.split,
        results,
        cost_usd=cost,
        evidence_path=f"docs/evidence/{stem}.md",
        sample_note=sample_note,
    )
    md, svg = write_outputs(
        report,
        results,
        args.out,
        stem,
        title=f"Detection evaluation ({args.split})",
        command=f"uv run poe eval --split {args.split}" + ("" if heldout else f" --n {args.n}"),
        notes=[sample_note],
    )
    print(
        f"calls live={sum(r.source == 'live' for r in client.records)} "
        f"cached={sum(r.source == 'cache' for r in client.records)} cost_usd={cost:.4f}; "
        f"wrote {md} and {svg}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
