"""Issue #3 fallback spike: Muse Spark proposes boxes, SAM 3.1 refines them; score both vs labels.

`BLADESIGHT_MODE=live python -m bladesight.detect.spike_boxes --data-dir <data> --n-damage 20
--n-clean 5`. Same 25 tiles as `spike`; dev only. Real calls follow `meta-api-check`.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

from PIL import Image

from ..data import image_path, load_split
from ..eval.matching import Box, match
from ..meta import ImagePart, MetaError, MetaSettings, build_client
from .propose import propose_boxes, refine_with_sam
from .spike import IOU_LEVELS, select_tiles


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bladesight.detect.spike_boxes")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--n-damage", type=int, default=20)
    parser.add_argument("--n-clean", type=int, default=5)
    parser.add_argument("--out", type=Path, default=Path("outputs/spike_boxes"))
    args = parser.parse_args(argv)
    if args.n_damage + args.n_clean > 25:
        parser.error("the spike is limited to 25 tiles (sprint rule)")

    settings = MetaSettings.from_env()
    client = build_client(settings, provider="meta")
    tiles = select_tiles(load_split("dev", args.data_dir), args.n_damage, args.n_clean)
    rows: list[dict[str, object]] = []
    stats: dict[str, dict[str, float]] = {
        k: {"truths": 0, "preds": 0, **{f"tp@{lv}": 0 for lv in IOU_LEVELS}}
        for k in ("spark_damage", "sam_damage", "spark_dirt", "sam_dirt")
    }
    clean_with = {"spark": 0, "sam": 0}
    clean_total = 0
    image_hit = {"spark": 0, "sam": 0}
    damaged_total = 0
    try:
        for tile in tiles:
            raw = image_path(tile, "dev", args.data_dir).read_bytes()
            width, height = Image.open(io.BytesIO(raw)).size
            image = ImagePart(data=raw, mime_type="image/png")
            proposals = propose_boxes(client, settings.chat_model, image, width, height)
            masks = (
                refine_with_sam(
                    client, settings.sam_model, image, [b for _, b in proposals], (width, height)
                )
                if proposals
                else []
            )
            by_id = {m.object_id: m for m in masks}
            sam_boxes = {
                i: tuple(float(v) for v in by_id[str(i)].box)
                for i in range(1, len(proposals) + 1)
                if str(i) in by_id
            }
            rows.append(
                {
                    "tile": tile.tile_id,
                    "proposals": [[lab, list(b)] for lab, b in proposals],
                    "sam": {str(i): list(b) for i, b in sam_boxes.items()},
                }
            )
            if tile.has_damage:
                damaged_total += 1
            if not tile.has_label:
                clean_total += 1
            for label in ("damage", "dirt"):
                truths: list[Box] = [
                    (b.x1, b.y1, b.x2, b.y2) for b in tile.boxes if b.label == label
                ]
                spark = [tuple(map(float, b)) for lab, b in proposals if lab == label]
                sam = [
                    sam_boxes[i]
                    for i, (lab, _) in enumerate(proposals, 1)
                    if lab == label and i in sam_boxes
                ]
                for name, preds in (("spark", spark), ("sam", sam)):
                    st = stats[f"{name}_{label}"]
                    st["truths"] += len(truths)
                    st["preds"] += len(preds)
                    for lv in IOU_LEVELS:
                        st[f"tp@{lv}"] += match(preds, [1.0] * len(preds), truths, lv).tp  # type: ignore[arg-type]
                    if label == "damage" and tile.has_damage and preds:
                        image_hit[name] += 1
                    if label == "damage" and not tile.has_label and preds:
                        clean_with[name] += 1
    except MetaError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    finally:
        print(
            f"calls: live={sum(r.source == 'live' for r in client.records)} "
            f"cached={sum(r.source == 'cache' for r in client.records)} "
            f"cost_usd={sum(r.cost_usd for r in client.records):.4f} "
            f"all_runs_usd={client.spend.spent_usd:.4f} limit_usd={client.spend.limit_usd:.2f}"
        )
    args.out.mkdir(parents=True, exist_ok=True)
    summary = {
        "tiles": len(tiles),
        "damaged_tiles": damaged_total,
        "clean_tiles": clean_total,
        "image_hit": image_hit,
        "clean_with_damage_prediction": clean_with,
        "stats": stats,
    }
    (args.out / "rows.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    (args.out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
