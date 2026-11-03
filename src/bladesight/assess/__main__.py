"""`python -m bladesight.assess <tile id>...`: detect, measure and grade the defects of dev tiles.

Detection replays from the cache when it exists; each grading call is a real Muse Spark call in
`BLADESIGHT_MODE=live` (follow `meta-api-check`). `--provider stub` spends nothing. Dev tiles only.
Writes the close and context crops next to the JSON under `outputs/assess/` for hand review.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ..data import TileLabel, image_path
from ..detect.pipeline import detect_tile
from ..measure import measure_detection
from ..meta import MetaError, MetaSettings, build_client
from .assess import AssessError, assess_defect
from .crops import close_and_context


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bladesight.assess")
    parser.add_argument("tiles", nargs="+", help="dev tile ids")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--out", type=Path, default=Path("outputs/assess"))
    parser.add_argument("--provider", choices=["meta", "stub"], default="meta")
    parser.add_argument("--max", type=int, default=10, help="stop after this many gradings")
    args = parser.parse_args(argv)

    settings = MetaSettings.from_env()
    client = build_client(settings, provider=args.provider)
    args.out.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    try:
        for tile_id in args.tiles:
            TileLabel.parse_tile_id(tile_id)
            png = image_path(tile_id, "dev", args.data_dir).read_bytes()
            detection = detect_tile(client, settings, tile_id, png)
            for det, meas in zip(detection.defects, measure_detection(detection), strict=True):
                if len(rows) >= args.max:
                    break
                name = det.defect.id.replace("/", "_")
                close, wide = close_and_context(png, det.defect.bbox)
                (args.out / f"{name}_close.png").write_bytes(close)
                (args.out / f"{name}_context.png").write_bytes(wide)
                try:
                    result = assess_defect(
                        client, settings, png, det.defect, meas, provider=args.provider
                    )
                    row: dict[str, object] = {"assessment": result.model_dump(mode="json")}
                except AssessError as error:
                    row = {"error": str(error)}
                rows.append(
                    {
                        "defect": det.defect.model_dump(mode="json", exclude={"outline"}),
                        "measurement": meas.model_dump(mode="json"),
                        **row,
                    }
                )
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
    (args.out / "assessments.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    for row in rows:
        a = row.get("assessment")
        d = row["defect"]
        assert isinstance(d, dict)
        print(d["id"], a if a else row.get("error"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
