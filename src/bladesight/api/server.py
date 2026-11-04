"""The API. Replay mode (the default, and what production runs) only reads the stored results in
`replay/` and `docs/evidence/eval_*.json`: no key and no model call are needed. Live mode adds
`POST /api/runs`, guarded by an admin key and by the cumulative spend cap of `bladesight.meta`.
"""

from __future__ import annotations

import json
import os
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from ..contracts import (
    SCHEMA_VERSION,
    AgentRun,
    EvalReport,
    Fleet,
    Health,
    Inspection,
    Report,
    WorkOrder,
)
from ..fleet.rank import build_fleet
from ..fleet.store import Store

VERSION = "0.1.0"
TILE_ID = re.compile(r"^DJI_\d{4}_\d{2}_\d{2}$")
DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]


@dataclass
class Settings:
    replay_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("BLADESIGHT_REPLAY_DIR", "replay"))
    )
    data_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("BLADESIGHT_DATA_DIR", "data"))
    )
    web_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("BLADESIGHT_WEB_DIR", "web/dist"))
    )
    evidence_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("BLADESIGHT_EVIDENCE_DIR", "docs/evidence"))
    )
    mode: str = field(default_factory=lambda: os.environ.get("BLADESIGHT_MODE", "replay"))
    admin_key: str = field(default_factory=lambda: os.environ.get("BLADESIGHT_ADMIN_KEY", ""))


def create_app(settings: Settings | None = None) -> FastAPI:
    cfg = settings or Settings()
    store = Store(cfg.replay_dir)
    app = FastAPI(title="BladeSight API", version=VERSION)
    app.add_middleware(CORSMiddleware, allow_origins=DEV_ORIGINS, allow_methods=["GET"])

    def not_found(what: str) -> HTTPException:
        return HTTPException(status_code=404, detail=f"{what} not found")

    @app.get("/api/health", response_model=Health)
    def health() -> Health:
        mode = "live" if cfg.mode == "live" else "replay"
        return Health(status="ok", mode=mode, version=VERSION, schema_version=SCHEMA_VERSION)

    @app.get("/api/fleet", response_model=Fleet)
    def fleet() -> Fleet:
        if not (cfg.replay_dir / "inspections").exists():
            raise not_found("fleet data (run `uv run poe fleet process`)")
        runs = store.runs() if (cfg.replay_dir / "runs").exists() else []
        latest = sorted(runs, key=lambda r: r.started_at)[-1].id if runs else None
        return build_fleet(store.inspections(), store.work_orders(), latest)

    @app.get("/api/inspections/{inspection_id}", response_model=Inspection)
    def inspection(inspection_id: str) -> Inspection:
        try:
            return store.inspection(inspection_id)
        except KeyError:
            raise not_found("inspection") from None

    @app.get("/api/work-orders", response_model=list[WorkOrder])
    def work_orders() -> list[WorkOrder]:
        return store.work_orders()

    @app.get("/api/reports/latest", response_model=Report)
    def report() -> Report:
        found = store.latest_report()
        if found is None:
            raise not_found("report")
        return found

    @app.get("/api/runs", response_model=list[AgentRun])
    def runs() -> list[AgentRun]:
        if not (cfg.replay_dir / "runs").exists():
            return []
        return sorted(store.runs(), key=lambda r: r.started_at)

    @app.get("/api/runs/{run_id}", response_model=AgentRun)
    def run(run_id: str) -> AgentRun:
        try:
            return store.run(run_id)
        except KeyError:
            raise not_found("run") from None

    @app.get("/api/eval", response_model=list[EvalReport])
    def evaluation() -> list[EvalReport]:
        reports = []
        for path in sorted(cfg.evidence_dir.glob("eval_*.json")):
            reports.append(EvalReport.model_validate(json.loads(path.read_text(encoding="utf-8"))))
        return reports

    def require_admin(x_admin_key: Annotated[str | None, Header()] = None) -> None:
        if cfg.mode != "live":
            raise HTTPException(status_code=403, detail="live runs are disabled (replay mode)")
        if (
            not cfg.admin_key
            or not x_admin_key
            or not secrets.compare_digest(x_admin_key, cfg.admin_key)
        ):
            raise HTTPException(status_code=403, detail="admin key required")

    @app.post("/api/runs", response_model=AgentRun, dependencies=[Depends(require_admin)])
    def start_run() -> AgentRun:
        from ..fleet.agent import run_agent
        from ..meta import MetaError, MetaSettings, build_client

        settings_ = MetaSettings.from_env()
        try:
            client = build_client(settings_, provider="meta")
            return run_agent(client, settings_, store, max_cost_usd=1.0)
        except MetaError as error:
            raise HTTPException(status_code=502, detail=str(error)) from None

    @app.get("/images/{name}")
    def image(name: str) -> Response:
        tile_id = name.removesuffix(".png")
        if not name.endswith(".png") or not TILE_ID.match(tile_id):
            raise not_found("image")
        path = cfg.data_dir / "dev" / "img" / f"{tile_id}.png"  # never the held-out split
        if not path.is_file():
            raise not_found("image")
        return FileResponse(
            path, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"}
        )

    if cfg.web_dir.is_dir():
        index = cfg.web_dir / "index.html"
        if (cfg.web_dir / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=cfg.web_dir / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> Response:
            if path.startswith(("api/", "images/")):
                raise not_found(path)
            candidate = (cfg.web_dir / path).resolve()
            if path and candidate.is_file() and cfg.web_dir.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(index)

    return app


app = create_app()
