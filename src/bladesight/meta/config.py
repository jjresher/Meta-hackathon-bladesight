"""Settings read from the environment (and `.env`, in-process only).

Secrets are `SecretStr`, so they never show in a repr, a log line or `status()`.
"""

from __future__ import annotations

import math
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Literal

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from .errors import MetaConfigError

DEFAULT_SPEND_LIMIT_USD = 0.50
DEFAULT_BASETEN_SPEND_LIMIT_USD = 10.00
DEFAULT_META_BASE_URL = "https://api.meta.ai"  # from Meta's official cURL example
DEFAULT_BASETEN_BASE_URL = "https://inference.baseten.co/v1"  # docs.baseten.co

# Model ids confirmed by Meta's docs (dev.meta.ai/docs). The "-contributor" variants are cheaper
# but Meta may train on the content: never a default. Override with META_CHAT_MODEL and
# META_SAM_MODEL.
MUSE_SPARK_MODEL = "muse-spark-1.3"
SAM_MODEL = "sam-3.1"
MUSE_SPARK_OPEN_MODEL = "meta-models/muse-spark-open"  # the id the Baseten /models listing shows


def project_root() -> Path:
    """The directory holding `pyproject.toml`, so caches and the spend log do not depend on cwd."""
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    return Path.cwd()


class MetaSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    meta_api_key: SecretStr | None = None
    meta_api_base_url: str = DEFAULT_META_BASE_URL
    chat_model: str = MUSE_SPARK_MODEL
    sam_model: str = SAM_MODEL
    # Defaults the Meta client fills into a ChatRequest that leaves them as None. Both values were
    # accepted by the real API (docs/evidence/meta-api-step1.md): store=false keeps Meta from
    # keeping our requests, and effort "low" cut reasoning from 686 to 203 tokens on the same
    # prompt. Override with META_STORE / META_REASONING_EFFORT; the value "default" sends neither.
    store: bool | None = False
    reasoning_effort: str | None = "low"
    baseten_api_key: SecretStr | None = None
    baseten_base_url: str = DEFAULT_BASETEN_BASE_URL
    spend_limit_usd: float = DEFAULT_SPEND_LIMIT_USD
    baseten_spend_limit_usd: float = DEFAULT_BASETEN_SPEND_LIMIT_USD
    mode: Literal["replay", "live"] = "replay"
    cache_dir: Path = Field(default_factory=lambda: _anchor(".cache/meta"))
    # Outside .cache/ on purpose: wiping the caches must not reset the spend caps.
    spend_log_path: Path = Field(default_factory=lambda: _anchor(".spend/spend_log.jsonl"))

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        dotenv_path: Path | str | None = ".env",
    ) -> MetaSettings:
        """Build settings from `environ`, or from `.env` plus the process environment.

        When `environ` is given it is the only source (tests pass a dict). Otherwise `.env` is
        parsed in-process with python-dotenv and real environment variables win over it.
        """
        if environ is None:
            values: dict[str, str] = {}
            if dotenv_path is not None and Path(dotenv_path).is_file():
                values.update({k: v for k, v in dotenv_values(dotenv_path).items() if v})
            values.update(os.environ)
        else:
            values = dict(environ)

        def get(name: str) -> str | None:
            value = values.get(name, "").strip()
            return value or None

        limit = _limit(get("META_SPEND_LIMIT_USD"), "META_SPEND_LIMIT_USD", DEFAULT_SPEND_LIMIT_USD)
        baseten_limit = _limit(
            get("BASETEN_SPEND_LIMIT_USD"),
            "BASETEN_SPEND_LIMIT_USD",
            DEFAULT_BASETEN_SPEND_LIMIT_USD,
        )

        mode = get("BLADESIGHT_MODE") or "replay"
        if mode not in ("replay", "live"):
            raise MetaConfigError("BLADESIGHT_MODE must be 'replay' or 'live'")

        key = get("META_API_KEY")
        baseten_key = get("BASETEN_API_KEY")
        return cls(
            meta_api_key=SecretStr(key) if key else None,
            meta_api_base_url=get("META_API_BASE_URL") or DEFAULT_META_BASE_URL,
            chat_model=get("META_CHAT_MODEL") or MUSE_SPARK_MODEL,
            sam_model=get("META_SAM_MODEL") or SAM_MODEL,
            store=_store(get("META_STORE")),
            reasoning_effort=_effort(get("META_REASONING_EFFORT")),
            baseten_api_key=SecretStr(baseten_key) if baseten_key else None,
            baseten_base_url=get("BASETEN_BASE_URL") or DEFAULT_BASETEN_BASE_URL,
            spend_limit_usd=limit,
            baseten_spend_limit_usd=baseten_limit,
            mode=mode,  # type: ignore[arg-type]
            cache_dir=_anchor(get("BLADESIGHT_CACHE_DIR") or ".cache/meta"),
            spend_log_path=_anchor(get("BLADESIGHT_SPEND_LOG") or ".spend/spend_log.jsonl"),
        )

    def status(self) -> dict[str, str]:
        """Step 0 of meta-api-check: `set`/`missing` per variable, never a value."""

        def flag(value: object) -> str:
            return "set" if value else "missing"

        return {
            "META_API_KEY": flag(self.meta_api_key),
            "META_API_BASE_URL": "set"
            if self.meta_api_base_url != DEFAULT_META_BASE_URL
            else "default",
            "META_CHAT_MODEL": self.chat_model,
            "META_SAM_MODEL": self.sam_model,
            "BASETEN_API_KEY": flag(self.baseten_api_key),
            "BASETEN_BASE_URL": "set"
            if self.baseten_base_url != DEFAULT_BASETEN_BASE_URL
            else "default",
            "META_SPEND_LIMIT_USD": f"{self.spend_limit_usd:.2f}",
            "BASETEN_SPEND_LIMIT_USD": f"{self.baseten_spend_limit_usd:.2f}",
            "BLADESIGHT_MODE": self.mode,
        }


def _store(raw: str | None) -> bool | None:
    if raw is None:
        return False  # the default: do not let Meta store our requests
    value = raw.lower()
    if value in ("true", "1", "yes"):
        return True
    if value in ("false", "0", "no"):
        return False
    if value == "default":
        return None  # send nothing; Meta's own default applies (it stores)
    raise MetaConfigError("META_STORE must be true, false or default")


def _effort(raw: str | None) -> str | None:
    if raw is None:
        return "low"
    return None if raw.lower() == "default" else raw


def _limit(raw: str | None, name: str, default: float) -> float:
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise MetaConfigError(f"{name} is not a number") from None
    if math.isnan(value) or value < 0:
        raise MetaConfigError(f"{name} must be >= 0")
    return value


def _anchor(path: str) -> Path:
    """Relative paths resolve against the project root, absolute ones are kept."""
    candidate = Path(path)
    return candidate if candidate.is_absolute() else project_root() / candidate
