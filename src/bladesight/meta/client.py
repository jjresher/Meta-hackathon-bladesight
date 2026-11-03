"""The one entry point for every model call: cache, spend cap, retries, then the provider."""

from __future__ import annotations

import logging
import math
import random
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .cache import DiskCache, cache_key
from .config import MetaSettings
from .errors import CacheMissError, MetaConfigError
from .http_provider import HttpProvider
from .models import (
    CallRecord,
    ChatRequest,
    ChatResult,
    ImagePart,
    SegmentRequest,
    SegmentResult,
    Usage,
)
from .provider import Provider
from .retry import RetryPolicy, call_with_retry
from .spend import (
    SpendTracker,
    cost_usd,
    estimate_chat_usd,
    estimate_segment_usd,
    rate_for,
)
from .stub import StubProvider

log = logging.getLogger("bladesight.meta")


@dataclass(frozen=True)
class ChatDefaults:
    """Values filled into a `ChatRequest` field that the caller left as None."""

    store: bool | None = None
    reasoning_effort: str | None = None


class MetaClient:
    def __init__(
        self,
        provider: Provider,
        *,
        spend: SpendTracker,
        cache: DiskCache | None = None,
        retry: RetryPolicy | None = None,
        use_cache: bool = True,
        cache_only: bool = False,
        chat_defaults: ChatDefaults | None = None,
        sleep: Callable[[float], None] = time.sleep,
        rng: Callable[[], float] = random.random,
    ) -> None:
        if not provider.simulated and math.isinf(spend.limit_usd):
            raise MetaConfigError(
                f"{provider.name}: a real provider needs a finite spend cap "
                "(SpendTracker.unlimited() is for the stub only)"
            )
        self.provider = provider
        self.spend = spend
        self.cache = cache
        self.retry = retry or RetryPolicy()
        self.use_cache = use_cache
        self.cache_only = cache_only
        self.chat_defaults = chat_defaults or ChatDefaults()
        self._sleep = sleep
        self._rng = rng
        self.records: list[CallRecord] = []

    def chat(self, request: ChatRequest) -> ChatResult:
        fill = {
            name: value
            for name, value in (
                ("store", self.chat_defaults.store),
                ("reasoning_effort", self.chat_defaults.reasoning_effort),
            )
            if value is not None and getattr(request, name) is None
        }
        if fill:
            request = request.model_copy(update=fill)
        return self._execute(
            "chat",
            request.model,
            request.cache_payload(),
            ChatResult,
            estimate_chat_usd(request),
            lambda: self.provider.chat(request),
        )

    def segment(self, request: SegmentRequest) -> SegmentResult:
        """One concept. The cache holds every mask; `threshold` filters after the lookup."""
        result = self._execute(
            "segment",
            request.model,
            request.cache_payload(),
            SegmentResult,
            estimate_segment_usd(request.model),
            lambda: self.provider.segment(request),
        )
        kept = [m for m in result.masks if m.score is None or m.score >= request.threshold]
        return result.model_copy(update={"masks": kept})

    def segment_concepts(
        self, model: str, image: ImagePart, concepts: list[str], threshold: float = 0.5
    ) -> SegmentResult:
        """SAM takes one concept per request, so each concept is its own call.

        Every concept is cached and retried on its own: if one fails after its retries the error
        is raised, but the concepts already done stay cached and a re-run only repeats the rest.
        """
        parts = [
            self.segment(SegmentRequest(model=model, image=image, concept=c, threshold=threshold))
            for c in concepts
        ]
        usage = Usage(
            input_tokens=sum(p.usage.input_tokens for p in parts),
            output_tokens=sum(p.usage.output_tokens for p in parts),
            calls=sum(p.usage.calls for p in parts),
        )
        return SegmentResult(
            masks=[m for p in parts for m in p.masks],
            usage=usage,
            model=model,
            request_id=parts[-1].request_id if parts else None,
        )

    def _execute[R: (ChatResult, SegmentResult)](
        self,
        operation: Literal["chat", "segment"],
        model: str,
        payload: dict[str, Any],
        result_type: type[R],
        estimate: float,
        call: Callable[[], R],
    ) -> R:
        key = cache_key(f"{self.provider.name}/{operation}", model, payload)
        caching = self.use_cache and self.cache is not None

        if caching:
            assert self.cache is not None
            hit = self.cache.get(key, result_type)
            if hit is not None:
                self._record(operation, model, hit, "cache", 1, [], 0.0, 0.0, False)
                return hit
        if self.cache_only:
            raise CacheMissError(
                f"{self.provider.name}/{operation}: not cached and the client is cache-only "
                "(replay mode; set BLADESIGHT_MODE=live for a real call)"
            )

        reservation = self.spend.reserve(estimate)
        try:
            result, retried = call_with_retry(call, self.retry, sleep=self._sleep, rng=self._rng)
        except Exception:
            # A failed call is released as free. A KeyboardInterrupt / SystemExit is deliberately
            # NOT caught: the request may already be billed, so its reservation stays counted.
            self.spend.release(reservation)
            raise
        usage = result.usage
        no_usage = operation == "chat" and usage.input_tokens == 0 and usage.output_tokens == 0
        if no_usage:
            # The response carried no usable usage, but the call may well have been billed: settle
            # at the worst-case reservation instead of at $0 so the cap cannot fail open.
            log.warning(
                "%s/%s: no usage in the response; settling at the estimate",
                self.provider.name,
                operation,
            )
        cost = reservation.estimate_usd if no_usage else cost_usd(model, usage)
        simulated = self.provider.simulated
        real_cost, simulated_cost = (0.0, cost) if simulated else (cost, 0.0)
        attempts = len(retried) + 1
        source: Literal["live", "stub"] = "stub" if simulated else "live"
        self.spend.settle(
            reservation,
            operation=operation,
            model=model,
            usage=result.usage,
            cost=real_cost,
            simulated_cost=simulated_cost,
            source=source,
            attempts=attempts,
            request_id=result.request_id,
        )
        if caching and result.status == "completed":
            assert self.cache is not None
            self.cache.put(key, result)
        codes = [e.code for e in retried]
        self._record(
            operation, model, result, source, attempts, codes, real_cost, simulated_cost, no_usage
        )
        return result

    def _record(
        self,
        operation: Literal["chat", "segment"],
        model: str,
        result: ChatResult | SegmentResult,
        source: Literal["live", "cache", "stub"],
        attempts: int,
        retried_codes: list[str],
        cost: float,
        simulated_cost: float,
        from_estimate: bool,
    ) -> None:
        record = CallRecord(
            operation=operation,
            provider=self.provider.name,
            model=model,
            source=source,
            attempts=attempts,
            retried_codes=retried_codes,
            cost_usd=cost,
            simulated_cost_usd=simulated_cost,
            price_documented=rate_for(model).documented,
            cost_from_estimate=from_estimate,
            request_id=result.request_id,
            response_model=result.model,
        )
        self.records.append(record)
        log.info(
            "meta call op=%s provider=%s model=%s source=%s attempts=%d retried=%s "
            "cost=$%.4f simulated=$%.4f",
            operation,
            self.provider.name,
            model,
            source,
            attempts,
            retried_codes or "-",
            cost,
            simulated_cost,
        )


