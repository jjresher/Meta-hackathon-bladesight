"""Pre-commit hook: refuse data, images, archives, weights, secrets and held-out files.

AGENTS.md rules 1-3. Small UI assets under web/public/ are allowed.
"""

from __future__ import annotations

import sys
from pathlib import PurePosixPath

FORBIDDEN_DIRS = ("data/", "eval/heldout/", "private/")
FORBIDDEN_SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".png",
    ".tif",
    ".tiff",
    ".bmp",
    ".webp",
    ".gif",
    ".mp4",
    ".mov",
    ".avi",
    ".zip",
    ".tar",
    ".gz",
    ".7z",
    ".pt",
    ".pth",
    ".onnx",
    ".safetensors",
    ".ckpt",
    ".parquet",
    ".duckdb",
    ".sqlite",
    ".db",
}
FORBIDDEN_NAMES = {".env"}
# Small UI assets may be raster; evidence charts must be SVG (no dataset crops in git).
ALLOWED = {
    "web/public/": {".svg", ".png", ".webp", ".gif"},
    "docs/evidence/": {".svg"},
}


def is_forbidden(path: str) -> str | None:
    p = PurePosixPath(path)
    name = p.name
    if name in FORBIDDEN_NAMES or (name.startswith(".env.") and name != ".env.example"):
        return "secret file"
    if any(path.startswith(d) for d in FORBIDDEN_DIRS):
        return "data or held-out directory"
    suffix = p.suffix.lower()
    if suffix in FORBIDDEN_SUFFIXES:
        for prefix, suffixes in ALLOWED.items():
            if path.startswith(prefix) and suffix in suffixes:
                return None
        return f"forbidden file type {suffix}"
    return None


def main(argv: list[str]) -> int:
    bad = [(f, reason) for f in argv if (reason := is_forbidden(f))]
    for f, reason in bad:
        print(f"forbidden: {f} ({reason}) — see AGENTS.md rules 1-3", file=sys.stderr)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
