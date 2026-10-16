"""Live model-backed firmware patch proposal generator (Phase 15G)."""

from __future__ import annotations

import asyncio
import queue
import threading
from dataclasses import dataclass
from typing import Any, Protocol

from nexus_model_gateway import ModelGatewayError, ModelPolicy

from nexus_board.errors import FirmwarePatchGenerationError
from nexus_board.firmware.patch import materialize_model_patch_operations


class _ModelGateway(Protocol):
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
    ) -> Any: ...


def _run_sync(coro: Any) -> Any:
    result_q: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)

    def _runner() -> None:
        try:
            result_q.put((True, asyncio.run(coro)))
        except Exception as exc:  # noqa: BLE001
            result_q.put((False, exc))

    thread = threading.Thread(target=_runner, daemon=True)
    thread.start()
    thread.join()
    ok, value = result_q.get()
    if ok:
        return value
    raise value


def _schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["operations"],
        "properties": {
            "operations": {
                "type": "array",
                "minItems": 1,
                "maxItems": 32,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["operationType", "path"],
                    "properties": {
                        "operationType": {
                            "type": "string",
                            "enum": ["create-file", "replace-file", "delete-file"],
                        },
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                },
            }
        },
    }


_SYSTEM = """You generate safe firmware patch operations for a PlatformIO ESP32 workspace.
Return JSON only, matching the schema exactly.
Never invent files outside workspace paths.
Only emit create-file/replace-file/delete-file operations.
Use replace-file for existing files and create-file for new files.
Do not include markdown fences or explanations."""


@dataclass
class LiveFirmwarePatchGenerator:
    gateway: _ModelGateway
    model_policy: ModelPolicy
    prompt_id: str = "firmware.patch-proposal.v1"
    prompt_version: str = "1.0.0"
    generator_id: str = "firmware-patch-generator-llm-v1"
    generator_version: str = "1.0.0"

    def generate(
        self,
        *,
        context: dict[str, Any],
        base_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        payload = {
            "requestedChange": context["requestedChange"],
            "baseSnapshotId": context["baseSnapshotId"],
            "inputArtifactReferences": context["inputArtifactReferences"],
            "snapshotFiles": context["snapshotFiles"],
            "fileContents": context["fileContents"],
            "toolchainProfile": {
                "profileId": "platformio-arduino-esp32-v1",
                "profileVersion": "1.0.0",
                "platformioEnv": "nexus",
                "board": "esp32dev",
                "framework": "arduino",
            },
            "operationContract": {
                "allowedOperationTypes": ["create-file", "replace-file", "delete-file"],
                "maxOperations": 32,
            },
        }
        try:
            generated = _run_sync(
                self.gateway.generate_structured(
                    task_name="firmware.patch-proposal",
                    system_instructions=_SYSTEM,
                    input_payload=payload,
                    output_schema=_schema(),
                    model_policy=self.model_policy,
                    prompt_id=self.prompt_id,
                    prompt_version=self.prompt_version,
                )
            )
        except ModelGatewayError as exc:
            raise FirmwarePatchGenerationError(
                f"Model patch generation failed: {exc.code}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            raise FirmwarePatchGenerationError(
                f"Model patch generation failed: {type(exc).__name__}"
            ) from exc
        parsed = getattr(generated, "parsed_output", None)
        if not isinstance(parsed, dict):
            raise FirmwarePatchGenerationError("Model did not return structured output")
        operations = materialize_model_patch_operations(
            generated=parsed,
            base_snapshot=base_snapshot,
        )
        return {
            "operations": operations,
            "generatorId": self.generator_id,
            "generatorVersion": self.generator_version,
            "generatorMetadata": {
                "mode": "llm",
                "provider": getattr(generated, "provider", self.model_policy.provider),
                "model": getattr(generated, "model", self.model_policy.model),
                "promptId": self.prompt_id,
                "promptVersion": self.prompt_version,
            },
        }
