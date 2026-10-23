"""Execution runtime service (sync providers + async sandbox jobs)."""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any, Protocol

from nexus_board.errors import BoardError, StaleExecutionResultError
from nexus_board.execution.limits import ExecutionLimits
from nexus_board.ids import content_digest, new_id, utc_now_iso
from nexus_board.registries.runtime_capabilities import RuntimeCapabilityRegistry
from nexus_board.services.ledger_service import ProjectLedgerService
from nexus_board.services.projection_service import ProjectBoardProjectionService

SANDBOX_CAPABILITY = "sandbox-execution"


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

    def get_produced_output(self, output_id: str) -> dict[str, Any]: ...

    def list_produced_outputs(self, project_id: str) -> list[dict[str, Any]]: ...

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any]: ...

    def get_workspace(self, workspace_id: str) -> dict[str, Any]: ...

    def update_workspace(self, workspace: dict[str, Any]) -> None: ...


class _ProjectStore(Protocol):
    def get_project(self, project_id: str) -> dict[str, Any]: ...

    def get_artifact(
        self,
        project_id: str,
        artifact_type: str,
        *,
        version: int | None = None,
    ) -> dict[str, Any]: ...


class CapabilityExecutor(Protocol):
    """Provider-neutral adapter injected by the application composition root."""

    def execute(self, request: dict[str, Any]) -> dict[str, Any]: ...


class _ArtifactTypeRegistry(Protocol):
    def get(self, artifact_type: str) -> dict[str, Any]: ...


