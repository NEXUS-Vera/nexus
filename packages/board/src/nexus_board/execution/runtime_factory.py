"""Select an ExecutionRuntime without silent security downgrade."""

from __future__ import annotations

import os
from typing import Any

from nexus_board.errors import BoardError
from nexus_board.execution.container_runtime import LocalContainerRuntime
from nexus_board.execution.process_runtime import ProcessRuntime
from nexus_board.execution.runtime_protocol import ExecutionRuntime


class RuntimeUnavailableError(BoardError):
    code = "RUNTIME_UNAVAILABLE"


def resolve_execution_runtime_kind(raw: str | None = None) -> str:
    value = (raw if raw is not None else os.environ.get("NEXUS_EXECUTION_RUNTIME", "process")).strip()
    value = value.lower()
    if value not in {"process", "container"}:
        raise RuntimeUnavailableError(
            f"Unsupported NEXUS_EXECUTION_RUNTIME={value!r}; expected process|container"
        )
    return value


def build_execution_runtime(
    kind: str | None = None,
    *,
    container_image: str | None = None,
    docker_executable: str = "docker",
) -> ExecutionRuntime:
    """Build the configured runtime. Never silently falls back."""
    resolved = resolve_execution_runtime_kind(kind)
    if resolved == "process":
        return ProcessRuntime()
    image = (
        container_image
        if container_image
        else os.environ.get("NEXUS_EXEC_CONTAINER_IMAGE") or "python:3.13-slim"
    )
    docker = docker_executable or os.environ.get("NEXUS_EXEC_DOCKER") or "docker"
    runtime = LocalContainerRuntime(
        image_reference=image,
        docker_executable=docker,
    )
    availability = runtime.availability()
    if not availability.available:
        raise RuntimeUnavailableError(
            availability.unavailable_reason
            or "Container execution runtime is unavailable"
        )
    return runtime


def runtime_selection_metadata(runtime: ExecutionRuntime) -> dict[str, Any]:
    availability = runtime.availability()
    return {
        "runtimeKind": availability.runtime_kind,
        "runtimeVersion": availability.runtime_version,
        "securityLevel": availability.security_level,
        "networkPolicy": availability.network_policy,
        "available": availability.available,
        "isolationGuarantees": list(availability.isolation_guarantees),
        "isolationLimitations": list(availability.isolation_limitations),
        "details": dict(availability.details),
        "unavailableReason": availability.unavailable_reason,
    }
