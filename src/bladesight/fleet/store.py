"""The replay store: JSON results the API and the agent read (no images, no secrets).

`replay/layout.json` (farm layout), `replay/inspections/<id>.json` (`Inspection`),
`replay/work_orders.json`, `replay/reports/<id>.json`, `replay/runs/<id>.json`, and
`replay/manifest.json` (the detection models behind the store, read by `GET /api/replays`).
Writing is atomic (temp file + rename) so a crash never leaves a half-written result.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter

from ..contracts import AgentRun, Inspection, Report, WorkOrder

REPLAY_DIR = Path("replay")
# The second replay: the same detections graded, verified and planned on Muse Spark Open.
OPEN_WEIGHTS_DIR = REPLAY_DIR / "open-weights"
_ORDERS = TypeAdapter(list[WorkOrder])


class Store:
    def __init__(self, root: Path | str = REPLAY_DIR) -> None:
        self.root = Path(root)

    # --- low level ------------------------------------------------------------------------
    def _write(self, path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=path.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=1)
                handle.write("\n")
            os.replace(tmp, path)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise

    def _model(self, path: Path, model: type[BaseModel]) -> Any:
        return model.model_validate_json(path.read_text(encoding="utf-8"))

    # --- manifest: which models produced this store -----------------------------------------
    def save_manifest(self, manifest: dict[str, Any]) -> None:
        self._write(self.root / "manifest.json", manifest)

    def manifest(self) -> dict[str, Any]:
        path = self.root / "manifest.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    # --- layout and inspections -----------------------------------------------------------
    def save_layout(self, layout: dict[str, Any]) -> None:
        self._write(self.root / "layout.json", layout)

    def layout(self) -> dict[str, Any]:
        return json.loads((self.root / "layout.json").read_text(encoding="utf-8"))

    def save_inspection(self, inspection: Inspection) -> None:
        self._write(
            self.root / "inspections" / f"{inspection.summary.id}.json",
            inspection.model_dump(mode="json"),
        )

    def has_inspection(self, inspection_id: str) -> bool:
        return (self.root / "inspections" / f"{inspection_id}.json").exists()

    def inspection(self, inspection_id: str) -> Inspection:
        path = self.root / "inspections" / f"{_safe(inspection_id)}.json"
        if not path.exists():
            raise KeyError(f"unknown inspection {inspection_id!r}")
        return self._model(path, Inspection)

    def inspections(self) -> list[Inspection]:
        folder = self.root / "inspections"
        return [self._model(p, Inspection) for p in sorted(folder.glob("*.json"))]

    # --- work orders, reports, runs -------------------------------------------------------
    def work_orders(self) -> list[WorkOrder]:
        path = self.root / "work_orders.json"
        return _ORDERS.validate_json(path.read_text("utf-8")) if path.exists() else []

    def save_work_orders(self, orders: list[WorkOrder]) -> None:
        self._write(self.root / "work_orders.json", _ORDERS.dump_python(orders, mode="json"))

    def save_report(self, report: Report) -> None:
        self._write(self.root / "reports" / f"{report.id}.json", report.model_dump(mode="json"))
        self._write(self.root / "reports" / "latest.json", report.model_dump(mode="json"))

    def latest_report(self) -> Report | None:
        path = self.root / "reports" / "latest.json"
        return self._model(path, Report) if path.exists() else None

    def save_run(self, run: AgentRun) -> None:
        self._write(self.root / "runs" / f"{run.id}.json", run.model_dump(mode="json"))

    def runs(self) -> list[AgentRun]:
        folder = self.root / "runs"
        return [self._model(p, AgentRun) for p in sorted(folder.glob("*.json"))]

    def run(self, run_id: str) -> AgentRun:
        path = self.root / "runs" / f"{_safe(run_id)}.json"
        if not path.exists():
            raise KeyError(f"unknown run {run_id!r}")
        return self._model(path, AgentRun)


def _safe(identifier: str) -> str:
    """Ids are used as file names: refuse anything that could leave the folder."""
    if not identifier or "/" in identifier or "\\" in identifier or identifier.startswith("."):
        raise KeyError(f"invalid id {identifier!r}")
    return identifier
