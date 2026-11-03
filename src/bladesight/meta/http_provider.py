"""HTTP provider for the Meta Model API (Responses format) and Baseten (chat completions).

Wire format follows Meta's docs (dev.meta.ai/docs): `POST {base}/v1/responses` with bearer auth.
Muse Spark takes `input` messages of `input_text` / `input_image` parts (images only in user
messages); SAM 3.1 takes ONE `input_text` concept plus an `input_image` and answers with
special-token text parsed by `meta-sam-parser`. Images are public URLs or base64 data URLs, so no
`/v1/files` upload is needed (that endpoint is for video only).

Baseten (docs.baseten.co) uses the OpenAI Chat Completions format at
`https://inference.baseten.co/v1`; its reasoning is always on and counts as output tokens, and its
429/529 responses are retried with backoff while 402 (payment required) is permanent.

Confirmed by real calls (docs/evidence/meta-api-step1.md): the Muse Spark request and `usage`
shape (reasoning tokens are inside `output_tokens`), `max_output_tokens`, `store: false` and
`reasoning.effort: "low"`, public image URLs, non-streaming SAM, SAM's zero-match reply
(`output_text == ""`), and real SAM masks: one-bit `!` payloads with a per-record `c=` confidence,
box `x2`/`y2` inclusive, `w`/`h` equal to the source image size, and a mask raster exactly the size
of its box (placed at the box's top-left; checked visually on two photos).

Still unconfirmed: `temperature` and the tool-call item shapes on Meta Responses, whether
`input_tokens` includes the cached tokens, `store` on SAM requests, effort values below "low", and
the IMAGE INPUT FORMAT for Baseten (we send an OpenAI-style `image_url` data URL)
(docs/limitations.md, #2).
"""

from __future__ import annotations

import io
import json
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any, Literal

import httpx
import numpy as np
from meta_sam_parser import (
    CompletedOutcome,
    InvalidSegmentationMaskError,
    ResponsesStreamError,
    SegmentationMaskRecord,
    decode_mask_to_raster,
    image_segmentation_format,
)
from PIL import Image, UnidentifiedImageError
from pydantic import SecretStr, ValidationError

from .errors import (
    MetaAuthError,
    MetaConfigError,
    MetaConnectionError,
    MetaError,
    MetaInvalidResponseError,
    MetaModelNotFoundError,
    MetaPaymentRequiredError,
    MetaRateLimitError,
    MetaRequestError,
    MetaServerError,
    MetaTimeoutError,
)
from .models import (
    ChatMessage,
    ChatRequest,
    ChatResult,
    ImagePart,
    SegmentMask,
    SegmentRequest,
    SegmentResult,
    TextPart,
    ToolCall,
    Usage,
)

DEFAULT_TIMEOUT_S = 60.0
CONNECT_TIMEOUT_S = 10.0
BODY_SNIPPET_CHARS = 200

SUPPORTED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp"})
MAX_IMAGES_PER_REQUEST = 50
MAX_INLINE_BYTES = 50 * 1024 * 1024

ChatFormat = Literal["responses", "chat_completions"]
CHAT_PATHS: dict[ChatFormat, str] = {
    "responses": "/v1/responses",
    "chat_completions": "/v1/chat/completions",
}
RESPONSES_PATH = "/v1/responses"
SAM_METADATA = {"mask_encoding": "one_bit", "include_confidence": "true"}

_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)(ms|s|m|h)")
_DURATION_UNITS = {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0}
_FRAME_W = re.compile(r"<\|box;[^|]*?\bw=(\d+)")
_FRAME_H = re.compile(r"<\|box;[^|]*?\bh=(\d+)")


def join_url(base_url: str, path: str) -> str:
    """Join a base URL and an absolute API path (`/v1/...`).

    Accepts a base with or without a trailing slash and with or without a trailing `/v1`, so
    `https://api.meta.ai`, `https://api.meta.ai/` and `https://api.meta.ai/v1` all give
    `https://api.meta.ai/v1/responses` instead of a doubled `/v1/v1`.
    """
    base = base_url.strip().rstrip("/")
    if base.endswith("/v1") and path.startswith("/v1/"):
        base = base[: -len("/v1")]
    return base + path


