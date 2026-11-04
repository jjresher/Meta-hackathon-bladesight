"""`uv run poe eval --split dev --n 300`: detection metrics on a dev sample, written as evidence.

Refuses `--split heldout` unless `ALLOW_HELDOUT=1` (only the single preregistered run of #16).
Real calls follow `meta-api-check` (`BLADESIGHT_MODE=live`, a cap sized for the run); the default
replay mode only reads the cache. `--provider stub` spends nothing (smoke test, not a result).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..data import HeldoutSealedError
from ..meta import MetaError, MetaSettings, build_client
from .report import build_report, write_outputs
from .runner import evaluate_tiles, load_tiles, sample_tiles


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

    try:
        tiles = load_tiles(args.split, args.data_dir)
    except HeldoutSealedError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 2
    settings = MetaSettings.from_env()
    client = build_client(settings, provider=args.provider)
    chosen = tiles if args.split == "heldout" else sample_tiles(tiles, args.n)
    try:
        results = evaluate_tiles(client, settings, chosen, args.split, args.data_dir)
    except MetaError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    cost = args.cost_usd if args.cost_usd is not None else sum(r.cost_usd for r in client.records)
    stem = args.stem or f"eval_{args.split}"
    report = build_report(
        args.split, results, cost_usd=cost, evidence_path=f"docs/evidence/{stem}.md"
    )
    md, svg = write_outputs(
        report,
        results,
        args.out,
        stem,
        title=f"Detection evaluation ({args.split})",
        command=f"uv run poe eval --split {args.split} --n {args.n}",
        notes=[
            "Sample: two thirds of the tiles have dataset boxes, one third none (seeded, "
            "`eval/runner.py`); the dev split is about 22% labeled, so recall is measurable but "
            "per-image false-alarm rates are not those of a real inspection.",
        ],
    )
    print(
        f"calls live={sum(r.source == 'live' for r in client.records)} "
        f"cached={sum(r.source == 'cache' for r in client.records)} cost_usd={cost:.4f}; "
        f"wrote {md} and {svg}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
