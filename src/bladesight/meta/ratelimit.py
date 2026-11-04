"""Client-side request rate limit, shared by every client of one provider in the process.

Baseten allows this account 15 requests per minute. Retries alone would keep hitting 429s and
burn attempts, so every request to a rate-limited provider first waits for a free slot in a
sliding 60-second window.
The window is per provider name and process-wide (`limiter_for`), so several clients, threads or
pipeline stages in one process share the same budget. It does not coordinate across processes:
run one live Baseten process at a time.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable

from .models import ChatRequest, ChatResult, SegmentRequest, SegmentResult
from .provider import Provider

BASETEN_REQUESTS_PER_MINUTE = 15


class RateLimiter:
    """At most `max_requests` starts in any `window_s` seconds (a sliding window)."""

    def __init__(
        self,
        max_requests: int,
        window_s: float = 60.0,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if max_requests < 1 or window_s <= 0:
            raise ValueError("a rate limit needs max_requests >= 1 and window_s > 0")
        self.max_requests = max_requests
        self.window_s = window_s
        self._clock = clock
        self._sleep = sleep
        self._starts: deque[float] = deque()
        self._lock = threading.Lock()
        self.waited_s = 0.0  # total time spent waiting, for logs and tests

    def acquire(self) -> float:
        """Block until a request may start; return the seconds waited."""
        waited = 0.0
        while True:
            with self._lock:
                now = self._clock()
                while self._starts and now - self._starts[0] >= self.window_s:
                    self._starts.popleft()
                if len(self._starts) < self.max_requests:
                    self._starts.append(now)
                    self.waited_s += waited
                    return waited
                wait = self.window_s - (now - self._starts[0])
            # Sleep outside the lock so other threads can still read the window.
            wait = max(wait, 0.001)
            self._sleep(wait)
            waited += wait


_LIMITERS: dict[str, RateLimiter] = {}
_LIMITERS_LOCK = threading.Lock()


def limiter_for(name: str, max_requests: int, window_s: float = 60.0) -> RateLimiter:
    """The process-wide limiter of provider `name` (created on first use)."""
    with _LIMITERS_LOCK:
        limiter = _LIMITERS.get(name)
        if limiter is None or limiter.max_requests != max_requests:
            limiter = RateLimiter(max_requests, window_s)
            _LIMITERS[name] = limiter
        return limiter


class RateLimitedProvider:
    """Wraps a provider so every attempt (retries included) waits for the limiter first."""

    def __init__(self, inner: Provider, limiter: RateLimiter) -> None:
        self.inner = inner
        self.limiter = limiter
        self.name = inner.name
        self.simulated = inner.simulated

    def chat(self, request: ChatRequest) -> ChatResult:
        self.limiter.acquire()
        return self.inner.chat(request)

    def segment(self, request: SegmentRequest) -> SegmentResult:
        self.limiter.acquire()
        return self.inner.segment(request)
