"""PostgreSQL-backed project kernel store."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from nexus_persistence.errors import (
    ArtifactVersionConflictError,
    ExecutionNotFoundError,
    LedgerImmutableError,
    ProjectNotFoundError,
    ProjectPersistenceError,
    ProjectStateConflictError,
    ProposalNotFoundError,
    SnapshotImmutableError,
    SnapshotNotFoundError,
    WorkspaceNotFoundError,
)
from nexus_persistence.postgres.models import (
    ArtifactCommandRunRow,
    ArtifactProposalRow,
    ExecutionRunRow,
    ProducedOutputRow,
    ProjectBoardProjectionRow,
    ProjectEventRow,
    ProjectGraphEdgeRow,
    ProjectGraphNodeRow,
    WorkspaceDraftRow,
    WorkspaceRow,
    WorkspaceSnapshotRow,
)
from nexus_persistence.postgres.store import PostgresProjectStore, _parse_dt


class PostgresKernelStore:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        project_store: PostgresProjectStore | None = None,
    ) -> None:
        self._session_factory = session_factory
        self.project_store = project_store or PostgresProjectStore(session_factory)

    def create_workspace(self, workspace: dict[str, Any], draft: dict[str, Any]) -> None:
        with self._session_factory() as session:
            try:
                session.add(
                    WorkspaceRow(
                        workspace_id=workspace["workspaceId"],
                        project_id=workspace["projectId"],
                        artifact_id=workspace["artifactId"],
                        artifact_type=workspace["artifactType"],
                        payload=workspace,
                        updated_at=_parse_dt(workspace["updatedAt"]),
                    )
                )
                session.add(
                    WorkspaceDraftRow(
                        workspace_id=draft["workspaceId"],
                        draft_version=int(draft["draftVersion"]),
                        payload=draft,
                        updated_at=_parse_dt(draft["updatedAt"]),
                    )
                )
                session.commit()
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                raise ProjectPersistenceError("Failed to create workspace.") from exc

    def get_workspace(self, workspace_id: str) -> dict[str, Any]:
        with self._session_factory() as session:
            row = session.get(WorkspaceRow, workspace_id)
            if row is None:
                raise WorkspaceNotFoundError(f"Workspace not found: {workspace_id}")
            return dict(row.payload)

    def get_workspace_by_project_artifact(
        self, project_id: str, artifact_type: str
    ) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = session.scalars(
                select(WorkspaceRow).where(
                    WorkspaceRow.project_id == project_id,
                    WorkspaceRow.artifact_type == artifact_type,
                )
            ).first()
            return dict(row.payload) if row else None

    def update_workspace(self, workspace: dict[str, Any]) -> None:
        with self._session_factory() as session:
            row = session.get(WorkspaceRow, workspace["workspaceId"])
            if row is None:
                raise WorkspaceNotFoundError(f"Workspace not found: {workspace['workspaceId']}")
            row.payload = workspace
            row.artifact_id = workspace["artifactId"]
            row.updated_at = _parse_dt(workspace["updatedAt"])
            session.commit()

    def get_draft(self, workspace_id: str) -> dict[str, Any]:
        with self._session_factory() as session:
            row = session.get(WorkspaceDraftRow, workspace_id)
            if row is None:
                raise WorkspaceNotFoundError(f"Draft not found for workspace: {workspace_id}")
            return dict(row.payload)

    def update_draft(self, draft: dict[str, Any]) -> None:
        with self._session_factory() as session:
            row = session.get(WorkspaceDraftRow, draft["workspaceId"])
            if row is None:
                raise WorkspaceNotFoundError(
                    f"Draft not found for workspace: {draft['workspaceId']}"
                )
            row.payload = draft
            row.draft_version = int(draft["draftVersion"])
            row.updated_at = _parse_dt(draft["updatedAt"])
            session.commit()

    def create_snapshot(self, snapshot: dict[str, Any]) -> None:
        with self._session_factory() as session:
            try:
                session.add(
                    WorkspaceSnapshotRow(
                        snapshot_id=snapshot["snapshotId"],
                        workspace_id=snapshot["workspaceId"],
                        project_id=snapshot["projectId"],
                        artifact_id=snapshot["artifactId"],
                        snapshot_version=int(snapshot["snapshotVersion"]),
                        payload=snapshot,
                        created_at=_parse_dt(snapshot["createdAt"]),
                    )
                )
                session.commit()
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                raise ProjectPersistenceError("Failed to create snapshot.") from exc

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        with self._session_factory() as session:
            row = session.get(WorkspaceSnapshotRow, snapshot_id)
            if row is None:
                raise SnapshotNotFoundError(f"Snapshot not found: {snapshot_id}")
            return dict(row.payload)

    def list_snapshots(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(WorkspaceSnapshotRow)
                .where(WorkspaceSnapshotRow.workspace_id == workspace_id)
                .order_by(WorkspaceSnapshotRow.snapshot_version.asc())
            ).all()
            return [dict(r.payload) for r in rows]

    def update_snapshot(self, snapshot: dict[str, Any]) -> None:
        raise SnapshotImmutableError("Snapshots are immutable.")

    def delete_snapshot(self, snapshot_id: str) -> None:
        raise SnapshotImmutableError("Snapshots are immutable.")

    def create_proposal(self, proposal: dict[str, Any]) -> None:
        with self._session_factory() as session:
            session.add(
                ArtifactProposalRow(
                    proposal_id=proposal["proposalId"],
                    project_id=proposal["projectId"],
                    artifact_id=proposal["artifactId"],
                    workspace_id=proposal["workspaceId"],
                    status=proposal["status"],
                    payload=proposal,
                    proposed_at=_parse_dt(proposal["proposedAt"]),
                )
            )
            session.commit()

    def get_proposal(self, proposal_id: str) -> dict[str, Any]:
        with self._session_factory() as session:
            row = session.get(ArtifactProposalRow, proposal_id)
            if row is None:
                raise ProposalNotFoundError(f"Proposal not found: {proposal_id}")
            return dict(row.payload)

    def list_proposals(self, project_id: str) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(ArtifactProposalRow)
                .where(ArtifactProposalRow.project_id == project_id)
                .order_by(ArtifactProposalRow.proposed_at.asc())
            ).all()
            return [dict(r.payload) for r in rows]

    def update_proposal_status(self, proposal_id: str, proposal: dict[str, Any]) -> None:
        with self._session_factory() as session:
            row = session.get(ArtifactProposalRow, proposal_id)
            if row is None:
                raise ProposalNotFoundError(f"Proposal not found: {proposal_id}")
            row.payload = proposal
            row.status = proposal["status"]
            session.commit()

    def append_command_run(self, command_run: dict[str, Any]) -> None:
        with self._session_factory() as session:
            session.add(
                ArtifactCommandRunRow(
                    command_run_id=command_run["commandRunId"],
                    command_id=command_run["commandId"],
                    project_id=command_run["projectId"],
                    workspace_id=command_run.get("workspaceId"),
                    status=command_run["status"],
                    payload=command_run,
                    started_at=_parse_dt(command_run["startedAt"]),
                )
            )
            session.commit()

    def get_command_run(self, command_run_id: str) -> dict[str, Any]:
        with self._session_factory() as session:
            row = session.get(ArtifactCommandRunRow, command_run_id)
            if row is None:
                raise ProjectPersistenceError(f"Command run not found: {command_run_id}")
            return dict(row.payload)

    def create_execution_run(self, execution_run: dict[str, Any]) -> None:
        with self._session_factory() as session:
            started = execution_run.get("startedAt")
            session.add(
                ExecutionRunRow(
                    execution_run_id=execution_run["executionRunId"],
                    project_id=execution_run["projectId"],
                    artifact_id=execution_run["artifactId"],
                    workspace_id=execution_run["workspaceId"],
                    status=execution_run["status"],
                    payload=execution_run,
                    started_at=_parse_dt(started) if started else None,
                )
            )
            session.commit()

    def update_execution_status(self, execution_run_id: str, execution_run: dict[str, Any]) -> None:
        with self._session_factory() as session:
            row = session.get(ExecutionRunRow, execution_run_id)
            if row is None:
                raise ExecutionNotFoundError(f"Execution not found: {execution_run_id}")
            row.payload = execution_run
            row.status = execution_run["status"]
            started = execution_run.get("startedAt")
            row.started_at = _parse_dt(started) if started else row.started_at
            session.commit()

    def get_execution_run(self, execution_run_id: str) -> dict[str, Any]:
        with self._session_factory() as session:
            row = session.get(ExecutionRunRow, execution_run_id)
            if row is None:
                raise ExecutionNotFoundError(f"Execution not found: {execution_run_id}")
            return dict(row.payload)

    def list_execution_runs(
        self, project_id: str, *, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        with self._session_factory() as session:
            stmt = (
                select(ExecutionRunRow)
                .where(ExecutionRunRow.project_id == project_id)
                .order_by(ExecutionRunRow.execution_run_id.asc())
            )
            rows = list(session.scalars(stmt).all())
            ids = [r.execution_run_id for r in rows]
            if cursor:
                try:
                    start = ids.index(cursor) + 1
                except ValueError:
                    start = 0
                rows = rows[start:]
            page = rows[:limit]
            items = [dict(r.payload) for r in page]
            next_cursor = page[-1].execution_run_id if len(rows) > limit else None
            return items, next_cursor

    def create_produced_output(self, output: dict[str, Any]) -> None:
        with self._session_factory() as session:
            session.add(
                ProducedOutputRow(
                    output_id=output["outputId"],
                    project_id=output["projectId"],
                    artifact_id=output["artifactId"],
                    workspace_id=output["workspaceId"],
                    execution_run_id=output["executionRunId"],
                    payload=output,
                    created_at=_parse_dt(output["createdAt"]),
                )
            )
            session.commit()

    def list_produced_outputs(self, project_id: str) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(ProducedOutputRow).where(ProducedOutputRow.project_id == project_id)
            ).all()
            return [dict(r.payload) for r in rows]

    def append_project_event(self, event: dict[str, Any]) -> None:
        with self._session_factory() as session:
            try:
                session.add(
                    ProjectEventRow(
                        event_id=event["eventId"],
                        project_id=event["projectId"],
                        event_type=event["eventType"],
                        occurred_at=_parse_dt(event["occurredAt"]),
                        payload=event,
                    )
                )
                session.commit()
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                raise ProjectPersistenceError("Failed to append project event.") from exc

    def update_project_event(self, event: dict[str, Any]) -> None:
        raise LedgerImmutableError("Project events are append-only.")

    def delete_project_event(self, event_id: str) -> None:
        raise LedgerImmutableError("Project events are append-only.")

    def list_project_events(
        self, project_id: str, *, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        with self._session_factory() as session:
            rows = list(
                session.scalars(
                    select(ProjectEventRow)
                    .where(ProjectEventRow.project_id == project_id)
                    .order_by(
                        ProjectEventRow.occurred_at.desc(),
                        ProjectEventRow.event_id.desc(),
                    )
                ).all()
            )
            ids = [r.event_id for r in rows]
            if cursor:
                try:
                    start = ids.index(cursor) + 1
                except ValueError:
                    start = 0
                rows = rows[start:]
            page = rows[:limit]
            items = [dict(r.payload) for r in page]
            next_cursor = page[-1].event_id if len(rows) > limit else None
            return items, next_cursor

    def upsert_board_projection(self, projection: dict[str, Any]) -> None:
        with self._session_factory() as session:
            row = session.get(ProjectBoardProjectionRow, projection["projectId"])
            if row is None:
                session.add(
                    ProjectBoardProjectionRow(
                        project_id=projection["projectId"],
                        projection_version=int(projection["projectionVersion"]),
                        project_state_version=int(projection["projectStateVersion"]),
                        payload=projection,
                        updated_at=_parse_dt(projection["updatedAt"]),
                    )
                )
            else:
                row.payload = projection
                row.projection_version = int(projection["projectionVersion"])
                row.project_state_version = int(projection["projectStateVersion"])
                row.updated_at = _parse_dt(projection["updatedAt"])
            session.commit()

    def get_board_projection(self, project_id: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = session.get(ProjectBoardProjectionRow, project_id)
            return dict(row.payload) if row else None

    def create_graph_node(self, node: dict[str, Any]) -> None:
        with self._session_factory() as session:
            session.add(
                ProjectGraphNodeRow(
                    node_id=node["nodeId"],
                    project_id=node["projectId"],
                    node_type=node["nodeType"],
                    ref_id=node.get("refId"),
                    payload=node,
                )
            )
            session.commit()

    def create_graph_edge(self, edge: dict[str, Any]) -> None:
        with self._session_factory() as session:
            session.add(
                ProjectGraphEdgeRow(
                    edge_id=edge["edgeId"],
                    project_id=edge["projectId"],
                    source_node_id=edge["sourceNodeId"],
                    target_node_id=edge["targetNodeId"],
                    edge_type=edge["edgeType"],
                    payload=edge,
                )
            )
            session.commit()

    def list_graph_nodes(self, project_id: str) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(ProjectGraphNodeRow).where(ProjectGraphNodeRow.project_id == project_id)
            ).all()
            return [dict(r.payload) for r in rows]

    def list_graph_edges(self, project_id: str) -> list[dict[str, Any]]:
        with self._session_factory() as session:
            rows = session.scalars(
                select(ProjectGraphEdgeRow).where(ProjectGraphEdgeRow.project_id == project_id)
            ).all()
            return [dict(r.payload) for r in rows]

    def get_graph_node(self, node_id: str) -> dict[str, Any] | None:
        with self._session_factory() as session:
            row = session.get(ProjectGraphNodeRow, node_id)
            return dict(row.payload) if row else None

    def accept_proposal_transaction(self, payload: dict[str, Any]) -> dict[str, Any]:
        proposal = dict(payload["proposal"])
        new_artifact = dict(payload["new_artifact"])
        events = [dict(e) for e in payload.get("events") or []]
        graph_nodes = [dict(n) for n in payload.get("graph_nodes") or []]
        graph_edges = [dict(e) for e in payload.get("graph_edges") or []]
        projection = payload.get("projection")
        superseded_ids = list(payload.get("superseded_proposal_ids") or [])
        with self._session_factory() as session:
            try:
                live = session.get(ArtifactProposalRow, proposal["proposalId"])
                if live is None:
                    raise ProposalNotFoundError(f"Proposal not found: {proposal['proposalId']}")
                if live.status not in {"proposed", "awaiting-approval"}:
                    raise ArtifactVersionConflictError(f"Proposal is not acceptible: {live.status}")
                project = self.project_store.apply_accepted_artifact_revision(
                    project_id=proposal["projectId"],
                    new_artifact=new_artifact,
                    next_state_version=int(payload["next_state_version"]),
                    updated_at=payload["updated_at"],
                    expected_artifact_version=int(proposal["baseArtifactVersion"]),
                    expected_project_state_version=int(proposal["baseProjectStateVersion"]),
                    session=session,
                )
                proposal["status"] = "accepted"
                proposal["resultingArtifactId"] = new_artifact["artifactId"]
                proposal["resultingArtifactVersion"] = new_artifact["artifactVersion"]
                if "decidedAt" in payload:
                    proposal["decidedAt"] = payload["decidedAt"]
                if "decidedBy" in payload:
                    proposal["decidedBy"] = payload["decidedBy"]
                if "decisionReason" in payload:
                    proposal["decisionReason"] = payload["decisionReason"]
                live.payload = proposal
                live.status = "accepted"

                for sid in superseded_ids:
                    other = session.get(ArtifactProposalRow, sid)
                    if other and other.status in {"proposed", "awaiting-approval"}:
                        other_payload = dict(other.payload)
                        other_payload["status"] = "conflicted"
                        other.payload = other_payload
                        other.status = "conflicted"

                for event in events:
                    session.add(
                        ProjectEventRow(
                            event_id=event["eventId"],
                            project_id=event["projectId"],
                            event_type=event["eventType"],
                            occurred_at=_parse_dt(event["occurredAt"]),
                            payload=event,
                        )
                    )
                for node in graph_nodes:
                    session.add(
                        ProjectGraphNodeRow(
                            node_id=node["nodeId"],
                            project_id=node["projectId"],
                            node_type=node["nodeType"],
                            ref_id=node.get("refId"),
                            payload=node,
                        )
                    )
                for edge in graph_edges:
                    session.add(
                        ProjectGraphEdgeRow(
                            edge_id=edge["edgeId"],
                            project_id=edge["projectId"],
                            source_node_id=edge["sourceNodeId"],
                            target_node_id=edge["targetNodeId"],
                            edge_type=edge["edgeType"],
                            payload=edge,
                        )
                    )
                if projection is not None:
                    prow = session.get(ProjectBoardProjectionRow, projection["projectId"])
                    if prow is None:
                        session.add(
                            ProjectBoardProjectionRow(
                                project_id=projection["projectId"],
                                projection_version=int(projection["projectionVersion"]),
                                project_state_version=int(projection["projectStateVersion"]),
                                payload=projection,
                                updated_at=_parse_dt(projection["updatedAt"]),
                            )
                        )
                    else:
                        prow.payload = projection
                        prow.projection_version = int(projection["projectionVersion"])
                        prow.project_state_version = int(projection["projectStateVersion"])
                        prow.updated_at = _parse_dt(projection["updatedAt"])
                session.commit()
                return {
                    "project": project,
                    "proposal": proposal,
                    "artifact": new_artifact,
                }
            except (
                ProjectNotFoundError,
                ProjectStateConflictError,
                ArtifactVersionConflictError,
                ProposalNotFoundError,
                ProjectPersistenceError,
            ):
                session.rollback()
                raise
            except Exception as exc:  # noqa: BLE001
                session.rollback()
                raise ProjectPersistenceError("Accept proposal transaction failed.") from exc
