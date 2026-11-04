"""API on the stub store: every endpoint, replay-only behaviour, path safety, no key needed."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fleet_fixtures import make_store

from bladesight.api import Settings, create_app
from bladesight.contracts import Fleet, Inspection, WorkOrder
from bladesight.fleet.store import Store

VERIFIED = "T01-2018/DJI_0001_01_01/d1"


@pytest.fixture
def parts(tmp_path: Path):
    store = make_store(tmp_path)
    data = tmp_path / "data"
    (data / "dev" / "img").mkdir(parents=True)
    (data / "dev" / "img" / "DJI_0001_01_01.png").write_bytes(b"\x89PNG\r\n\x1a\nfake")
    (data / "heldout" / "img").mkdir(parents=True)
    (data / "heldout" / "img" / "DJI_0002_01_01.png").write_bytes(b"secret")
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    settings = Settings(
        replay_dir=store.root,
        data_dir=data,
        web_dir=tmp_path / "nodist",
        evidence_dir=evidence,
        mode="replay",
        admin_key="",
    )
    return store, settings, TestClient(create_app(settings))


def test_health_reports_replay_mode_and_needs_no_key(
    parts, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("META_API_KEY", raising=False)
    _, _, client = parts
    body = client.get("/api/health").json()
    assert body["status"] == "ok" and body["mode"] == "replay" and body["schema_version"]


def test_fleet_is_ranked_and_synthetic(parts) -> None:
    _, _, client = parts
    fleet = Fleet.model_validate(client.get("/api/fleet").json())
    assert fleet.synthetic is True and fleet.turbines[0].id == "T01" and fleet.turbines[0].rank == 1


def test_inspection_work_orders_report_and_runs(parts) -> None:
    store, _, client = parts
    inspection = Inspection.model_validate(client.get("/api/inspections/T01-2018").json())
    assert inspection.summary.max_severity == 4
    assert client.get("/api/inspections/T99-2018").status_code == 404
    assert client.get("/api/inspections/..%2Flayout").status_code == 404
    assert client.get("/api/work-orders").json() == []
    assert client.get("/api/reports/latest").status_code == 404
    assert client.get("/api/runs").json() == [] and client.get("/api/runs/run-x").status_code == 404
    order = WorkOrder(
        id="WO-001", kind="repair", priority="P1", turbine_id="T01", inspection_id="T01-2018",
        defect_ids=[VERIFIED], action="a", rationale="r", evidence=["e"], due_within_days=30,
    )  # fmt: skip
    store.save_work_orders([order])
    assert client.get("/api/work-orders").json()[0]["id"] == "WO-001"


def test_images_are_dev_tiles_only_and_path_safe(parts) -> None:
    _, _, client = parts
    ok = client.get("/images/DJI_0001_01_01.png")
    assert ok.status_code == 200 and ok.headers["content-type"] == "image/png"
    assert client.get("/images/DJI_0002_01_01.png").status_code == 404  # only in held-out
    for bad in ["../x.png", "DJI_0001_01_01", "DJI_1_1_1.png", "%2e%2e%2fsecret.png"]:
        assert client.get(f"/images/{bad}").status_code == 404


def test_eval_reads_the_evidence_json(parts) -> None:
    _, settings, client = parts
    assert client.get("/api/eval").json() == []
    fixture = json.loads(Path("web/src/fixtures/eval.json").read_text(encoding="utf-8"))[0]
    (settings.evidence_dir / "eval_dev.json").write_text(json.dumps(fixture), encoding="utf-8")
    assert client.get("/api/eval").json()[0]["split"] == "dev"


def test_eval_serves_the_committed_evidence_folder(parts) -> None:
    _, settings, _ = parts
    real = Settings(**{**settings.__dict__, "evidence_dir": Path("docs/evidence")})
    response = TestClient(create_app(real)).get("/api/eval")
    assert response.status_code == 200
    assert [r["split"] for r in response.json()] == ["dev", "heldout"]


def test_live_runs_are_refused_in_replay_mode_and_without_the_key(parts, tmp_path: Path) -> None:
    _, settings, client = parts
    assert client.post("/api/runs").status_code == 403
    live = Settings(**{**settings.__dict__, "mode": "live", "admin_key": "s3cret"})
    live_client = TestClient(create_app(live))
    assert live_client.post("/api/runs").status_code == 403
    assert live_client.post("/api/runs", headers={"X-Admin-Key": "wrong"}).status_code == 403
    assert live_client.get("/api/health").json()["mode"] == "live"


def test_empty_store_is_a_404_not_a_crash(tmp_path: Path) -> None:
    settings = Settings(replay_dir=tmp_path / "none", data_dir=tmp_path, web_dir=tmp_path / "x",
                        evidence_dir=tmp_path, mode="replay", admin_key="")  # fmt: skip
    client = TestClient(create_app(settings))
    assert client.get("/api/fleet").status_code == 404
    assert client.get("/api/runs").json() == []


def test_the_web_build_is_served_with_spa_fallback(parts, tmp_path: Path) -> None:
    _, settings, _ = parts
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>BladeSight</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    web = Settings(**{**settings.__dict__, "web_dir": dist})
    client = TestClient(create_app(web))
    assert "BladeSight" in client.get("/").text
    assert "BladeSight" in client.get("/fleet/T01").text  # client-side route
    assert client.get("/assets/app.js").status_code == 200
    assert client.get("/api/nope").status_code == 404
    assert client.get("/../../etc/passwd").status_code in (200, 404)
    assert "root:" not in client.get("/..%2f..%2fetc%2fpasswd").text


def test_store_is_untouched_by_reads(parts) -> None:
    store, _, client = parts
    before = sorted(p.name for p in store.root.rglob("*.json"))
    client.get("/api/fleet")
    assert before == sorted(p.name for p in store.root.rglob("*.json"))
    assert isinstance(store, Store)


def test_the_uvicorn_target_is_the_application_not_a_module() -> None:
    """Regression: `bladesight.api:app` once resolved to a submodule named `app`."""
    import importlib

    from fastapi import FastAPI

    assert isinstance(importlib.import_module("bladesight.api").app, FastAPI)


def test_odd_inputs_do_not_crash_the_server(parts, tmp_path: Path) -> None:
    _, settings, _ = parts
    dist = tmp_path / "dist2"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>BladeSight</title>", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("TOP-SECRET", encoding="utf-8")
    client = TestClient(create_app(Settings(**{**settings.__dict__, "web_dir": dist})))
    assert client.get("/%00").status_code == 200  # falls back to the index, no 500
    for probe in ["/%2e%2e/secret.txt", "/..%2fsecret.txt"]:
        assert "TOP-SECRET" not in client.get(probe).text
    live = Settings(**{**settings.__dict__, "mode": "live", "admin_key": "s3cret"})
    odd = TestClient(create_app(live)).post("/api/runs", headers={"X-Admin-Key": "clé-ñ".encode()})
    assert odd.status_code == 403  # a non-ASCII key is refused, not a 500


def test_the_environment_default_is_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BLADESIGHT_MODE", raising=False)
    monkeypatch.delenv("META_API_KEY", raising=False)
    assert Settings().mode == "replay" and Settings().admin_key == ""
