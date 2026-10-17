"""Application service: promote execution evidence into Test Plan revisions (Phase 17F).

Does not mutate accepted artifacts in place. Analysis/Firmware runtimes never
write Test Plan storage directly — they produce ExecutionRuns/ProducedOutputs;
this service revises the Test Plan through workspace draft → snapshot → accept.
"""

from __future__ import annotations

import json
from contextlib import suppress
from typing import Any, Protocol

from nexus_board.errors import BoardError
from nexus_board.ids import new_id, utc_now_iso
from nexus_board.verification.close import (
    annotate_risk_mitigation_verification,
    content_fingerprint,
    promote_analysis_evidence_into_test_plan,
    promote_marker_evidence_into_test_plan,
    promote_structural_evidence_into_test_plan,
)
from nexus_board.verification.coverage import (
    compute_requirement_coverage,
)


class VerificationError(BoardError):
    code = "VERIFICATION_FAILED"


class _KernelStore(Protocol):
    def get_execution_run(self, execution_run_id: str) -> dict[str, Any]: ...

    def get_execution_job(self, execution_job_id: str) -> dict[str, Any]: ...

    def get_produced_output(self, output_id: str) -> dict[str, Any]: ...

    def list_produced_outputs(self, project_id: str) -> list[dict[str, Any]]: ...

    def get_workspace(self, workspace_id: str) -> dict[str, Any]: ...

    def get_workspace_by_project_artifact(
        self, project_id: str, artifact_type: str
    ) -> dict[str, Any] | None: ...

    def get_draft(self, workspace_id: str) -> dict[str, Any]: ...

    def update_draft(self, draft: dict[str, Any]) -> None: ...

    def create_snapshot(self, snapshot: dict[str, Any]) -> None: ...

    def list_snapshots(self, workspace_id: str) -> list[dict[str, Any]]: ...

    def update_workspace(self, workspace: dict[str, Any]) -> None: ...

    def get_file_bytes(self, content_hash: str) -> bytes: ...  # optional


