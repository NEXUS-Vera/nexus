"""Model gateway protocol."""

from __future__ import annotations

from typing import Protocol

from .types import ModelPolicy, StructuredGenerationResult


class ModelGateway(Protocol):
    """Shared model access boundary used by agents.

    Domain workflows must not call provider SDKs directly.
    """

    async def generate_structured(
        self,
        *,
        task_name: str,
        system_instructions: str,
        input_payload: dict[str, object],
        output_schema: dict[str, object],
        model_policy: ModelPolicy,
        prompt_id: str | None = None,
        prompt_version: str | None = None,
    ) -> StructuredGenerationResult:
        """Generate JSON that conforms to output_schema.

        Raises ModelGatewayError on transport, configuration, or parse failures.
        """
        ...
