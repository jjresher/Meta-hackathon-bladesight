"""`uv run poe fleet <command>`: build the synthetic farm, process it, run the agent.

- `build`: write `replay/layout.json` from the dev split (seeded, free).
- `process`: detect, measure, assess and verify every image of the farm and store the results in
  `replay/` (real calls: `BLADESIGHT_MODE=live`, about 0.04 USD per tile; resumable).
- `run`: the agent over the stored results (real calls in live mode; replay from the cache
  otherwise) and its trace, work orders and report in `replay/`.
- `regrade`: re-grade and re-verify the defects stored in `--source-dir` (same detections and
  measurements, no detection call) on `--chat-provider`, into `--replay-dir`.
- `status`: what the store holds.
- `compare`: `docs/evidence/open_weights_farm.md`, the Meta replay vs the Open replay (free).
- `backfill`: fill the provenance and trace fields into a store written before they existed
  (free, no model call; `backfill.py`).

`--chat-provider` (or `BLADESIGHT_CHAT_PROVIDER`) picks the model of severity, verification, the
agent and its report: `meta` (Muse Spark) or `baseten` (Muse Spark Open, open weights). Detection
stays on the Meta Model API (`--provider`). The Muse Spark Open replay lives in
`replay/open-weights/` (`OPEN_WEIGHTS_DIR`).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from ..chat import CHAT_PROVIDERS, ChatProvider, chat_provider_from_env, chat_target
from ..data import load_split
from ..meta import MetaClient, MetaError, MetaSettings, build_client
from .agent import MAX_TOKENS, run_agent
from .build import build_layout
from .process import process_farm, regrade_farm
from .store import OPEN_WEIGHTS_DIR, REPLAY_DIR, Store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bladesight.fleet")
    parser.add_argument(
        "command",
        choices=[
            "build",
            "process",
            "regrade",
            "run",
            "status",
            "evidence",
            "backfill",
            "compare",
        ],
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--replay-dir", type=Path, default=REPLAY_DIR)
    parser.add_argument(
        "--provider", choices=["meta", "stub"], default="meta", help="detection provider"
    )
    parser.add_argument(
        "--chat-provider",
        choices=CHAT_PROVIDERS,
        default=None,
        help="severity, verification, agent and report (default: BLADESIGHT_CHAT_PROVIDER, "
        "else --provider)",
    )
    parser.add_argument(
        "--source-dir", type=Path, default=REPLAY_DIR, help="regrade: the store to re-grade"
    )
    parser.add_argument("--workers", type=int, default=1, help="regrade: parallel defects")
    parser.add_argument(
        "--open-dir", type=Path, default=OPEN_WEIGHTS_DIR, help="evidence/compare: Open replay"
    )
    parser.add_argument(
        "--open-farm-cost", type=float, default=0.0, help="compare: USD of the Open regrade"
    )
    parser.add_argument("--only", action="append", help="process: only this inspection id")
    parser.add_argument("--max-steps", type=int, default=40)
    parser.add_argument("--max-cost", type=float, default=1.0, help="run: agent budget in USD")
    parser.add_argument("--run-id")
    parser.add_argument(
        "--farm-cost", type=float, default=0.0, help="evidence: USD of the live farm runs"
    )
    parser.add_argument(
        "--agent-cost", type=float, default=0.0, help="evidence: USD of the agent run"
    )
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

    if args.command == "backfill":
        from .backfill import backfill

        print(f"backfilled {args.replay_dir}: {backfill(store)}")
        return 0

    if args.command == "evidence":
        from .evidence import render

        out = Path("docs/evidence/fleet_run.md")
        open_store = Store(args.open_dir) if (args.open_dir / "inspections").exists() else None
        out.write_text(
            render(store, args.farm_cost, args.agent_cost, open_store=open_store),
            encoding="utf-8",
        )
        print(f"wrote {out}")
        return 0

    if args.command == "compare":
        from .compare import render_comparison

        out = Path("docs/evidence/open_weights_farm.md")
        out.write_text(
            render_comparison(
                store,
                Store(args.open_dir),
                meta_farm_cost=args.farm_cost,
                open_farm_cost=args.open_farm_cost,
            ),
            encoding="utf-8",
        )
        print(f"wrote {out}")
        return 0

    settings = MetaSettings.from_env()
    chat_provider: ChatProvider = args.chat_provider or chat_provider_from_env(args.provider)
    clients: list[MetaClient] = []
    if args.command == "process":
        clients.append(build_client(settings, provider=args.provider))
    chat = chat_target(
        settings,
        chat_provider,
        client=clients[0] if clients and chat_provider == args.provider else None,
    )
    if chat.client not in clients:
        clients.append(chat.client)
    only = set(args.only) if args.only else None
    try:
        if args.command == "process":
            done = process_farm(
                clients[0],
                settings,
                store,
                args.data_dir,
                only=only,
                provider=args.provider,
                chat=chat,
            )
            print(f"processed {len(done)} inspections: {', '.join(done) or '-'}")
        elif args.command == "regrade":
            if args.source_dir.resolve() == args.replay_dir.resolve():
                print("error: --source-dir and --replay-dir must differ", file=sys.stderr)
                return 2
            done = regrade_farm(
                chat,
                settings,
                Store(args.source_dir),
                store,
                args.data_dir,
                only=only,
                workers=args.workers,
            )
            print(f"regraded {len(done)} inspections on {chat.model}: {', '.join(done) or '-'}")
        else:
            run = run_agent(
                chat.client,
                settings,
                store,
                max_steps=args.max_steps,
                max_cost_usd=args.max_cost,
                run_id=args.run_id,
                provider=chat.provider,
                model=chat.model,
                max_tokens=chat.budget(MAX_TOKENS),
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
        for client in clients:
            print(
                f"{client.provider.name}: calls "
                f"live={sum(r.source == 'live' for r in client.records)} "
                f"cached={sum(r.source == 'cache' for r in client.records)} "
                f"cost_usd={sum(r.cost_usd for r in client.records):.4f} "
                f"all_runs_usd={client.spend.spent_usd:.4f} "
                f"limit_usd={client.spend.limit_usd:.2f}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