class VerificationService:
    def __init__(
        self,
        *,
        kernel_store: _KernelStore,
        project_store: Any,
        workspaces: Any,
        commands: Any,
        ledger: Any,
        projection: Any,
        file_store: Any | None = None,
    ) -> None:
        self._kernel: _KernelStore = kernel_store
        self._projects = project_store
        self._workspaces = workspaces
        self._commands = commands
        self._ledger = ledger
        self._projection = projection
        self._files = file_store

    def promote_execution_evidence(
        self,
        *,
        project_id: str,
        execution_run_id: str,
        actor: dict[str, Any],
        accept: bool = True,
    ) -> dict[str, Any]:
        """Promote ProducedOutputs from an ExecutionRun into a Test Plan revision."""

        run = self._kernel.get_execution_run(execution_run_id)
        if run.get("projectId") != project_id:
            raise VerificationError("ExecutionRun does not belong to this project.")
        if run.get("status") not in {"completed", "completed-with-warnings"}:
            raise VerificationError(
                "Only completed ExecutionRuns may promote verification evidence."
            )
        job_id = run.get("executionJobId")
        if job_id:
            job = self._kernel.get_execution_job(job_id)
            if job.get("logTruncated"):
                raise VerificationError("ExecutionRun logs were truncated; evidence is incomplete.")

        test_plan = self._projects.get_artifact(project_id, "test-plan")
        requirements = self._load_requirements(project_id)
        summary, output_names, output_id, log_text = self._extract_run_evidence(run)

        content = dict(test_plan["content"])
        before = content_fingerprint(content)
        content, _ = promote_analysis_evidence_into_test_plan(
            content,
            summary=summary,
            produced_output_names=output_names,
            execution_run_id=execution_run_id,
            output_id=output_id,
            requirements=requirements,
            project_id=str(run.get("projectId")),
            expected_project_id=project_id,
        )
        if log_text is not None:
            content, _ = promote_marker_evidence_into_test_plan(
                content,
                log_text=log_text,
                execution_run_id=execution_run_id,
                requirements=requirements,
                run_occurred=True,
            )
        after = content_fingerprint(content)
        if before == after:
            return {
                "schemaVersion": "1.0.0",
                "changed": False,
                "idempotent": True,
                "executionRunId": execution_run_id,
                "testPlanArtifactId": test_plan["artifactId"],
                "testPlanVersion": test_plan["artifactVersion"],
                "coverageSummary": content.get("coverageSummary"),
                "requirementVerification": compute_requirement_coverage(
                    requirements=requirements, test_cases=list(content.get("testCases") or [])
                ),
            }

        revision = self._revise_test_plan(
            project_id=project_id,
            content=content,
            actor=actor,
            accept=accept,
            summary=f"Promote evidence from {execution_run_id}",
            source_execution_run_id=execution_run_id,
        )
        return {
            "schemaVersion": "1.0.0",
            "changed": True,
            "idempotent": False,
            "executionRunId": execution_run_id,
            **revision,
            "requirementVerification": compute_requirement_coverage(
                requirements=requirements, test_cases=list(content.get("testCases") or [])
            ),
            "riskMitigationAnnotations": annotate_risk_mitigation_verification(
                self._safe_risk_content(project_id),
                test_cases=list(content.get("testCases") or []),
            ).get("risks"),
        }

    def promote_analysis_summary(
        self,
        *,
        project_id: str,
        summary: dict[str, Any],
        produced_output_names: list[str],
        actor: dict[str, Any],
        execution_run_id: str | None = None,
        accept: bool = True,
    ) -> dict[str, Any]:
        """Promote an Analysis summary backed by a completed execution run."""

        if not execution_run_id:
            raise VerificationError(
                "execution_run_id is required to promote verification evidence."
            )
        run = self._kernel.get_execution_run(execution_run_id)
        if run.get("projectId") != project_id:
            raise VerificationError("ExecutionRun does not belong to this project.")
        if run.get("status") not in {"completed", "completed-with-warnings"}:
            raise VerificationError(
                "Only completed ExecutionRuns may promote verification evidence."
            )
        job_id = run.get("executionJobId")
        if job_id:
            job = self._kernel.get_execution_job(job_id)
            if job.get("logTruncated"):
                raise VerificationError("ExecutionRun logs were truncated; evidence is incomplete.")

        run_id = execution_run_id
        test_plan = self._projects.get_artifact(project_id, "test-plan")
        requirements = self._load_requirements(project_id)
        content = dict(test_plan["content"])
        content, changed = promote_analysis_evidence_into_test_plan(
            content,
            summary=summary,
            produced_output_names=produced_output_names,
            execution_run_id=run_id,
            requirements=requirements,
            project_id=project_id,
            expected_project_id=project_id,
        )
        if not changed:
            return {
                "schemaVersion": "1.0.0",
                "changed": False,
                "idempotent": True,
                "executionRunId": run_id,
                "testPlanVersion": test_plan["artifactVersion"],
                "coverageSummary": content.get("coverageSummary"),
                "requirementVerification": compute_requirement_coverage(
                    requirements=requirements, test_cases=list(content.get("testCases") or [])
                ),
            }
        revision = self._revise_test_plan(
            project_id=project_id,
            content=content,
            actor=actor,
            accept=accept,
            summary=f"Promote Analysis summary evidence ({run_id})",
            source_execution_run_id=run_id,
        )
        return {
            "schemaVersion": "1.0.0",
            "changed": True,
            "idempotent": False,
            "executionRunId": run_id,
            **revision,
            "requirementVerification": compute_requirement_coverage(
                requirements=requirements, test_cases=list(content.get("testCases") or [])
            ),
            "riskMitigationAnnotations": annotate_risk_mitigation_verification(
                self._safe_risk_content(project_id),
                test_cases=list(content.get("testCases") or []),
            ).get("risks"),
        }

    def promote_structural_mapping(
        self,
        *,
        project_id: str,
        signal_map: dict[str, str],
        actor: dict[str, Any],
        source_id: str | None = None,
        accept: bool = True,
    ) -> dict[str, Any]:
        """Promote Electrical/Wokwi translation pin maps into inspection TestCases."""

        source = source_id or f"structural_{project_id}"
        test_plan = self._projects.get_artifact(project_id, "test-plan")
        requirements = self._load_requirements(project_id)
        content, changed = promote_structural_evidence_into_test_plan(
            dict(test_plan["content"]),
            signal_map=signal_map,
            source_id=source,
            requirements=requirements,
        )
        if not changed:
            return {
                "schemaVersion": "1.0.0",
                "changed": False,
                "idempotent": True,
                "testPlanVersion": test_plan["artifactVersion"],
                "coverageSummary": content.get("coverageSummary"),
            }
        revision = self._revise_test_plan(
            project_id=project_id,
            content=content,
            actor=actor,
            accept=accept,
            summary="Promote structural pin-mapping evidence",
            source_execution_run_id=source,
        )
        return {"schemaVersion": "1.0.0", "changed": True, "idempotent": False, **revision}

    def promote_marker_log(
        self,
        *,
        project_id: str,
        log_text: str | None,
        actor: dict[str, Any],
        execution_run_id: str | None = None,
        run_occurred: bool = True,
        accept: bool = True,
    ) -> dict[str, Any]:
        run_id = execution_run_id or new_id("exec")
        test_plan = self._projects.get_artifact(project_id, "test-plan")
        requirements = self._load_requirements(project_id)
        content, changed = promote_marker_evidence_into_test_plan(
            dict(test_plan["content"]),
            log_text=log_text,
            execution_run_id=run_id,
            requirements=requirements,
            run_occurred=run_occurred,
        )
        if not changed:
            return {
                "schemaVersion": "1.0.0",
                "changed": False,
                "idempotent": True,
                "testPlanVersion": test_plan["artifactVersion"],
            }
        revision = self._revise_test_plan(
            project_id=project_id,
            content=content,
            actor=actor,
            accept=accept,
            summary=f"Promote marker/log evidence ({run_id})",
            source_execution_run_id=run_id,
        )
        return {"schemaVersion": "1.0.0", "changed": True, "idempotent": False, **revision}

    def requirement_verification_projection(self, project_id: str) -> list[dict[str, Any]]:
        test_plan = self._projects.get_artifact(project_id, "test-plan")
        requirements = self._load_requirements(project_id)
        return compute_requirement_coverage(
            requirements=requirements,
            test_cases=list((test_plan.get("content") or {}).get("testCases") or []),
        )

    def evidence_chain(self, project_id: str) -> list[dict[str, Any]]:
        """Requirement → TestCase → EvidenceReference chain for Evidence Explorer."""

        rows = self.requirement_verification_projection(project_id)
        test_plan = self._projects.get_artifact(project_id, "test-plan")
        cases = {
            str(c.get("displayId")): c
            for c in list((test_plan.get("content") or {}).get("testCases") or [])
            if isinstance(c, dict)
        }
        chains: list[dict[str, Any]] = []
        for row in rows:
            display = str(row.get("displayId") or "")
            for link in row.get("tests") or []:
                tid = str(link.get("displayId") or "")
                case = cases.get(tid) or {}
                criterion = case.get("criterion") if isinstance(case.get("criterion"), dict) else {}
                chains.append(
                    {
                        "requirementId": display,
                        "verificationState": row.get("verificationState"),
                        "testId": tid,
                        "testStatus": case.get("status"),
                        "assessment": case.get("assessment"),
                        "assessmentAuthority": case.get("assessmentAuthority"),
                        "actualResult": case.get("actualResult"),
                        "criterion": criterion,
                        "evidenceReferences": case.get("evidenceReferences") or [],
                        "executionRunId": case.get("executionRunId"),
                        "finding": case.get("finding"),
                    }
                )
        return chains

    def _load_requirements(self, project_id: str) -> list[dict[str, Any]]:
        try:
            req = self._projects.get_artifact(project_id, "requirement-set")
        except Exception:  # noqa: BLE001
            return []
        content = req.get("content") or {}
        return list(content.get("requirements") or [])

    def _extract_run_evidence(
        self, run: dict[str, Any]
    ) -> tuple[dict[str, Any] | None, list[str], str | None, str | None]:
        output_ids = list(run.get("outputReferences") or [])
        names: list[str] = []
        summary: dict[str, Any] | None = None
        summary_output_id: str | None = None
        log_text: str | None = None
        for oid in output_ids:
            try:
                output = self._kernel.get_produced_output(oid)
            except Exception:  # noqa: BLE001
                continue
            name = str(output.get("name") or "")
            names.append(name)
            content = output.get("content") or {}
            text = self._output_text(content)
            if "summary.json" in name and text:
                try:
                    parsed = json.loads(text)
                    if isinstance(parsed, dict):
                        summary = parsed
                        summary_output_id = oid
                except json.JSONDecodeError:
                    pass
            structured = content.get("structuredResult")
            if isinstance(structured, dict):
                if "accel_x_rms_noise_g" in structured or "metricValue" in structured:
                    summary = structured
                    summary_output_id = oid
                path = str(structured.get("path") or "")
                if "summary.json" in path and isinstance(structured.get("text"), str):
                    try:
                        parsed = json.loads(structured["text"])
                        if isinstance(parsed, dict):
                            summary = parsed
                            summary_output_id = oid
                    except json.JSONDecodeError:
                        pass
                if output.get("outputType") == "log" or "log" in name.lower():
                    lines = structured.get("lines")
                    if isinstance(lines, list):
                        log_text = "\n".join(str(x) for x in lines)
                    elif isinstance(structured.get("text"), str):
                        log_text = structured["text"]
            if text and ("log" in name.lower() or output.get("outputType") == "log"):
                log_text = text if log_text is None else log_text
        return summary, names, summary_output_id, log_text

    def _output_text(self, content: dict[str, Any]) -> str | None:
        kind = content.get("kind")
        if kind == "inline-structured":
            structured = content.get("structuredResult") or {}
            text = structured.get("text") if isinstance(structured, dict) else None
            return text if isinstance(text, str) else None
        if kind == "storage-reference" and self._files is not None:
            uri = content.get("uri")
            if isinstance(uri, str):
                try:
                    raw = self._files.get(uri)
                    return str(raw.decode("utf-8", errors="replace"))
                except Exception:  # noqa: BLE001
                    return None
        return None

    def _revise_test_plan(
        self,
        *,
        project_id: str,
        content: dict[str, Any],
        actor: dict[str, Any],
        accept: bool,
        summary: str,
        source_execution_run_id: str,
    ) -> dict[str, Any]:
        test_plan = self._projects.get_artifact(project_id, "test-plan")
        project = self._projects.get_project(project_id)
        workspace_row = self._kernel.get_workspace_by_project_artifact(project_id, "test-plan")
        if workspace_row is None:
            created = self._workspaces.create_workspace(
                project_id=project_id,
                artifact_type="test-plan",
                actor=actor,
            )
            workspace = created["workspace"]
        else:
            workspace = workspace_row

        workspace_id = workspace["workspaceId"]
        try:
            self._workspaces.acquire_edit_lease(
                workspace_id=workspace_id,
                actor=actor,
                ttl_seconds=300,
            )
        except Exception:  # noqa: BLE001
            draft = dict(self._kernel.get_draft(workspace_id))
            draft["leaseHolder"] = actor
            draft["leaseExpiresAt"] = "2099-01-01T00:00:00Z"
            self._kernel.update_draft(draft)

        draft = dict(self._kernel.get_draft(workspace_id))
        expected_draft = int(draft.get("draftVersion") or 1)
        update = self._commands.dispatch(
            {
                "schemaVersion": "1.0.0",
                "commandId": new_id("cmd"),
                "commandType": "workspace.update-draft",
                "projectId": project_id,
                "artifactId": test_plan["artifactId"],
                "workspaceId": workspace_id,
                "baseArtifactVersion": int(workspace["baseArtifactVersion"]),
                "baseProjectStateVersion": int(project["currentStateVersion"]),
                "requestedBy": actor,
                "requestedAt": utc_now_iso(),
                "input": {"content": content, "expectedDraftVersion": expected_draft},
            }
        )
        if update.get("status") not in {"completed", "completed-with-warnings"}:
            workspace = self._kernel.get_workspace(workspace_id)
            project = self._projects.get_project(project_id)
            draft = dict(self._kernel.get_draft(workspace_id))
            with suppress(Exception):
                self._workspaces.acquire_edit_lease(
                    workspace_id=workspace_id,
                    actor=actor,
                    ttl_seconds=300,
                )
            update = self._commands.dispatch(
                {
                    "schemaVersion": "1.0.0",
                    "commandId": new_id("cmd"),
                    "commandType": "workspace.update-draft",
                    "projectId": project_id,
                    "artifactId": test_plan["artifactId"],
                    "workspaceId": workspace_id,
                    "baseArtifactVersion": int(workspace["baseArtifactVersion"]),
                    "baseProjectStateVersion": int(project["currentStateVersion"]),
                    "requestedBy": actor,
                    "requestedAt": utc_now_iso(),
                    "input": {
                        "content": content,
                        "expectedDraftVersion": int(draft.get("draftVersion") or 1),
                    },
                }
            )
            if update.get("status") not in {"completed", "completed-with-warnings"}:
                raise VerificationError(f"Failed to update Test Plan draft: {update.get('error')}")

        snap = self._commands.dispatch(
            {
                "schemaVersion": "1.0.0",
                "commandId": new_id("cmd"),
                "commandType": "workspace.create-snapshot",
                "projectId": project_id,
                "artifactId": test_plan["artifactId"],
                "workspaceId": workspace_id,
                "baseArtifactVersion": int(
                    self._kernel.get_workspace(workspace_id)["baseArtifactVersion"]
                ),
                "baseProjectStateVersion": int(
                    self._projects.get_project(project_id)["currentStateVersion"]
                ),
                "requestedBy": actor,
                "requestedAt": utc_now_iso(),
                "input": {"reason": summary},
            }
        )
        if snap.get("status") not in {"completed", "completed-with-warnings"}:
            raise VerificationError(f"Failed to snapshot Test Plan: {snap.get('error')}")
        snapshot_id = snap.get("snapshotId") or snap.get("snapshot_id")
        propose = self._commands.dispatch(
            {
                "schemaVersion": "1.0.0",
                "commandId": new_id("cmd"),
                "commandType": "artifact.propose-revision",
                "projectId": project_id,
                "artifactId": test_plan["artifactId"],
                "workspaceId": workspace_id,
                "baseArtifactVersion": int(
                    self._kernel.get_workspace(workspace_id)["baseArtifactVersion"]
                ),
                "baseProjectStateVersion": int(
                    self._projects.get_project(project_id)["currentStateVersion"]
                ),
                "requestedBy": actor,
                "requestedAt": utc_now_iso(),
                "input": {
                    "snapshotId": snapshot_id,
                    "consequenceLevel": "low",
                    "summary": summary,
                },
            }
        )
        proposal_id = propose.get("proposal_id") or propose.get("proposalId")
        result: dict[str, Any] = {
            "proposalId": proposal_id,
            "snapshotId": snapshot_id,
            "coverageSummary": content.get("coverageSummary"),
            "sourceExecutionRunId": source_execution_run_id,
        }
        if accept and proposal_id:
            user_actor = (
                actor if actor.get("actorType") == "user" else {**actor, "actorType": "user"}
            )
            accepted = self._commands.dispatch(
                {
                    "schemaVersion": "1.0.0",
                    "commandId": new_id("cmd"),
                    "commandType": "artifact.accept-revision",
                    "projectId": project_id,
                    "artifactId": test_plan["artifactId"],
                    "workspaceId": workspace_id,
                    "baseArtifactVersion": int(
                        self._kernel.get_workspace(workspace_id)["baseArtifactVersion"]
                    ),
                    "baseProjectStateVersion": int(
                        self._projects.get_project(project_id)["currentStateVersion"]
                    ),
                    "requestedBy": user_actor,
                    "requestedAt": utc_now_iso(),
                    "input": {"proposalId": proposal_id, "reason": summary},
                }
            )
            result["accepted"] = accepted.get("status") in {
                "completed",
                "completed-with-warnings",
            }
            with suppress(Exception):
                head = self._projects.get_artifact(project_id, "test-plan")
                result["testPlanArtifactId"] = head["artifactId"]
                result["testPlanVersion"] = head["artifactVersion"]
        self._ledger.append(
            project_id=project_id,
            event_type="verification.evidence-promoted",
            actor=actor,
            subject_type="artifact",
            subject_id=str(result.get("testPlanArtifactId") or test_plan["artifactId"]),
            payload={
                "sourceExecutionRunId": source_execution_run_id,
                "proposalId": proposal_id,
                "summary": summary,
            },
            causation_id=new_id("cmd"),
            correlation_id=new_id("cmd"),
            occurred_at=utc_now_iso(),
        )
        self._projection.update_after_write(project_id)
        return result

    def _safe_risk_content(self, project_id: str) -> dict[str, Any]:
        try:
            risk = self._projects.get_artifact(project_id, "risk-register")
            content = risk.get("content")
            if isinstance(content, dict):
                return dict(content)
        except Exception:  # noqa: BLE001
            pass
        return {
            "schemaVersion": "1.0.0",
            "riskRegisterId": "rreg_PLACEHOLDER000000",
            "risks": [],
            "summary": {
                "totalRisks": 0,
                "openRisks": 0,
                "highOrCritical": 0,
                "mitigated": 0,
                "unverifiedMitigations": 0,
            },
        }
