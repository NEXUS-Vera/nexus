"""Scripted model gateway for deterministic tests."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .types import ModelGatewayError, ModelPolicy, StructuredGenerationResult

Script = Callable[[str, dict[str, object], dict[str, object]], dict[str, Any] | ModelGatewayError]


@dataclass
class FakeModelGateway:
    """Returns scripted structured outputs by task name."""

    scripts: dict[str, Script] = field(default_factory=dict)
    default_script: Script | None = None
    call_log: list[dict[str, Any]] = field(default_factory=list)

    def set_script(self, task_name: str, script: Script) -> None:
        self.scripts[task_name] = script

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
        self.call_log.append(
            {
                "task_name": task_name,
                "prompt_id": prompt_id,
                "prompt_version": prompt_version,
                "input_payload": input_payload,
                "system_instructions_len": len(system_instructions),
            }
        )
        script = self.scripts.get(task_name, self.default_script)
        if script is None:
            raise ModelGatewayError(
                code="MODEL_PROVIDER_UNAVAILABLE",
                message=f"No fake script registered for task {task_name}",
                provider=model_policy.provider,
                model=model_policy.model,
            )
        outcome = script(task_name, input_payload, output_schema)
        if isinstance(outcome, ModelGatewayError):
            raise outcome
        return StructuredGenerationResult(
            parsed_output=outcome,
            provider=model_policy.provider,
            model=model_policy.model,
            latency_ms=1,
            input_tokens=10,
            output_tokens=20,
            finish_reason="stop",
            request_id=f"fake_{len(self.call_log)}",
            retry_count=0,
            prompt_id=prompt_id,
            prompt_version=prompt_version,
        )
