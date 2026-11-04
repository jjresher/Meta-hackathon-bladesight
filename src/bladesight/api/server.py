"""The API. Replay mode (the default, and what production runs) only reads the stored results in
`replay/` and `docs/evidence/eval_*.json`: no key and no model call are needed. Live mode adds
`POST /api/runs`, guarded by an admin key and by the cumulative spend cap of `bladesight.meta`.

Two replays can be stored: `meta` (`replay/`, Muse Spark on the Meta Model API, the default) and
`baseten` (`replay/open-weights/`, the same detections graded, verified and planned on Muse Spark
Open). The data endpoints take `?provider=meta|baseten`; `GET /api/replays` lists what exists and
which model ran each stage.
"""

from __future__ import annotations

import json
import os
import re
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query
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
    ReplaySet,
    Report,
    StageModel,
    WorkOrder,
)
from ..fleet.rank import all_defects, build_fleet
from ..fleet.store import Store

VERSION = "0.1.0"
TILE_ID = re.compile(r"^DJI_\d{4}_\d{2}_\d{2}$")
DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
ReplayProvider = Literal["meta", "baseten"]
REPLAY_SUBDIR: dict[str, str | None] = {"meta": None, "baseten": "open-weights"}
REPLAY_LABEL = {
    "meta": "Muse Spark on the Meta Model API",
    "baseten": "Muse Spark Open (Meta open weights) on Baseten",
}
REPLAY_NOTE = {
    "meta": "Detection, severity, verification, the agent and the report on the Meta Model API.",
    "baseten": "The same stored detections as the meta replay (SAM 3.1 is not open weights and "
    "stays on the Meta Model API); severity, verification, the agent and the report re-run on "
    "Muse Spark Open.",
}
ProviderQuery = Annotated[
    ReplayProvider, Query(description="which stored replay: meta (default) or baseten")
]


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

    def root_of(provider: str) -> Path:
        sub = REPLAY_SUBDIR[provider]
        return cfg.replay_dir / sub if sub else cfg.replay_dir

    stores = {p: Store(root_of(p)) for p in REPLAY_SUBDIR}
    app = FastAPI(title="BladeSight API", version=VERSION)
    app.add_middleware(CORSMiddleware, allow_origins=DEV_ORIGINS, allow_methods=["GET"])

    def not_found(what: str) -> HTTPException:
        return HTTPException(status_code=404, detail=f"{what} not found")

    @app.get("/api/health", response_model=Health)
    def health() -> Health:
        mode = "live" if cfg.mode == "live" else "replay"
        return Health(status="ok", mode=mode, version=VERSION, schema_version=SCHEMA_VERSION)

    def pick(provider: str) -> Store:
        chosen = stores[provider]
        if provider != "meta" and not (chosen.root / "inspections").exists():
            raise not_found(f"{provider} replay")
        return chosen

    def runs_of(chosen: Store) -> list[AgentRun]:
        if not (chosen.root / "runs").exists():
            return []
        return sorted(chosen.runs(), key=lambda r: r.started_at)

    @app.get("/api/replays", response_model=list[ReplaySet])
    def replays() -> list[ReplaySet]:
        out = []
        for provider, chosen in stores.items():
            if not (chosen.root / "inspections").exists():
                continue
            inspections = chosen.inspections()
            stages = [StageModel.model_validate(s) for s in chosen.manifest().get("detection", [])]
            graded = [
                d for i in inspections for d in all_defects(i) if d.assessment and d.verification
            ]
            if graded:
                a, v = graded[0].assessment, graded[0].verification
                assert a is not None and v is not None
                stages.append(StageModel(stage="severity", model=a.model, provider=a.provider))
                if v.model and v.provider:
                    stages.append(
                        StageModel(stage="verification", model=v.model, provider=v.provider)
                    )
            runs_ = runs_of(chosen)
            if runs_:
                stages.append(
                    StageModel(stage="agent", model=runs_[-1].model, provider=runs_[-1].provider)
                )
            out.append(
                ReplaySet(
                    provider=provider,  # type: ignore[arg-type]
                    label=REPLAY_LABEL[provider],
                    default=provider == "meta",
                    stages=stages,
                    run_id=runs_[-1].id if runs_ else None,
                    n_inspections=len(inspections),
                    note=REPLAY_NOTE[provider],
                )
            )
        return out

    @app.get("/api/fleet", response_model=Fleet)
    def fleet(provider: ProviderQuery = "meta") -> Fleet:
        chosen = pick(provider)
        if not (chosen.root / "inspections").exists():
            raise not_found("fleet data (run `uv run poe fleet process`)")
        runs_ = runs_of(chosen)
        latest = runs_[-1].id if runs_ else None
        return build_fleet(chosen.inspections(), chosen.work_orders(), latest)

    @app.get("/api/inspections/{inspection_id}", response_model=Inspection)
    def inspection(inspection_id: str, provider: ProviderQuery = "meta") -> Inspection:
        try:
            return pick(provider).inspection(inspection_id)
        except KeyError:
            raise not_found("inspection") from None

    @app.get("/api/work-orders", response_model=list[WorkOrder])
    def work_orders(provider: ProviderQuery = "meta") -> list[WorkOrder]:
        return pick(provider).work_orders()

    @app.get("/api/reports/latest", response_model=Report)
    def report(provider: ProviderQuery = "meta") -> Report:
        found = pick(provider).latest_report()
        if found is None:
            raise not_found("report")
        return found

    @app.get("/api/runs", response_model=list[AgentRun])
    def runs(provider: ProviderQuery = "meta") -> list[AgentRun]:
        return runs_of(pick(provider))

    @app.get("/api/runs/{run_id}", response_model=AgentRun)
    def run(run_id: str, provider: ProviderQuery = "meta") -> AgentRun:
        try:
            return pick(provider).run(run_id)
        except KeyError:
            raise not_found("run") from None

    @app.get("/api/eval", response_model=list[EvalReport])
    def evaluation() -> list[EvalReport]:
        # The two official reports only: eval_fresh_v2*.json are other shapes and other runs (#22).
        paths = [cfg.evidence_dir / name for name in ("eval_dev.json", "eval_heldout.json")]
        return [
            EvalReport.model_validate(json.loads(path.read_text(encoding="utf-8")))
            for path in paths
            if path.exists()
        ]

    def require_admin(x_admin_key: Annotated[str | None, Header()] = None) -> None:
        if cfg.mode != "live":
            raise HTTPException(status_code=403, detail="live runs are disabled (replay mode)")
        if (
            not cfg.admin_key
            or not x_admin_key
            or not secrets.compare_digest(x_admin_key.encode(), cfg.admin_key.encode())
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

    if (cfg.web_dir / "index.html").is_file():  # no build, no UI: `/` is then a plain 404
        index = cfg.web_dir / "index.html"
        if (cfg.web_dir / "assets").is_dir():
            app.mount("/assets", StaticFiles(directory=cfg.web_dir / "assets"), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str) -> Response:
            if path.startswith(("api/", "images/")):
                raise not_found(path)
            try:
                candidate = (cfg.web_dir / path).resolve()
            except ValueError:  # e.g. a NUL byte in the path
                return FileResponse(index)
            if path and candidate.is_file() and cfg.web_dir.resolve() in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(index)

    return app


app = create_app()
