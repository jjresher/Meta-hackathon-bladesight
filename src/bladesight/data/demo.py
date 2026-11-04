"""Fetch only the tiles the demo shows, by streaming the Dataset Ninja archive (build time).

The deployed image never contains the dataset: at build time this reads the 2.8 GB tar as a
stream, extracts the few PNGs named by `replay/` into `data/dev/img/` and stops as soon as all
are found. The held-out split is never touched (only dev tile ids from the replay store are
accepted). If the download fails the build continues without images: the API answers 404 for
them and the UI shows its image placeholder.
"""

from __future__ import annotations

import argparse
import json
import sys
import tarfile
from collections.abc import Iterator
from pathlib import Path
from typing import IO

import httpx

from .build import ARCHIVE_URL
from .models import TileLabel


class _Stream:
    """A minimal read-only file object over an httpx byte iterator (what `tarfile` needs)."""

    def __init__(self, chunks: Iterator[bytes]) -> None:
        self._chunks = chunks
        self._buffer = b""

    def read(self, size: int = -1) -> bytes:
        while size < 0 or len(self._buffer) < size:
            try:
                self._buffer += next(self._chunks)
            except StopIteration:
                break
        if size < 0:
            data, self._buffer = self._buffer, b""
        else:
            data, self._buffer = self._buffer[:size], self._buffer[size:]
        return data


HELDOUT_MANIFEST = Path(__file__).resolve().parents[3] / "eval" / "heldout_manifest.sha256"


def heldout_ids(manifest: Path | None = None) -> set[str]:
    """Tile ids listed in the committed held-out manifest (names only, no file is read)."""
    manifest = manifest or HELDOUT_MANIFEST
    if not manifest.exists():
        return set()
    names = (line.partition("  ")[2] for line in manifest.read_text("utf-8").splitlines())
    return {Path(n).stem for n in names if n.startswith("heldout/img/")}


def tile_ids_from_replay(replay_dir: Path) -> set[str]:
    ids: set[str] = set()
    for path in (replay_dir / "inspections").glob("*.json"):
        for image in json.loads(path.read_text(encoding="utf-8"))["images"]:
            ids.add(image["tile_id"])
    for tile_id in ids:
        TileLabel.parse_tile_id(tile_id)  # also rejects anything that is not a DTU tile id
    if banned := ids & heldout_ids():
        raise ValueError(f"the replay store names held-out tiles: {sorted(banned)[:3]}")
    return ids


def extract_from_stream(fileobj: IO[bytes] | _Stream, wanted: set[str], dest: Path) -> set[str]:
    """Extract `ds/img/<tile>.png` for the wanted tiles from a tar stream; returns those found."""
    found: set[str] = set()
    dest.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=fileobj, mode="r|") as archive:  # type: ignore[arg-type]
        for member in archive:
            parts = member.name.removeprefix("./").split("/")
            if len(parts) != 3 or parts[:2] != ["ds", "img"] or not member.isreg():
                continue
            tile_id = parts[2].removesuffix(".png")
            if tile_id not in wanted or not parts[2].endswith(".png") or member.size > 20_000_000:
                continue
            handle = archive.extractfile(member)
            if handle is None:
                continue
            (dest / f"{tile_id}.png").write_bytes(handle.read())
            found.add(tile_id)
            if found == wanted:
                break
    return found


def fetch(replay_dir: Path, data_dir: Path, url: str = ARCHIVE_URL) -> tuple[int, int]:
    wanted = tile_ids_from_replay(replay_dir) - {
        p.stem for p in (data_dir / "dev" / "img").glob("*.png")
    }
    if not wanted:
        return 0, 0
    with httpx.stream(
        "GET", url, follow_redirects=True, timeout=httpx.Timeout(60.0, read=120.0)
    ) as response:
        response.raise_for_status()
        found = extract_from_stream(
            _Stream(response.iter_bytes(1 << 20)), wanted, data_dir / "dev" / "img"
        )
    return len(found), len(wanted)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bladesight.data.demo")
    parser.add_argument("--replay-dir", type=Path, default=Path("replay"))
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    args = parser.parse_args(argv)
    try:
        got, wanted = fetch(args.replay_dir, args.data_dir)
    except (httpx.HTTPError, tarfile.TarError, OSError) as error:
        print(f"warning: demo tiles not fetched ({error}); images will be missing", file=sys.stderr)
        return 0  # never fail the image build over the pictures
    print(f"demo tiles: {got} of {wanted} fetched")
    if got < wanted:
        print("warning: some demo tiles were not found in the archive", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
