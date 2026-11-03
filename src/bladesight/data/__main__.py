"""`python -m bladesight.data` (`uv run poe data`): download, convert, split, seal, verify.

The first build writes `eval/heldout_manifest.sha256` and `eval/split_summary.json`; every later
build must reproduce the committed manifest byte for byte, or it fails.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .build import (
    ARCHIVE_NAME,
    ARCHIVE_SHA256,
    MANIFEST,
    SUMMARY,
    DataBuildError,
    build,
    download,
    sha256_file,
)
from .splits import DATA_DIR


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m bladesight.data")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument(
        "--write-manifest",
        action="store_true",
        help="overwrite the committed manifest and summary (first build only)",
    )
    args = parser.parse_args(argv)

    archive = args.data_dir / "raw" / ARCHIVE_NAME
    try:
        print(f"download: {archive}")
        download(archive)
        digest = sha256_file(archive)
        if digest != ARCHIVE_SHA256:
            raise DataBuildError(f"archive sha256 {digest} does not match {ARCHIVE_SHA256}")
        print(f"archive sha256: {digest}")
        result = build(archive, args.data_dir)
    except DataBuildError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    manifest_text = "".join(f"{line}\n" for line in result.manifest_lines)
    for split, counts in result.counts.items():
        print(f"{split}: {json.dumps(counts)}")
    print(f"manifest sha256: {result.summary['manifest_sha256']}")

    if args.write_manifest or not MANIFEST.exists():
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(manifest_text, encoding="utf-8")
        SUMMARY.write_text(json.dumps(result.summary, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {MANIFEST} and {SUMMARY}")
        return 0
    if MANIFEST.read_text(encoding="utf-8") != manifest_text:
        print(f"error: the rebuilt held-out split does not match {MANIFEST}", file=sys.stderr)
        return 1
    print(f"OK: the split reproduces {MANIFEST}; data/heldout is sealed (chmod 000)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
