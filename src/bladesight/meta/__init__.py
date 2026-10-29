"""Meta Model API client: Muse Spark, SAM 3.1, Muse Spark Open (Baseten).

Every model call goes through `MetaClient`: disk cache, hard spend cap, retries with backoff.
"""

from .cache import DiskCache, cache_key
from .client import MetaClient, build_client
from .config import (
    MUSE_SPARK_MODEL,
    MUSE_SPARK_OPEN_MODEL,
    SAM_MODEL,
    MetaSettings,
)
from .errors import (
    CacheMissError,
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
    SpendCapExceededError,
    SpendLogError,
)
from .http_provider import HttpProvider
from .models import (
    CallRecord,
    ChatMessage,
    ChatRequest,
    ChatResult,
    ImagePart,
    SegmentMask,
    SegmentRequest,
    SegmentResult,
    TextPart,
    ToolCall,
    ToolSpec,
    Usage,
)
from .provider import Provider
from .retry import RetryPolicy
from .spend import SpendTracker
from .stub import StubProvider

__all__ = [
    "MUSE_SPARK_MODEL",
    "MUSE_SPARK_OPEN_MODEL",
    "SAM_MODEL",
    "CacheMissError",
    "CallRecord",
    "ChatMessage",
    "ChatRequest",
    "ChatResult",
    "DiskCache",
    "HttpProvider",
    "ImagePart",
    "MetaAuthError",
    "MetaClient",
    "MetaConfigError",
    "MetaConnectionError",
    "MetaError",
    "MetaInvalidResponseError",
    "MetaModelNotFoundError",
    "MetaPaymentRequiredError",
    "MetaRateLimitError",
    "MetaRequestError",
    "MetaServerError",
    "MetaSettings",
    "MetaTimeoutError",
    "Provider",
    "RetryPolicy",
    "SegmentMask",
    "SegmentRequest",
    "SegmentResult",
    "SpendCapExceededError",
    "SpendLogError",
    "SpendTracker",
    "StubProvider",
    "TextPart",
    "ToolCall",
    "ToolSpec",
    "Usage",
    "build_client",
    "cache_key",
]
