"""Demo-tile streaming, the smoke check and the deploy files, with no network."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from fleet_fixtures import make_store

from bladesight.api import Settings, create_app
from bladesight.api.smoke import check
from bladesight.data.demo import _Stream, extract_from_stream, tile_ids_from_replay

ROOT = Path(__file__).resolve().parents[1]


def _tar(names: list[str]) -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for name in names:
            payload = f"png:{name}".encode()
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            archive.addfile(info, io.BytesIO(payload))
    return buffer.getvalue()


def test_extract_only_the_wanted_tiles_from_a_stream_and_stop_early(tmp_path: Path) -> None:
    names = ["ds/ann/DJI_0001_01_01.png.json"] + [
        f"ds/img/DJI_{i:04d}_01_01.png" for i in range(1, 30)
    ]
    data = _tar(names)
    chunks = iter([data[i : i + 700] for i in range(0, len(data), 700)])  # awkward chunk size
    wanted = {"DJI_0003_01_01", "DJI_0005_01_01", "DJI_9999_01_01"}
    found = extract_from_stream(_Stream(chunks), wanted, tmp_path)
    assert found == {"DJI_0003_01_01", "DJI_0005_01_01"}
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "DJI_0003_01_01.png",
        "DJI_0005_01_01.png",
    ]
    assert (tmp_path / "DJI_0003_01_01.png").read_bytes() == b"png:ds/img/DJI_0003_01_01.png"


def test_extraction_ignores_traversal_and_foreign_members(tmp_path: Path) -> None:
    data = _tar(
        ["ds/img/../../evil.png", "other/img/DJI_0003_01_01.png", "ds/img/DJI_0003_01_01.txt"]
    )
    found = extract_from_stream(io.BytesIO(data), {"DJI_0003_01_01"}, tmp_path / "out")
    assert found == set() and not (tmp_path / "evil.png").exists()


def test_tile_ids_come_from_the_replay_store(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    assert tile_ids_from_replay(store.root) == {"DJI_0001_01_01"}


def test_smoke_check_passes_on_a_good_app_and_fails_on_an_empty_one(tmp_path: Path) -> None:
    store = make_store(tmp_path)
    data = tmp_path / "data" / "dev" / "img"
    data.mkdir(parents=True)
    (data / "DJI_0001_01_01.png").write_bytes(b"\x89PNG\r\n\x1a\n")
    web = tmp_path / "dist"
    web.mkdir()
    (web / "index.html").write_text("<!doctype html>", encoding="utf-8")
    good = Settings(replay_dir=store.root, data_dir=tmp_path / "data", web_dir=web,
                    evidence_dir=tmp_path, mode="replay", admin_key="")  # fmt: skip
    assert check(TestClient(create_app(good))) == []
    empty = Settings(replay_dir=tmp_path / "none", data_dir=tmp_path, web_dir=tmp_path / "x",
                     evidence_dir=tmp_path, mode="replay", admin_key="")  # fmt: skip
    failures = check(TestClient(create_app(empty)))
    assert any("/api/fleet" in f for f in failures)


@pytest.mark.parametrize(
    "needle", ["BLADESIGHT_MODE=replay", "--locked --no-dev", "bladesight.data.demo --strict"]
)
def test_dockerfile_is_replay_only_and_never_copies_data_or_secrets(needle: str) -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert needle in text
    assert "COPY data" not in text and ".env" not in text.replace("BLADESIGHT_", "")
    ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "data" in ignore.split() and "**/.env" in ignore.split()


def test_render_blueprint_sets_replay_and_a_health_check_and_no_secret() -> None:
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "healthCheckPath: /api/health" in text and "value: replay" in text
    assert "plan: free" in text and "autoDeployTrigger: commit" in text
    assert "starter" not in text and "autoDeploy:" not in text  # not a valid plan / deprecated key
    for secret_name in ("META_API_KEY", "BASETEN_API_KEY", "BLADESIGHT_ADMIN_KEY", "sk-"):
        assert secret_name not in text


def test_a_web_dir_without_an_index_does_not_break_the_api(tmp_path: Path) -> None:
    """Regression found running the Docker image: an empty web/dist made `/` answer 500."""
    store = make_store(tmp_path)
    empty = tmp_path / "dist"
    empty.mkdir()
    settings = Settings(replay_dir=store.root, data_dir=tmp_path, web_dir=empty,
                        evidence_dir=tmp_path, mode="replay", admin_key="")  # fmt: skip
    client = TestClient(create_app(settings))
    assert client.get("/").status_code == 404
    assert client.get("/api/health").status_code == 200
    assert [f for f in check(client, ui=False) if "/api/fleet" in f or "/api/health" in f] == []


def test_a_held_out_tile_in_the_replay_store_is_refused(tmp_path: Path) -> None:
    from bladesight.data import demo

    store = make_store(tmp_path)
    manifest = tmp_path / "manifest.sha256"
    manifest.write_text("0" * 64 + "  heldout/img/DJI_0001_01_01.png\n", encoding="utf-8")
    assert demo.heldout_ids(manifest) == {"DJI_0001_01_01"}
    original = demo.HELDOUT_MANIFEST
    demo.HELDOUT_MANIFEST = manifest
    try:
        with pytest.raises(ValueError):
            demo.tile_ids_from_replay(store.root)
    finally:
        demo.HELDOUT_MANIFEST = original


def test_a_failed_download_degrades_to_a_warning(tmp_path: Path, monkeypatch) -> None:
    import httpx

    from bladesight.data import demo

    store = make_store(tmp_path)
    monkeypatch.setattr(
        demo, "fetch", lambda *a, **k: (_ for _ in ()).throw(httpx.ConnectError("x"))
    )
    args = ["--replay-dir", str(store.root), "--data-dir", str(tmp_path / "d")]
    assert demo.main(args) == 0
    assert demo.main(["--strict", *args]) == 1


def test_strict_fails_the_build_on_a_partial_download(tmp_path: Path, monkeypatch) -> None:
    from bladesight.data import demo

    store = make_store(tmp_path)
    args = ["--replay-dir", str(store.root), "--data-dir", str(tmp_path / "d")]
    monkeypatch.setattr(demo, "fetch", lambda *a, **k: (12, 96))
    assert demo.main(args) == 0
    assert demo.main(["--strict", *args]) == 1
    monkeypatch.setattr(demo, "fetch", lambda *a, **k: (96, 96))
    assert demo.main(["--strict", *args]) == 0
