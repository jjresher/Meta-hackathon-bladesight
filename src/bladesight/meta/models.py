"""Request and response models shared by the client, the providers and the stub."""

from __future__ import annotations

import base64
import hashlib
from typing import Annotated, Any, Literal

import numpy as np
from pydantic import BaseModel, Field, field_validator, model_validator


class Usage(BaseModel):
    """Token counts as the provider reports them.

    `output_tokens` includes reasoning tokens (confirmed on a real Muse Spark response: 711 output
    tokens of which 686 were reasoning). ASSUMPTION, UNCONFIRMED: `input_tokens` includes
    `cached_input_tokens` (the cost math bills the cached part at the cached rate and the rest at
    the input rate; if the API reports them separately, cost is understated). The first real
    response had `cached_tokens == 0`, so it did not settle this.
    """

    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 1


class TextPart(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ImagePart(BaseModel):
    """An image given as bytes (sent as a base64 data URL) or as a public URL."""

    type: Literal["image"] = "image"
    data: bytes | None = None
    url: str | None = None
    mime_type: str = "image/jpeg"

    @model_validator(mode="after")
    def _exactly_one_source(self) -> ImagePart:
        if (self.data is None) == (self.url is None):
            raise ValueError("an image needs exactly one of data or url")
        return self

    def image_url(self) -> str:
        """The value of the API's `image_url` field: the public URL or a data URL."""
        if self.url is not None:
            return self.url
        assert self.data is not None
        return f"data:{self.mime_type};base64,{base64.b64encode(self.data).decode('ascii')}"

    def cache_payload(self) -> dict[str, str]:
        if self.url is not None:
            return {"type": "image", "url": self.url}
        assert self.data is not None
        return {
            "type": "image",
            "sha256": hashlib.sha256(self.data).hexdigest(),
            "mime_type": self.mime_type,
        }


Part = Annotated[TextPart | ImagePart, Field(discriminator="type")]


class ToolSpec(BaseModel):
    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=lambda: {"type": "object", "properties": {}})


class ToolCall(BaseModel):
    id: str
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: list[Part] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    tool_call_id: str | None = None

    @field_validator("content", mode="before")
    @classmethod
    def _wrap_text(cls, value: Any) -> Any:
        return [{"type": "text", "text": value}] if isinstance(value, str) else value

    @model_validator(mode="after")
    def _images_only_from_the_user(self) -> ChatMessage:
        if self.role != "user" and any(isinstance(p, ImagePart) for p in self.content):
            raise ValueError("images are only allowed in user messages")
        return self

    @classmethod
    def of(
        cls,
        role: Literal["system", "user", "assistant", "tool"],
        text: str = "",
        *,
        tool_calls: list[ToolCall] | None = None,
        tool_call_id: str | None = None,
    ) -> ChatMessage:
        content: list[Part] = [TextPart(text=text)] if text else []
        return cls(
            role=role, content=content, tool_calls=tool_calls or [], tool_call_id=tool_call_id
        )

    @classmethod
    def user(cls, text: str, *images: ImagePart) -> ChatMessage:
        return cls(role="user", content=[TextPart(text=text), *images])

    def cache_payload(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": [
                p.cache_payload() if isinstance(p, ImagePart) else p.model_dump()
                for p in self.content
            ],
            "tool_calls": [c.model_dump() for c in self.tool_calls],
            "tool_call_id": self.tool_call_id,
        }


class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    tools: list[ToolSpec] = Field(default_factory=list)
    temperature: float | None = None  # omitted from the request when None
    reasoning_effort: str | None = None  # sent as {"reasoning": {"effort": ...}} when set
    max_tokens: int = 1024  # sent as max_output_tokens; reasoning tokens count toward it

    def images(self) -> list[ImagePart]:
        return [p for m in self.messages for p in m.content if isinstance(p, ImagePart)]

    def cache_payload(self) -> dict[str, Any]:
        return {
            "messages": [m.cache_payload() for m in self.messages],
            "tools": [t.model_dump() for t in self.tools],
            "temperature": self.temperature,
            "reasoning_effort": self.reasoning_effort,
            "max_tokens": self.max_tokens,
        }


class ChatResult(BaseModel):
    text: str = ""
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    model: str = ""
    request_id: str | None = None


