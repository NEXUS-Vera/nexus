"""Deterministic workflow step ledger for fixture-backed initialization.

Records each step when it actually starts and completes. This is not an
asynchronous workflow engine — only a truthful execution log for WorkflowRun.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

StepStatus = Literal["pending", "running", "completed", "failed"]
RunStatus = Literal["pending", "running", "completed", "completed-with-warnings", "failed"]


def _format_ts(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class WorkflowLedger:
    """Append-only recorder for workflow stepRecords."""

    workflow_run_id: str
    workflow_type: str
    project_id: str
    turn_id: str
    warnings: list[dict[str, Any]] = field(default_factory=list)
    error_references: list[dict[str, Any]] = field(default_factory=list)
    _steps: list[dict[str, Any]] = field(default_factory=list)
    _last_ts: datetime | None = None
    _start_time: str | None = None
    _completion_time: str | None = None
    _run_status: RunStatus = "running"
    _failed: bool = False
    _step_index: int = 0

    def _next_ts(self) -> str:
        now = datetime.now(UTC).replace(microsecond=0)
        if self._last_ts is not None and now <= self._last_ts:
            now = self._last_ts + timedelta(seconds=1)
        self._last_ts = now
        return _format_ts(now)

    def begin_run(self) -> None:
        self._start_time = self._next_ts()
        self._run_status = "running"

    def start_step(self, step_type: str) -> dict[str, Any]:
        if self._failed:
            raise RuntimeError(f"Cannot start step {step_type} after workflow failure")
        self._step_index += 1
        step: dict[str, Any] = {
            "stepId": f"step_{self._step_index:02d}_{step_type}",
            "stepType": step_type,
            "status": "running",
            "attempt": 1,
            "startedAt": self._next_ts(),
        }
        self._steps.append(step)
        return step

    def complete_step(
        self,
        step: dict[str, Any],
        *,
        output_artifact_references: list[dict[str, Any]] | None = None,
    ) -> None:
        if step.get("status") != "running":
            raise RuntimeError(f"Step {step.get('stepId')} is not running")
        step["status"] = "completed"
        step["completedAt"] = self._next_ts()
        if output_artifact_references is not None:
            step["outputArtifactReferences"] = output_artifact_references

    def fail_step(
        self,
        step: dict[str, Any],
        *,
        error_reference: dict[str, Any] | None = None,
    ) -> None:
        if step.get("status") != "running":
            raise RuntimeError(f"Step {step.get('stepId')} is not running")
        step["status"] = "failed"
        step["completedAt"] = self._next_ts()
        if error_reference is not None:
            step["errorReference"] = error_reference
            self.error_references.append(error_reference)
        self._failed = True
        self._run_status = "failed"
        self._completion_time = step["completedAt"]

    def finish_success(self) -> None:
        if self._failed:
            raise RuntimeError("Cannot finish a failed workflow as success")
        self._completion_time = self._next_ts()
        self._run_status = "completed-with-warnings" if self.warnings else "completed"

    def to_workflow_run(self) -> dict[str, Any]:
        if self._start_time is None:
            raise RuntimeError("Workflow run was never started")
        payload: dict[str, Any] = {
            "schemaVersion": "1.0.0",
            "workflowRunId": self.workflow_run_id,
            "workflowType": self.workflow_type,
            "projectId": self.project_id,
            "turnId": self.turn_id,
            "runStatus": self._run_status,
            "stepRecords": list(self._steps),
            "startTime": self._start_time,
            "warnings": list(self.warnings),
            "errorReferences": list(self.error_references),
        }
        if self._completion_time is not None:
            payload["completionTime"] = self._completion_time
        return payload

    @property
    def failed(self) -> bool:
        return self._failed

    @property
    def step_records(self) -> list[dict[str, Any]]:
        return list(self._steps)