class ExecutionService:
    def __init__(
        self,
        kernel_store: _KernelStore,
        project_store: _ProjectStore,
        artifact_types: _ArtifactTypeRegistry,
        capabilities: RuntimeCapabilityRegistry,
        ledger: ProjectLedgerService,
        projection: ProjectBoardProjectionService,
        capability_executors: Mapping[str, CapabilityExecutor] | None = None,
        job_service: Any | None = None,
    ) -> None:
        self._kernel = kernel_store
        self._projects = project_store
        self._artifact_types = artifact_types
        self._capabilities = capabilities
        self._ledger = ledger
        self._projection = projection
        self._capability_executors = dict(capability_executors or {})
        self._jobs = job_service
        self.invalidation: Any | None = None

    def list_runs(
        self, project_id: str, *, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        return self._kernel.list_execution_runs(project_id, limit=limit, cursor=cursor)

    def get_run(self, execution_run_id: str) -> dict[str, Any]:
        return self._kernel.get_execution_run(execution_run_id)

    def list_logs(
        self,
        execution_run_id: str,
        *,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        if self._jobs is None:
            raise StaleExecutionResultError("Execution job service is not configured")
        result = self._jobs.list_logs(
            execution_run_id,
            after_sequence=after_sequence,
            limit=limit,
        )
        assert isinstance(result, dict)
        return result

    def cancel(
        self, execution_run_id: str, *, actor: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        if self._jobs is None:
            raise StaleExecutionResultError("Execution job service is not configured")
        result = self._jobs.cancel(execution_run_id, actor=actor)
        assert isinstance(result, dict)
        return result

    def get_job_for_run(self, execution_run_id: str) -> dict[str, Any] | None:
        if self._jobs is None:
            return None
        job = self._jobs.get_job_for_run(execution_run_id)
        if job is None:
            return None
        assert isinstance(job, dict)
        return job

    def list_outputs(self, project_id: str) -> list[dict[str, Any]]:
        return self._kernel.list_produced_outputs(project_id)

    def get_output(self, output_id: str) -> dict[str, Any]:
        return self._kernel.get_produced_output(output_id)

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
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if max_duration_ms is not None and not 1 <= max_duration_ms <= 300_000:
            raise BoardError(
                "maxDurationMs must be between 1 and 300000", code="COMMAND_VALIDATION_FAILED"
            )
        execution_options = dict(options or {})
        max_output_bytes = execution_options.get("maxOutputBytes")
        if max_output_bytes is not None and (
            not isinstance(max_output_bytes, int) or not 1 <= max_output_bytes <= 10_485_760
        ):
            raise BoardError(
                "maxOutputBytes must be between 1 and 10485760", code="COMMAND_VALIDATION_FAILED"
            )
        if not self._capabilities.is_available(capability) and capability != "circuit-simulation":
            raise BoardError(f"Capability unavailable: {capability}", code="CAPABILITY_UNAVAILABLE")
        required = self._artifact_types.get(artifact_type).get("requiredCapabilities") or []
        if capability not in required:
            raise StaleExecutionResultError(
                f"Capability {capability} is not permitted for {artifact_type}"
            )
        if capability == SANDBOX_CAPABILITY:
            return self._execute_sandbox(
                project_id=project_id,
                artifact_id=artifact_id,
                workspace_id=workspace_id,
                snapshot_id=snapshot_id,
                capability=capability,
                actor=actor,
                base_artifact_version=base_artifact_version,
                base_project_state_version=base_project_state_version,
                causation_id=causation_id,
                max_duration_ms=max_duration_ms,
                options=execution_options,
            )
        if capability not in {"structured-validation", "fake-execution"} and (
            capability not in self._capability_executors
        ):
            raise StaleExecutionResultError(f"Unsupported capability: {capability}")
        snapshot = self._kernel.get_snapshot(snapshot_id)
        if (
            snapshot.get("projectId") != project_id
            or snapshot.get("artifactId") != artifact_id
            or snapshot.get("workspaceId") != workspace_id
        ):
            raise StaleExecutionResultError(
                "Execution snapshot does not belong to the requested workspace"
            )

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
            "startedAt": now,
            "outputReferences": [],
            "evidenceReferences": [],
        }
        if capability == "circuit-simulation" and execution_options.get("firmwareOutputId"):
            run["inputOutputReferences"] = [execution_options["firmwareOutputId"]]
        self._kernel.create_execution_run(run)
        if self.invalidation is not None:
            self.invalidation.record_run(run)
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

        try:
            if capability in self._capability_executors:
                provider_result = self._capability_executors[capability].execute(
                    {
                        "projectId": project_id,
                        "artifactId": artifact_id,
                        "artifactType": artifact_type,
                        "artifactVersion": base_artifact_version,
                        "workspaceId": workspace_id,
                        "snapshotId": snapshot_id,
                        "snapshot": snapshot,
                        "maxDurationMs": max_duration_ms,
                        "options": execution_options,
                    }
                )
            else:
                provider_result = None
            if provider_result is not None:
                output_size = len(
                    json.dumps(
                        provider_result.get("outputs") or [],
                        sort_keys=True,
                        default=str,
                    ).encode("utf-8")
                )
                output_limit = int(max_output_bytes or 1_000_000)
                if output_size > output_limit:
                    raise ValueError("Capability outputs exceeded maxOutputBytes")
        except Exception as exc:  # noqa: BLE001
            failed = dict(run)
            failed["status"] = "timed-out" if isinstance(exc, TimeoutError) else "failed"
            failed["completedAt"] = utc_now_iso()
            failed["error"] = {
                "code": getattr(exc, "code", type(exc).__name__.upper()),
                "message": str(exc)[:500] or "Capability execution failed.",
            }
            self._kernel.update_execution_status(run_id, failed)
            self._ledger.append(
                project_id=project_id,
                event_type="execution.failed",
                actor=actor,
                subject_type="execution",
                subject_id=run_id,
                payload={
                    "executionRunId": run_id,
                    "reason": failed["error"]["code"],
                },
                causation_id=causation_id,
                correlation_id=causation_id,
                occurred_at=failed["completedAt"],
            )
            self._projection.update_after_write(project_id)
            raise BoardError(failed["error"]["message"], code=failed["error"]["code"]) from exc

        # Check staleness against current heads at completion time.
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
            if provider_result is None:
                outputs = self._produce_outputs(
                    run=run,
                    capability=capability,
                    snapshot_id=snapshot_id,
                    completed_at=completed,
                )
            else:
                outputs = self._normalize_provider_outputs(
                    run=run,
                    provider_result=provider_result,
                    completed_at=completed,
                )
                external_reference = provider_result.get("externalWorkspaceReference")
                if isinstance(external_reference, dict):
                    self._record_external_workspace_reference(
                        workspace_id=workspace_id,
                        reference=external_reference,
                        updated_at=completed,
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
                        "executionRunId": run_id,
                        "evidenceId": f"ev_{output['outputId'][4:]}",
                        "evidenceStatus": "unverified",
                        "status": "unverified",
                    },
                    causation_id=causation_id,
                    correlation_id=causation_id,
                    occurred_at=completed,
                )

        run = dict(run)
        if provider_result is not None and provider_result.get("inputOutputReferences"):
            run["inputOutputReferences"] = provider_result["inputOutputReferences"]
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

        provider_status = (
            provider_result.get("status") if isinstance(provider_result, dict) else None
        )
        run["status"] = (
            "completed-with-warnings"
            if provider_status == "completed-with-warnings"
            else "completed"
        )
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

    def _execute_sandbox(
        self,
        *,
        project_id: str,
        artifact_id: str,
        workspace_id: str,
        snapshot_id: str,
        capability: str,
        actor: dict[str, Any],
        base_artifact_version: int,
        base_project_state_version: int,
        causation_id: str | None,
        max_duration_ms: int | None,
        options: dict[str, Any],
    ) -> dict[str, Any]:
        if self._jobs is None:
            raise StaleExecutionResultError("Execution job service is not configured")
        command_spec = options.get("commandSpec")
        if not isinstance(command_spec, dict):
            raise StaleExecutionResultError("sandbox-execution requires commandSpec")
        snapshot = self._kernel.get_snapshot(snapshot_id)
        if (
            snapshot.get("projectId") != project_id
            or snapshot.get("artifactId") != artifact_id
            or snapshot.get("workspaceId") != workspace_id
        ):
            raise StaleExecutionResultError(
                "Execution snapshot does not belong to the requested workspace"
            )
        cap = self._capabilities.get(capability)
        now = utc_now_iso()
        run_id = new_id("exec")
        run: dict[str, Any] = {
            "schemaVersion": "1.0.0",
            "executionRunId": run_id,
            "executionRequestId": new_id("execreq"),
            "projectId": project_id,
            "artifactId": artifact_id,
            "workspaceId": workspace_id,
            "providerId": cap["providerId"],
            "capability": capability,
            "status": "queued",
            "baseArtifactVersion": base_artifact_version,
            "baseProjectStateVersion": base_project_state_version,
            "inputSnapshotId": snapshot_id,
            "startedAt": now,
            "outputReferences": [],
            "evidenceReferences": [],
        }
        self._kernel.create_execution_run(run)
        if self.invalidation is not None:
            self.invalidation.record_run(run)
        self._ledger.append(
            project_id=project_id,
            event_type="execution.queued",
            actor=actor,
            subject_type="execution",
            subject_id=run_id,
            payload={"executionRunId": run_id, "capability": capability, "async": True},
            causation_id=causation_id,
            correlation_id=causation_id,
            occurred_at=now,
        )
        limits = None
        if max_duration_ms is not None or options.get("maxOutputBytes") is not None:
            overrides: dict[str, int] = {}
            if max_duration_ms is not None:
                overrides["wall_time_ms"] = int(max_duration_ms)
            if options.get("maxOutputBytes") is not None:
                overrides["produced_output_bytes"] = int(options["maxOutputBytes"])
            limits = ExecutionLimits().override(**overrides)
        submitted = self._jobs.submit(
            run=run,
            snapshot=snapshot,
            command_spec=command_spec,
            actor=actor,
            limits=limits,
            causation_id=causation_id,
        )
        self._projection.update_after_write(project_id)
        return {
            "executionRun": submitted["executionRun"],
            "executionJob": submitted["executionJob"],
            "outputs": [],
            "accepted": True,
        }

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

    def _normalize_provider_outputs(
        self,
        *,
        run: dict[str, Any],
        provider_result: dict[str, Any],
        completed_at: str,
    ) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        provider_id = str(provider_result.get("providerId") or run["providerId"])
        for item in provider_result.get("outputs") or []:
            if not isinstance(item, dict):
                continue
            structured = item.get("structuredResult")
            if not isinstance(structured, dict):
                structured = {"value": structured}
            output = self._output(
                run=run,
                output_type=str(item.get("outputType") or "structured-result"),
                name=str(item.get("name") or "capability-output"),
                structured=structured,
                created_at=completed_at,
            )
            output["providerId"] = provider_id
            output["mediaType"] = str(item.get("mediaType") or "application/json")
            output["evidenceStatus"] = str(item.get("evidenceStatus") or "unverified")
            entity_references = item.get("entityReferences")
            if isinstance(entity_references, list):
                output["entityReferences"] = entity_references
            provenance = item.get("provenance")
            if isinstance(provenance, dict):
                output["provenance"] = provenance
            else:
                output["provenance"] = {
                    "schemaVersion": "1.0.0",
                    "sourceType": "external-provider",
                    "sourceReference": provider_id,
                    "derivedFromIds": [
                        run["artifactId"],
                        run["inputSnapshotId"],
                    ],
                    "notes": (
                        "Provider representation or runtime observation; "
                        "not proof of real component compatibility."
                    ),
                }
            normalized.append(output)
        return normalized

    def _record_external_workspace_reference(
        self,
        *,
        workspace_id: str,
        reference: dict[str, Any],
        updated_at: str,
    ) -> None:
        workspace = dict(self._kernel.get_workspace(workspace_id))
        references = list(workspace.get("externalWorkspaceReferences") or [])
        external_id = reference.get("externalReferenceId")
        references = [
            item
            for item in references
            if not (
                item.get("providerId") == reference.get("providerId")
                and item.get("externalReferenceId") == external_id
            )
        ]
        references.append(reference)
        workspace["externalWorkspaceReferences"] = references
        workspace["updatedAt"] = updated_at
        self._kernel.update_workspace(workspace)

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
