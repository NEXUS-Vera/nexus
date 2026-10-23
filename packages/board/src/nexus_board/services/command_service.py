"""Unified artifact command dispatcher."""

from __future__ import annotations

import re
from collections.abc import Callable
from contextvars import ContextVar
from typing import Any, Protocol

from nexus_persistence.errors import ArtifactNotFoundError

from nexus_board.errors import (
    ApprovalRequiredError,
    ArtifactVersionConflictError,
    BoardError,
    CommandValidationError,
    GovernanceRejectedError,
    ProjectStateConflictError,
    ProposalNotFoundError,
    StaleExecutionResultError,
)
from nexus_board.governance.concurrency import check_artifact_and_project_versions
from nexus_board.governance.policy import (
    actor_kind_from_actor_type,
    evaluate_approval_requirement,
    may_perform_command,
)
from nexus_board.ids import new_id, utc_now_iso
from nexus_board.registries.artifact_types import ArtifactTypeRegistry
from nexus_board.services.architecture_graph import (
    materialize_layered_architecture_graph,
    should_materialize_for_artifact_type,
)
from nexus_board.services.deletion_impact import inspect_functional_node_deletion_impact
from nexus_board.services.draft_lease import DEFAULT_LEASE_TTL_SECONDS
from nexus_board.services.execution_service import ExecutionService
from nexus_board.services.graph_service import ProjectGraphService
from nexus_board.services.invalidation_service import protected_fields
from nexus_board.services.ledger_service import ProjectLedgerService
from nexus_board.services.projection_service import ProjectBoardProjectionService
from nexus_board.services.workspace_service import WorkspaceService

# Domain workflows register revision validation/materialization without introducing
# a dependency from the shared kernel to an individual agent.
VERIFICATION_WRITE: ContextVar[bool] = ContextVar("verification_write", default=False)

COMMAND_ID_RE = re.compile(r"^cmd_[A-Za-z0-9]{16,}$")
COMMAND_TYPES = {
    "workspace.create",
    "workspace.update-draft",
    "workspace.acquire-edit-lease",
    "workspace.release-edit-lease",
    "workspace.discard-draft",
    "workspace.create-snapshot",
    "workspace.restore-snapshot",
    "artifact.validate-draft",
    "artifact.propose-revision",
    "artifact.accept-revision",
    "artifact.reject-revision",
    "artifact.execute",
    "artifact.inspect-deletion-impact",
}


class _KernelStore(Protocol):
    def append_command_run(self, command_run: dict[str, Any]) -> None: ...

    def create_proposal(self, proposal: dict[str, Any]) -> None: ...

    def get_proposal(self, proposal_id: str) -> dict[str, Any]: ...

    def list_proposals(self, project_id: str) -> list[dict[str, Any]]: ...

    def update_proposal_status(self, proposal_id: str, proposal: dict[str, Any]) -> None: ...

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any]: ...

    def get_workspace(self, workspace_id: str) -> dict[str, Any]: ...

    def get_draft(self, workspace_id: str) -> dict[str, Any]: ...

    def update_draft(self, draft: dict[str, Any]) -> None: ...

    def update_workspace(self, workspace: dict[str, Any]) -> None: ...

    def list_graph_nodes(self, project_id: str) -> list[dict[str, Any]]: ...

    def accept_proposal_transaction(self, payload: dict[str, Any]) -> dict[str, Any]: ...


class _ProjectStore(Protocol):
    def get_project(self, project_id: str) -> dict[str, Any]: ...

    def get_artifact(
        self,
        project_id: str,
        artifact_type: str,
        *,
        version: int | None = None,
    ) -> dict[str, Any]: ...

    def get_artifacts(self, project_id: str) -> list[dict[str, Any]]: ...


