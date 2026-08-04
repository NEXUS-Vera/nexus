"""Fake execution runtime service."""

from __future__ import annotations

from typing import Any, Protocol

from nexus_board.errors import StaleExecutionResultError
from nexus_board.ids import content_digest, new_id, utc_now_iso
from nexus_board.registries.runtime_capabilities import RuntimeCapabilityRegistry
from nexus_board.services.ledger_service import ProjectLedgerService
from nexus_board.services.projection_service import ProjectBoardProjectionService


class _KernelStore(Protocol):
    def create_execution_run(self, execution_run: dict[str, Any]) -> None: ...

    def update_execution_status(
        self, execution_run_id: str, execution_run: dict[str, Any]
    ) -> None: ...

    def get_execution_run(self, execution_run_id: str) -> dict[str, Any]: ...

    def list_execution_runs(
        self, project_id: str, *, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]: ...

    def create_produced_output(self, output: dict[str, Any]) -> None: ...

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any]: ...


class _ProjectStore(Protocol):
    def get_project(self, project_id: str) -> dict[str, Any]: ...

    def get_artifact(
        self,
        project_id: str,
        artifact_type: str,
        *,
        version: int | None = None,
    ) -> dict[str, Any]: ...


class ExecutionService:
    def __init__(
        self,
        kernel_store: _KernelStore,
        project_store: _ProjectStore,
        capabilities: RuntimeCapabilityRegistry,
        ledger: ProjectLedgerService,
        projection: ProjectBoardProjectionService,
    ) -> None:
        self._kernel = kernel_store
        self._projects = project_store
        self._capabilities = capabilities
        self._ledger = ledger
        self._projection = projection

    def list_runs(
        self, project_id: str, *, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        return self._kernel.list_execution_runs(project_id, limit=limit, cursor=cursor)

    def execute(
        self,
        *,
        project_id: str,
        artifact_id: str,
        artifact_type: str,
        workspace_id: str,
        snapshot_id: str,
        capability: str,
        actor: dict[str, Any],
        base_artifact_version: int,
        base_project_state_version: int,
        causation_id: str | None = None,
        max_duration_ms: int | None = None,
    ) -> dict[str, Any]:
        if not self._capabilities.is_available(capability):
            raise StaleExecutionResultError(f"Capability unavailable: {capability}")
        if capability not in {"structured-validation", "fake-execution"}:
            raise StaleExecutionResultError(f"Unsupported capability: {capability}")

        cap = self._capabilities.get(capability)
        now = utc_now_iso()
        request_id = new_id("execreq")
        run_id = new_id("exec")
        run: dict[str, Any] = {
            "schemaVersion": "1.0.0",
            "executionRunId": run_id,
            "executionRequestId": request_id,
            "projectId": project_id,
            "artifactId": artifact_id,
            "workspaceId": workspace_id,
            "providerId": cap["providerId"],
            "capability": capability,
            "status": "queued",
            "baseArtifactVersion": base_artifact_version,
            "baseProjectStateVersion": base_project_state_version,
            "inputSnapshotId": snapshot_id,
            "queuedAt": now,
            "outputReferences": [],
            "evidenceReferences": [],
        }
        if max_duration_ms is not None:
            run["resourceLimits"] = {"maxDurationMs": max_duration_ms}
        self._kernel.create_execution_run(run)
        self._ledger.append(
            project_id=project_id,
            event_type="execution.queued",
            actor=actor,
            subject_type="execution",
            subject_id=run_id,
            payload={"executionRunId": run_id, "capability": capability},
            causation_id=causation_id,
            correlation_id=causation_id,
            occurred_at=now,
        )

        # queued → running
        started = utc_now_iso()
        run = dict(run)
        run["status"] = "running"
        run["startedAt"] = started
        self._kernel.update_execution_status(run_id, run)
        self._ledger.append(
            project_id=project_id,
            event_type="execution.started",
            actor=actor,
            subject_type="execution",
            subject_id=run_id,
            payload={"executionRunId": run_id},
            causation_id=causation_id,
            correlation_id=causation_id,
            occurred_at=started,
        )

        # Check staleness against current heads at completion time
        project = self._projects.get_project(project_id)
        current_state_version = int(project["currentStateVersion"])
        try:
            art = self._projects.get_artifact(project_id, artifact_type)
            current_artifact_version = int(art["artifactVersion"])
        except Exception:  # noqa: BLE001
            current_artifact_version = base_artifact_version

        stale = (
            current_state_version != base_project_state_version
            or current_artifact_version != base_artifact_version
        )

        completed = utc_now_iso()
        outputs: list[dict[str, Any]] = []
        if not stale:
            outputs = self._produce_outputs(
                run=run,
                capability=capability,
                snapshot_id=snapshot_id,
                completed_at=completed,
            )
            for output in outputs:
                self._kernel.create_produced_output(output)
                self._ledger.append(
                    project_id=project_id,
                    event_type="output.produced",
                    actor=actor,
                    subject_type="output",
                    subject_id=output["outputId"],
                    payload={
                        "outputId": output["outputId"],
                        "executionRunId": run_id,
                        "outputType": output["outputType"],
                    },
                    causation_id=causation_id,
                    correlation_id=causation_id,
                    occurred_at=completed,
                )
                self._ledger.append(
                    project_id=project_id,
                    event_type="evidence.attached",
                    actor=actor,
                    subject_type="evidence",
                    subject_id=f"ev_{output['outputId'][4:]}",
                    payload={
                        "outputId": output["outputId"],
                        "evidenceStatus": "unverified",
                    },
                    causation_id=causation_id,
                    correlation_id=causation_id,
                    occurred_at=completed,
                )

        run = dict(run)
        run["completedAt"] = completed
        run["outputReferences"] = [o["outputId"] for o in outputs]
        run["evidenceReferences"] = [f"ev_{o['outputId'][4:]}" for o in outputs]
        if outputs:
            run["logReference"] = outputs[-1]["outputId"]
        if stale:
            run["status"] = "stale"
            self._kernel.update_execution_status(run_id, run)
            self._ledger.append(
                project_id=project_id,
                event_type="execution.failed",
                actor=actor,
                subject_type="execution",
                subject_id=run_id,
                payload={
                    "executionRunId": run_id,
                    "reason": "STALE_EXECUTION_RESULT",
                },
                causation_id=causation_id,
                correlation_id=causation_id,
                occurred_at=completed,
            )
            self._projection.update_after_write(project_id)
            raise StaleExecutionResultError("Execution bases were stale; result not promoted.")

        run["status"] = "completed"
        self._kernel.update_execution_status(run_id, run)
        self._ledger.append(
            project_id=project_id,
            event_type="execution.completed",
            actor=actor,
            subject_type="execution",
            subject_id=run_id,
            payload={"executionRunId": run_id, "capability": capability},
            causation_id=causation_id,
            correlation_id=causation_id,
            occurred_at=completed,
        )
        self._projection.update_after_write(project_id)
        return {"executionRun": run, "outputs": outputs}

    def _produce_outputs(
        self,
        *,
        run: dict[str, Any],
        capability: str,
        snapshot_id: str,
        completed_at: str,
    ) -> list[dict[str, Any]]:
        snapshot = self._kernel.get_snapshot(snapshot_id)
        structured = snapshot["content"].get("structuredContent") or {}
        outputs: list[dict[str, Any]] = []
        if capability == "structured-validation":
            report = {
                "ok": True,
                "issueCount": 0,
                "checkedKeys": sorted(structured.keys()),
            }
            outputs.append(
                self._output(
                    run=run,
                    output_type="validation-report",
                    name="fake-validation-report",
                    structured=report,
                    created_at=completed_at,
                )
            )
        # Always emit a structured-result + log for fake-execution; also for validation.
        result = {
            "capability": capability,
            "echo": structured,
            "provider": "fake",
        }
        outputs.append(
            self._output(
                run=run,
                output_type="structured-result",
                name="fake-structured-result",
                structured=result,
                created_at=completed_at,
            )
        )
        outputs.append(
            self._output(
                run=run,
                output_type="log",
                name="fake-execution-log",
                structured={"lines": [f"fake {capability} completed"]},
                created_at=completed_at,
            )
        )
        return outputs

    @staticmethod
    def _output(
        *,
        run: dict[str, Any],
        output_type: str,
        name: str,
        structured: dict[str, Any],
        created_at: str,
    ) -> dict[str, Any]:
        return {
            "schemaVersion": "1.0.0",
            "outputId": new_id("out"),
            "projectId": run["projectId"],
            "artifactId": run["artifactId"],
            "workspaceId": run["workspaceId"],
            "executionRunId": run["executionRunId"],
            "outputType": output_type,
            "name": name,
            "mediaType": "application/json",
            "content": {"kind": "inline-structured", "structuredResult": structured},
            "contentDigest": content_digest(structured),
            "createdAt": created_at,
            "evidenceStatus": "unverified",
            "supports": [
                {"supportKind": "artifact", "targetId": run["artifactId"]},
            ],
        }
