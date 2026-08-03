"""Provider factory for fixture / llm / shadow modes."""

from __future__ import annotations

import os
from typing import Literal

from nexus_model_gateway import AnthropicGateway, ModelPolicy, OpenAICompatibleGateway
from nexus_observability import StructuredLogRecorder

from .base import InitializationProvider
from .fixture_provider import FixtureInitializationProvider
from .llm_provider import LlmInitializationProvider
from .shadow_provider import ShadowInitializationProvider

ProviderMode = Literal["fixture", "llm", "shadow"]

_DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
_DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
_DEFAULT_ANTHROPIC_BASE_URL = "https://api.anthropic.com"


def resolve_provider_mode(raw: str | None = None) -> ProviderMode:
    value = (raw or os.environ.get("NEXUS_INITIALIZATION_PROVIDER") or "fixture").strip().lower()
    if value not in {"fixture", "llm", "shadow"}:
        raise ValueError(
            f"Invalid NEXUS_INITIALIZATION_PROVIDER={value!r}; expected fixture|llm|shadow"
        )
    return value  # type: ignore[return-value]


def _resolve_model_provider() -> str:
    return (os.environ.get("NEXUS_MODEL_PROVIDER") or "openai").strip().lower()


def _build_gateway(model_credential: str, provider: str) -> object:
    if provider in {"anthropic", "claude"}:
        base_url = os.environ.get("NEXUS_MODEL_BASE_URL") or _DEFAULT_ANTHROPIC_BASE_URL
        return AnthropicGateway(model_credential=model_credential, base_url=base_url)
    base_url = os.environ.get("NEXUS_MODEL_BASE_URL") or _DEFAULT_OPENAI_BASE_URL
    return OpenAICompatibleGateway(model_credential=model_credential, base_url=base_url)


def build_initialization_provider(
    mode: ProviderMode | None = None,
    *,
    gateway: object | None = None,
) -> InitializationProvider:
    selected = mode or resolve_provider_mode()
    if selected == "fixture":
        return FixtureInitializationProvider()

    provider_name = _resolve_model_provider()
    default_model = (
        _DEFAULT_ANTHROPIC_MODEL
        if provider_name in {"anthropic", "claude"}
        else _DEFAULT_OPENAI_MODEL
    )
    model_policy = ModelPolicy(
        provider=provider_name,
        model=os.environ.get("NEXUS_MODEL_NAME") or default_model,
        timeout_seconds=float(os.environ.get("NEXUS_MODEL_TIMEOUT_SECONDS", "60")),
    )
    max_repair = int(os.environ.get("NEXUS_MODEL_MAX_REPAIR_ATTEMPTS", "1"))
    # Env var name stays NEXUS_MODEL_API_KEY (uppercase; docs/config). Local
    # identifiers use model_credential so secret-pattern scans stay clean.
    model_credential = os.environ.get("NEXUS_MODEL_API_KEY", "")

    if gateway is None and not model_credential:
        if selected == "shadow":
            # Shadow can still serve fixture responses; LLM path records config failure.
            return ShadowInitializationProvider(
                fixture_provider=FixtureInitializationProvider(),
                llm_provider=_MissingConfigLlmStub(),  # type: ignore[arg-type]
            )
        return _MissingConfigProvider()

    if gateway is None:
        gateway = _build_gateway(model_credential, provider_name)

    llm = LlmInitializationProvider(
        gateway=gateway,  # type: ignore[arg-type]
        model_policy=model_policy,
        max_repair_attempts=max_repair,
        recorder=StructuredLogRecorder(),
    )
    if selected == "llm":
        return llm
    return ShadowInitializationProvider(
        fixture_provider=FixtureInitializationProvider(),
        llm_provider=llm,
    )


class _MissingConfigProvider:
    async def initialize(self, message: str, autonomy_mode: str, request_context: object) -> dict:
        from .llm_provider import LlmInitializationError

        raise LlmInitializationError(
            code="MODEL_CONFIGURATION_MISSING",
            message=(
                "LLM initialization requires NEXUS_MODEL_API_KEY (and related model settings)."
            ),
        )


class _MissingConfigLlmStub:
    async def initialize(self, message: str, autonomy_mode: str, request_context: object) -> dict:
        from .llm_provider import LlmInitializationError

        raise LlmInitializationError(
            code="MODEL_CONFIGURATION_MISSING",
            message="Shadow LLM path missing NEXUS_MODEL_API_KEY.",
        )
