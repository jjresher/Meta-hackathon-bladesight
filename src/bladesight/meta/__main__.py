"""Development CLI: `python -m bladesight.meta {status,chat,segment}`.

Real calls follow the `meta-api-check` skill. Run with the key loaded into the process only:
`uv run --env-file .env python -m bladesight.meta status`. Nothing here prints a secret.
"""

from __future__ import annotations

import argparse
import mimetypes
import sys
from pathlib import Path

from .client import MetaClient, build_client
from .config import MUSE_SPARK_OPEN_MODEL, MetaSettings
from .errors import MetaError
from .models import ChatMessage, ChatRequest, ImagePart

STUB_MODEL = "stub-model"


def _load_image(path_or_url: str) -> ImagePart:
    if path_or_url.startswith(("http://", "https://")):
        return ImagePart(url=path_or_url)
    resolved = Path(path_or_url).resolve()
    if "heldout" in resolved.parts:
        raise SystemExit("refusing to read the sealed held-out split (AGENTS.md rule 3)")
    mime = mimetypes.guess_type(resolved.name)[0] or "image/jpeg"
    return ImagePart(data=resolved.read_bytes(), mime_type=mime)


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--no-cache", action="store_true", help="skip cache reads and writes")
    parser.add_argument(
        "--cache-only", action="store_true", help="never call the network; fail on a cache miss"
    )
    parser.add_argument("--image", help="dev image path or public http(s) URL (never data/heldout)")


def default_chat_model(provider: str, settings: MetaSettings) -> str:
    if provider == "baseten":
        return MUSE_SPARK_OPEN_MODEL
    return STUB_MODEL if provider == "stub" else settings.chat_model


def _report(client: MetaClient) -> None:
    for record in client.records:
        print(
            f"source={record.source} provider={record.provider} op={record.operation} "
            f"model={record.response_model or record.model} attempts={record.attempts} "
            f"retried={','.join(record.retried_codes) or '-'} "
            f"est_cost_usd={record.cost_usd:.4f} "
            f"simulated_usd={record.simulated_cost_usd:.4f} "
            f"price={'documented' if record.price_documented else 'UNCONFIRMED'} "
            f"cost_from_estimate={str(record.cost_from_estimate).lower()} "
            f"request_id={record.request_id or '-'}"
        )
    print(
        f"{client.spend.provider}_spent_usd_all_runs={client.spend.spent_usd:.4f} "
        f"limit_usd={client.spend.limit_usd:.2f}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bladesight.meta")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="step 0: print set/missing per variable, no network")

    chat = sub.add_parser("chat", help="one chat call (Muse Spark, Muse Spark Open or stub)")
    _add_common(chat)
    chat.add_argument("--provider", choices=["meta", "baseten", "stub"], default="meta")
    chat.add_argument("--model")
    chat.add_argument("--prompt", required=True)
    chat.add_argument(
        "--max-tokens",
        type=int,
        default=1024,
        help="output cap; Muse Spark's default reasoning alone used 686 tokens for a short answer",
    )
    chat.add_argument(
        "--reasoning-effort", help="sent as reasoning.effort; overrides META_REASONING_EFFORT"
    )
    chat.add_argument(
        "--store",
        choices=["true", "false"],
        help="sent as store on Meta Responses; overrides META_STORE",
    )

    seg = sub.add_parser("segment", help="one SAM 3.1 call (or stub)")
    _add_common(seg)
    seg.add_argument("--provider", choices=["meta", "stub"], default="meta")
    seg.add_argument("--model")
    seg.add_argument(
        "--concept", action="append", required=True, help="one short noun phrase; repeat the flag"
    )
    seg.add_argument("--threshold", type=float, default=0.5, help="minimum confidence to keep")

    args = parser.parse_args(argv)
    try:
        settings = MetaSettings.from_env()
        if args.command == "status":
            for name, value in settings.status().items():
                print(f"{name}={value}")
            return 0

        client = build_client(
            settings,
            provider=args.provider,
            use_cache=not args.no_cache,
            cache_only=True if args.cache_only else None,
        )
        if args.command == "chat":
            images = [_load_image(args.image)] if args.image else []
            request = ChatRequest(
                model=args.model or default_chat_model(args.provider, settings),
                messages=[ChatMessage.user(args.prompt, *images)],
                max_tokens=args.max_tokens,
                reasoning_effort=args.reasoning_effort,
                store=None if args.store is None else args.store == "true",
            )
            result = client.chat(request)
            print(result.text[:500])
        else:
            if not args.image:
                parser.error("segment needs --image")
            seg_result = client.segment_concepts(
                args.model or (STUB_MODEL if args.provider == "stub" else settings.sam_model),
                _load_image(args.image),
                args.concept,
                threshold=args.threshold,
            )
            for mask in seg_result.masks:
                score = "n/a" if mask.score is None else f"{mask.score:.3f}"
                print(f"concept={mask.concept} score={score} box={mask.box} area_px={mask.area}")
            if not seg_result.masks:
                print("no matches (normal: zero matches is not an error)")
        _report(client)
        return 0
    except MetaError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
