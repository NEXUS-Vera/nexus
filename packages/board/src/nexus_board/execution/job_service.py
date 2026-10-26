"""ExecutionJob lifecycle: enqueue, run, cancel, logs, cleanup, and recovery."""

from __future__ import annotations

import threading
from contextlib import suppress
from typing import Any, Protocol

from nexus_persistence.file_store.protocol import FileStore

from nexus_board.errors import BoardError, CommandValidationError
from nexus_board.execution.command_spec import validate_command_spec
from nexus_board.execution.failure_codes import (
    CLEANUP_FAILED,
    RUNTIME_LOST,
    RUNTIME_UNAVAILABLE,
    WORKSPACE_MATERIALIZATION_FAILED,
)
from nexus_board.execution.job_states import (
    JOB_TERMINAL_STATUSES,
    assert_job_transition,
    job_status_to_run_status,
)
from nexus_board.execution.limits import ExecutionLimits, default_execution_limits
from nexus_board.execution.materialize import (
    cleanup_materialization,
    materialize_filesystem_snapshot,
)
from nexus_board.execution.process_runtime import ProcessRuntime
from nexus_board.execution.runtime_factory import RuntimeUnavailableError
from nexus_board.execution.runtime_protocol import (
    ExecutionRuntime,
    RuntimeExecuteRequest,
)
from nexus_board.execution.scheduler import (
    InProcessExecutionScheduler,
    SchedulerConfig,
)
from nexus_board.ids import content_digest, new_id, utc_now_iso


class ExecutionJobNotFoundError(BoardError):
    code = "EXECUTION_JOB_NOT_FOUND"


class ExecutionJobCancelError(BoardError):
    code = "EXECUTION_JOB_CANCEL_FAILED"


class _KernelStore(Protocol):
    def create_execution_run(self, execution_run: dict[str, Any]) -> None: ...

    def update_execution_status(
        self, execution_run_id: str, execution_run: dict[str, Any]
    ) -> None: ...

    def get_execution_run(self, execution_run_id: str) -> dict[str, Any]: ...

    def create_execution_job(self, job: dict[str, Any]) -> None: ...

    def update_execution_job(self, job: dict[str, Any]) -> None: ...

    def get_execution_job(self, execution_job_id: str) -> dict[str, Any]: ...

    def get_execution_job_by_run(self, execution_run_id: str) -> dict[str, Any] | None: ...

    def list_nonterminal_execution_jobs(self) -> list[dict[str, Any]]: ...

    def append_execution_log_chunk(self, chunk: dict[str, Any]) -> None: ...

    def list_execution_log_chunks(
        self,
        execution_job_id: str,
        *,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]: ...

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


