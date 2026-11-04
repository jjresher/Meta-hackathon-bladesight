"""`uv run poe detect <tile id or dev image path>`: detect defects on one dev tile + overlay.

Real calls follow the `meta-api-check` skill (`BLADESIGHT_MODE=live`); the default replay mode only
reads the cache. `--provider stub` spends nothing. Dev tiles only.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from ..data import TileLabel, image_path
from ..measure import measure_detection
from ..meta import MetaError, MetaSettings, build_client
from .overlay import render_overlay
from .pipeline import detect_tile


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bladesight.detect")
    parser.add_argument("tile", help="dev tile id (DJI_0702_04_05) or a path to a dev PNG")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("outputs/detect"))
    parser.add_argument("--provider", choices=["meta", "stub"], default="meta")
    parser.add_argument("--no-blade", action="store_true", help="skip the blade concept call")
    args = parser.parse_args(argv)

    path = Path(args.tile)
    if path.suffix:
        if "heldout" in path.resolve().parts:
            parser.error("refusing the sealed held-out split (AGENTS.md rule 3)")
        tile_id = path.stem
    else:
        tile_id = args.tile
        path = image_path(tile_id, "dev", args.data_dir)
    TileLabel.parse_tile_id(tile_id)

    settings = MetaSettings.from_env()
    client = build_client(settings, provider=args.provider)
    started = time.monotonic()
    try:
        detection = detect_tile(
            client, settings, tile_id, path.read_bytes(), with_blade=not args.no_blade
        )
    except MetaError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    elapsed = time.monotonic() - started
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / f"{tile_id}.png").write_bytes(render_overlay(path.read_bytes(), detection))
    (args.out / f"{tile_id}.json").write_text(
        json.dumps([d.defect.model_dump(mode="json") for d in detection.defects], indent=1),
        encoding="utf-8",
    )
    for det, m in zip(detection.defects, measure_detection(detection), strict=True):
        d = det.defect
        print(
            f"{d.id} label={d.label} source={d.source} score={d.score:.2f} "
            f"area_px={d.mask_area_px:.0f} bbox=({d.bbox.x1:.0f},{d.bbox.y1:.0f},"
            f"{d.bbox.x2:.0f},{d.bbox.y2:.0f}) tile_share={m.tile_area_ratio:.4f} "
            f"elongation={m.elongation:.2f} position={m.position}"
        )
    if not detection.defects:
        print("no defects (zero is a valid answer)")
    live = sum(r.source == "live" for r in client.records)
    print(
        f"blade={'found' if detection.blade_mask is not None else 'not found'} "
        f"proposals={detection.n_proposals} calls_live={live} "
        f"calls_cached={sum(r.source == 'cache' for r in client.records)} "
        f"cost_usd={sum(r.cost_usd for r in client.records):.4f} seconds={elapsed:.1f} "
        f"overlay={args.out / (tile_id + '.png')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
