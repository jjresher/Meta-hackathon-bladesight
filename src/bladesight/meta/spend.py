"""Prices, spend estimate, and the cumulative per-provider cap backed by the on-disk spend log.

The cap is cumulative across runs and processes: before every live call `SpendTracker.reserve`
sums this provider's history from `spend_log.jsonl` (settled costs plus still-open reservations)
under an inter-process file lock, and appends a reservation for the call's worst-case cost before
releasing the lock. A second process therefore sees the first one's in-flight spend and cannot
push the total over the cap. Each provider (meta, baseten) has its own cap; the log is shared.

The log fails closed: a line that is truncated, not an object, not valid JSON, has an unknown kind
or a missing / null / non-finite / negative amount raises `SpendLogError` instead of being skipped,
because skipping it would silently lower the total and let calls past the cap.
"""

from __future__ import annotations

import json
import logging
import math
import threading
import time
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .errors import MetaConfigError, SpendCapExceededError, SpendLogError
from .models import ChatRequest, Usage

try:  # POSIX only; without it the cap is still enforced per process (documented limitation).
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None  # type: ignore[assignment]

log = logging.getLogger("bladesight.meta")

CHARS_PER_TOKEN = 4
TOKENS_PER_IMAGE = 1500  # Meta: a ~1280 px image is roughly 1,300-1,500 input tokens


@dataclass(frozen=True)
class Rate:
    """USD per million input / cached-input / output tokens, plus a flat price per call."""

    input_per_mtok: float = 0.0
    cached_input_per_mtok: float | None = None  # None: cached tokens are billed as input
    output_per_mtok: float = 0.0
    per_call: float = 0.0
    # True: the rate comes from the provider's published pricing page. It is NOT checked against an
    # invoice. False: a placeholder or the conservative default.
    documented: bool = True


# Keyed by exact model id. Meta rates: pay-as-you-go, standard mode, from dev.meta.ai/docs.
# Reasoning tokens are part of output_tokens and are billed as output.
PRICING: dict[str, Rate] = {
    "muse-spark-1.3": Rate(1.25, 0.15, 4.25),
    "muse-spark-1.2": Rate(1.25, 0.15, 4.25),
    "muse-spark-1.1": Rate(1.25, 0.15, 4.25),
    # Contributor variants: cheaper, but Meta may train on the content. Never a default.
    "muse-spark-1.3-contributor": Rate(0.10, 0.002, 0.20),
    "muse-spark-1.2-contributor": Rate(0.10, 0.002, 0.20),
    # $2.50 per 1,000 images. Video ($0.20 per 1,000 frames, min 50 frames) is not used.
    "sam-3.1": Rate(per_call=0.0025),
    # Baseten (baseten.co/pricing): same per-1M-token rates as Muse Spark. Reasoning is always on
    # and is billed as output. Both slugs: the hackathon one and the one the docs list.
    "meta-models/muse-spark-open-1026": Rate(1.25, 0.15, 4.25),
    "meta-models/muse-spark-open": Rate(1.25, 0.15, 4.25),
}
# Unknown model ids are never free: a conservative, unconfirmed rate keeps the cap meaningful.
DEFAULT_RATE = Rate(5.0, None, 20.0, per_call=0.05, documented=False)


def rate_for(model: str) -> Rate:
    return PRICING.get(model, DEFAULT_RATE)


def cost_usd(model: str, usage: Usage) -> float:
    rate = rate_for(model)
    cached = min(usage.cached_input_tokens, usage.input_tokens)
    cached_rate = (
        rate.input_per_mtok if rate.cached_input_per_mtok is None else rate.cached_input_per_mtok
    )
    return (
        (usage.input_tokens - cached) * rate.input_per_mtok / 1e6
        + cached * cached_rate / 1e6
        + usage.output_tokens * rate.output_per_mtok / 1e6
        + usage.calls * rate.per_call
    )


def estimate_chat_usd(request: ChatRequest) -> float:
    """Worst case for the pre-call check: all input uncached plus the full `max_tokens` output."""
    chars = sum(len(p.text) for m in request.messages for p in m.content if p.type == "text")
    chars += sum(len(t.model_dump_json()) for t in request.tools)
    input_tokens = chars // CHARS_PER_TOKEN + TOKENS_PER_IMAGE * len(request.images())
    usage = Usage(input_tokens=input_tokens, output_tokens=request.max_tokens, calls=1)
    return cost_usd(request.model, usage)


def estimate_segment_usd(model: str) -> float:
    return cost_usd(model, Usage(calls=1))


@dataclass(frozen=True)
class Reservation:
    id: str
    estimate_usd: float


