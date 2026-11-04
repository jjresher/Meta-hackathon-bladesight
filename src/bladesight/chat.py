"""The chat provider selector: which model grades, verifies, plans and writes the report.

One setting picks the provider of every Muse Spark *chat* stage (severity, the second look, the
fleet agent and its report): `--chat-provider` on the CLIs, or `BLADESIGHT_CHAT_PROVIDER`.

- `meta`: Muse Spark on the Meta Model API (`META_CHAT_MODEL`, default `muse-spark-1.3`).
- `baseten`: Muse Spark Open, Meta's open-weights model, on Baseten's OpenAI-compatible chat
  completions (`BASETEN_CHAT_MODEL`, default `meta-models/muse-spark-open`, the id the account's
  `/v1/models` listing shows). It always reasons and the reasoning counts against the output
  budget, so every request gets at least `OPEN_WEIGHTS_MIN_OUTPUT_TOKENS`
  (`docs/evidence/open_weights.md`: at 1,500 tokens it returned empty replies on 23 of 40 crops).
- `stub`: the free test double.

Detection is not covered: SAM 3.1 has no open-weights path here and stays on the Meta Model API.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal, cast, get_args

from .meta import MetaClient, MetaConfigError, MetaSettings, build_client

ChatProvider = Literal["meta", "baseten", "stub"]
CHAT_PROVIDERS: tuple[str, ...] = get_args(ChatProvider)
ENV_VAR = "BLADESIGHT_CHAT_PROVIDER"
OPEN_WEIGHTS_MIN_OUTPUT_TOKENS = 6000


@dataclass(frozen=True)
class ChatTarget:
    """A client plus the model id and output budget floor of one chat provider."""

    client: MetaClient
    provider: ChatProvider
    model: str
    min_output_tokens: int = 0

    def budget(self, max_tokens: int) -> int:
        return max(max_tokens, self.min_output_tokens)


def chat_provider_from_env(default: ChatProvider = "meta") -> ChatProvider:
    raw = os.environ.get(ENV_VAR, "").strip() or default
    if raw not in CHAT_PROVIDERS:
        raise MetaConfigError(f"{ENV_VAR} must be one of {', '.join(CHAT_PROVIDERS)}")
    return cast(ChatProvider, raw)


def model_for(provider: ChatProvider, settings: MetaSettings) -> str:
    return settings.baseten_chat_model if provider == "baseten" else settings.chat_model


def chat_target(
    settings: MetaSettings,
    provider: ChatProvider,
    *,
    client: MetaClient | None = None,
) -> ChatTarget:
    """`client` reuses an existing client (e.g. the one the detection stage already built)."""
    built = client or build_client(settings, provider=provider)
    return ChatTarget(
        client=built,
        provider=provider,
        model=model_for(provider, settings),
        min_output_tokens=OPEN_WEIGHTS_MIN_OUTPUT_TOKENS if provider == "baseten" else 0,
    )
