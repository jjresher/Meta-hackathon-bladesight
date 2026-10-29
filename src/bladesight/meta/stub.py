"""Deterministic provider for tests and CI: no network, no money.

Responses are canned (or supplied by the test) and failures can be scripted, so retry, cache and
spend-cap behavior is exercised without any real call. Its calls report 0 real USD; the cost they
would have had is tagged as simulated.
"""

from __future__ import annotations

import io
import time
from collections import deque
from collections.abc import Iterable

import numpy as np
from PIL import Image

from .models import (
    ChatRequest,
    ChatResult,
    SegmentMask,
    SegmentRequest,
    SegmentResult,
    Usage,
)

STUB_REQUEST_ID = "stub-request"
URL_IMAGE_SIZE = (100, 100)


class StubProvider:
    name = "stub"
    simulated = True

    def __init__(
        self,
        *,
        chat_responses: Iterable[ChatResult] = (),
        segment_responses: Iterable[SegmentResult] = (),
        failures: Iterable[BaseException] = (),
        delay: float = 0.0,
    ) -> None:
        """`failures` are raised first, one per call. `delay` widens race windows in tests."""
        self._chat_responses = deque(chat_responses)
        self._segment_responses = deque(segment_responses)
        self._failures = deque(failures)
        self._delay = delay
        self.chat_calls: list[ChatRequest] = []
        self.segment_calls: list[SegmentRequest] = []

    @property
    def call_count(self) -> int:
        return len(self.chat_calls) + len(self.segment_calls)

    def _before_reply(self) -> None:
        if self._delay:
            time.sleep(self._delay)
        if self._failures:
            raise self._failures.popleft()

    def chat(self, request: ChatRequest) -> ChatResult:
        self.chat_calls.append(request)
        self._before_reply()
        if self._chat_responses:
            return self._chat_responses.popleft()
        return ChatResult(
            text="stub response",
            usage=Usage(input_tokens=100, output_tokens=20),
            model=request.model,
            request_id=STUB_REQUEST_ID,
        )

    def segment(self, request: SegmentRequest) -> SegmentResult:
        self.segment_calls.append(request)
        self._before_reply()
        if self._segment_responses:
            return self._segment_responses.popleft()
        if request.image.data is not None:
            with Image.open(io.BytesIO(request.image.data)) as image:
                width, height = image.size
        else:
            width, height = URL_IMAGE_SIZE
        frame = np.zeros((height, width), dtype=bool)
        frame[height // 4 : 3 * height // 4, width // 4 : 3 * width // 4] = True
        mask = SegmentMask.from_frame_array(request.concept, 0.9, frame)
        return SegmentResult(
            masks=[mask], usage=Usage(calls=1), model=request.model, request_id=STUB_REQUEST_ID
        )
