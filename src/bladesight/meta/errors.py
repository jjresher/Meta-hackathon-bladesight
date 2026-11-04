"""Error types for the Meta API client.

Every failure surfaces as a `MetaError` subclass so callers can decide what to do without parsing
messages. Messages never contain credentials or request headers.
"""

from __future__ import annotations

from typing import ClassVar


class MetaError(Exception):
    """Base class. `retryable` tells the retry loop whether another attempt can help."""

    retryable: ClassVar[bool] = False

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        request_id: str | None = None,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.request_id = request_id
        self.retry_after = retry_after
        self.attempts = 1

    @property
    def code(self) -> str:
        """Short label for logs: the HTTP status when there is one, else the error kind."""
        return str(self.status_code) if self.status_code is not None else self.kind

    kind: ClassVar[str] = "error"

    def __str__(self) -> str:
        parts = [self.message]
        if self.status_code is not None:
            parts.append(f"status={self.status_code}")
        if self.request_id:
            parts.append(f"request_id={self.request_id}")
        if self.attempts > 1:
            parts.append(f"attempts={self.attempts}")
        return " ".join(parts)


class MetaConfigError(MetaError):
    """Missing or invalid configuration (key, base URL, spend limit)."""

    kind = "config"


class MetaAuthError(MetaError):
    """401/403: the key or its permissions. Never retried; the human must act."""

    kind = "auth"


class MetaRequestError(MetaError):
    """Other 4xx: the request itself is wrong. Never retried."""

    kind = "request"


class MetaRateLimitError(MetaError):
    """429. Retried, honoring `Retry-After`."""

    retryable = True
    kind = "rate_limit"


class MetaServerError(MetaError):
    """5xx. Retried."""

    retryable = True
    kind = "server"


class MetaTimeoutError(MetaError):
    """The per-call timeout elapsed. Retried."""

    retryable = True
    kind = "timeout"


class MetaConnectionError(MetaError):
    """Network-level failure before a response arrived. Retried."""

    retryable = True
    kind = "connection"


class MetaInvalidResponseError(MetaError):
    """A 2xx response whose body does not match the expected shape.

    Not retried by `call_with_retry`: `MetaClient` retries it once on a fresh reservation and
    settles each such attempt at its estimate, because a 2xx was probably billed.
    """

    kind = "invalid_response"


class MetaPaymentRequiredError(MetaRequestError):
    """402: the account needs credit or a payment method. Permanent: never retried."""

    kind = "payment_required"


class MetaModelNotFoundError(MetaRequestError):
    """404 model_not_found: the model id is wrong. Never retried."""

    kind = "model_not_found"


class SpendCapExceededError(MetaError):
    """The call would pass the provider's cumulative cap. Raised before any network traffic."""

    kind = "spend_cap"

    def __init__(
        self, *, spent_usd: float, estimate_usd: float, limit_usd: float, provider: str = ""
    ) -> None:
        label = f"{provider} " if provider else ""
        super().__init__(
            f"{label}spend cap reached: spent ${spent_usd:.4f} (all runs) + estimate "
            f"${estimate_usd:.4f} > limit ${limit_usd:.4f}; raising the cap is the human's decision"
        )
        self.provider = provider
        self.spent_usd = spent_usd
        self.estimate_usd = estimate_usd
        self.limit_usd = limit_usd


class SpendLogError(MetaError):
    """The spend log cannot be trusted (truncated, non-numeric, NaN, null...). Calls are refused.

    A damaged log must never lower or bypass a cap, so the client fails closed until a human has
    inspected the file named in the message.
    """

    kind = "spend_log"


class CacheMissError(MetaError):
    """Cache-only (replay) mode and the answer is not cached."""

    kind = "cache_miss"