class SpendTracker:
    """Cumulative per-provider spend with a hard cap. Thread- and process-safe on POSIX."""

    def __init__(
        self, limit_usd: float, *, provider: str, log_path: Path | str | None = None
    ) -> None:
        if math.isnan(limit_usd) or limit_usd < 0:
            raise MetaConfigError(f"{provider}: the spend limit must be a number >= 0")
        self.limit_usd = limit_usd
        self.provider = provider
        self.log_path = Path(log_path) if log_path else None
        self._memory: list[dict[str, Any]] = []
        self._thread_lock = threading.Lock()
        self.live_calls = 0

    @classmethod
    def unlimited(cls, provider: str = "test") -> SpendTracker:
        return cls(math.inf, provider=provider)

    # --- public protocol -------------------------------------------------------------------

    def reserve(self, estimate_usd: float) -> Reservation:
        """Refuse the call if history + in-flight + `estimate_usd` would pass the cap.

        This is where the cumulative check happens: the total is read from the spend log (all
        runs, all processes) and the reservation is appended before the file lock is released.
        """
        with self._guard():
            spent = self._total_locked()
            if spent + estimate_usd > self.limit_usd:
                raise SpendCapExceededError(
                    spent_usd=spent,
                    estimate_usd=estimate_usd,
                    limit_usd=self.limit_usd,
                    provider=self.provider,
                )
            reservation = Reservation(uuid.uuid4().hex, estimate_usd)
            self._append({"kind": "reserve", "id": reservation.id, "est_cost_usd": estimate_usd})
            return reservation

    def settle(
        self,
        reservation: Reservation,
        *,
        operation: str,
        model: str,
        usage: Usage,
        cost: float,
        simulated_cost: float,
        source: str,
        attempts: int,
        request_id: str | None,
    ) -> None:
        """Replace the reservation with the actual cost. `simulated_cost` is stub-only."""
        if (
            not (math.isfinite(cost) and math.isfinite(simulated_cost))
            or cost < 0
            or simulated_cost < 0
        ):
            log.warning("invalid cost for %s; settling at the reservation estimate", model)
            cost, simulated_cost = (
                (0.0, reservation.estimate_usd)
                if simulated_cost
                else (
                    reservation.estimate_usd,
                    0.0,
                )
            )
        with self._guard():
            self._append(
                {
                    "kind": "settle",
                    "id": reservation.id,
                    "operation": operation,
                    "model": model,
                    "source": source,
                    "attempts": attempts,
                    "input_tokens": usage.input_tokens,
                    "cached_input_tokens": usage.cached_input_tokens,
                    "output_tokens": usage.output_tokens,
                    "est_cost_usd": round(cost, 8),
                    "simulated_cost_usd": round(simulated_cost, 8),
                    "request_id": request_id,
                }
            )
            self.live_calls += 1

    def release(self, reservation: Reservation) -> None:
        """The call failed after all retries: nothing is billed, free the reservation."""
        with self._guard():
            self._append({"kind": "release", "id": reservation.id})

    @property
    def spent_usd(self) -> float:
        """Cumulative spend for this provider (settled + in flight), read from the log."""
        with self._guard():
            return self._total_locked()

    # --- storage ---------------------------------------------------------------------------

    @contextmanager
    def _guard(self) -> Iterator[None]:
        with self._thread_lock:
            if self.log_path is None or fcntl is None:
                yield
                return
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            lock_path = self.log_path.with_name(self.log_path.name + ".lock")
            with lock_path.open("a") as handle:
                fcntl.flock(handle, fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    fcntl.flock(handle, fcntl.LOCK_UN)

    def _append(self, entry: dict[str, Any]) -> None:
        entry = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
            "provider": self.provider,
            **entry,
        }
        if self.log_path is None:
            self._memory.append(entry)
            return
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
            handle.flush()

    def _entries(self) -> Iterator[dict[str, Any]]:
        if self.log_path is None:
            yield from self._memory
            return
        try:
            text = self.log_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return
        except (OSError, UnicodeDecodeError) as exc:
            raise SpendLogError(f"cannot read the spend log {self.log_path}: {exc}") from None
        for number, line in enumerate(text.splitlines(), 1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                raise SpendLogError(
                    self._bad(number, "not valid JSON (truncated write?)")
                ) from None
            if not isinstance(entry, dict):
                raise SpendLogError(self._bad(number, "not a JSON object"))
            yield entry

    def _bad(self, number: int, why: str) -> str:
        return (
            f"spend log {self.log_path} line {number}: {why}; refusing every call until a human "
            "inspects the file (a damaged log must not lower the cap)"
        )

    def _total_locked(self) -> float:
        """Settled cost plus open reservations for this provider. Caller holds the lock.

        A reservation with no settle or release (a crashed process) stays counted at its
        estimate, which errs on the side of not overspending. Any malformed line raises.
        """
        settled = 0.0
        open_reservations: dict[str, float] = {}
        for number, entry in enumerate(self._entries(), 1):
            kind = entry.get("kind")
            provider = entry.get("provider")
            if kind not in ("reserve", "settle", "release") or not isinstance(provider, str):
                raise SpendLogError(self._bad(number, "unknown kind or missing provider"))
            entry_id = entry.get("id")
            if not isinstance(entry_id, str) or not entry_id:
                raise SpendLogError(self._bad(number, "missing id"))
            # Validate every line before looking at its provider: damage anywhere in the shared
            # log makes the whole file untrustworthy.
            estimate = self._amount(entry, "est_cost_usd", number) if kind != "release" else 0.0
            simulated = (
                self._amount(entry, "simulated_cost_usd", number) if kind == "settle" else 0.0
            )
            if provider != self.provider:
                continue
            if kind == "reserve":
                open_reservations[entry_id] = estimate
            elif kind == "settle":
                open_reservations.pop(entry_id, None)
                settled += estimate + simulated
            else:
                open_reservations.pop(entry_id, None)
        return settled + sum(open_reservations.values())

    def _amount(self, entry: dict[str, Any], field: str, number: int) -> float:
        value = entry.get(field)
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise SpendLogError(self._bad(number, f"{field} is missing or not a number"))
        if not math.isfinite(value) or value < 0:
            raise SpendLogError(self._bad(number, f"{field} is not a finite non-negative number"))
        return float(value)