def build_client(
    settings: MetaSettings,
    *,
    provider: Literal["meta", "baseten", "stub"] = "meta",
    use_cache: bool | None = None,
    cache_only: bool | None = None,
    spend_limit_usd: float | None = None,
    spend_log_path: Path | str | None = None,
    retry: RetryPolicy | None = None,
    stub: StubProvider | None = None,
) -> MetaClient:
    """Assemble a client from settings.

    `cache_only` defaults to replay mode (`BLADESIGHT_MODE=replay`), so a real call needs
    `BLADESIGHT_MODE=live`; a cache-only (replay) client needs no API key, which is only checked
    lazily if a network call is ever attempted. Each provider has its own cumulative cap
    (`META_SPEND_LIMIT_USD`, `BASETEN_SPEND_LIMIT_USD`) summed from the shared spend log. A stub
    client never touches the network, ignores the mode, keeps its spend in memory and is uncapped
    unless `spend_limit_usd` is given; `use_cache` defaults to on for real providers and off for
    the stub.
    """
    backend: Provider
    log_path: Path | str | None
    if provider == "stub":
        backend = stub or StubProvider()
        limit = spend_limit_usd if spend_limit_usd is not None else math.inf
        cache_only = False if cache_only is None else cache_only
        use_cache = False if use_cache is None else use_cache
        log_path = spend_log_path
    else:
        use_cache = True if use_cache is None else use_cache
        if cache_only is None:
            cache_only = settings.mode == "replay"
        log_path = spend_log_path or settings.spend_log_path
        if provider == "meta":
            if settings.meta_api_key is None and not cache_only:
                raise MetaConfigError("META_API_KEY is missing")
            limit = spend_limit_usd if spend_limit_usd is not None else settings.spend_limit_usd
            backend = HttpProvider(
                "meta", settings.meta_api_base_url, settings.meta_api_key, chat_format="responses"
            )
        else:
            if settings.baseten_api_key is None and not cache_only:
                raise MetaConfigError("BASETEN_API_KEY is missing")
            limit = (
                spend_limit_usd if spend_limit_usd is not None else settings.baseten_spend_limit_usd
            )
            # Basic accounts default to ~15 RPM / 100k TPM (unverified): back off much more slowly.
            retry = retry or RetryPolicy(max_attempts=5, base_delay=4.0, max_delay=30.0)
            backend = HttpProvider(
                "baseten",
                settings.baseten_base_url,
                settings.baseten_api_key,
                chat_format="chat_completions",
                supports_segment=False,
            )
    defaults = (
        ChatDefaults(store=settings.store, reasoning_effort=settings.reasoning_effort)
        if provider == "meta"
        else ChatDefaults()
    )
    return MetaClient(
        backend,
        chat_defaults=defaults,
        spend=SpendTracker(limit, provider=provider, log_path=log_path),
        cache=DiskCache(Path(settings.cache_dir) / "responses"),
        retry=retry,
        use_cache=use_cache,
        cache_only=cache_only,
    )
