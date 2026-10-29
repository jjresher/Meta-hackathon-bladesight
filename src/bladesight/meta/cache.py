"""Disk cache keyed by sha256 of (endpoint, model, payload)."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

CACHE_VERSION = 2  # 2: single-concept SAM masks with boxes and frame size


def cache_key(endpoint: str, model: str, payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        {"endpoint": endpoint, "model": model, "payload": payload},
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class DiskCache:
    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)

    def _path(self, key: str) -> Path:
        return self.directory / key[:2] / f"{key}.json"

    def get[M: BaseModel](self, key: str, result_type: type[M]) -> M | None:
        path = self._path(key)
        try:
            entry = json.loads(path.read_text(encoding="utf-8"))
            if entry.get("version") != CACHE_VERSION:
                return None
            return result_type.model_validate(entry["result"])
        except FileNotFoundError:
            return None
        except (OSError, ValueError, KeyError, ValidationError):
            # Corrupt or foreign entry: treat as a miss and drop it so the next put replaces it.
            path.unlink(missing_ok=True)
            return None

    def put(self, key: str, result: BaseModel) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        entry = {"version": CACHE_VERSION, "result": result.model_dump(mode="json")}
        fd, tmp_name = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(entry, handle)
            os.replace(tmp_name, path)
        except BaseException:
            Path(tmp_name).unlink(missing_ok=True)
            raise
