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
    "needle", ["BLADESIGHT_MODE=replay", "--locked --no-dev", "bladesight.data.demo"]
)
def test_dockerfile_is_replay_only_and_never_copies_data_or_secrets(needle: str) -> None:
    text = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert needle in text
    assert "COPY data" not in text and ".env" not in text.replace("BLADESIGHT_", "")
    ignore = (ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "data" in ignore.split() and ".env" in ignore.split()


def test_render_blueprint_sets_replay_and_a_health_check_and_no_secret() -> None:
    text = (ROOT / "render.yaml").read_text(encoding="utf-8")
    assert "healthCheckPath: /api/health" in text and "value: replay" in text
    for secret_name in ("META_API_KEY", "BASETEN_API_KEY", "BLADESIGHT_ADMIN_KEY", "sk-"):
        assert secret_name not in text
