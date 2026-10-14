"""ExecutionRuntime protocol for Nexus-owned compute."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from nexus_board.execution.limits import ExecutionLimits

# securityLevel values — honest, not aspirational.
SECURITY_LEVEL_LIMITED = "limited"  # ProcessRuntime
SECURITY_LEVEL_ISOLATED = "isolated"  # LocalContainerRuntime

NETWORK_POLICY_NONE = "none"
NETWORK_POLICY_RESTRICTED = "restricted"


@dataclass
class RuntimeAvailability:
    available: bool
    runtime_kind: str
    runtime_version: str
    security_level: str = SECURITY_LEVEL_LIMITED
    network_policy: str = NETWORK_POLICY_NONE
    isolation_guarantees: list[str] = field(default_factory=list)
    isolation_limitations: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)
    unavailable_reason: str | None = None


@dataclass
class RuntimeExecuteRequest:
    job_id: str
    workspace_root: Path
    command_spec: dict[str, Any]
    limits: ExecutionLimits
    cancel_check: Any = None  # callable[[], bool]
    network_policy: str = NETWORK_POLICY_NONE
    on_started: Any = None  # callable[[dict[str, Any]], None]


@dataclass
class CollectedOutput:
    path: str
    kind: str
    content: bytes
    content_hash: str


@dataclass
class RuntimeExecuteResult:
    status: str  # succeeded | failed | timed-out | cancelled
    exit_code: int | None
    stdout: str
    stderr: str
    system_messages: list[str]
    outputs: list[CollectedOutput]
    log_truncated: bool
    failure_code: str | None = None
    failure_message: str | None = None
    executable_fingerprint: str | None = None
    image_reference: str | None = None
    image_digest: str | None = None
    cleanup_warning: str | None = None


class ExecutionRuntime(Protocol):
    def availability(self) -> RuntimeAvailability: ...

    def execute(self, request: RuntimeExecuteRequest) -> RuntimeExecuteResult: ...

    def cancel(self, job_id: str) -> None: ...

    def cleanup(self, job_id: str, *, handle: dict[str, Any] | None = None) -> None:
        """Idempotent teardown of processes/containers/staging for a job."""

    def reconcile_handle(self, handle: dict[str, Any]) -> str | None:
        """Return a terminal job status if a prior-process handle is gone.

        Returns None when the runtime still owns the job, or cannot decide.
        For ProcessRuntime, prior-process handles are always treated as lost.
        """
