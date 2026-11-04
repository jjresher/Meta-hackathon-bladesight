"""Gold-set selection and the CSV labelling store (no server, no images)."""

from __future__ import annotations

from pathlib import Path

import pytest

from bladesight.data import TileLabel
from bladesight.eval.gold import (
    FIELDS,
    page,
    read_rows,
    select_gold,
    set_severity,
    write_rows,
)


def _tiles() -> list[TileLabel]:
    tiles = []
    for p in range(200):
        side = 8 + (p % 20) * 3  # box sizes from 64 to 1000+ px^2
        tiles.append(
            TileLabel.model_validate(
                {
                    "tile_id": f"DJI_{p:04d}_01_01",
                    "source_photo": f"DJI_{p:04d}",
                    "row": 1,
                    "col": 1,
                    "width": 586,
                    "height": 371,
                    "boxes": [
                        {"label": "damage", "x1": 10, "y1": 10, "x2": 10 + side, "y2": 10 + side},
                        {"label": "dirt", "x1": 100, "y1": 100, "x2": 200, "y2": 200},
                    ],
                }
            )
        )
    return tiles


def test_select_gold_is_reproducible_blind_and_spread_over_sizes() -> None:
    rows = select_gold(_tiles())
    assert rows == select_gold(_tiles()) and len(rows) == 40
    assert all(r["label"] == "damage" and r["severity"] == "" for r in rows)
    assert len({r["tile_id"][:8] for r in rows}) == 40  # one box per source photo
    sizes = sorted((float(r["x2"]) - float(r["x1"])) for r in rows)
    assert sizes[0] < 20 and sizes[-1] > 40  # small and large crops both present
    assert list(rows[0]) == FIELDS and rows == sorted(rows, key=lambda r: r["crop_id"])


def test_csv_roundtrip_and_labelling(tmp_path: Path) -> None:
    path = tmp_path / "severity.csv"
    write_rows(select_gold(_tiles()), path)
    first = read_rows(path)[0]["crop_id"]
    set_severity(path, first, "4", "open crack")
    assert read_rows(path)[0]["severity"] == "4" and read_rows(path)[0]["note"] == "open crack"
    set_severity(path, first, "0")
    assert read_rows(path)[0]["severity"] == "0"  # unreadable
    set_severity(path, first, "")
    assert read_rows(path)[0]["severity"] == ""
    assert len(read_rows(path)) == 40


@pytest.mark.parametrize("bad", ["6", "x", "-1", "10"])
def test_bad_values_and_unknown_ids_are_rejected(tmp_path: Path, bad: str) -> None:
    path = tmp_path / "severity.csv"
    write_rows(select_gold(_tiles()), path)
    with pytest.raises(ValueError):
        set_severity(path, read_rows(path)[0]["crop_id"], bad)
    with pytest.raises(ValueError):
        set_severity(path, "DJI_9999_01_01#0", "3")


def test_the_page_never_mentions_model_grades() -> None:
    html = page().decode()
    assert "model" in html.lower()  # only to say the grades are hidden
    assert "/api/label" in html and "Backspace" in html


def _serve(tmp_path: Path):
    import io
    import threading

    from PIL import Image

    from bladesight.eval.gold import make_server

    csv_path = tmp_path / "severity.csv"
    write_rows(select_gold(_tiles()), csv_path)
    first = read_rows(csv_path)[0]
    (tmp_path / "dev" / "img").mkdir(parents=True)
    buffer = io.BytesIO()
    Image.new("RGB", (586, 371), (90, 90, 90)).save(buffer, format="PNG")
    (tmp_path / "dev" / "img" / f"{first['tile_id']}.png").write_bytes(buffer.getvalue())
    server = make_server(tmp_path, csv_path, 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, csv_path, first


def _request(
    server, method: str, path: str, body: bytes | None = None, headers: dict | None = None
):
    import http.client

    port = server.server_address[1]
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    base = {"Host": f"127.0.0.1:{port}"}
    conn.request(method, path, body=body, headers={**base, **(headers or {})})
    response = conn.getresponse()
    data = response.read()
    conn.close()
    return response.status, data


def test_server_serves_crops_and_saves_labels_but_refuses_foreign_posts(tmp_path: Path) -> None:
    import json

    server, csv_path, first = _serve(tmp_path)
    try:
        assert _request(server, "GET", "/")[0] == 200
        status, data = _request(server, "GET", "/crop/0/close")
        assert status == 200 and data.startswith(b"\x89PNG")
        assert _request(server, "GET", "/crop/-1/close")[0] == 404
        assert _request(server, "GET", "/crop/0/other")[0] == 404
        body = json.dumps({"crop_id": first["crop_id"], "severity": "4"}).encode()
        json_headers = {"Content-Type": "application/json", "Content-Length": str(len(body))}
        assert _request(server, "POST", "/api/label", body, json_headers)[0] == 200
        assert read_rows(csv_path)[0]["severity"] == "4"
        # a page on another site: wrong Origin, or a simple text/plain request, is refused
        evil = {**json_headers, "Origin": "http://evil.example"}
        assert _request(server, "POST", "/api/label", body, evil)[0] == 403
        plain = {"Content-Type": "text/plain", "Content-Length": str(len(body))}
        assert _request(server, "POST", "/api/label", body, plain)[0] == 403
        rebinding = {**json_headers, "Host": "evil.example"}
        assert _request(server, "POST", "/api/label", body, rebinding)[0] == 403
        bad = json.dumps({"crop_id": first["crop_id"], "severity": "9"}).encode()
        bad_headers = {"Content-Type": "application/json", "Content-Length": str(len(bad))}
        assert _request(server, "POST", "/api/label", bad, bad_headers)[0] == 400
        assert read_rows(csv_path)[0]["severity"] == "4"
    finally:
        server.shutdown()
        server.server_close()


def test_relabelling_keeps_a_hand_written_note(tmp_path: Path) -> None:
    path = tmp_path / "severity.csv"
    write_rows(select_gold(_tiles()), path)
    crop = read_rows(path)[1]["crop_id"]
    set_severity(path, crop, "3", 'looks like "paint", loss, \nsecond line')
    set_severity(path, crop, "4")
    row = read_rows(path)[1]
    assert row["severity"] == "4" and row["note"] == 'looks like "paint", loss, \nsecond line'


def test_select_gold_refuses_to_return_fewer_crops_than_asked() -> None:
    with pytest.raises(ValueError):
        select_gold(_tiles()[:20])


def test_the_crops_the_labeller_saw_are_frozen() -> None:
    """Pinned hashes: if these change, the model is compared on other images than the human saw."""
    import hashlib
    import io

    from PIL import Image

    from bladesight.contracts import BBox
    from bladesight.eval.gold import _frozen_crop

    image = Image.new("RGB", (586, 371))
    for x in range(586):
        for y in range(371):
            image.putpixel((x, y), ((x * 7) % 256, (y * 11) % 256, ((x + y) * 3) % 256))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    box = BBox(x1=100, y1=80, x2=140, y2=95)
    close = hashlib.sha256(_frozen_crop(buffer.getvalue(), box, 0.4, 40.0)).hexdigest()
    wide = hashlib.sha256(_frozen_crop(buffer.getvalue(), box, 3.0, 96.0)).hexdigest()
    assert close == "33181fe83b48c47261de5e695bcbc98968747e84ba950b675c8362ca3265010e"
    assert wide == "403cde2824270ce32901a478a396c9e7d3cd096f7975693062b054e5e867b8c3"
