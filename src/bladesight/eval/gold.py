"""Severity gold set (issue #10): pick 40 dev crops, label them locally, blind to the model.

`uv run poe gold prepare` writes `eval/gold/severity.csv` (ids and boxes only, no images, empty
`severity`). `uv run poe gold label` serves a local page (127.0.0.1) that shows each crop with the
rubric and saves the keys 1-5 (0 = unreadable) straight into the CSV. The model's grades are never
shown. Crops are the dataset's own boxes, so the choice does not depend on our detector.
"""

from __future__ import annotations

import csv
import io
import json
import os
import random
import tempfile
import threading
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib import resources
from pathlib import Path

from ..assess.crops import crop_png
from ..contracts import BBox
from ..data import TileLabel, image_path, load_split

GOLD_CSV = Path("eval/gold/severity.csv")
FIELDS = ["crop_id", "tile_id", "box_index", "label", "x1", "y1", "x2", "y2", "severity", "note"]
N_CROPS = 40
SEED = 20261030
MIN_AREA_PX = 60.0
SEVERITIES = {"0", "1", "2", "3", "4", "5"}  # 0 = unreadable, not gradable


@dataclass(frozen=True)
class Candidate:
    tile: TileLabel
    index: int
    area: float


def select_gold(tiles: list[TileLabel], n: int = N_CROPS, seed: int = SEED) -> list[dict[str, str]]:
    """One damage box per source photo, spread over four size quartiles, seeded and sorted by id."""
    rng = random.Random(seed)
    candidates: list[Candidate] = []
    for tile in sorted(tiles, key=lambda t: t.tile_id):
        for i, box in enumerate(tile.boxes):
            if box.label == "damage" and box.area >= MIN_AREA_PX:
                candidates.append(Candidate(tile, i, box.area))
    rng.shuffle(candidates)
    seen: set[str] = set()
    unique = []
    for c in candidates:
        if c.tile.source_photo not in seen:
            seen.add(c.tile.source_photo)
            unique.append(c)
    unique.sort(key=lambda c: c.area)
    per = n // 4
    chosen: list[Candidate] = []
    for q in range(4):
        lo, hi = q * len(unique) // 4, (q + 1) * len(unique) // 4
        bucket = unique[lo:hi]
        rng.shuffle(bucket)
        chosen += bucket[:per]
    if len(chosen) != per * 4:
        raise ValueError(f"only {len(chosen)} crops available for n={n}")
    chosen.sort(key=lambda c: (c.tile.tile_id, c.index))
    rows = []
    for c in chosen:
        b = c.tile.boxes[c.index]
        rows.append(
            {
                "crop_id": f"{c.tile.tile_id}#{c.index}",
                "tile_id": c.tile.tile_id,
                "box_index": str(c.index),
                "label": b.label,
                "x1": f"{b.x1:g}",
                "y1": f"{b.y1:g}",
                "x2": f"{b.x2:g}",
                "y2": f"{b.y2:g}",
                "severity": "",
                "note": "",
            }
        )
    return rows


def write_rows(rows: list[dict[str, str]], path: Path = GOLD_CSV) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")  # atomic: never a half-written CSV
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
            handle.write(buffer.getvalue())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def read_rows(path: Path = GOLD_CSV) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


_LOCK = threading.Lock()


def set_severity(path: Path, crop_id: str, severity: str, note: str | None = None) -> None:
    """Write one label (`""` clears it). Raises ValueError for unknown ids or values."""
    if severity != "" and severity not in SEVERITIES:
        raise ValueError(f"severity must be one of {sorted(SEVERITIES)} or empty")
    with _LOCK:
        rows = read_rows(path)
        for row in rows:
            if row["crop_id"] == crop_id:
                row["severity"] = severity
                if note is not None:  # a label change keeps a note typed by hand
                    row["note"] = note
                write_rows(rows, path)
                return
    raise ValueError(f"unknown crop id {crop_id!r}")


