"""Provider factory for fixture / llm / shadow modes."""

from __future__ import annotations

import os
from typing import Literal

from nexus_model_gateway import ModelPolicy, OpenAICompatibleGateway
from nexus_observability import StructuredLogRecorder

from .base import InitializationProvider
from .fixture_provider import FixtureInitializationProvider
from .llm_provider import LlmInitializationProvider
from .shadow_provider import ShadowInitializationProvider

ProviderMode = Literal["fixture", "llm", "shadow"]


def resolve_provider_mode(raw: str | None = None) -> ProviderMode:
    value = (raw or os.environ.get("NEXUS_INITIALIZATION_PROVIDER") or "fixture").strip().lower()
    if value not in {"fixture", "llm", "shadow"}:
        raise ValueError(
            f"Invalid NEXUS_INITIALIZATION_PROVIDER={value!r}; expected fixture|llm|shadow"
        )
    return value  # type: ignore[return-value]


def build_initialization_provider(
    mode: ProviderMode | None = None,
    *,
    gateway: object | None = None,
) -> InitializationProvider:
    selected = mode or resolve_provider_mode()
    if selected == "fixture":
        return FixtureInitializationProvider()

    model_policy = ModelPolicy(
        provider=os.environ.get("NEXUS_MODEL_PROVIDER", "openai"),
        model=os.environ.get("NEXUS_MODEL_NAME", "gpt-4.1-mini"),
        timeout_seconds=float(os.environ.get("NEXUS_MODEL_TIMEOUT_SECONDS", "60")),
    )
    max_repair = int(os.environ.get("NEXUS_MODEL_MAX_REPAIR_ATTEMPTS", "1"))
    api_key = os.environ.get("NEXUS_MODEL_API_KEY", "")
    base_url = os.environ.get("NEXUS_MODEL_BASE_URL", "https://api.openai.com/v1")

    if gateway is None and not api_key:
        if selected == "shadow":
            # Shadow can still serve fixture responses; LLM path records config failure.
            return ShadowInitializationProvider(
                fixture_provider=FixtureInitializationProvider(),
                llm_provider=_MissingConfigLlmStub(),  # type: ignore[arg-type]
            )
        return _MissingConfigProvider()

    if gateway is None:
        gateway = OpenAICompatibleGateway(api_key=api_key, base_url=base_url)

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
