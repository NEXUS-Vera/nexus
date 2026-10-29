"""Bounded, review-paused repair over existing jobs, patches and project events.

No automatic approval and no model-authored verification. Each advance starts
at most one execution or correction proposal; callers explicitly advance after review.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Iterator
from contextlib import contextmanager
from threading import RLock
from typing import Any

from nexus_board.errors import BoardError, CommandValidationError
from nexus_board.ids import new_id
from nexus_board.services.draft_lease import is_lease_active

from nexus_embedded_systems.workflows.project_initialization.prompts.catalog import (
    EXECUTION_REPAIR_REQUEST,
)

# The existing API is a single-process sidecar. Serialize advances there;
# ledger revisions reject stale callers without another workflow state store.
_LOCK = RLock()
TERMINAL = {"exhausted", "cancelled", "rejected", "unavailable", "stopped", "completed"}
ACTIVE = {"queued", "starting", "running", "cancelling"}


def _unavailable(code: str) -> bool:
    return "UNAVAILABLE" in code or code in {
        "PROCESS_START_FAILED",
        "WOKWI_CLI_MISSING",
        "WOKWI_CREDENTIAL_MISSING",
        "SIMULATOR_FIXTURE_REJECTED",
    }


def _excerpt(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    if limit < 2:
        return text[:limit]
    half = limit // 2
    return text[:half] + text[-half:]


class RepairWorkflow:
    def __init__(self, kernel: Any) -> None:
        self.kernel = kernel
        self.runtime = kernel.workspace_runtime

    def get(self, project_id: str, repair_id: str) -> dict[str, Any]:
        if not isinstance(repair_id, str) or not repair_id:
            raise CommandValidationError("repairId must be a nonempty string")
        cursor = None
        states = []
        while True:
            events, cursor = self.kernel.ledger.list_events(project_id, limit=100, cursor=cursor)
            states.extend(
                json.loads(e["payload"]["summary"])
                for e in events
                if e["eventType"] == "decision.accepted"
                and e["subject"]["subjectId"] == repair_id
                and str(e["payload"].get("status", "")).startswith("repair.")
            )
            if cursor is None:
                break
        if not states:
            raise BoardError("Repair not found", code="REPAIR_NOT_FOUND")
        state = max(states, key=lambda s: s["revision"])
        if state.get("schemaVersion") != "1.0.0":
            raise CommandValidationError("Unsupported repair state schemaVersion")
        return copy.deepcopy(state)

    def _save(self, state: dict[str, Any], actor: dict[str, Any]) -> dict[str, Any]:
        state["revision"] += 1
        self.kernel.ledger.append(
            project_id=state["projectId"],
            event_type="decision.accepted",
            actor=actor,
            subject_type="decision",
            subject_id=state["repairId"],
            # An accepted execution-control request, not patch approval.
            # The existing event contract supports status and a summary string;
            # the owning workflow alone decodes its versioned progress summary.
            payload={"status": f"repair.{state['status']}", "summary": json.dumps(state)},
            correlation_id=state["repairId"],
        )
        return state

    def start(
        self,
        project_id: str,
        actor: dict[str, Any],
        run_id: str,
        target: str,
        max_attempts: int = 3,
        require_real: bool = True,
        scope: str = "full",
    ) -> dict[str, Any]:
        if not isinstance(scope, str) or scope not in {"build", "full"}:
            raise CommandValidationError("scope must be build or full")
        if type(max_attempts) is not int or not 1 <= max_attempts <= 3:
            raise CommandValidationError(
                "maxAttempts must be between 1 and 3 (initial run included)"
            )
        if not isinstance(run_id, str) or not run_id:
            raise CommandValidationError("executionRunId must be a nonempty string")
        if (
            not isinstance(target, str)
            or target not in {"firmware", "analysis"}
            or type(require_real) is not bool
        ):
            raise CommandValidationError(
                "target must be firmware or analysis; requireReal is boolean"
            )
        run = self.runtime.get_execution(project_id=project_id, execution_run_id=run_id)[
            "executionRun"
        ]
        if run["status"] in ACTIVE or run["status"] == "cancelled":
            raise CommandValidationError("Repair requires a terminal failure or failed assessment")
        stage = self._stage(run)
        if scope == "build" and (
            target != "firmware" or stage != "compile" or run["status"] != "failed"
        ):
            raise CommandValidationError(
                "Build scope requires a failed compile run and target firmware"
            )
        if stage in {"compile", "test"} and target != "firmware":
            raise CommandValidationError("Compiler failures require a firmware correction")
        if stage == "simulate" and target != "firmware":
            raise CommandValidationError("Simulator failures require a firmware correction")
        state = {
            "schemaVersion": "1.0.0",
            "repairId": new_id("repair"),
            "projectId": project_id,
            "revision": 0,
            "status": "inspect",
            "target": target,
            "scope": scope,
            "maxAttempts": max_attempts,
            "requireReal": require_real,
            "evidenceMode": "real-requested" if require_real else "regression",
            "attempts": [{"runIds": [run_id]}],
            "runId": run_id,
            "stage": stage,
            "rerunFirmwareTests": stage == "test",
        }
        if run["status"] in {"completed", "completed-with-warnings"}:
            cases = self._cases(project_id, run_id)
            if not cases or all(c.get("assessment") == "PASS" for c in cases):
                raise CommandValidationError("Completed run has no failed deterministic assessment")
        with _LOCK:
            return self._save(state, actor)

    def _stage(self, run: dict[str, Any]) -> str:
        if run.get("capability") == "circuit-simulation":
            return "simulate"
        workspace = self.kernel.kernel_store.get_workspace(run["workspaceId"])
        if workspace["artifactType"] == "firmware":
            snapshot = self.kernel.kernel_store.get_snapshot(run["inputSnapshotId"])
            return "test" if snapshot.get("reason") == "before-test" else "compile"
        if workspace["artifactType"] == "analysis":
            return "analyze"
        raise CommandValidationError("Unsupported repair execution operation")

    def _cases(self, project_id: str, run_id: str) -> list[dict[str, Any]]:
        cases = self.kernel.project_store.get_artifact(project_id, "test-plan")["content"][
            "testCases"
        ]
        return [
            c
            for c in cases
            if c.get("executionRunId") == run_id
            or any(e.get("executionRunId") == run_id for e in c.get("evidenceReferences", []))
        ]

    def advance(
        self,
        project_id: str,
        repair_id: str,
        actor: dict[str, Any],
        revision: int,
        *,
        cancel: bool = False,
    ) -> dict[str, Any]:
        with _LOCK:
            state = self.get(project_id, repair_id)
            if state["revision"] != revision:
                raise BoardError("Stale repair revision", code="REPAIR_CONFLICT")
            if state["status"] in TERMINAL:
                return state
            try:
                if cancel:
                    run = self.runtime.get_execution(
                        project_id=project_id, execution_run_id=state["runId"]
                    )["executionRun"]
                    if run["status"] in ACTIVE:
                        self.runtime.cancel_execution(
                            project_id=project_id, execution_run_id=state["runId"], actor=actor
                        )
                    state.update(
                        status="cancelled", explanation="Repair cancelled; attempts retained."
                    )
                elif state["status"] == "review":
                    proposal = self.kernel.kernel_store.get_firmware_patch_proposal(
                        state["proposalId"]
                    )
                    if proposal["status"] == "discarded":
                        state.update(
                            status="rejected", explanation="Correction rejected; no rerun."
                        )
                    elif proposal["status"] == "applied":
                        state["attempts"].append({"runIds": [], "proposalId": state["proposalId"]})
                        state["stage"] = "compile" if state["target"] == "firmware" else "analyze"
                        self._launch(state, actor)
                    else:
                        return state
                elif state["status"] == "running":
                    run = self.runtime.get_execution(
                        project_id=project_id, execution_run_id=state["runId"]
                    )["executionRun"]
                    if run["status"] in ACTIVE:
                        return state
                    if run["status"] in {"cancelled", "timed-out"}:
                        state.update(
                            status="cancelled" if run["status"] == "cancelled" else "stopped",
                            explanation=run["status"],
                        )
                    elif run["status"] not in {"completed", "completed-with-warnings"}:
                        state["status"] = "inspect"
                    elif state["stage"] == "compile" and state.get("scope", "full") == "build":
                        state.update(
                            status="completed",
                            explanation=(
                                "Build-only repair completed with a successful rebuild; "
                                "no simulation, analysis or P1-P5 evidence promotion."
                            ),
                        )
                    elif state["stage"] == "compile":
                        state["firmwareOutputId"] = self._output(
                            state, ".pio/build/nexus/firmware.elf"
                        )["outputId"]
                        state["stage"] = "test" if state["rerunFirmwareTests"] else "simulate"
                        self._launch(state, actor)
                    elif state["stage"] == "test":
                        self.kernel.verification.promote_execution_evidence(
                            project_id=project_id, execution_run_id=state["runId"], actor=actor
                        )
                        state["stage"] = "simulate"
                        self._launch(state, actor)
                    elif state["stage"] == "simulate":
                        self.kernel.verification.promote_execution_evidence(
                            project_id=project_id, execution_run_id=state["runId"], actor=actor
                        )
                        self._import(state, actor)
                        state["stage"] = "analyze"
                        self._launch(state, actor)
                    else:
                        self.kernel.verification.promote_execution_evidence(
                            project_id=project_id, execution_run_id=state["runId"], actor=actor
                        )
                        cases = [
                            c
                            for rid in state["attempts"][-1]["runIds"]
                            for c in self._cases(project_id, rid)
                        ]
                        state["status"] = (
                            "completed"
                            if cases
                            and all(
                                c.get("assessment") == "PASS"
                                and c.get("status") == "passed"
                                and c.get("assessmentAuthority") == "deterministic-code"
                                for c in cases
                            )
                            else "inspect"
                        )
                        state["explanation"] = (
                            "Deterministic assessment recorded; inspect linked test cases."
                        )
                elif state["status"] in {"launching", "diagnosing"}:
                    state.update(
                        status="stopped",
                        explanation=(
                            "Interrupted operation; inspect linked execution/proposal events "
                            "before starting another repair."
                        ),
                    )
                else:
                    self._inspect(state, actor)
            except BoardError as exc:
                # Synchronous providers persist a failed run before raising. Link it
                # through their existing causation events, including unavailable runs.
                cursor = None
                failed_run_id = None
                while True:
                    events, cursor = self.kernel.ledger.list_events(
                        project_id, limit=100, cursor=cursor
                    )
                    for event in events:
                        rid = event["payload"].get("executionRunId")
                        if event.get("correlationId") == repair_id and rid:
                            known = [r for a in state["attempts"] for r in a["runIds"]]
                            if rid not in known:
                                state["attempts"][-1]["runIds"].append(rid)
                                failed_run_id = rid
                    if cursor is None:
                        break
                if failed_run_id:
                    state["runId"] = failed_run_id
                state.update(
                    status=(
                        "unavailable"
                        if _unavailable(exc.code)
                        else "inspect"
                        if failed_run_id and state["stage"] == "simulate"
                        else "stopped"
                    ),
                    explanation=exc.message,
                    errorCode=exc.code,
                )
            return self._save(state, actor)

    def _inspect(self, state: dict[str, Any], actor: dict[str, Any]) -> None:
        project_id, run_id = state["projectId"], state["runId"]
        result = self.runtime.get_execution(project_id=project_id, execution_run_id=run_id)
        run, job = result["executionRun"], result.get("executionJob") or {}
        error = run.get("error") or {}
        if run["status"] in {"cancelled", "timed-out"}:
            state.update(status="stopped", explanation=run["status"])
            return
        if _unavailable(error.get("code", "")):
            state.update(
                status="unavailable",
                explanation="Execution prerequisite unavailable",
                errorCode=error.get("code"),
            )
            return
        chunks = (
            self.runtime.list_logs(project_id=project_id, execution_run_id=run_id, limit=100)[
                "chunks"
            ]
            if job
            else []
        )
        diagnostics = {
            "executionRunId": run_id,
            "snapshotId": run.get("inputSnapshotId"),
            "error": error,
            "job": {k: job.get(k) for k in ("exitCode", "failure", "logTruncated")},
            "logExcerpt": _excerpt("".join(c.get("content", "") for c in chunks), 4000),
            "logExcerptLimited": len(chunks) == 100
            or sum(len(c.get("content", "")) for c in chunks) > 4000,
            "testCases": [
                {
                    key: case.get(key)
                    for key in (
                        "testId",
                        "verificationMethod",
                        "criterion",
                        "actualResult",
                        "assessment",
                        "status",
                    )
                }
                for case in self._cases(project_id, run_id)
                if case.get("assessment") != "PASS"
            ]
            if state["stage"] in {"analyze", "simulate"}
            else [],
            "outputReferences": run.get("outputReferences", []),
        }
        state["attempts"][-1]["diagnostics"] = diagnostics
        if len(state["attempts"]) >= state["maxAttempts"]:
            state.update(
                status="exhausted", explanation="Attempt limit reached; failure evidence retained."
            )
            return
        request = EXECUTION_REPAIR_REQUEST + json.dumps(diagnostics, ensure_ascii=True)
        # Both existing patch contracts cap requestedChange at 4096 characters.
        # Keep the beginning and end of diagnostics and mark excerpts explicitly;
        # the complete original chunks stay linked to the failed execution.
        while len(request) > 4096 and diagnostics["logExcerpt"]:
            limit = len(diagnostics["logExcerpt"]) // 2
            diagnostics["logExcerpt"] = _excerpt(diagnostics["logExcerpt"], limit) if limit else ""
            diagnostics["logExcerptLimited"] = True
            request = EXECUTION_REPAIR_REQUEST + json.dumps(diagnostics, ensure_ascii=True)
        if len(request) > 4096:
            raise CommandValidationError(
                "Failure criteria exceed generation bound; inspect linked evidence"
            )
        method = (
            self.runtime.propose_firmware_patch
            if state["target"] == "firmware"
            else self.runtime.propose_analysis_patch
        )
        state["status"] = "diagnosing"
        self._save(state, actor)
        proposal = method(
            project_id=project_id,
            artifact_type=state["target"],
            actor=actor,
            requested_change=request,
            causation_id=state["repairId"],
            **({"require_model": True} if state["target"] == "analysis" else {}),
        )["proposal"]
        state.update(status="review", proposalId=proposal["proposalId"])
        if (proposal.get("generatorMetadata") or {}).get("mode") != "llm":
            state["evidenceMode"] = "regression"
        state["attempts"][-1]["correctionProposalId"] = proposal["proposalId"]

    def _output(self, state: dict[str, Any], name: str) -> dict[str, Any]:
        outputs = self.runtime.list_outputs_for_run(
            project_id=state["projectId"], execution_run_id=state["runId"]
        )["outputs"]
        matches = [o for o in outputs if o["name"] == name]
        if len(matches) != 1:
            raise CommandValidationError(f"Required output missing or ambiguous: {name}")
        return matches[0]

    @contextmanager
    def _downstream_lease(
        self, state: dict[str, Any], actor: dict[str, Any], artifact_type: str
    ) -> Iterator[dict[str, Any]]:
        binding = self.runtime.resolve_binding(
            project_id=state["projectId"], artifact_type=artifact_type, actor=actor
        )
        lease = binding["draft"].get("editLease")
        already_owned = is_lease_active(lease) and lease["ownerActorId"] == actor["actorId"]
        # Ordinary acquisition rejects an active lease owned by another actor.
        # Only release leases acquired here; caller-held leases remain intact.
        if not already_owned:
            try:
                self.kernel.workspaces.acquire_edit_lease(
                    workspace_id=binding["workspaceId"], actor=actor
                )
            except BoardError as exc:
                raise BoardError(
                    f"Repair cannot access {artifact_type} workspace: {exc.message}",
                    code=exc.code,
                ) from exc
        try:
            yield binding
        finally:
            if not already_owned:
                self.kernel.workspaces.release_edit_lease(
                    workspace_id=binding["workspaceId"], actor=actor
                )

    def _import(self, state: dict[str, Any], actor: dict[str, Any]) -> None:
        output = self._output(state, "serial.log")
        with self._downstream_lease(state, actor, "analysis") as binding:
            self.runtime.import_produced_output_into_analysis_input(
                project_id=state["projectId"],
                artifact_type="analysis",
                actor=actor,
                output_id=output["outputId"],
                path="data/serial.log",
                expected_draft_version=binding["draft"]["draftVersion"],
                base_artifact_version=binding["baseArtifactVersion"],
                base_project_state_version=self.kernel.project_store.get_project(
                    state["projectId"]
                )["currentStateVersion"],
            )

    def _launch(self, state: dict[str, Any], actor: dict[str, Any]) -> None:
        state["status"] = "launching"
        self._save(state, actor)
        common = {
            "project_id": state["projectId"],
            "actor": actor,
            "causation_id": state["repairId"],
        }
        if state["stage"] == "compile":
            result = self.runtime.compile_firmware(
                **common, artifact_type="firmware", require_real=state["requireReal"]
            )
        elif state["stage"] == "test":
            result = self.runtime.test_firmware(**common, artifact_type="firmware")
        elif state["stage"] == "analyze":
            with self._downstream_lease(state, actor, "analysis"):
                result = self.runtime.run_analysis(
                    **common, artifact_type="analysis", require_real=state["requireReal"]
                )
        else:
            with self._downstream_lease(state, actor, "electrical-architecture") as binding:
                snap = self.kernel.workspaces.create_snapshot(
                    workspace_id=binding["workspaceId"], actor=actor, reason="before-execution"
                )
                result = self.kernel.executions.execute(
                    **common,
                    artifact_id=binding["artifactId"],
                    artifact_type="electrical-architecture",
                    workspace_id=binding["workspaceId"],
                    snapshot_id=snap["snapshotId"],
                    capability="circuit-simulation",
                    base_artifact_version=binding["baseArtifactVersion"],
                    base_project_state_version=self.kernel.project_store.get_project(
                        state["projectId"]
                    )["currentStateVersion"],
                    options={"firmwareOutputId": state["firmwareOutputId"]},
                )
        state.update(status="running", runId=result["executionRun"]["executionRunId"])
        state["attempts"][-1]["runIds"].append(state["runId"])
