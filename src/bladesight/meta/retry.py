"""Exponential backoff with full jitter."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from dataclasses import dataclass

from .errors import MetaError


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 4
    base_delay: float = 0.5
    max_delay: float = 8.0
    max_retry_after: float = 120.0

    def delay(self, attempt: int, error: MetaError, rng: Callable[[], float]) -> float:
        """Seconds to wait after failed attempt number `attempt` (1-based).

        `Retry-After` is a floor: we always wait at least that long.
        """
        backoff = min(self.max_delay, self.base_delay * 2 ** (attempt - 1)) * rng()
        if error.retry_after is not None:
            return max(backoff, error.retry_after)
        return backoff

    def gives_up_on(self, error: MetaError) -> bool:
        """True when the server asks for a wait longer than we are willing to block for."""
        return error.retry_after is not None and error.retry_after > self.max_retry_after


def call_with_retry[T](
    fn: Callable[[], T],
    policy: RetryPolicy,
    *,
    sleep: Callable[[float], None] = time.sleep,
    rng: Callable[[], float] = random.random,
) -> tuple[T, list[MetaError]]:
    """Run `fn`, retrying retryable `MetaError`s. Returns the result and the retried errors.

    After the last attempt the final error is re-raised with `attempts` set.
    """
    retried: list[MetaError] = []
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return fn(), retried
        except MetaError as error:
            error.attempts = attempt
            if not error.retryable or attempt == policy.max_attempts or policy.gives_up_on(error):
                raise
            retried.append(error)
            sleep(policy.delay(attempt, error, rng))
    raise AssertionError("unreachable: max_attempts must be >= 1")  # pragma: no cover
