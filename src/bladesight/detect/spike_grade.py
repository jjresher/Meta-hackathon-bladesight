"""Issue #3 spike: can Muse Spark grade a defect crop and answer in valid JSON? (5 dev crops)

The rubric here is a throwaway probe, not `docs/rubric.md` (written in #7). Dev tiles only.
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

from PIL import Image

from ..data import image_path, load_split
from ..meta import ChatMessage, ChatRequest, ImagePart, MetaError, MetaSettings, build_client
from .spike import select_tiles

PROBE = (
    "You inspect wind turbine blades from drone photos. Image 1 is a close crop of one suspected "
    "defect; image 2 is the surrounding context (the crop is the centre). Grade the defect: "
    "1 = cosmetic (dirt, light discoloration), 2 = minor surface wear, 3 = moderate (visible "
    "erosion or paint loss, no exposed structure), 4 = serious (cracks or exposed laminate), "
    '5 = critical (deep damage, structural risk). Reply with JSON only: {"defect_type": '
    '"crack|erosion|lightning|surface_damage|dirt|other", "severity": 1-5, "rationale": "one '
    'sentence", "confidence": 0-1}.'
)


def crop(raw: bytes, box: tuple[float, float, float, float], pad: float) -> bytes:
    image = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = image.size
    x1, y1, x2, y2 = box
    bw, bh = max(x2 - x1, 8), max(y2 - y1, 8)
    region = (
        max(0, int(x1 - pad * bw)),
        max(0, int(y1 - pad * bh)),
        min(w, int(x2 + pad * bw)),
        min(h, int(y2 + pad * bh)),
    )
    out = io.BytesIO()
    image.crop(region).resize((256, 256)).save(out, format="PNG")
    return out.getvalue()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bladesight.detect.spike_grade")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--n", type=int, default=5)
    parser.add_argument("--out", type=Path, default=Path("outputs/spike_grade"))
    args = parser.parse_args(argv)
    if args.n > 5:
        parser.error("the grading probe is limited to 5 crops")
    settings = MetaSettings.from_env()
    client = build_client(settings, provider="meta")
    tiles = select_tiles(load_split("dev", args.data_dir), 25, 0)[: args.n]
    rows, valid = [], 0
    try:
        for tile in tiles:
            raw = image_path(tile, "dev", args.data_dir).read_bytes()
            box = next(b for b in tile.boxes if b.label == "damage")
            close = ImagePart(
                data=crop(raw, (box.x1, box.y1, box.x2, box.y2), 0.5), mime_type="image/png"
            )
            wide = ImagePart(
                data=crop(raw, (box.x1, box.y1, box.x2, box.y2), 4.0), mime_type="image/png"
            )
            reply = client.chat(
                ChatRequest(
                    model=settings.chat_model,
                    messages=[ChatMessage.user(PROBE, close, wide)],
                    max_tokens=1500,
                )
            ).text
            try:
                start, end = reply.find("{"), reply.rfind("}")
                parsed = json.loads(reply[start : end + 1])
                ok = 1 <= int(parsed["severity"]) <= 5 and 0 <= float(parsed["confidence"]) <= 1
            except (ValueError, KeyError, TypeError):
                parsed, ok = None, False
            valid += ok
            rows.append({"tile": tile.tile_id, "valid": ok, "reply": reply[:400], "parsed": parsed})
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
    (args.out / "rows.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(f"valid JSON: {valid}/{len(rows)}")
    for r in rows:
        print(r["tile"], r["valid"], r["parsed"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