def crop_for(row: dict[str, str], data_dir: Path, pad: float) -> bytes:
    png = image_path(row["tile_id"], "dev", data_dir).read_bytes()
    box = BBox(x1=float(row["x1"]), y1=float(row["y1"]), x2=float(row["x2"]), y2=float(row["y2"]))
    return crop_png(png, box, pad=pad, min_side=96.0 if pad > 1 else 40.0)


def page() -> bytes:
    return resources.files("bladesight.eval").joinpath("gold_page.html").read_bytes()


def make_server(data_dir: Path, path: Path = GOLD_CSV, port: int = 8765) -> ThreadingHTTPServer:
    """The labelling server, bound to 127.0.0.1 (port 0 picks a free one)."""

    class Handler(BaseHTTPRequestHandler):
        def _send(self, body: bytes, kind: str, code: int = 200) -> None:
            self.send_response(code)
            self.send_header("Content-Type", kind)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if not self._local():
                self._send(b"forbidden", "text/plain", 403)
            elif self.path == "/":
                self._send(page(), "text/html; charset=utf-8")
            elif self.path == "/api/rows":
                self._send(json.dumps(read_rows(path)).encode(), "application/json")
            elif self.path.startswith("/crop/"):
                try:
                    _, _, index, kind = self.path.split("/")
                    if kind not in ("close", "context") or not index.isdigit():
                        raise ValueError("bad crop path")
                    row = read_rows(path)[int(index)]
                    pad = 0.4 if kind == "close" else 3.0
                    self._send(crop_for(row, data_dir, pad), "image/png")
                except (ValueError, IndexError, OSError):
                    self._send(b"not found", "text/plain", 404)
            else:
                self._send(b"not found", "text/plain", 404)

        def _local(self) -> bool:
            """Same-origin only: a page on another site cannot write labels (CSRF / rebinding)."""
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            allowed = {f"127.0.0.1:{port}", f"localhost:{port}"}
            return host in allowed and (origin is None or origin.split("//", 1)[-1] in allowed)

        def do_POST(self) -> None:
            if self.path != "/api/label":
                self._send(b"not found", "text/plain", 404)
                return
            content_type = self.headers.get("Content-Type", "")
            if not self._local() or not content_type.startswith("application/json"):
                self._send(b"forbidden", "text/plain", 403)
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size < 4096:
                    raise ValueError("bad length")
                data = json.loads(self.rfile.read(size))
                set_severity(path, str(data["crop_id"]), str(data["severity"]))
                self._send(b"{}", "application/json")
            except (ValueError, KeyError, TypeError):
                self._send(b"bad request", "text/plain", 400)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    port = server.server_address[1]  # the handler reads the real port for its Host check
    return server


def serve(data_dir: Path, path: Path = GOLD_CSV, port: int = 8765) -> None:
    server = make_server(data_dir, path, port)
    print(
        f"Labelling at http://127.0.0.1:{server.server_address[1]}/ "
        f"(Ctrl+C to stop; saved to {path})"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(prog="python -m bladesight.eval.gold")
    parser.add_argument("command", choices=["prepare", "label", "status"])
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--csv", type=Path, default=GOLD_CSV)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--force", action="store_true", help="prepare: overwrite existing labels")
    args = parser.parse_args(argv)
    if args.command == "prepare":
        if args.csv.exists() and any(r["severity"] for r in read_rows(args.csv)) and not args.force:
            print(f"{args.csv} already has labels; use --force to overwrite")
            return 1
        rows = select_gold(load_split("dev", args.data_dir))
        write_rows(rows, args.csv)
        print(f"wrote {len(rows)} crop ids to {args.csv}")
    elif args.command == "label":
        serve(args.data_dir, args.csv, args.port)
    else:
        rows = read_rows(args.csv)
        done = sum(bool(r["severity"]) for r in rows)
        print(f"{done}/{len(rows)} labelled")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
