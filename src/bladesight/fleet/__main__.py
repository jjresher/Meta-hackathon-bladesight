"""`uv run poe fleet <command>`: build the synthetic farm, process it, run the agent.

- `build`: write `replay/layout.json` from the dev split (seeded, free).
- `process`: detect, measure, assess and verify every image of the farm and store the results in
  `replay/` (real calls: `BLADESIGHT_MODE=live`, about 0.04 USD per tile; resumable).
- `run`: the agent over the stored results (real calls in live mode; replay from the cache
  otherwise) and its trace, work orders and report in `replay/`.
- `status`: what the store holds.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ..data import load_split
from ..meta import MetaError, MetaSettings, build_client
from .agent import run_agent
from .build import build_layout
from .process import process_farm
from .store import REPLAY_DIR, Store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bladesight.fleet")
    parser.add_argument("command", choices=["build", "process", "run", "status"])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--replay-dir", type=Path, default=REPLAY_DIR)
    parser.add_argument("--provider", choices=["meta", "stub"], default="meta")
    parser.add_argument("--only", action="append", help="process: only this inspection id")
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--max-cost", type=float, default=1.0, help="run: agent budget in USD")
    parser.add_argument("--run-id")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    store = Store(args.replay_dir)

    if args.command == "build":
        layout = build_layout(load_split("dev", args.data_dir))
        store.save_layout(layout)
        print(f"wrote {args.replay_dir / 'layout.json'}: {len(layout['turbines'])} turbines")
        return 0
    if args.command == "status":
        inspections = store.inspections() if (args.replay_dir / "inspections").exists() else []
        print(
            f"layout={'yes' if (args.replay_dir / 'layout.json').exists() else 'no'} "
            f"inspections={len(inspections)} work_orders={len(store.work_orders())} "
            f"runs={len(store.runs()) if (args.replay_dir / 'runs').exists() else 0}"
        )
        return 0

    settings = MetaSettings.from_env()
    client = build_client(settings, provider=args.provider)
    try:
        if args.command == "process":
            done = process_farm(
                client,
                settings,
                store,
                args.data_dir,
                only=set(args.only) if args.only else None,
                provider=args.provider,
            )
            print(f"processed {len(done)} inspections: {', '.join(done) or '-'}")
        else:
            run = run_agent(
                client,
                settings,
                store,
                max_steps=args.max_steps,
                max_cost_usd=args.max_cost,
                run_id=args.run_id,
                provider=args.provider,
            )
            print(
                f"run {run.id}: {run.status}, {len(run.steps)} steps, "
                f"{len(run.work_order_ids)} work orders, report={run.report_id}, "
                f"replay={run.replay}"
            )
    except MetaError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    finally:
        print(
            f"calls live={sum(r.source == 'live' for r in client.records)} "
            f"cached={sum(r.source == 'cache' for r in client.records)} "
            f"cost_usd={sum(r.cost_usd for r in client.records):.4f} "
            f"all_runs_usd={client.spend.spent_usd:.4f} limit_usd={client.spend.limit_usd:.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
