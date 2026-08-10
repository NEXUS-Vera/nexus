"""Project board projection service."""

from __future__ import annotations

from typing import Any, Protocol

from nexus_board.ids import utc_now_iso
from nexus_board.registries.artifact_types import default_artifact_type_registry


class _ProjectionStore(Protocol):
    def upsert_board_projection(self, projection: dict[str, Any]) -> None: ...

    def get_board_projection(self, project_id: str) -> dict[str, Any] | None: ...

    def list_project_events(
        self, project_id: str, *, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]: ...

    def list_execution_runs(
        self, project_id: str, *, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]: ...

    def list_produced_outputs(self, project_id: str) -> list[dict[str, Any]]: ...

    def get_workspace_by_project_artifact(
        self, project_id: str, artifact_type: str
    ) -> dict[str, Any] | None: ...


class _ProjectStore(Protocol):
    def get_project(self, project_id: str) -> dict[str, Any]: ...

    def get_artifacts(self, project_id: str) -> list[dict[str, Any]]: ...

    def get_current_state(self, project_id: str) -> dict[str, Any]: ...


class ProjectBoardProjectionService:
    def __init__(self, kernel_store: _ProjectionStore, project_store: _ProjectStore) -> None:
        self._kernel = kernel_store
        self._projects = project_store
        self._registry = default_artifact_type_registry()

    def get_board(self, project_id: str) -> dict[str, Any]:
        existing = self._kernel.get_board_projection(project_id)
        if existing is not None:
            return existing
        return self.rebuild_project_board_projection(project_id)

    def update_after_write(self, project_id: str) -> dict[str, Any]:
        return self.rebuild_project_board_projection(project_id)

    def rebuild_project_board_projection(self, project_id: str) -> dict[str, Any]:
        project = self._projects.get_project(project_id)
        try:
            artifacts = self._projects.get_artifacts(project_id)
        except Exception:  # noqa: BLE001
            artifacts = []
        artifact_by_type = {a["artifactType"]: a for a in artifacts}
        state = None
        try:
            state = self._projects.get_current_state(project_id)
        except Exception:  # noqa: BLE001
            state = None

        summaries: list[dict[str, Any]] = []
        for definition in self._registry.list():
            atype = definition["artifactType"]
            if definition["boardVisibility"] == "hidden":
                continue
            art = artifact_by_type.get(atype)
            workspace = self._kernel.get_workspace_by_project_artifact(project_id, atype)
            if art is None:
                summaries.append(
                    {
                        "artifactType": atype,
                        "lifecycleStatus": "drafted",
                        "evidenceStatus": "unverified",
                        "approvalStatus": "not-required",
                        "workspaceStatus": workspace["status"] if workspace else "empty",
                        "blockerCount": 0,
                        "openQuestionCount": 0,
                        "lastChangedAt": project.get("updatedAt") or utc_now_iso(),
                        "summary": (
                            "Not yet created"
                            if atype
                            in {
                                "component-plan",
                                "electrical-architecture",
                                "physical-architecture",
                            }
                            else None
                        ),
                    }
                )
                continue
            summaries.append(
                {
                    "artifactType": atype,
                    "artifactId": art["artifactId"],
                    "artifactVersion": art["artifactVersion"],
                    "lifecycleStatus": art.get("lifecycleStatus", "ready"),
                    "evidenceStatus": art.get("evidenceStatus", "unverified"),
                    "approvalStatus": art.get("approvalStatus", "proposed"),
                    "workspaceStatus": workspace["status"] if workspace else "ready",
                    "blockerCount": 0,
                    "openQuestionCount": 0,
                    "lastChangedAt": art.get("updatedAt") or art.get("createdAt") or utc_now_iso(),
                    **ProjectBoardProjectionService._artifact_summary_fields(atype, art),
                }
            )

        next_action = artifact_by_type.get("next-action")
        next_summary = None
        if next_action is not None:
            content = next_action.get("content") or {}
            next_summary = {
                "artifactId": next_action["artifactId"],
                "artifactVersion": next_action["artifactVersion"],
                "title": content.get("title") or content.get("recommendedAction") or "Next action",
                "priority": content.get("priority") or "medium",
                "blockerCount": len(content.get("blockingIssueIds") or []),
            }

        events, _ = self._kernel.list_project_events(project_id, limit=10)
        recent_changes = [
            {
                "eventId": e["eventId"],
                "eventType": e["eventType"],
                "occurredAt": e["occurredAt"],
                "summary": e["eventType"],
            }
            for e in events[:10]
        ]
        executions, _ = self._kernel.list_execution_runs(project_id, limit=5)
        recent_exec = []
        for run in executions[:5]:
            recent_exec.append(
                {
                    "executionRunId": run["executionRunId"],
                    "capability": run.get("capability"),
                    "status": run.get("status"),
                    "startedAt": run.get("startedAt") or run.get("queuedAt") or utc_now_iso(),
                    "completedAt": run.get("completedAt"),
                    "artifactType": self._artifact_type_for(run.get("artifactId"), artifacts),
                }
            )

        outputs = self._kernel.list_produced_outputs(project_id)
        unverified = sum(1 for o in outputs if o.get("evidenceStatus") == "unverified")
        tested = sum(1 for o in outputs if o.get("evidenceStatus") == "tested")
        contradicted = sum(1 for o in outputs if o.get("evidenceStatus") == "contradicted")

        open_questions = 0
        blocking = 0
        if state is not None:
            open_questions = len(state.get("openQuestions") or [])
            blocking = len(
                [
                    i
                    for i in (state.get("validationIssues") or [])
                    if i.get("severity") in {"error", "blocker"}
                ]
            )

        existing = self._kernel.get_board_projection(project_id)
        projection_version = int(existing["projectionVersion"]) + 1 if existing else 1
        phase = "DEFINE"
        if any(a.get("artifactType") == "functional-architecture" for a in artifacts):
            phase = "DESIGN"

        projection: dict[str, Any] = {
            "schemaVersion": "1.0.0",
            "projectId": project_id,
            "projectionVersion": projection_version,
            "projectStateVersion": int(project["currentStateVersion"]),
            "projectTitle": project.get("title") or project_id,
            "currentPhase": phase,
            "artifactSummaries": summaries,
            "openQuestionCount": open_questions,
            "blockingIssueCount": blocking,
            "recentExecutionSummaries": recent_exec,
            "recentChanges": recent_changes,
            "evidenceSummary": {
                "totalCount": len(outputs),
                "unverifiedCount": unverified,
                "testedCount": tested,
                "contradictedCount": contradicted,
            },
            "updatedAt": utc_now_iso(),
        }
        if next_summary is not None:
            projection["nextActionSummary"] = next_summary
        self._kernel.upsert_board_projection(projection)
        return projection

    @staticmethod
    def _artifact_summary_fields(artifact_type: str, art: dict[str, Any]) -> dict[str, Any]:
        if artifact_type == "component-plan":
            return ProjectBoardProjectionService._component_plan_summary_fields(art)
        if artifact_type == "electrical-architecture":
            return ProjectBoardProjectionService._electrical_summary_fields(art)
        if artifact_type == "physical-architecture":
            return ProjectBoardProjectionService._physical_summary_fields(art)
        return {}

    @staticmethod
    def _component_plan_summary_fields(art: dict[str, Any]) -> dict[str, Any]:
        content = art.get("content") or {}
        if not isinstance(content, dict):
            return {}
        roles = content.get("componentRoles") or []
        candidates = content.get("candidates") or []
        selections = content.get("selectionDecisions") or []
        checks = content.get("compatibilityChecks") or []
        coverage = content.get("coverageSummary") or {}
        selected = sum(
            1 for s in selections if isinstance(s, dict) and s.get("selectionState") == "approved"
        )
        unresolved = sum(
            1
            for c in checks
            if isinstance(c, dict) and c.get("status") in {"unknown", "fail", "warning"}
        )
        fields: dict[str, Any] = {
            "roleCount": len(roles) if isinstance(roles, list) else 0,
            "candidateCount": len(candidates) if isinstance(candidates, list) else 0,
            "selectedCount": selected,
            "awaitingApprovalCount": int(coverage.get("rolesAwaitingApproval") or 0),
            "blockedRoleCount": int(coverage.get("rolesWithBlockedSelection") or 0),
            "unresolvedCompatibilityCheckCount": unresolved,
        }
        maturity = content.get("maturity")
        if isinstance(maturity, str):
            fields["maturity"] = maturity
        return fields

    @staticmethod
    def _electrical_summary_fields(art: dict[str, Any]) -> dict[str, Any]:
        content = art.get("content") or {}
        if not isinstance(content, dict):
            return {}
        nodes = content.get("nodes") or []
        coverage = content.get("coverageSummary") or {}
        provisional = sum(
            1
            for n in nodes
            if isinstance(n, dict) and n.get("implementationStatus") in {"preferred", "provisional"}
        )
        approved = int(coverage.get("approvedImplementationCount") or 0)
        if approved == 0:
            approved = sum(
                1
                for n in nodes
                if isinstance(n, dict) and n.get("implementationStatus") == "approved"
            )
        return {
            "nodeCount": len(nodes) if isinstance(nodes, list) else 0,
            "unresolvedConnectionCount": int(coverage.get("unresolvedConnectionCount") or 0),
            "provisionalImplementationCount": provisional
            or int(coverage.get("preferredImplementationCount") or 0),
            "approvedImplementationCount": approved,
        }

    @staticmethod
    def _physical_summary_fields(art: dict[str, Any]) -> dict[str, Any]:
        content = art.get("content") or {}
        if not isinstance(content, dict):
            return {}
        nodes = content.get("nodes") or []
        coverage = content.get("coverageSummary") or {}
        return {
            "nodeCount": len(nodes) if isinstance(nodes, list) else 0,
            "unresolvedPlacementCount": int(coverage.get("unresolvedPlacementCount") or 0),
            "provisionalRelationshipCount": int(coverage.get("provisionalRelationshipCount") or 0),
        }

    @staticmethod
    def _artifact_type_for(artifact_id: str | None, artifacts: list[dict[str, Any]]) -> str | None:
        if not artifact_id:
            return None
        for art in artifacts:
            if art.get("artifactId") == artifact_id:
                return art.get("artifactType")
        return None
