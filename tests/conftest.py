import io
import os
from pathlib import Path

import pytest
from PIL import Image

from bladesight.meta import ChatMessage, ChatRequest, ImagePart, SegmentRequest

# Two records in SAM 3.1's wire format, taken from the meta-sam-parser docs: a 60x27 mask at
# (211, 228) with confidence 0.96, and a 48x27 mask at (155, 228) without a confidence. Frame is
# 320x334.
SAM_TEXT = (
    "<0f>0<|box;x1=211;y1=228;x2=270;y2=254;w=320;h=334;c=0.96|>"
    "<|mask;x=0;y=0;c=0.96;data=27,60,~!!!!M!0c[0o91w?q1!pIH4pPRVp2B3'7`e.ioeAf6-k/#Xd8%dX9x(|>"
    ",1<|box;x1=155;y1=228;x2=202;y2=254;w=320;h=334|>"
    "<|mask;x=0;y=0;data=27,48,~!!!!J!0c[q=Pj_zs=*4C4(/./x#:/`S_GnD`=o3?X{emCgO$y@|>\n"
)
SAM_FIRST_MASK_AREA = 1539


@pytest.fixture(autouse=True)
def _isolated_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No test may read the real .env or write the real cache or spend log."""
    for name in list(os.environ):
        if name.startswith(("META_", "BASETEN_", "BLADESIGHT_")):
            monkeypatch.delenv(name)
    monkeypatch.setenv("BLADESIGHT_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("BLADESIGHT_SPEND_LOG", str(tmp_path / "spend_log.jsonl"))


def make_image_bytes(
    width: int = 32, height: int = 16, color: int = 128, fmt: str = "PNG"
) -> bytes:
    buffer = io.BytesIO()
    Image.new("L", (width, height), color).save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.fixture
def image() -> ImagePart:
    return ImagePart(data=make_image_bytes(), mime_type="image/png")


def chat_request(
    prompt: str = "hello",
    *images: ImagePart,
    model: str = "muse-spark-1.3",
    max_tokens: int = 256,
) -> ChatRequest:
    return ChatRequest(
        model=model, messages=[ChatMessage.user(prompt, *images)], max_tokens=max_tokens
    )


def segment_request(
    image: ImagePart, concept: str = "crack", threshold: float = 0.5
) -> SegmentRequest:
    return SegmentRequest(model="sam-3.1", image=image, concept=concept, threshold=threshold)
