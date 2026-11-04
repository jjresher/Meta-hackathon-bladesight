"""`uv run poe eval --split dev --n 300`: detection metrics on a dev sample, written as evidence.

Refuses `--split heldout` unless `ALLOW_HELDOUT=1` (only the single preregistered run of #16).
Real calls follow `meta-api-check` (`BLADESIGHT_MODE=live`, a cap sized for the run); the default
replay mode only reads the cache. `--provider stub` spends nothing (smoke test, not a result).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from dataclasses import replace
from pathlib import Path

from ..data import HeldoutSealedError
from ..data.splits import HELDOUT_ENV
from ..meta import MetaError, MetaSettings, build_client
from . import heldout as ho
from .heldout import SAMPLE_SEED, HeldoutError, preflight, reseal, sample_heldout, verify_manifest
from .metrics import aggregate
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
    parser.add_argument(
        "--reseal-only",
        action="store_true",
        help="held-out: restore mode 000 on data/heldout after a killed run, then exit",
    )
    args = parser.parse_args(argv)
    if args.reseal_only:
        reseal(args.data_dir)
        print(f"{args.data_dir / 'heldout'} sealed")
        return 0
    if args.split == "dev" and args.n > 300:
        parser.error("the dev evaluation is limited to 300 tiles (sprint rule)")
    if args.stem is not None and (
        not re.fullmatch(r"[A-Za-z0-9_.-]+", args.stem) or args.stem.startswith(".")
    ):
        parser.error("--stem must be a plain file name stem")
    if args.split != "heldout":
        target = (args.out / f"{args.stem or 'eval_' + args.split}.md").resolve()
        if target == ho.EVIDENCE.resolve() or (args.stem or "").startswith("eval_heldout"):
            parser.error("only the preregistered held-out run may write the held-out evidence")

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
        settings = MetaSettings.from_env()
        try:
            if ho.ENFORCE_FROZEN:
                if args.provider != "meta" or args.stem or args.cost_usd is not None:
                    raise HeldoutError("the held-out run takes no --provider, --stem or --cost-usd")
                if args.out != Path("docs/evidence"):
                    raise HeldoutError("the held-out run writes only to docs/evidence")
                ho.check_frozen(settings)
            prereg_hash = preflight(args.data_dir)
        except HeldoutError as error:
            print(f"refused: {error}", file=sys.stderr)
            return 2
    else:
        settings = MetaSettings.from_env()
    try:
        weights: dict[str, float] = {}
        try:
            if heldout:
                ho.unseal_heldout(args.data_dir)  # inside the try: any failure reseals
            if heldout:  # verify BEFORE reading any label
                print(f"manifest ok: {verify_manifest(args.data_dir)} held-out files match")
            tiles = load_tiles(args.split, args.data_dir)
        except HeldoutSealedError as error:
            print(f"refused: {error}", file=sys.stderr)
            return 2
        if heldout:
            chosen, weights = sample_heldout(tiles)
        else:
            chosen = sample_tiles(tiles, args.n)
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
    out_dir = ho.EVIDENCE.parent if heldout and ho.ENFORCE_FROZEN else args.out
    if heldout:
        flat = aggregate([replace(r, weight=1.0) for r in results], "damage")
        unweighted = f"TP {flat.tp:.0f}, FP {flat.fp:.0f}, FN {flat.fn:.0f}"
        n_clean = sum(not r.has_label for r in results)
        clean_total = round(n_clean * max((r.weight for r in results), default=1.0))
        sample_note = (
            f"Preregistered sample of the held-out split: all {len(results) - n_clean} labeled "
            f"tiles plus {n_clean} of its {clean_total} clean tiles (seed {SAMPLE_SEED}); each "
            f"clean tile weighs {clean_total / max(n_clean, 1):.2f}, so precision, false positives "
            "and false alarms per image are scaled to the whole split. Recall and image-level "
            f"rates are not affected. Unweighted damage counts at IoU 0.3: {unweighted}. "
            f"Preregistration sha256 {prereg_hash}. Code commit {ho.git_sha()} (no uncommitted "
            f"changes in src/, pyproject.toml, uv.lock or the preregistration). Models "
            f"{ho.FROZEN['chat_model']} and {ho.FROZEN['sam_model']}, reasoning effort "
            f"{ho.FROZEN['reasoning_effort']}, store false (checked against the preregistered "
            "values before the run)."
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
        out_dir,
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
