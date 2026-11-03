"""The interface every backend implements: the real HTTP API and the test stub."""

from __future__ import annotations

from typing import Protocol

from .models import ChatRequest, ChatResult, SegmentRequest, SegmentResult


class Provider(Protocol):
    name: str
    simulated: bool  # True for the stub: its calls spend nothing real

    def chat(self, request: ChatRequest) -> ChatResult: ...

    def segment(self, request: SegmentRequest) -> SegmentResult:
        """Segment ONE concept. Fan-out over several concepts lives in `MetaClient`."""
        ...
