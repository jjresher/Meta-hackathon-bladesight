from pathlib import Path

import numpy as np
import pytest
from conftest import chat_request, make_image_bytes, segment_request

from bladesight.meta import (
    CacheMissError,
    DiskCache,
    ImagePart,
    MetaClient,
    SpendTracker,
    StubProvider,
    cache_key,
)


def make_client(tmp_path: Path, stub: StubProvider | None = None, **kwargs: object) -> MetaClient:
    return MetaClient(
        stub or StubProvider(),
        spend=SpendTracker.unlimited(),
        cache=DiskCache(tmp_path / "cache"),
        sleep=lambda _s: None,
        **kwargs,  # type: ignore[arg-type]
    )


def test_miss_then_hit_skips_the_provider(tmp_path: Path) -> None:
    stub = StubProvider()
    client = make_client(tmp_path, stub)

    first = client.chat(chat_request("same"))
    second = client.chat(chat_request("same"))

    assert second == first
    assert stub.call_count == 1
    assert [r.source for r in client.records] == ["stub", "cache"]
    assert client.records[1].cost_usd == 0
    assert client.records[1].simulated_cost_usd == 0


def test_different_payload_is_a_different_entry(tmp_path: Path) -> None:
    stub = StubProvider()
    client = make_client(tmp_path, stub)
    client.chat(chat_request("one"))
    client.chat(chat_request("two"))
    client.chat(chat_request("one", model="muse-spark-1.2"))
    assert stub.call_count == 3


def test_cache_survives_a_new_client(tmp_path: Path) -> None:
    make_client(tmp_path).chat(chat_request())
    stub = StubProvider()
    make_client(tmp_path, stub).chat(chat_request())
    assert stub.call_count == 0


def test_no_cache_bypasses_reads_and_writes(tmp_path: Path) -> None:
    stub = StubProvider()
    client = make_client(tmp_path, stub, use_cache=False)
    client.chat(chat_request())
    client.chat(chat_request())
    assert stub.call_count == 2
    assert not (tmp_path / "cache").exists()


def test_cache_only_miss_raises_without_calling(tmp_path: Path) -> None:
    stub = StubProvider()
    client = make_client(tmp_path, stub, cache_only=True)
    with pytest.raises(CacheMissError):
        client.chat(chat_request())
    assert stub.call_count == 0


def test_cache_only_serves_hits(tmp_path: Path) -> None:
    make_client(tmp_path).chat(chat_request())
    stub = StubProvider()
    client = make_client(tmp_path, stub, cache_only=True)
    assert client.chat(chat_request()).text == "stub response"
    assert stub.call_count == 0


def test_corrupt_entry_is_a_miss_and_is_replaced(tmp_path: Path) -> None:
    client = make_client(tmp_path)
    client.chat(chat_request())
    (entry,) = (tmp_path / "cache").rglob("*.json")
    entry.write_text("{not json", encoding="utf-8")

    stub = StubProvider()
    make_client(tmp_path, stub).chat(chat_request())

    assert stub.call_count == 1
    assert "stub response" in entry.read_text(encoding="utf-8")


def test_key_depends_on_image_bytes_not_identity() -> None:
    a = ImagePart(data=make_image_bytes(color=1), mime_type="image/png")
    b = ImagePart(data=make_image_bytes(color=1), mime_type="image/png")
    c = ImagePart(data=make_image_bytes(color=2), mime_type="image/png")

    def key(img: ImagePart) -> str:
        req = chat_request("look", img)
        return cache_key("meta/chat", req.model, req.cache_payload())

    assert key(a) == key(b)
    assert key(a) != key(c)


def test_key_depends_on_image_url() -> None:
    def key(url: str) -> str:
        req = chat_request("look", ImagePart(url=url))
        return cache_key("meta/chat", req.model, req.cache_payload())

    assert key("https://x.test/a.jpg") == key("https://x.test/a.jpg")
    assert key("https://x.test/a.jpg") != key("https://x.test/b.jpg")


def test_key_depends_on_endpoint() -> None:
    req = chat_request()
    assert cache_key("meta/chat", req.model, req.cache_payload()) != cache_key(
        "baseten/chat", req.model, req.cache_payload()
    )


def test_segment_mask_round_trips_through_the_cache(tmp_path: Path, image: ImagePart) -> None:
    client = make_client(tmp_path)
    live = client.segment(segment_request(image, "crack"))
    cached = client.segment(segment_request(image, "crack"))

    assert client.records[1].source == "cache"
    assert cached.masks[0].concept == "crack"
    assert np.array_equal(cached.masks[0].array(), live.masks[0].array())
    assert np.array_equal(cached.masks[0].frame_array(), live.masks[0].frame_array())
    assert cached.masks[0].area == 16 * 8  # central quarter of a 32x16 image


def test_threshold_is_applied_after_the_cache_so_sweeps_are_free(
    tmp_path: Path, image: ImagePart
) -> None:
    stub = StubProvider()  # its mask has confidence 0.9
    client = make_client(tmp_path, stub)

    kept = client.segment(segment_request(image, threshold=0.5))
    dropped = client.segment(segment_request(image, threshold=0.95))

    assert len(kept.masks) == 1
    assert dropped.masks == []
    assert stub.call_count == 1  # the second threshold was served from the cache