class HttpProvider:
    simulated = False

    def __init__(
        self,
        name: str,
        base_url: str,
        api_key: SecretStr | None,
        *,
        timeout: float = DEFAULT_TIMEOUT_S,
        chat_format: ChatFormat = "responses",
        chat_path: str | None = None,
        supports_segment: bool = True,
        allow_contributor: bool = False,
        client: httpx.Client | None = None,
    ) -> None:
        if not base_url:
            raise MetaConfigError(f"{name}: base URL is missing")
        self.name = name
        self._base_url = base_url.strip().rstrip("/")
        self._api_key = api_key
        self._chat_format = chat_format
        self._chat_path = chat_path or CHAT_PATHS[chat_format]
        self._supports_segment = supports_segment
        self._allow_contributor = allow_contributor
        self._http = client or httpx.Client(
            timeout=httpx.Timeout(timeout, connect=min(CONNECT_TIMEOUT_S, timeout))
        )
        # Latest `x-ratelimit-remaining-*` values seen, e.g. {"requests": 14, "tokens": 98000}.
        self.rate_limit_remaining: dict[str, int] = {}

    def __repr__(self) -> str:
        return f"HttpProvider(name={self.name!r}, base_url={self._base_url!r}, api_key=***)"

    # --- transport -------------------------------------------------------------------------

    def _check_model(self, model: str) -> None:
        # Contributor variants are cheaper but Meta may train on the content: opt-in only.
        if "contributor" in model and not self._allow_contributor:
            raise MetaConfigError(
                f"{model}: contributor models let Meta train on the content and are never used "
                "unless allow_contributor=True"
            )

    def _request(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        url = join_url(self._base_url, path)
        if self._api_key is None:
            # Lazy on purpose: a replay (cache-only) client needs no key and never gets here.
            raise MetaConfigError(f"{self.name}: no API key is set; cannot call {path}")
        headers = {"Authorization": f"Bearer {self._api_key.get_secret_value()}"}
        try:
            response = self._http.post(url, headers=headers, json=payload)
        except httpx.TimeoutException:
            raise MetaTimeoutError(f"{self.name}: timeout calling {path}") from None
        except httpx.TransportError as exc:
            raise MetaConnectionError(
                f"{self.name}: network error calling {path} ({type(exc).__name__})"
            ) from None
        request_id = response.headers.get("x-request-id") or response.headers.get("request-id")
        self._note_rate_limits(response.headers)
        if response.status_code >= 400:
            raise self._error_for(response, path, request_id)
        try:
            body = response.json()
        except ValueError:
            raise MetaInvalidResponseError(
                f"{self.name}: {path} returned a non-JSON body",
                status_code=response.status_code,
                request_id=request_id,
            ) from None
        if not isinstance(body, dict):
            raise MetaInvalidResponseError(
                f"{self.name}: {path} returned JSON that is not an object",
                status_code=response.status_code,
                request_id=request_id,
            )
        body.setdefault("_request_id", request_id)
        return body

    def _note_rate_limits(self, headers: httpx.Headers) -> None:
        for name, value in headers.items():
            if name.lower().startswith("x-ratelimit-remaining-"):
                try:
                    self.rate_limit_remaining[
                        name.lower().removeprefix("x-ratelimit-remaining-")
                    ] = int(float(value))
                except ValueError:
                    continue

    def _error_for(self, response: httpx.Response, path: str, request_id: str | None) -> MetaError:
        status = response.status_code
        snippet = response.text[:BODY_SNIPPET_CHARS].replace("\n", " ")
        message = f"{self.name}: {path} failed: {snippet}"
        retry_after = _parse_retry_after(response.headers.get("retry-after"))
        if retry_after is None:  # fall back to the rate-limit reset headers (names unconfirmed)
            retry_after = _rate_limit_reset(response.headers)
        kwargs: dict[str, Any] = {"status_code": status, "request_id": request_id}
        if status in (401, 403):
            return MetaAuthError(f"{self.name}: {path} rejected the credentials", **kwargs)
        if status == 402:
            return MetaPaymentRequiredError(
                f"{self.name}: {path} payment required (add credit or a payment method)", **kwargs
            )
        if status == 404:
            return MetaModelNotFoundError(message, **kwargs)
        if status == 429:
            return MetaRateLimitError(message, retry_after=retry_after, **kwargs)
        if status >= 500:
            return MetaServerError(message, retry_after=retry_after, **kwargs)
        # 429 and 5xx (including Baseten's 529) are retried above; other 4xx, 400 included, are not.
        return MetaRequestError(message, **kwargs)

    # --- chat ------------------------------------------------------------------------------

    def chat(self, request: ChatRequest) -> ChatResult:
        self._check_model(request.model)
        _check_images(request.images())
        if self._chat_format == "responses":
            body = self._request(self._chat_path, _responses_payload(request))
            return self._parse_responses_chat(body, request.model)
        body = self._request(self._chat_path, _completions_payload(request))
        return self._parse_completions_chat(body, request.model)

    def _parse_responses_chat(self, body: dict[str, Any], model: str) -> ChatResult:
        request_id = body.get("_request_id") or body.get("id")
        try:
            output = _output_items(body)
            texts: list[str] = []
            tool_calls: list[ToolCall] = []
            for item in output:  # "reasoning" items are skipped; their tokens are in usage
                if item.get("type") == "message":
                    texts += _message_texts(item)
                elif item.get("type") == "function_call":
                    tool_calls.append(
                        ToolCall(
                            id=item["call_id"],
                            name=item["name"],
                            arguments=json.loads(item.get("arguments") or "{}"),
                        )
                    )
            if not texts and not tool_calls and body.get("status") != "incomplete":
                raise ValueError("output has no message or function call")
            usage = body.get("usage") or {}
            return ChatResult(
                text="".join(texts),
                tool_calls=tool_calls,
                usage=_token_usage(
                    usage,
                    "input_tokens",
                    "output_tokens",
                    (usage.get("input_tokens_details") or {}).get("cached_tokens"),
                ),
                model=str(body.get("model") or model),
                request_id=request_id,
                status=str(body.get("status") or "completed"),
            )
        except (KeyError, TypeError, AttributeError, ValueError, ValidationError):
            raise MetaInvalidResponseError(
                f"{self.name}: responses output does not match the expected shape",
                request_id=request_id,
            ) from None

    def _parse_completions_chat(self, body: dict[str, Any], model: str) -> ChatResult:
        request_id = body.get("_request_id") or body.get("id")
        try:
            message = body["choices"][0]["message"]
            tool_calls = [
                ToolCall(
                    id=c["id"],
                    name=c["function"]["name"],
                    arguments=json.loads(c["function"].get("arguments") or "{}"),
                )
                for c in message.get("tool_calls") or []
            ]
            usage = body.get("usage") or {}
            return ChatResult(
                text=message.get("content") or "",
                tool_calls=tool_calls,
                usage=_token_usage(
                    usage,
                    "prompt_tokens",
                    "completion_tokens",  # includes reasoning
                    (usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
                ),
                model=str(body.get("model") or model),
                request_id=request_id,
            )
        except (KeyError, IndexError, TypeError, ValueError, ValidationError):
            raise MetaInvalidResponseError(
                f"{self.name}: chat response does not match the expected shape",
                request_id=request_id,
            ) from None

    # --- SAM 3.1 ---------------------------------------------------------------------------

    def segment(self, request: SegmentRequest) -> SegmentResult:
        if not self._supports_segment:
            raise MetaConfigError(f"{self.name}: segmentation is not supported by this provider")
        self._check_model(request.model)
        _check_images([request.image])
        body = self._request(RESPONSES_PATH, _segment_payload(request))
        return self._parse_segment(body, request)

    def _parse_segment(self, body: dict[str, Any], request: SegmentRequest) -> SegmentResult:
        request_id = body.get("_request_id") or body.get("id")
        try:
            text = "".join(
                t
                for item in _output_items(body)
                if item.get("type") == "message"
                for t in _message_texts(item)
            )
            parser = image_segmentation_format().create_parser()
            parser.push(text)
            result = parser.finish(CompletedOutcome()).result
            if any(d.severity == "error" for d in result.diagnostics):
                raise ValueError("segmentation output has malformed records")
            frame_size = _frame_size(text, request.image)
            masks = [
                _to_mask(record, request.concept, frame_size)
                for record in result.records
                if isinstance(record, SegmentationMaskRecord)
            ]
        except (
            KeyError,
            TypeError,
            AttributeError,
            ValueError,
            ResponsesStreamError,
            InvalidSegmentationMaskError,
        ):
            raise MetaInvalidResponseError(
                f"{self.name}: segmentation response does not match the expected shape",
                request_id=request_id,
            ) from None
        # Zero matches is normal: an empty output_text gives an empty list, not an error.
        # SAM reports no tokens; `usage.images_processed` is the per-image count (observed live as
        # 1; per-image billing itself comes from Meta's pricing page). Odd values fall back to 1.
        images = _count((body.get("usage") or {}).get("images_processed"))
        return SegmentResult(
            masks=masks,
            usage=Usage(calls=images if images else 1),
            model=str(body.get("model") or request.model),
            request_id=request_id,
            status=str(body.get("status") or "completed"),
        )


def _count(value: object) -> int | None:
    """A non-negative whole number, or None for anything else (negative, bool, string, 2.5)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float) and value.is_integer() and value >= 0:
        return int(value)
    return None


def _token_usage(usage: dict[str, Any], input_key: str, output_key: str, cached: object) -> Usage:
    """Token usage from a response. A field that is present but not a non-negative whole number
    makes the whole usage unknown (all zero), so the client settles the call at its reservation
    estimate instead of trusting, or being broken by, a hostile or garbled value."""
    raws = (("input", usage.get(input_key)), ("output", usage.get(output_key)), ("cached", cached))
    values: dict[str, int] = {}
    for name, raw in raws:
        if raw is None:
            values[name] = 0
            continue
        counted = _count(raw)
        if counted is None:
            return Usage()
        values[name] = counted
    return Usage(
        input_tokens=values["input"],
        cached_input_tokens=min(values["cached"], values["input"]),
        output_tokens=values["output"],
    )


def _output_items(body: dict[str, Any]) -> list[dict[str, Any]]:
    output = body["output"]
    if not isinstance(output, list):
        raise TypeError("output is not a list")
    if body.get("status") in ("failed", "cancelled"):
        raise ValueError(f"response status is {body['status']}")
    return output


def _message_texts(item: dict[str, Any]) -> list[str]:
    return [c["text"] for c in item.get("content") or [] if c.get("type") == "output_text"]


def _check_images(images: list[ImagePart]) -> None:
    """Client-side checks of the documented input limits, so a bad request never costs a call."""
    if len(images) > MAX_IMAGES_PER_REQUEST:
        raise MetaRequestError(f"too many images: {len(images)} > {MAX_IMAGES_PER_REQUEST}")
    inline = 0
    for image in images:
        if image.data is not None:
            if image.mime_type not in SUPPORTED_IMAGE_TYPES:
                raise MetaRequestError(f"unsupported image type {image.mime_type}")
            inline += len(image.data)
    if inline > MAX_INLINE_BYTES:
        raise MetaRequestError("inline images exceed the 50 MB limit")


def _frame_size(text: str, image: ImagePart) -> tuple[int, int] | None:
    """Source frame size: as the server saw it (box `w`/`h`), else from the local image."""
    w, h = _FRAME_W.search(text), _FRAME_H.search(text)
    if w and h:
        return int(w.group(1)), int(h.group(1))
    if image.data is not None:
        try:
            with Image.open(io.BytesIO(image.data)) as opened:
                return opened.size
        except UnidentifiedImageError:
            return None
    return None


def _to_mask(
    record: SegmentationMaskRecord, concept: str, frame_size: tuple[int, int] | None
) -> SegmentMask:
    mask = record.mask
    raster = np.frombuffer(decode_mask_to_raster(mask), dtype=np.uint8)
    raster = raster.reshape(mask.height, mask.width).astype(bool)
    bounds = record.bounds
    box = (int(bounds.left), int(bounds.top), int(bounds.right), int(bounds.bottom))
    return SegmentMask.from_raster(concept, record.confidence, raster, box, frame_size)


def _responses_payload(request: ChatRequest) -> dict[str, Any]:
    """Meta `/v1/responses` body for Muse Spark."""
    items: list[dict[str, Any]] = []
    for message in request.messages:
        if message.role == "tool":
            text = "".join(p.text for p in message.content if isinstance(p, TextPart))
            items.append(
                {"type": "function_call_output", "call_id": message.tool_call_id, "output": text}
            )
            continue
        text_type = "output_text" if message.role == "assistant" else "input_text"
        parts: list[dict[str, Any]] = []
        for part in message.content:
            if isinstance(part, ImagePart):
                parts.append({"type": "input_image", "image_url": part.image_url()})
            else:
                parts.append({"type": text_type, "text": part.text})
        if parts:
            items.append({"type": "message", "role": message.role, "content": parts})
        items += [
            {
                "type": "function_call",
                "call_id": c.id,
                "name": c.name,
                "arguments": json.dumps(c.arguments),
            }
            for c in message.tool_calls
        ]
    payload: dict[str, Any] = {"model": request.model, "input": items, "stream": False}
    payload["max_output_tokens"] = request.max_tokens
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    if request.reasoning_effort is not None:
        payload["reasoning"] = {"effort": request.reasoning_effort}
    if request.store is not None:
        payload["store"] = request.store
    if request.tools:
        payload["tools"] = [
            {
                "type": "function",
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            }
            for t in request.tools
        ]
    return payload


def _segment_payload(request: SegmentRequest) -> dict[str, Any]:
    """SAM 3.1 body: ONE concept as `input_text` plus the image as `image_url` (no file upload)."""
    return {
        "model": request.model,
        "input": [
            {
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": request.concept},
                    {"type": "input_image", "image_url": request.image.image_url()},
                ],
            }
        ],
        "stream": False,
        "metadata": dict(SAM_METADATA),
    }


def _completions_payload(request: ChatRequest) -> dict[str, Any]:
    """OpenAI chat-completions body, for Baseten."""
    payload: dict[str, Any] = {
        "model": request.model,
        "messages": [_completion_message(m) for m in request.messages],
        "max_tokens": request.max_tokens,
    }
    if request.temperature is not None:
        payload["temperature"] = request.temperature
    if request.tools:
        payload["tools"] = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters,
                },
            }
            for t in request.tools
        ]
    return payload


def _completion_message(message: ChatMessage) -> dict[str, Any]:
    parts: list[dict[str, Any]] = []
    for part in message.content:
        if isinstance(part, ImagePart):
            parts.append({"type": "image_url", "image_url": {"url": part.image_url()}})
        else:
            parts.append({"type": "text", "text": part.text})
    out: dict[str, Any] = {"role": message.role, "content": parts}
    if message.tool_calls:
        out["tool_calls"] = [
            {
                "id": c.id,
                "type": "function",
                "function": {"name": c.name, "arguments": json.dumps(c.arguments)},
            }
            for c in message.tool_calls
        ]
    if message.tool_call_id:
        out["tool_call_id"] = message.tool_call_id
    return out


def _parse_retry_after(value: str | None, now: datetime | None = None) -> float | None:
    """Seconds from a `Retry-After` header: a number, or an HTTP date (RFC 9110)."""
    if value is None:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            when = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        return max(0.0, (when - (now or datetime.now(UTC))).total_seconds())
    return seconds if seconds >= 0 else None


def _parse_duration(value: str) -> float | None:
    """Seconds from `"6"`, `"1.5"` or a Go-style duration such as `"1m30s"` / `"250ms"`."""
    value = value.strip()
    try:
        seconds = float(value)
    except ValueError:
        parts = _DURATION_PART.findall(value)
        if not parts or "".join(n + u for n, u in parts) != value:
            return None
        seconds = sum(float(n) * _DURATION_UNITS[u] for n, u in parts)
    return seconds if seconds >= 0 else None


def _rate_limit_reset(headers: httpx.Headers) -> float | None:
    waits = [
        w
        for name, value in headers.items()
        if name.lower().startswith("x-ratelimit-reset")
        and (w := _parse_duration(value)) is not None
    ]
    return max(waits) if waits else None
