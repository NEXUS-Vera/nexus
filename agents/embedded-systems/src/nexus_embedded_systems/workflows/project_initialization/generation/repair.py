"""LLM-backed repair for a single invalid artifact.

Repair only ever rewrites the one artifact identified by `artifact_name`. It
never regenerates sibling artifacts and never introduces claims beyond what
is needed to address the reported validation defects (see the
`embedded.artifact-repair.v1` prompt in `..prompts.catalog`).
"""

from __future__ import annotations

import time
from typing import Any

from nexus_model_gateway import (
    ModelGateway,
    ModelGatewayError,
    ModelPolicy,
    StructuredGenerationResult,
)
from nexus_observability import GenerationObservation, ObservationRecorder

from ..prompts import get_prompt

_REPAIR_PROMPT_ID = "embedded.artifact-repair.v1"
_REPAIR_STAGE = "artifact-repair"


async def repair_artifact(
    *,
    gateway: ModelGateway,
    model_policy: ModelPolicy,
    artifact_name: str,
    original_content: dict[str, Any],
    validation_codes: list[str],
    validation_messages: list[str],
    output_schema: dict[str, Any],
    recorder: ObservationRecorder,
    request_id: str | None,
    workflow_run_id: str | None,
) -> dict[str, Any]:
    """Ask the model to repair exactly one invalid artifact's content.

    Returns the repaired content dict, unwrapped from the `repairedContent`
    envelope the model returns. Raises `ModelGatewayError` on transport,
    configuration, or malformed-output failures; callers decide retry policy.
    An observation is always recorded via `recorder`, on both success and
    failure.
    """

    prompt = get_prompt(_REPAIR_PROMPT_ID)
    input_payload: dict[str, object] = {
        "artifactName": artifact_name,
        "originalContent": original_content,
        "validationCodes": list(validation_codes),
        "validationMessages": list(validation_messages),
    }

    started = time.perf_counter()
    result: StructuredGenerationResult | None = None
    validation_result = "success"
    error_code: str | None = None
    try:
        result = await gateway.generate_structured(
            task_name=_REPAIR_STAGE,
            system_instructions=prompt.system_instructions,
            input_payload=input_payload,
            output_schema=output_schema,
            model_policy=model_policy,
            prompt_id=prompt.prompt_id,
            prompt_version=prompt.version,
        )
        repaired_content = result.parsed_output.get("repairedContent")
        if not isinstance(repaired_content, dict):
            validation_result = "invalid-output"
            error_code = "MODEL_REPAIR_OUTPUT_MALFORMED"
            raise ModelGatewayError(
                code=error_code,
                message="Repair response did not include a repairedContent object.",
                provider=model_policy.provider,
                model=model_policy.model,
                request_id=result.request_id,
            )
        return repaired_content
    except ModelGatewayError as exc:
        if validation_result == "success":
            validation_result = "failure"
        error_code = exc.code
        raise
    finally:
        duration_ms = int((time.perf_counter() - started) * 1000)
        recorder.record_generation(
            GenerationObservation(
                request_id=request_id,
                workflow_run_id=workflow_run_id,
                stage=_REPAIR_STAGE,
                provider=model_policy.provider,
                model=model_policy.model,
                duration_ms=duration_ms,
                input_tokens=result.input_tokens if result is not None else None,
                output_tokens=result.output_tokens if result is not None else None,
                retry_count=result.retry_count if result is not None else None,
                repair_count=1,
                validation_result=validation_result,
                error_code=error_code,
                prompt_id=prompt.prompt_id,
                prompt_version=prompt.version,
                metadata={
                    "artifactName": artifact_name,
                    "validationCodes": list(validation_codes),
                },
            )
        )
