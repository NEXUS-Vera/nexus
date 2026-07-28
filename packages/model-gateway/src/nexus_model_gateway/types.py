"""Model gateway public types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class ModelPolicy:
    """Runtime policy for a structured generation call."""

    provider: str
    model: str
    timeout_seconds: float = 60.0
    max_transport_retries: int = 2
    temperature: float = 0.0


@dataclass(frozen=True)
class StructuredGenerationResult:
    """Successful structured generation result.

    Does not include chain-of-thought or hidden reasoning.
    """

    parsed_output: dict[str, Any]
    provider: str
    model: str
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None
    finish_reason: str | None
    request_id: str | None
    retry_count: int
    prompt_id: str | None = None
    prompt_version: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelGatewayError(Exception):
    """Normalized model-gateway failure."""

    def __init__(
        self,
        *,
        code: str,
        message: str,
        retryable: bool = False,
        provider: str | None = None,
        model: str | None = None,
        request_id: str | None = None,
        internal_detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.provider = provider
        self.model = model
        self.request_id = request_id
        # Internal diagnostics only — never send to clients.
        self.internal_detail = internal_detail


InitializationProviderName = Literal["fixture", "llm", "shadow"]