class ArtifactCommandService:
    def __init__(
        self,
        kernel_store: _KernelStore,
        project_store: _ProjectStore,
        registry: ArtifactTypeRegistry,
        workspaces: WorkspaceService,
        executions: ExecutionService,
        ledger: ProjectLedgerService,
        projection: ProjectBoardProjectionService,
        graph: ProjectGraphService,
    ) -> None:
        self._kernel = kernel_store
        self._projects = project_store
        self._registry = registry
        self._workspaces = workspaces
        self._executions = executions
        self._ledger = ledger
        self._projection = projection
        self._graph = graph
        self.invalidation: Any | None = None

    revision_validator: Callable[[str, str, dict[str, Any], bool, dict[str, Any]], None] | None = (
        None
    )
    revision_materializer: Callable[[str, dict[str, Any], dict[str, Any]], None] | None = None

    def _validate_domain_revision(
        self,
        project_id: str,
        kind: str,
        content: dict[str, Any],
        accepting: bool,
        actor: dict[str, Any],
    ) -> None:
        if kind == "execution-plan" and (
            self.revision_validator is None or self.revision_materializer is None
        ):
            raise CommandValidationError("Execution-plan workflow is not configured.")
        if self.revision_validator is not None:
            self.revision_validator(project_id, kind, content, accepting, actor)

    def dispatch(self, command: dict[str, Any]) -> dict[str, Any]:
        self._validate_command_shape(command)
        command_type = command["commandType"]
        actor = command["requestedBy"]
        actor_kind = actor_kind_from_actor_type(actor.get("actorType", "system"))

        started = utc_now_iso()
        handlers = {
            "workspace.create": self._workspace_create,
            "workspace.update-draft": self._update_draft,
            "workspace.acquire-edit-lease": self._acquire_edit_lease,
            "workspace.release-edit-lease": self._release_edit_lease,
            "workspace.discard-draft": self._discard_draft,
            "workspace.create-snapshot": self._create_snapshot,
            "workspace.restore-snapshot": self._restore_snapshot,
            "artifact.validate-draft": self._validate_draft,
            "artifact.propose-revision": self._propose_revision,
            "artifact.accept-revision": self._accept_revision,
            "artifact.reject-revision": self._reject_revision,
            "artifact.execute": self._execute,
            "artifact.inspect-deletion-impact": self._inspect_deletion_impact,
        }
        try:
            if not may_perform_command(actor_kind, command_type):
                raise GovernanceRejectedError(
                    f"Actor kind {actor_kind} may not perform {command_type}"
                )
            result_body = handlers[command_type](command, actor_kind)
            status = result_body.pop("_status", "completed")
            result = self._result(
                command,
                status=status,
                started_at=started,
                **result_body,
            )
        except (
            ArtifactVersionConflictError,
            ProjectStateConflictError,
            StaleExecutionResultError,
        ) as exc:
            result = self._result(
                command,
                status="conflicted",
                started_at=started,
                error={"code": exc.code, "message": exc.message},
            )
        except ApprovalRequiredError as exc:
            result = self._result(
                command,
                status="rejected",
                started_at=started,
                error={"code": exc.code, "message": exc.message},
                proposal_id=getattr(exc, "proposal_id", None),
            )
        except GovernanceRejectedError as exc:
            result = self._result(
                command,
                status="rejected",
                started_at=started,
                error={"code": exc.code, "message": exc.message},
            )
        except BoardError as exc:
            result = self._result(
                command,
                status="failed",
                started_at=started,
                error={"code": exc.code, "message": exc.message},
            )

        self._kernel.append_command_run(result)
        return result

    def _validate_command_shape(self, command: dict[str, Any]) -> None:
        if command.get("schemaVersion") != "1.0.0":
            raise CommandValidationError("Unsupported command schemaVersion.")
        command_id = command.get("commandId")
        if not isinstance(command_id, str) or not COMMAND_ID_RE.match(command_id):
            raise CommandValidationError("Invalid commandId.")
        if command.get("commandType") not in COMMAND_TYPES:
            raise CommandValidationError("Unknown commandType.")
        if "projectId" not in command or "requestedBy" not in command:
            raise CommandValidationError("Command missing required fields.")

    def _workspace_create(self, command: dict[str, Any], actor_kind: str) -> dict[str, Any]:
        del actor_kind
        artifact_type = command["input"]["artifactType"]
        created = self._workspaces.create_if_missing(
            project_id=command["projectId"],
            artifact_type=artifact_type,
            actor=command["requestedBy"],
            initial_content=command["input"].get("initialContent"),
        )
        return {
            "workspace_id": created["workspace"]["workspaceId"],
            "artifact_id": created["workspace"]["artifactId"],
        }

    def _update_draft(self, command: dict[str, Any], actor_kind: str) -> dict[str, Any]:
        del actor_kind
        workspace = self._kernel.get_workspace(command["workspaceId"])
        self._validate_verification_fields(
            command["projectId"], workspace["artifactType"], command["input"]["content"]
        )
        updated = self._workspaces.update_draft(
            workspace_id=command["workspaceId"],
            content=command["input"]["content"],
            expected_draft_version=int(command["input"]["expectedDraftVersion"]),
            actor=command["requestedBy"],
            base_artifact_version=int(command["baseArtifactVersion"]),
            base_project_state_version=int(command["baseProjectStateVersion"]),
        )
        return {
            "workspace_id": updated["workspace"]["workspaceId"],
            "artifact_id": updated["workspace"]["artifactId"],
        }

    def _acquire_edit_lease(self, command: dict[str, Any], actor_kind: str) -> dict[str, Any]:
        del actor_kind
        ttl = command["input"].get("ttlSeconds")
        acquired = self._workspaces.acquire_edit_lease(
            workspace_id=command["workspaceId"],
            actor=command["requestedBy"],
            ttl_seconds=int(ttl) if ttl is not None else DEFAULT_LEASE_TTL_SECONDS,
        )
        return {
            "workspace_id": acquired["workspace"]["workspaceId"],
            "artifact_id": acquired["workspace"]["artifactId"],
            "result_payload": {"editLease": acquired["draft"].get("editLease")},
        }

    def _release_edit_lease(self, command: dict[str, Any], actor_kind: str) -> dict[str, Any]:
        del actor_kind
        released = self._workspaces.release_edit_lease(
            workspace_id=command["workspaceId"],
            actor=command["requestedBy"],
            lease_token=command["input"].get("leaseToken"),
        )
        return {
            "workspace_id": released["workspace"]["workspaceId"],
            "artifact_id": released["workspace"]["artifactId"],
        }

    def _discard_draft(self, command: dict[str, Any], actor_kind: str) -> dict[str, Any]:
        del actor_kind
        refresh = command["input"].get("refreshLease")
        discarded = self._workspaces.discard_draft(
            workspace_id=command["workspaceId"],
            expected_draft_version=int(command["input"]["expectedDraftVersion"]),
            actor=command["requestedBy"],
            base_artifact_version=int(command["baseArtifactVersion"]),
            base_project_state_version=int(command["baseProjectStateVersion"]),
            refresh_lease=True if refresh is None else bool(refresh),
        )
        return {
            "workspace_id": discarded["workspace"]["workspaceId"],
            "artifact_id": discarded["workspace"]["artifactId"],
        }

    def _create_snapshot(self, command: dict[str, Any], actor_kind: str) -> dict[str, Any]:
        del actor_kind
        snapshot = self._workspaces.create_snapshot(
            workspace_id=command["workspaceId"],
            reason=command["input"]["reason"],
            actor=command["requestedBy"],
            causation_id=command["commandId"],
        )
        return {
            "workspace_id": command["workspaceId"],
            "artifact_id": command.get("artifactId"),
            "snapshot_id": snapshot["snapshotId"],
        }

    def _restore_snapshot(self, command: dict[str, Any], actor_kind: str) -> dict[str, Any]:
        del actor_kind
        restored = self._workspaces.restore_snapshot(
            workspace_id=command["workspaceId"],
            snapshot_id=command["input"]["snapshotId"],
            actor=command["requestedBy"],
        )
        return {
            "workspace_id": restored["workspace"]["workspaceId"],
            "artifact_id": restored["workspace"]["artifactId"],
            "snapshot_id": restored["snapshot"]["snapshotId"],
        }

    def _validate_draft(self, command: dict[str, Any], actor_kind: str) -> dict[str, Any]:
        del actor_kind
        snapshot_id = command["input"]["snapshotId"]
        draft = self._kernel.get_draft(command["workspaceId"])
        draft = dict(draft)
        draft["validationState"] = "valid"
        draft["updatedAt"] = utc_now_iso()
        self._kernel.update_draft(draft)
        return {
            "workspace_id": command["workspaceId"],
            "artifact_id": command.get("artifactId"),
            "snapshot_id": snapshot_id,
        }

    def _propose_revision(self, command: dict[str, Any], actor_kind: str) -> dict[str, Any]:
        workspace = self._kernel.get_workspace(command["workspaceId"])
        project = self._projects.get_project(command["projectId"])
        check_artifact_and_project_versions(
            expected_artifact_version=int(command["baseArtifactVersion"]),
            actual_artifact_version=int(workspace["baseArtifactVersion"]),
            expected_project_state_version=int(command["baseProjectStateVersion"]),
            actual_project_state_version=int(project["currentStateVersion"]),
        )
        consequence = command["input"].get("consequenceLevel") or "medium"
        if consequence not in {"low", "medium", "high", "safety-critical"}:
            consequence = "medium"
        approval = evaluate_approval_requirement(
            actor_kind,  # type: ignore[arg-type]
            "artifact.propose-revision",
            consequence,  # type: ignore[arg-type]
            project.get("autonomyMode") or "collaborate",
        )
        if workspace["artifactType"] == "execution-plan":
            approval = {
                "schemaVersion": "1.0.0",
                "required": True,
                "reason": "Execution plan materialization requires explicit user approval",
                "consequenceLevel": "high",
                "allowedApproverKinds": ["user"],
                "autoAcceptAllowed": False,
            }
        snapshot = self._kernel.get_snapshot(command["input"]["snapshotId"])
        self._validate_verification_fields(
            command["projectId"],
            workspace["artifactType"],
            snapshot["content"].get("structuredContent") or {},
        )
        if (
            snapshot["projectId"] != command["projectId"]
            or snapshot["workspaceId"] != workspace["workspaceId"]
        ):
            raise CommandValidationError("Snapshot workspace/project mismatch.")
        self._validate_domain_revision(
            command["projectId"],
            workspace["artifactType"],
            snapshot["content"].get("structuredContent") or {},
            False,
            command["requestedBy"],
        )
        now = utc_now_iso()
        status = "awaiting-approval" if approval["required"] else "proposed"
        proposal = {
            "schemaVersion": "1.0.0",
            "proposalId": new_id("prop"),
            "projectId": command["projectId"],
            "artifactId": workspace["artifactId"],
            "artifactType": workspace["artifactType"],
            "workspaceId": workspace["workspaceId"],
            "snapshotId": command["input"]["snapshotId"],
            "baseArtifactVersion": int(command["baseArtifactVersion"]),
            "baseProjectStateVersion": int(command["baseProjectStateVersion"]),
            "status": status,
            "proposedBy": command["requestedBy"],
            "proposedAt": now,
            "consequenceLevel": consequence,
            "approvalRequirement": approval,
        }
        if command["input"].get("summary"):
            proposal["summary"] = command["input"]["summary"]
        self._kernel.create_proposal(proposal)
        self._ledger.append(
            project_id=command["projectId"],
            event_type="artifact.revision-proposed",
            actor=command["requestedBy"],
            subject_type="proposal",
            subject_id=proposal["proposalId"],
            payload={
                "proposalId": proposal["proposalId"],
                "artifactType": workspace["artifactType"],
                "snapshotId": proposal["snapshotId"],
            },
            causation_id=command["commandId"],
            correlation_id=command["commandId"],
            occurred_at=now,
        )
        # Auto-accept only for agent proposals when policy allows.
        if (
            actor_kind == "agent"
            and approval.get("autoAcceptAllowed")
            and not approval.get("required")
        ):
            accept_cmd = {
                **command,
                "commandType": "artifact.accept-revision",
                "commandId": new_id("cmd"),
                "input": {
                    "proposalId": proposal["proposalId"],
                    "reason": "auto-accept",
                },
            }
            accepted = self._accept_revision(accept_cmd, "user")
            return {
                **accepted,
                "proposal_id": proposal["proposalId"],
            }
        self._projection.update_after_write(command["projectId"])
        return {
            "workspace_id": workspace["workspaceId"],
            "artifact_id": workspace["artifactId"],
            "snapshot_id": proposal["snapshotId"],
            "proposal_id": proposal["proposalId"],
            "_status": ("completed" if status == "proposed" else "completed-with-warnings"),
        }

    def _accept_revision(self, command: dict[str, Any], actor_kind: str) -> dict[str, Any]:
        proposal_id = command["input"]["proposalId"]
        proposal = self._kernel.get_proposal(proposal_id)
        project = self._projects.get_project(command["projectId"])
        if proposal["projectId"] != command["projectId"]:
            raise CommandValidationError("Proposal project mismatch.")
        if proposal.get("status") not in {"proposed", "awaiting-approval"}:
            raise ArtifactVersionConflictError(
                f"Proposal not open for acceptance: {proposal.get('status')}"
            )

        approval = proposal.get("approvalRequirement") or evaluate_approval_requirement(
            actor_kind,  # type: ignore[arg-type]
            "artifact.accept-revision",
            proposal.get("consequenceLevel") or "medium",
            project.get("autonomyMode") or "collaborate",
        )
        if approval.get("required") and actor_kind != "user":
            err = ApprovalRequiredError("User approval required for this revision.")
            err.proposal_id = proposal_id  # type: ignore[attr-defined]
            raise err
        if actor_kind == "execution":
            raise GovernanceRejectedError("Execution actors may not approve.")
        if actor_kind == "external-provider":
            raise GovernanceRejectedError("External providers may not mutate accepted artifacts.")

        if proposal["artifactType"] == "execution-plan":
            workspace = self._kernel.get_workspace(proposal["workspaceId"])
            check_artifact_and_project_versions(
                expected_artifact_version=int(command["baseArtifactVersion"]),
                actual_artifact_version=int(proposal["baseArtifactVersion"]),
                expected_project_state_version=int(command["baseProjectStateVersion"]),
                actual_project_state_version=int(project["currentStateVersion"]),
            )
            check_artifact_and_project_versions(
                expected_artifact_version=int(proposal["baseArtifactVersion"]),
                actual_artifact_version=int(workspace["baseArtifactVersion"]),
                expected_project_state_version=int(proposal["baseProjectStateVersion"]),
                actual_project_state_version=int(project["currentStateVersion"]),
            )
            if actor_kind != "user":
                raise GovernanceRejectedError("Only users may approve execution plans.")
        # Competing open proposals on same base → conflict the others after accept
        open_proposals = [
            p
            for p in self._kernel.list_proposals(command["projectId"])
            if p["proposalId"] != proposal_id
            and p.get("artifactType") == proposal["artifactType"]
            and p.get("status") in {"proposed", "awaiting-approval"}
            and int(p.get("baseArtifactVersion", -1)) == int(proposal["baseArtifactVersion"])
        ]

        snapshot = self._kernel.get_snapshot(proposal["snapshotId"])
        content = snapshot["content"].get("structuredContent") or {}
        self._validate_domain_revision(
            command["projectId"], proposal["artifactType"], content, True, command["requestedBy"]
        )
        promotion_run = (
            self._promotion_run(command["projectId"], proposal_id)
            if proposal["artifactType"] == "test-plan"
            else None
        )
        self._validate_verification_fields(
            command["projectId"],
            proposal["artifactType"],
            content,
            promoted=promotion_run is not None,
        )
        if (
            (promotion_run or VERIFICATION_WRITE.get())
            and self.invalidation is not None
            and proposal["artifactType"] == "test-plan"
        ):
            for case in content.get("testCases", []):
                if (case.get("applicability") or {}).get(
                    "state"
                ) == "CURRENT" and not self.invalidation.basis_is_current(
                    command["projectId"], case
                ):
                    raise StaleExecutionResultError("Verification basis is no longer current.")
        now = utc_now_iso()
        previous = None
        try:
            previous = self._projects.get_artifact(command["projectId"], proposal["artifactType"])
        except Exception:  # noqa: BLE001
            previous = None

        next_version = int(previous["artifactVersion"]) + 1 if previous else 1
        new_artifact: dict[str, Any] = {
            "schemaVersion": "1.0.0",
            "artifactId": new_id("art"),
            "projectId": command["projectId"],
            "artifactType": proposal["artifactType"],
            "artifactVersion": next_version,
            "contentSchemaVersion": "1.0.0",
            "lifecycleStatus": "ready",
            "evidenceStatus": "unverified",
            "approvalStatus": ("user-approved" if actor_kind == "user" else "agent-decided"),
            "createdBy": command["requestedBy"],
            "createdAt": now,
            "updatedAt": now,
            "sourceTurnId": previous["sourceTurnId"] if previous else new_id("turn"),
            "workflowRunId": previous["workflowRunId"] if previous else new_id("run"),
            "content": content,
        }
        if previous is not None:
            new_artifact["supersedesArtifactId"] = previous["artifactId"]
            new_artifact["supersedesArtifactVersion"] = previous["artifactVersion"]

        accept_event = {
            "schemaVersion": "1.0.0",
            "eventId": new_id("evt"),
            "projectId": command["projectId"],
            "eventType": "artifact.revision-accepted",
            "occurredAt": now,
            "actor": command["requestedBy"],
            "subject": {
                "subjectType": "artifact",
                "subjectId": new_artifact["artifactId"],
            },
            "causationId": command["commandId"],
            "correlationId": command["commandId"],
            "payload": {
                "proposalId": proposal_id,
                "artifactType": proposal["artifactType"],
                "resultingArtifactId": new_artifact["artifactId"],
                "resultingArtifactVersion": next_version,
            },
        }
        events = [accept_event]
        if previous is not None:
            events.append(
                {
                    "schemaVersion": "1.0.0",
                    "eventId": new_id("evt"),
                    "projectId": command["projectId"],
                    "eventType": "artifact.superseded",
                    "occurredAt": now,
                    "actor": command["requestedBy"],
                    "subject": {
                        "subjectType": "artifact",
                        "subjectId": previous["artifactId"],
                    },
                    "causationId": command["commandId"],
                    "correlationId": command["commandId"],
                    "payload": {
                        "artifactType": proposal["artifactType"],
                        "supersededBy": new_artifact["artifactId"],
                    },
                }
            )

        graph_nodes = []
        graph_edges = []
        new_node = {
            "schemaVersion": "1.0.0",
            "nodeId": new_id("gnode"),
            "projectId": command["projectId"],
            "nodeType": "artifact",
            "refId": new_artifact["artifactId"],
            "label": proposal["artifactType"],
            "createdByEventId": accept_event["eventId"],
            "createdAt": now,
        }
        graph_nodes.append(new_node)
        if previous is not None:
            existing_nodes = {
                n.get("refId"): n
                for n in self._kernel.list_graph_nodes(command["projectId"])  # type: ignore[attr-defined]
            }
            prev_node = existing_nodes.get(previous["artifactId"])
            if prev_node is None:
                prev_node = {
                    "schemaVersion": "1.0.0",
                    "nodeId": new_id("gnode"),
                    "projectId": command["projectId"],
                    "nodeType": "artifact",
                    "refId": previous["artifactId"],
                    "label": proposal["artifactType"],
                    "createdByEventId": accept_event["eventId"],
                    "createdAt": now,
                }
                graph_nodes.append(prev_node)
            graph_edges.append(
                {
                    "schemaVersion": "1.0.0",
                    "edgeId": new_id("gedge"),
                    "projectId": command["projectId"],
                    "sourceNodeId": new_node["nodeId"],
                    "targetNodeId": prev_node["nodeId"],
                    "edgeType": "supersedes",
                    "createdByEventId": accept_event["eventId"],
                    "validFrom": now,
                }
            )

        next_state_version = int(project["currentStateVersion"]) + 1
        self._kernel.accept_proposal_transaction(
            {
                "proposal": proposal,
                "new_artifact": new_artifact,
                "next_state_version": next_state_version,
                "updated_at": now,
                "decidedAt": now,
                "decidedBy": command["requestedBy"],
                "decisionReason": command["input"].get("reason") or "accepted",
                "events": events,
                "graph_nodes": graph_nodes,
                "graph_edges": graph_edges,
                "superseded_proposal_ids": [p["proposalId"] for p in open_proposals],
                "projection": None,
            }
        )
        # Refresh workspace base versions to new accepted head
        workspace = self._kernel.get_workspace(proposal["workspaceId"])
        workspace = dict(workspace)
        workspace["artifactId"] = new_artifact["artifactId"]
        workspace["baseArtifactVersion"] = next_version
        workspace["baseProjectStateVersion"] = next_state_version
        workspace["updatedAt"] = now
        workspace["status"] = "ready"
        self._kernel.update_workspace(workspace)
        draft = self._kernel.get_draft(workspace["workspaceId"])
        draft = dict(draft)
        draft["baseArtifactVersion"] = next_version
        draft["baseProjectStateVersion"] = next_state_version
        draft["updatedAt"] = now
        self._kernel.update_draft(draft)

        if should_materialize_for_artifact_type(proposal["artifactType"]):
            try:
                current_artifacts = self._projects.get_artifacts(command["projectId"])
            except Exception:  # noqa: BLE001
                current_artifacts = [new_artifact]
            materialize_layered_architecture_graph(
                self._kernel,  # type: ignore[arg-type]
                command["projectId"],
                current_artifacts,
                accept_event["eventId"],
            )

        if self.invalidation is not None:
            self.invalidation.process(command["projectId"], previous, new_artifact)
            if previous and proposal["artifactType"] == "test-plan":
                self.invalidation.revalidated(command["projectId"], previous["content"], content)
        if proposal["artifactType"] == "execution-plan" and self.revision_materializer is not None:
            self.revision_materializer(command["projectId"], new_artifact, command["requestedBy"])
        self._projection.update_after_write(command["projectId"])
        return {
            "workspace_id": proposal["workspaceId"],
            "artifact_id": new_artifact["artifactId"],
            "snapshot_id": proposal["snapshotId"],
            "proposal_id": proposal_id,
            "produced_artifact_reference": {
                "artifactId": new_artifact["artifactId"],
                "artifactVersion": next_version,
            },
        }

    def _promotion_run(self, project_id: str, proposal_id: str) -> str | None:
        events, cursor = self._ledger.list_events(project_id, limit=1000)
        while True:
            for event in events:
                if (
                    event["eventType"] == "verification.evidence-promoted"
                    and event.get("payload", {}).get("proposalId") == proposal_id
                ):
                    return event["payload"].get("sourceExecutionRunId")
            if not cursor:
                return None
            events, cursor = self._ledger.list_events(project_id, limit=1000, cursor=cursor)

    def _validate_verification_fields(
        self, project_id: str, kind: str, content: dict[str, Any], *, promoted: bool = False
    ) -> None:
        if kind != "test-plan" or VERIFICATION_WRITE.get() or promoted:
            return
        try:
            current = self._projects.get_artifact(project_id, kind)["content"]
        except (KeyError, ArtifactNotFoundError):
            current = {}
        if protected_fields(current) != protected_fields(content):
            raise CommandValidationError("applicability and verificationBasis are system-managed.")

    def _reject_revision(self, command: dict[str, Any], actor_kind: str) -> dict[str, Any]:
        if actor_kind != "user":
            raise GovernanceRejectedError("Only users may reject revisions.")
        proposal_id = command["input"]["proposalId"]
        proposal = self._kernel.get_proposal(proposal_id)
        if proposal.get("status") not in {"proposed", "awaiting-approval"}:
            raise ProposalNotFoundError("Proposal is not open for rejection.")
        now = utc_now_iso()
        proposal = dict(proposal)
        proposal["status"] = "rejected"
        proposal["decidedAt"] = now
        proposal["decidedBy"] = command["requestedBy"]
        proposal["decisionReason"] = command["input"].get("reason") or "rejected"
        self._kernel.update_proposal_status(proposal_id, proposal)
        self._ledger.append(
            project_id=command["projectId"],
            event_type="artifact.revision-rejected",
            actor=command["requestedBy"],
            subject_type="proposal",
            subject_id=proposal_id,
            payload={
                "proposalId": proposal_id,
                "reason": proposal["decisionReason"],
            },
            causation_id=command["commandId"],
            correlation_id=command["commandId"],
            occurred_at=now,
        )
        self._projection.update_after_write(command["projectId"])
        return {
            "workspace_id": proposal["workspaceId"],
            "artifact_id": proposal["artifactId"],
            "proposal_id": proposal_id,
            "snapshot_id": proposal.get("snapshotId"),
        }

    def _execute(self, command: dict[str, Any], actor_kind: str) -> dict[str, Any]:
        del actor_kind
        workspace = self._kernel.get_workspace(command["workspaceId"])
        result = self._executions.execute(
            project_id=command["projectId"],
            artifact_id=workspace["artifactId"],
            artifact_type=workspace["artifactType"],
            workspace_id=workspace["workspaceId"],
            snapshot_id=command["input"]["snapshotId"],
            capability=command["input"]["capability"],
            actor=command["requestedBy"],
            base_artifact_version=int(command["baseArtifactVersion"]),
            base_project_state_version=int(command["baseProjectStateVersion"]),
            causation_id=command["commandId"],
            max_duration_ms=command["input"].get("maxDurationMs"),
            options={
                key: command["input"][key]
                for key in (
                    "maxOutputBytes",
                    "commandSpec",
                    "executionMode",
                    "expectedText",
                    "requestedOutputs",
                )
                if key in command["input"]
            },
        )
        return {
            "workspace_id": workspace["workspaceId"],
            "artifact_id": workspace["artifactId"],
            "snapshot_id": command["input"]["snapshotId"],
            "execution_run_id": result["executionRun"]["executionRunId"],
            "output_references": [o["outputId"] for o in result.get("outputs") or []],
            "evidence_references": result["executionRun"].get("evidenceReferences") or [],
            "result_payload": (
                {
                    "executionJobId": result["executionJob"]["executionJobId"],
                    "accepted": True,
                }
                if result.get("executionJob")
                else None
            ),
        }

    def _inspect_deletion_impact(self, command: dict[str, Any], actor_kind: str) -> dict[str, Any]:
        del actor_kind
        entity_type = command["input"]["entityType"]
        entity_id = command["input"]["entityId"]
        if entity_type != "functional-node":
            raise CommandValidationError(f"Unsupported deletion entityType: {entity_type}")

        def _content(artifact_type: str) -> dict[str, Any] | None:
            try:
                artifact = self._projects.get_artifact(command["projectId"], artifact_type)
            except Exception:  # noqa: BLE001
                return None
            content = artifact.get("content")
            return content if isinstance(content, dict) else None

        functional = _content("functional-architecture")
        if functional is None:
            raise CommandValidationError("functional-architecture artifact is required.")
        impact = inspect_functional_node_deletion_impact(
            node_id=entity_id,
            functional_content=functional,
            component_plan_content=_content("component-plan"),
            electrical_content=_content("electrical-architecture"),
            physical_content=_content("physical-architecture"),
        )
        return {
            "workspace_id": command.get("workspaceId"),
            "artifact_id": command.get("artifactId"),
            "result_payload": impact,
        }

    def _result(
        self,
        command: dict[str, Any],
        *,
        status: str,
        started_at: str,
        workspace_id: str | None = None,
        artifact_id: str | None = None,
        snapshot_id: str | None = None,
        proposal_id: str | None = None,
        execution_run_id: str | None = None,
        produced_artifact_reference: dict[str, Any] | None = None,
        output_references: list[str] | None = None,
        evidence_references: list[str] | None = None,
        error: dict[str, Any] | None = None,
        result_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        completed = utc_now_iso()
        result: dict[str, Any] = {
            "schemaVersion": "1.0.0",
            "commandRunId": new_id("cmdrun"),
            "commandId": command["commandId"],
            "status": status,
            "projectId": command["projectId"],
            "artifactId": artifact_id or command.get("artifactId"),
            "workspaceId": workspace_id or command.get("workspaceId"),
            "outputReferences": output_references or [],
            "evidenceReferences": evidence_references or [],
            "issueReferences": [],
            "startedAt": started_at,
            "completedAt": completed,
        }
        if snapshot_id:
            result["snapshotId"] = snapshot_id
        if proposal_id:
            result["proposalId"] = proposal_id
        if execution_run_id:
            result["executionRunId"] = execution_run_id
        if produced_artifact_reference:
            result["producedArtifactReference"] = produced_artifact_reference
        if error:
            result["error"] = error
        if result_payload is not None:
            result["resultPayload"] = result_payload
        return result