class ExecutionJobService:
    """Owns infrastructure ExecutionJob lifecycle for sandbox-execution runs."""

    def __init__(
        self,
        kernel_store: _KernelStore,
        project_store: _ProjectStore,
        file_store: FileStore,
        ledger: Any,
        projection: Any,
        *,
        runtime: ExecutionRuntime | None = None,
        scheduler: InProcessExecutionScheduler | None = None,
        scheduler_config: SchedulerConfig | None = None,
        default_limits: ExecutionLimits | None = None,
        auto_start: bool = True,
        recover_on_start: bool = True,
    ) -> None:
        self._kernel = kernel_store
        self._projects = project_store
        self._files = file_store
        self._ledger = ledger
        self._projection = projection
        self._runtime = runtime or ProcessRuntime()
        self._defaults = default_limits or default_execution_limits()
        self._log_lock = threading.Lock()
        self._log_bytes: dict[str, int] = {}
        self._log_seq: dict[str, int] = {}
        self._cancel_flags: dict[str, bool] = {}
        self._scheduler = scheduler or InProcessExecutionScheduler(
            scheduler_config,
            on_dispatch=self._dispatch_job,
        )
        if recover_on_start:
            self.recover_stranded_jobs()
        if auto_start:
            self._scheduler.start()

    @property
    def scheduler(self) -> InProcessExecutionScheduler:
        return self._scheduler

    @property
    def runtime(self) -> ExecutionRuntime:
        return self._runtime

    def shutdown(self) -> None:
        self._scheduler.stop(wait=False)

    def health(self) -> dict[str, Any]:
        availability = self._runtime.availability()
        sched = self._scheduler.health()
        return {
            "scheduler": sched,
            "runtimeAvailability": {
                "available": availability.available,
                "runtimeKind": availability.runtime_kind,
                "runtimeVersion": availability.runtime_version,
                "securityLevel": availability.security_level,
                "networkPolicy": availability.network_policy,
                "isolationGuarantees": list(availability.isolation_guarantees),
                "isolationLimitations": list(availability.isolation_limitations),
                "unavailableReason": availability.unavailable_reason,
                "details": dict(availability.details),
            },
            "queuedJobs": sched["queuedJobs"],
            "runningJobs": sched["runningJobs"],
            "globalCapacity": sched["globalCapacity"],
            "perProjectCapacity": sched["perProjectCapacity"],
            "rejectedJobs": sched["rejectedJobs"],
        }

    def recover_stranded_jobs(self) -> list[dict[str, Any]]:
        """Mark non-terminal jobs from a prior process as failed/runtime-lost.

        In-process scheduler ownership does not survive API restart. Process
        handles cannot be proven. Container handles are reconciled when
        present; otherwise jobs fail closed.
        """
        recovered: list[dict[str, Any]] = []
        for job in self._kernel.list_nonterminal_execution_jobs():
            if job.get("status") in JOB_TERMINAL_STATUSES:
                continue
            handle = dict(job.get("runtimeHandle") or {})
            terminal = self._runtime.reconcile_handle(handle)
            if terminal is None:
                continue
            failure_code = RUNTIME_LOST
            if terminal == "lost":
                terminal_status = "failed"
            elif terminal in JOB_TERMINAL_STATUSES:
                terminal_status = terminal
            else:
                terminal_status = "failed"
            with suppress(Exception):
                self._runtime.cleanup(job["executionJobId"], handle=handle)
            updated = dict(job)
            updated["failure"] = {
                "code": failure_code,
                "message": "Execution ownership lost after runtime restart",
            }
            status = updated["status"]
            try:
                if status == "queued":
                    updated = self._transition_job(updated, "cancelled", completed=True)
                    updated["failure"] = {
                        "code": RUNTIME_LOST,
                        "message": "Queued job abandoned after runtime restart",
                    }
                    self._kernel.update_execution_job(updated)
                elif status == "cancelling":
                    updated = self._transition_job(updated, "cancelled", completed=True)
                elif status in {"starting", "running"}:
                    if terminal_status == "cancelled":
                        updated = self._transition_job(updated, "cancelling")
                        updated = self._transition_job(updated, "cancelled", completed=True)
                    else:
                        updated = self._transition_job(updated, "failed", completed=True)
                else:
                    updated["status"] = "failed"
                    updated["completedAt"] = utc_now_iso()
                    self._kernel.update_execution_job(updated)
            except BoardError:
                updated["status"] = "failed"
                updated["completedAt"] = utc_now_iso()
                self._kernel.update_execution_job(updated)
            try:
                run = self._kernel.get_execution_run(updated["executionRunId"])
                self._finalize_run(run=run, job=updated, outputs=[])
            except Exception:  # noqa: BLE001
                pass
            recovered.append(updated)
        return recovered

    def submit(
        self,
        *,
        run: dict[str, Any],
        snapshot: dict[str, Any],
        command_spec: dict[str, Any],
        actor: dict[str, Any],
        limits: ExecutionLimits | None = None,
        causation_id: str | None = None,
    ) -> dict[str, Any]:
        """Create and enqueue an ExecutionJob for an already-persisted queued run."""
        del actor, causation_id
        availability = self._runtime.availability()
        if not availability.available:
            raise RuntimeUnavailableError(
                availability.unavailable_reason or "Execution runtime unavailable"
            )
        spec = validate_command_spec(command_spec)
        content = snapshot.get("content") or {}
        if content.get("kind") != "filesystem":
            raise CommandValidationError("sandbox-execution requires a filesystem snapshot")
        manifest = content.get("filesystemManifest") or {}
        manifest_digest = str(manifest.get("manifestDigest") or "")
        if not manifest_digest:
            raise CommandValidationError("filesystem snapshot missing manifestDigest")

        resolved_limits = limits or self._defaults
        runtime_identity: dict[str, Any] = {
            "runtimeKind": availability.runtime_kind,
            "runtimeVersion": availability.runtime_version,
            "workspaceSnapshotId": snapshot["snapshotId"],
            "workspaceManifestDigest": manifest_digest,
            "commandSpecVersion": "1.0.0",
            "limits": resolved_limits.to_contract(),
            "securityLevel": availability.security_level,
            "networkPolicy": availability.network_policy,
            "isolationGuarantees": list(availability.isolation_guarantees),
            "isolationLimitations": list(availability.isolation_limitations),
        }
        details = availability.details or {}
        if details.get("imageReference"):
            runtime_identity["imageReference"] = str(details["imageReference"])

        job_id = new_id("execjob")
        now = utc_now_iso()
        job: dict[str, Any] = {
            "schemaVersion": "1.0.0",
            "executionJobId": job_id,
            "executionRunId": run["executionRunId"],
            "projectId": run["projectId"],
            "workspaceSnapshotId": snapshot["snapshotId"],
            "status": "queued",
            "runtimeKind": availability.runtime_kind,
            "runtimeIdentity": runtime_identity,
            "commandSpec": spec,
            "limits": resolved_limits.to_contract(),
            "createdAt": now,
            "logTruncated": False,
        }
        self._kernel.create_execution_job(job)
        run = dict(run)
        run["executionJobId"] = job_id
        run["runtimeIdentity"] = runtime_identity
        run["status"] = "queued"
        self._kernel.update_execution_status(run["executionRunId"], run)

        def persist_queue_position(position: int) -> None:
            queued = dict(job)
            queued["queuePosition"] = position
            self._kernel.update_execution_job(queued)

        try:
            self._scheduler.enqueue(job_id, run["projectId"], on_enqueued=persist_queue_position)
        except BoardError as exc:
            job = dict(job)
            job["status"] = "failed"
            job["completedAt"] = utc_now_iso()
            job["failure"] = {
                "code": getattr(exc, "code", "EXECUTION_QUEUE_FULL"),
                "message": str(exc)[:500],
            }
            self._kernel.update_execution_job(job)
            run = dict(run)
            run["executionJobId"] = job_id
            run["runtimeIdentity"] = runtime_identity
            run["status"] = "failed"
            run["error"] = dict(job["failure"])
            run["completedAt"] = job["completedAt"]
            self._kernel.update_execution_status(run["executionRunId"], run)
            raise
        # Never write stale queued state after notifying the worker.
        job = self._kernel.get_execution_job(job_id)
        run = self._kernel.get_execution_run(run["executionRunId"])
        return {"executionJob": job, "executionRun": run}

    def cancel(
        self, execution_run_id: str, *, actor: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        del actor
        run = self._kernel.get_execution_run(execution_run_id)
        job = self._kernel.get_execution_job_by_run(execution_run_id)
        if job is None:
            raise ExecutionJobNotFoundError("No ExecutionJob for this run")
        status = job["status"]
        if status in JOB_TERMINAL_STATUSES:
            return {"executionJob": job, "executionRun": run}
        if status == "queued":
            self._scheduler.mark_queued_cancelled(job["executionJobId"])
            job = self._transition_job(job, "cancelled", completed=True)
            run = self._finalize_run(run=run, job=job, outputs=[])
            return {"executionJob": job, "executionRun": run}
        if status in {"starting", "running", "cancelling"}:
            self._cancel_flags[job["executionJobId"]] = True
            self._scheduler.mark_queued_cancelled(job["executionJobId"])
            if status != "cancelling":
                job = self._transition_job(job, "cancelling")
                run = self._sync_run_from_job(run, job)
            self._runtime.cancel(job["executionJobId"])
            return {"executionJob": job, "executionRun": run}
        raise ExecutionJobCancelError(f"Cannot cancel job in status {status}")

    def get_job_for_run(self, execution_run_id: str) -> dict[str, Any] | None:
        return self._kernel.get_execution_job_by_run(execution_run_id)

    def list_logs(
        self,
        execution_run_id: str,
        *,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> dict[str, Any]:
        job = self._kernel.get_execution_job_by_run(execution_run_id)
        if job is None:
            raise ExecutionJobNotFoundError("No ExecutionJob for this run")
        chunks = self._kernel.list_execution_log_chunks(
            job["executionJobId"],
            after_sequence=after_sequence,
            limit=limit,
        )
        return {
            "executionJobId": job["executionJobId"],
            "executionRunId": execution_run_id,
            "chunks": chunks,
            "logTruncated": bool(job.get("logTruncated")),
            "jobStatus": job["status"],
        }

    def cleanup_job(self, job_id: str) -> None:
        """Idempotent cleanup of runtime handles for a job."""
        job = self._kernel.get_execution_job(job_id)
        handle = dict(job.get("runtimeHandle") or {})
        self._runtime.cleanup(job_id, handle=handle)

    def _dispatch_job(self, job_id: str) -> None:
        job = self._kernel.get_execution_job(job_id)
        run = self._kernel.get_execution_run(job["executionRunId"])
        if self._scheduler.is_cancel_requested(job_id) or job["status"] == "cancelled":
            if job["status"] == "queued":
                job = self._transition_job(job, "cancelled", completed=True)
                self._finalize_run(run=run, job=job, outputs=[])
            return

        limits = ExecutionLimits.from_mapping(job.get("limits"))
        materialization = None
        cleanup_warning: str | None = None
        try:
            avail = self._runtime.availability()
            if not avail.available:
                job = dict(job)
                job["failure"] = {
                    "code": RUNTIME_UNAVAILABLE,
                    "message": (avail.unavailable_reason or "Runtime unavailable")[:500],
                }
                job = self._transition_job(job, "starting", started=True)
                job = self._transition_job(job, "failed", completed=True)
                self._finalize_run(run=run, job=job, outputs=[])
                return

            job = self._transition_job(job, "starting", started=True)
            run = self._sync_run_from_job(run, job)
            self._append_log(job_id, "system", "Job starting")

            try:
                materialization, manifest = materialize_filesystem_snapshot(
                    kernel_store=self._kernel,
                    file_store=self._files,
                    snapshot_id=job["workspaceSnapshotId"],
                    workspace_bytes_limit=limits.workspace_bytes,
                )
                del manifest
            except Exception as exc:  # noqa: BLE001
                job = dict(job)
                job["failure"] = {
                    "code": getattr(exc, "code", WORKSPACE_MATERIALIZATION_FAILED),
                    "message": str(exc)[:500] or "Workspace materialization failed",
                }
                job = self._transition_job(job, "failed", completed=True)
                self._append_log(job_id, "system", f"Materialization failed: {exc}")
                self._finalize_run(run=run, job=job, outputs=[])
                return

            if self._cancel_flags.get(job_id):
                job = self._transition_job(job, "cancelling")
                job = self._transition_job(job, "cancelled", completed=True)
                self._finalize_run(run=run, job=job, outputs=[])
                return

            job = self._transition_job(job, "running")
            run = self._sync_run_from_job(run, job)
            self._append_log(job_id, "system", "Job running")

            def _persist_handle(handle: dict[str, Any]) -> None:
                current = self._kernel.get_execution_job(job_id)
                current = dict(current)
                current["runtimeHandle"] = handle
                self._kernel.update_execution_job(current)
                nonlocal job
                job = current

            result = self._runtime.execute(
                RuntimeExecuteRequest(
                    job_id=job_id,
                    workspace_root=materialization,
                    command_spec=job["commandSpec"],
                    limits=limits,
                    cancel_check=lambda: bool(self._cancel_flags.get(job_id)),
                    on_started=_persist_handle,
                )
            )

            identity = dict(job.get("runtimeIdentity") or {})
            if result.executable_fingerprint:
                identity["executableFingerprint"] = result.executable_fingerprint
            if result.image_reference:
                identity["imageReference"] = result.image_reference
            if result.image_digest:
                identity["imageDigest"] = result.image_digest
            identity["securityLevel"] = avail.security_level
            identity["networkPolicy"] = avail.network_policy
            job = dict(job)
            job["runtimeIdentity"] = identity
            job["exitCode"] = result.exit_code
            job["logTruncated"] = bool(result.log_truncated)
            if result.failure_code:
                job["failure"] = {
                    "code": result.failure_code,
                    "message": (result.failure_message or result.failure_code)[:500],
                }
            if result.cleanup_warning:
                cleanup_warning = result.cleanup_warning
                job["cleanupWarning"] = cleanup_warning

            if result.stdout:
                self._append_log(job_id, "stdout", result.stdout, limits=limits)
            if result.stderr:
                self._append_log(job_id, "stderr", result.stderr, limits=limits)
            for message in result.system_messages:
                self._append_log(job_id, "system", message, limits=limits)

            terminal = result.status
            if any(
                entry.get("name") == "NEXUS_FIRMWARE_PROFILE"
                for entry in job["commandSpec"].get("environment", [])
            ):
                unsafe_flags = [
                    flag
                    for flag in ("-Woverflow", "-Wdiv-by-zero")
                    if flag in result.stdout or flag in result.stderr
                ]
                if unsafe_flags:
                    job["failure"] = {
                        "code": "FIRMWARE_UNSAFE_COMPILER_WARNING",
                        "message": "Unsafe firmware compiler warning: " + ", ".join(unsafe_flags),
                    }
                    self._append_log(job_id, "system", job["failure"]["message"], limits=limits)
                    if terminal == "succeeded":
                        terminal = "failed"
            if (
                terminal == "cancelled"
                and job["status"] != "cancelling"
                and job["status"] in {"starting", "running"}
            ):
                job = self._transition_job(job, "cancelling")
            assert_job_transition(job["status"], terminal)
            job = self._transition_job(job, terminal, completed=True)

            outputs: list[dict[str, Any]] = []
            if terminal == "succeeded":
                outputs = self._promote_outputs(run=run, job=job, collected=result.outputs)
            self._finalize_run(run=run, job=job, outputs=outputs, cleanup_warning=cleanup_warning)
        except Exception as exc:  # noqa: BLE001
            try:
                if job["status"] not in JOB_TERMINAL_STATUSES and job["status"] not in {
                    "failed",
                    "timed-out",
                    "cancelled",
                }:
                    target = "failed"
                    if job["status"] in {"starting", "running", "cancelling"}:
                        try:
                            assert_job_transition(job["status"], target)
                        except BoardError:
                            target = "cancelled" if job["status"] == "cancelling" else "failed"
                    job = dict(job)
                    job["failure"] = {
                        "code": getattr(exc, "code", type(exc).__name__.upper()),
                        "message": str(exc)[:500] or "Job failed",
                    }
                    if job["status"] not in JOB_TERMINAL_STATUSES:
                        job = self._transition_job(job, "failed", completed=True)
                self._append_log(job_id, "system", f"Job failed: {exc}")
                self._finalize_run(run=run, job=job, outputs=[])
            except Exception:  # noqa: BLE001
                pass
        finally:
            try:
                self._runtime.cleanup(job_id, handle=dict(job.get("runtimeHandle") or {}))
            except Exception as exc:  # noqa: BLE001
                try:
                    latest = self._kernel.get_execution_job(job_id)
                    if latest.get("status") == "succeeded" and not latest.get("cleanupWarning"):
                        latest = dict(latest)
                        latest["cleanupWarning"] = f"{CLEANUP_FAILED}: {exc}"[:500]
                        self._kernel.update_execution_job(latest)
                except Exception:  # noqa: BLE001
                    pass
            cleanup_materialization(materialization)
            self._cancel_flags.pop(job_id, None)
            self._log_bytes.pop(job_id, None)
            self._log_seq.pop(job_id, None)

    def _transition_job(
        self,
        job: dict[str, Any],
        nxt: str,
        *,
        started: bool = False,
        completed: bool = False,
    ) -> dict[str, Any]:
        assert_job_transition(job["status"], nxt)
        updated = dict(job)
        updated["status"] = nxt
        now = utc_now_iso()
        if started and "startedAt" not in updated:
            updated["startedAt"] = now
        if completed:
            updated["completedAt"] = now
        self._kernel.update_execution_job(updated)
        return updated

    def _sync_run_from_job(self, run: dict[str, Any], job: dict[str, Any]) -> dict[str, Any]:
        updated = dict(run)
        updated["status"] = job_status_to_run_status(job["status"])
        updated["executionJobId"] = job["executionJobId"]
        updated["runtimeIdentity"] = job.get("runtimeIdentity")
        if job.get("startedAt"):
            updated["startedAt"] = job["startedAt"]
        if job.get("completedAt"):
            updated["completedAt"] = job["completedAt"]
        if job.get("failure"):
            updated["error"] = dict(job["failure"])
        self._kernel.update_execution_status(updated["executionRunId"], updated)
        return updated

    def _finalize_run(
        self,
        *,
        run: dict[str, Any],
        job: dict[str, Any],
        outputs: list[dict[str, Any]],
        cleanup_warning: str | None = None,
    ) -> dict[str, Any]:
        project_id = run["projectId"]
        completed = job.get("completedAt") or utc_now_iso()
        stale = False
        try:
            project = self._projects.get_project(project_id)
            current_state = int(project["currentStateVersion"])
            stale = current_state != int(run["baseProjectStateVersion"])
        except Exception:  # noqa: BLE001
            stale = False

        updated = dict(run)
        updated["executionJobId"] = job["executionJobId"]
        updated["runtimeIdentity"] = job.get("runtimeIdentity")
        updated["completedAt"] = completed
        if cleanup_warning:
            updated["cleanupWarning"] = cleanup_warning
        if stale:
            updated["status"] = "stale"
            updated["outputReferences"] = []
            updated["evidenceReferences"] = []
            if job.get("failure"):
                updated["error"] = dict(job["failure"])
            self._kernel.update_execution_status(updated["executionRunId"], updated)
            self._ledger.append(
                project_id=project_id,
                event_type="execution.failed",
                actor={
                    "schemaVersion": "1.0.0",
                    "actorId": "actor_SYSTEM",
                    "actorType": "system",
                },
                subject_type="execution",
                subject_id=updated["executionRunId"],
                payload={
                    "executionRunId": updated["executionRunId"],
                    "reason": "STALE_EXECUTION_RESULT",
                },
                occurred_at=completed,
            )
            self._projection.update_after_write(project_id)
            return updated

        for output in outputs:
            self._kernel.create_produced_output(output)
            self._ledger.append(
                project_id=project_id,
                event_type="output.produced",
                actor={
                    "schemaVersion": "1.0.0",
                    "actorId": "actor_SYSTEM",
                    "actorType": "system",
                },
                subject_type="output",
                subject_id=output["outputId"],
                payload={
                    "outputId": output["outputId"],
                    "executionRunId": updated["executionRunId"],
                    "outputType": output["outputType"],
                },
                occurred_at=completed,
            )

        updated["outputReferences"] = [o["outputId"] for o in outputs]
        updated["evidenceReferences"] = [f"ev_{o['outputId'][4:]}" for o in outputs]
        if outputs:
            updated["logReference"] = outputs[-1]["outputId"]
        status = job_status_to_run_status(job["status"])
        if cleanup_warning and status == "completed":
            status = "completed-with-warnings"
        updated["status"] = status
        if job.get("failure") and updated["status"] in {"failed", "timed-out", "cancelled"}:
            updated["error"] = dict(job["failure"])
        self._kernel.update_execution_status(updated["executionRunId"], updated)

        event_type = (
            "execution.completed"
            if updated["status"] in {"completed", "completed-with-warnings"}
            else "execution.failed"
        )
        self._ledger.append(
            project_id=project_id,
            event_type=event_type,
            actor={
                "schemaVersion": "1.0.0",
                "actorId": "actor_SYSTEM",
                "actorType": "system",
            },
            subject_type="execution",
            subject_id=updated["executionRunId"],
            payload={
                "executionRunId": updated["executionRunId"],
                "executionJobId": job["executionJobId"],
                "status": updated["status"],
            },
            occurred_at=completed,
        )
        self._projection.update_after_write(project_id)
        return updated

    def _promote_outputs(
        self,
        *,
        run: dict[str, Any],
        job: dict[str, Any],
        collected: list[Any],
    ) -> list[dict[str, Any]]:
        outputs: list[dict[str, Any]] = []
        now = utc_now_iso()
        for item in collected:
            content: dict[str, Any]
            is_binary = b"\x00" in item.content
            try:
                item.content.decode("utf-8")
                is_utf8 = True
            except UnicodeDecodeError:
                is_utf8 = False
            if len(item.content) > 1024 or is_binary or not is_utf8:
                content_hash = self._files.put(item.content)
                content = {
                    "kind": "storage-reference",
                    "storageKind": "file-store",
                    "uri": content_hash,
                }
                digest = content_hash
            else:
                structured = {
                    "path": item.path,
                    "kind": item.kind,
                    "text": item.content.decode("utf-8", errors="replace"),
                }
                content = {
                    "kind": "inline-structured",
                    "structuredResult": structured,
                }
                digest = content_digest(structured)
            output_type = {
                "result": "structured-result",
                "artifact": "file-reference",
                "log": "log",
            }.get(item.kind, "file-reference")
            outputs.append(
                {
                    "schemaVersion": "1.0.0",
                    "outputId": new_id("out"),
                    "projectId": run["projectId"],
                    "artifactId": run["artifactId"],
                    "workspaceId": run["workspaceId"],
                    "executionRunId": run["executionRunId"],
                    "providerId": run.get("providerId"),
                    "outputType": output_type,
                    "name": item.path,
                    "mediaType": "application/octet-stream",
                    "content": content,
                    "contentDigest": digest,
                    "createdAt": now,
                    "evidenceStatus": "unverified",
                    "supports": [{"supportKind": "artifact", "targetId": run["artifactId"]}],
                    "provenance": {
                        "schemaVersion": "1.0.0",
                        "sourceType": "external-provider",
                        "sourceReference": job["executionJobId"],
                        "derivedFromIds": [run["artifactId"], run["inputSnapshotId"]],
                        "notes": "Runtime produced output; not engineering evidence by itself.",
                    },
                }
            )
        return outputs

    def _append_log(
        self,
        job_id: str,
        stream: str,
        content: str,
        *,
        limits: ExecutionLimits | None = None,
    ) -> None:
        if not content:
            return
        resolved = limits or self._defaults
        with self._lock_for_logs():
            used = self._log_bytes.get(job_id, 0)
            seq = self._log_seq.get(job_id, 0)
            remaining = resolved.total_log_bytes - used
            if remaining <= 0:
                job = self._kernel.get_execution_job(job_id)
                if not job.get("logTruncated"):
                    job = dict(job)
                    job["logTruncated"] = True
                    self._kernel.update_execution_job(job)
                return
            chunk_limit = min(resolved.log_chunk_bytes, remaining)
            offset = 0
            truncated = False
            while offset < len(content):
                piece = content[offset : offset + chunk_limit]
                offset += len(piece)
                if (
                    offset < len(content)
                    and used + len(piece.encode("utf-8")) >= resolved.total_log_bytes
                ):
                    truncated = True
                seq += 1
                encoded = piece.encode("utf-8")
                used += len(encoded)
                self._kernel.append_execution_log_chunk(
                    {
                        "schemaVersion": "1.0.0",
                        "executionJobId": job_id,
                        "sequence": seq,
                        "stream": stream,
                        "timestamp": utc_now_iso(),
                        "content": piece,
                        "truncated": truncated and offset >= len(content),
                    }
                )
                if used >= resolved.total_log_bytes:
                    job = self._kernel.get_execution_job(job_id)
                    job = dict(job)
                    job["logTruncated"] = True
                    self._kernel.update_execution_job(job)
                    break
            self._log_bytes[job_id] = used
            self._log_seq[job_id] = seq

    def _lock_for_logs(self) -> threading.Lock:
        return self._log_lock