class SegmentRequest(BaseModel):
    """One image and ONE concept (a short noun phrase). SAM 3.1 takes a single concept per call."""

    model: str
    image: ImagePart
    concept: str = Field(min_length=1)
    threshold: float = 0.5  # applied to the model's confidence after the cache, not sent

    @field_validator("concept")
    @classmethod
    def _single_noun_phrase(cls, value: str) -> str:
        value = value.strip()
        if not value or any(c in value for c in ",;\n") or " and " in f" {value} ":
            raise ValueError(
                "SAM takes one short noun phrase per request; send one request per concept"
            )
        return value

    def cache_payload(self) -> dict[str, Any]:
        return {"image": self.image.cache_payload(), "concept": self.concept}


class SegmentMask(BaseModel):
    """One mask. The raster covers exactly `box` (left, top, right, bottom; half-open, source px).

    `packed` is the raster as base64 packed bits, so it round-trips through the JSON cache.
    `score` is the model's confidence in 0-1, or None when the response carried none.
    """

    concept: str
    score: float | None
    box: tuple[int, int, int, int]
    width: int
    height: int
    packed: str
    frame_width: int | None = None
    frame_height: int | None = None

    @classmethod
    def from_raster(
        cls,
        concept: str,
        score: float | None,
        raster: np.ndarray,
        box: tuple[int, int, int, int],
        frame_size: tuple[int, int] | None = None,
    ) -> SegmentMask:
        bits = np.asarray(raster, dtype=bool)
        height, width = bits.shape
        left, top, right, bottom = box
        if (right - left, bottom - top) != (width, height):
            raise ValueError("raster size does not match the box")
        return cls(
            concept=concept,
            score=score,
            box=box,
            width=width,
            height=height,
            packed=base64.b64encode(np.packbits(bits).tobytes()).decode("ascii"),
            frame_width=frame_size[0] if frame_size else None,
            frame_height=frame_size[1] if frame_size else None,
        )

    @classmethod
    def from_frame_array(cls, concept: str, score: float | None, frame: np.ndarray) -> SegmentMask:
        """Build from a full-frame boolean array by cropping to its bounding box."""
        frame = np.asarray(frame, dtype=bool)
        rows, cols = np.where(frame)
        if rows.size == 0:
            raise ValueError("an empty mask has no box")
        top, bottom = int(rows.min()), int(rows.max()) + 1
        left, right = int(cols.min()), int(cols.max()) + 1
        height, width = frame.shape
        return cls.from_raster(
            concept,
            score,
            frame[top:bottom, left:right],
            (left, top, right, bottom),
            (width, height),
        )

    def array(self) -> np.ndarray:
        """The raster, `height` x `width`, covering `box`."""
        bits = np.unpackbits(np.frombuffer(base64.b64decode(self.packed), dtype=np.uint8))
        return bits[: self.width * self.height].reshape(self.height, self.width).astype(bool)

    def frame_array(self) -> np.ndarray:
        """The mask placed on a full source-size frame."""
        if self.frame_width is None or self.frame_height is None:
            raise ValueError("the source frame size is unknown for this mask")
        frame = np.zeros((self.frame_height, self.frame_width), dtype=bool)
        left, top, right, bottom = self.box
        frame[top:bottom, left:right] = self.array()
        return frame

    @property
    def area(self) -> int:
        return int(self.array().sum())


class SegmentResult(BaseModel):
    masks: list[SegmentMask] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)
    model: str = ""
    request_id: str | None = None


class CallRecord(BaseModel):
    """What one client call did. `source` proves where the answer came from (meta-api-check).

    A stub call reports `cost_usd=0.0` (it spends nothing); the cost it would have had is in
    `simulated_cost_usd` so cap logic stays testable. `price_documented` is True when the rate comes
    from the provider's published pricing (not checked against an invoice) and False for a
    placeholder or the conservative default. `cost_from_estimate` is True when the response carried
    no usable usage, so the call was settled at its worst-case reservation instead.
    """

    operation: Literal["chat", "segment"]
    provider: str
    model: str
    source: Literal["live", "cache", "stub"]
    attempts: int = 1
    retried_codes: list[str] = Field(default_factory=list)
    cost_usd: float = 0.0
    simulated_cost_usd: float = 0.0
    price_documented: bool = True
    cost_from_estimate: bool = False
    request_id: str | None = None
    response_model: str = ""
