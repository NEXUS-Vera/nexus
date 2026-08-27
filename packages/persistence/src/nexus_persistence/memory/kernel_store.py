"""In-memory project kernel store."""

from __future__ import annotations

import copy
import threading
from typing import Any

from nexus_persistence.errors import (
    ArtifactVersionConflictError,
    ExecutionNotFoundError,
    LedgerImmutableError,
    ProjectNotFoundError,
    ProjectPersistenceError,
    ProjectStateConflictError,
    ProposalNotFoundError,
    FirmwarePatchNotFoundError,
    AnalysisPatchNotFoundError,
    SnapshotImmutableError,
    SnapshotNotFoundError,
    WorkspaceNotFoundError,
)
from nexus_persistence.memory.store import InMemoryProjectStore


class InMemoryKernelStore:
    def __init__(self, project_store: InMemoryProjectStore | None = None) -> None:
        self.project_store = project_store or InMemoryProjectStore()
        self._lock = getattr(self.project_store, "_lock", threading.RLock())
        self._workspaces: dict[str, dict[str, Any]] = {}
        self._workspace_by_project_type: dict[tuple[str, str], str] = {}
        self._drafts: dict[str, dict[str, Any]] = {}
        self._workspace_files: dict[tuple[str, str], dict[str, Any]] = {}
        self._snapshots: dict[str, dict[str, Any]] = {}
        self._snapshots_by_workspace: dict[str, list[str]] = {}
        self._proposals: dict[str, dict[str, Any]] = {}
        self._proposals_by_project: dict[str, list[str]] = {}
        self._firmware_patch_proposals: dict[str, dict[str, Any]] = {}
        self._analysis_patch_proposals: dict[str, dict[str, Any]] = {}
        self._command_runs: dict[str, dict[str, Any]] = {}
        self._execution_runs: dict[str, dict[str, Any]] = {}
        self._executions_by_project: dict[str, list[str]] = {}
        self._execution_jobs: dict[str, dict[str, Any]] = {}
        self._execution_jobs_by_run: dict[str, str] = {}
        self._execution_log_chunks: dict[str, list[dict[str, Any]]] = {}
        self._outputs: dict[str, dict[str, Any]] = {}
        self._outputs_by_project: dict[str, list[str]] = {}
        self._events: dict[str, dict[str, Any]] = {}
        self._events_by_project: dict[str, list[str]] = {}
        self._projections: dict[str, dict[str, Any]] = {}
        self._graph_nodes: dict[str, dict[str, Any]] = {}
        self._graph_edges: dict[str, dict[str, Any]] = {}
        self._nodes_by_project: dict[str, list[str]] = {}
        self._edges_by_project: dict[str, list[str]] = {}

    # --- workspaces ---
    def create_workspace(self, workspace: dict[str, Any], draft: dict[str, Any]) -> None:
        with self._lock:
            ws_id = workspace["workspaceId"]
            key = (workspace["projectId"], workspace["artifactType"])
            if key in self._workspace_by_project_type:
                raise ProjectPersistenceError(
                    f"Workspace already exists for {workspace['artifactType']}"
                )
            self._workspaces[ws_id] = copy.deepcopy(workspace)
            self._workspace_by_project_type[key] = ws_id
            self._drafts[ws_id] = copy.deepcopy(draft)

    def get_workspace(self, workspace_id: str) -> dict[str, Any]:
        with self._lock:
            ws = self._workspaces.get(workspace_id)
            if ws is None:
                raise WorkspaceNotFoundError(f"Workspace not found: {workspace_id}")
            return copy.deepcopy(ws)

    def get_workspace_by_project_artifact(
        self, project_id: str, artifact_type: str
    ) -> dict[str, Any] | None:
        with self._lock:
            ws_id = self._workspace_by_project_type.get((project_id, artifact_type))
            if ws_id is None:
                return None
            return copy.deepcopy(self._workspaces[ws_id])

    def update_workspace(self, workspace: dict[str, Any]) -> None:
        with self._lock:
            ws_id = workspace["workspaceId"]
            if ws_id not in self._workspaces:
                raise WorkspaceNotFoundError(f"Workspace not found: {ws_id}")
            self._workspaces[ws_id] = copy.deepcopy(workspace)

    # --- drafts ---
    def get_draft(self, workspace_id: str) -> dict[str, Any]:
        with self._lock:
            draft = self._drafts.get(workspace_id)
            if draft is None:
                raise WorkspaceNotFoundError(f"Draft not found for workspace: {workspace_id}")
            return copy.deepcopy(draft)

    def update_draft(self, draft: dict[str, Any]) -> None:
        with self._lock:
            ws_id = draft["workspaceId"]
            if ws_id not in self._drafts:
                raise WorkspaceNotFoundError(f"Draft not found for workspace: {ws_id}")
            self._drafts[ws_id] = copy.deepcopy(draft)

    # --- workspace files ---
    def upsert_workspace_file(self, file_record: dict[str, Any]) -> None:
        with self._lock:
            key = (file_record["workspaceId"], file_record["path"])
            self._workspace_files[key] = copy.deepcopy(file_record)

    def get_workspace_file(self, workspace_id: str, path: str) -> dict[str, Any] | None:
        with self._lock:
            record = self._workspace_files.get((workspace_id, path))
            return copy.deepcopy(record) if record is not None else None

    def list_workspace_files(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._lock:
            items = [
                copy.deepcopy(record)
                for (ws_id, _), record in self._workspace_files.items()
                if ws_id == workspace_id
            ]
            items.sort(key=lambda item: item["path"])
            return items

    def delete_workspace_file(self, workspace_id: str, path: str) -> None:
        with self._lock:
            self._workspace_files.pop((workspace_id, path), None)

    def replace_workspace_files(self, workspace_id: str, files: list[dict[str, Any]]) -> None:
        with self._lock:
            for key in [k for k in self._workspace_files if k[0] == workspace_id]:
                del self._workspace_files[key]
            for record in files:
                if record["workspaceId"] != workspace_id:
                    raise ProjectPersistenceError("File workspaceId mismatch on replace")
                key = (workspace_id, record["path"])
                self._workspace_files[key] = copy.deepcopy(record)

    def list_referenced_content_hashes(self) -> set[str]:
        with self._lock:
            hashes: set[str] = set()
            for record in self._workspace_files.values():
                content_hash = record.get("contentHash")
                if isinstance(content_hash, str):
                    hashes.add(content_hash)
            for snapshot in self._snapshots.values():
                content = snapshot.get("content") or {}
                if content.get("kind") != "filesystem":
                    continue
                manifest = content.get("filesystemManifest") or {}
                for entry in manifest.get("entries") or []:
                    content_hash = entry.get("contentHash")
                    if isinstance(content_hash, str):
                        hashes.add(content_hash)
            for output in self._outputs.values():
                content = output.get("content") or {}
                if content.get("kind") != "storage-reference":
                    continue
                if content.get("storageKind") != "file-store":
                    continue
                uri = content.get("uri")
                if isinstance(uri, str) and uri.startswith("sha256:"):
                    hashes.add(uri)
            return hashes

    # --- snapshots ---
    def create_snapshot(self, snapshot: dict[str, Any]) -> None:
        with self._lock:
            snap_id = snapshot["snapshotId"]
            if snap_id in self._snapshots:
                raise ProjectPersistenceError(f"Snapshot already exists: {snap_id}")
            self._snapshots[snap_id] = copy.deepcopy(snapshot)
            self._snapshots_by_workspace.setdefault(snapshot["workspaceId"], []).append(snap_id)

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        with self._lock:
            snap = self._snapshots.get(snapshot_id)
            if snap is None:
                raise SnapshotNotFoundError(f"Snapshot not found: {snapshot_id}")
            return copy.deepcopy(snap)

    def list_snapshots(self, workspace_id: str) -> list[dict[str, Any]]:
        with self._lock:
            ids = self._snapshots_by_workspace.get(workspace_id, [])
            return [copy.deepcopy(self._snapshots[i]) for i in ids]

    def update_snapshot(self, snapshot: dict[str, Any]) -> None:
        raise SnapshotImmutableError("Snapshots are immutable.")

    def delete_snapshot(self, snapshot_id: str) -> None:
        raise SnapshotImmutableError("Snapshots are immutable.")

    def reclaim_snapshot(self, snapshot_id: str) -> None:
        """GC-only reclaim of an unreferenced snapshot. Callers must verify protection."""
        with self._lock:
            snap = self._snapshots.pop(snapshot_id, None)
            if snap is None:
                raise SnapshotNotFoundError(f"Snapshot not found: {snapshot_id}")
            ws_id = snap["workspaceId"]
            ids = self._snapshots_by_workspace.get(ws_id, [])
            self._snapshots_by_workspace[ws_id] = [i for i in ids if i != snapshot_id]

    def list_all_snapshots(self) -> list[dict[str, Any]]:
        with self._lock:
            return [copy.deepcopy(s) for s in self._snapshots.values()]

    def list_all_workspaces(self) -> list[dict[str, Any]]:
        with self._lock:
            return [copy.deepcopy(w) for w in self._workspaces.values()]

    def list_all_proposals(self) -> list[dict[str, Any]]:
        with self._lock:
            return [copy.deepcopy(p) for p in self._proposals.values()]

    def list_all_execution_runs(self) -> list[dict[str, Any]]:
        with self._lock:
            return [copy.deepcopy(r) for r in self._execution_runs.values()]

    def list_all_execution_jobs(self) -> list[dict[str, Any]]:
        with self._lock:
            return [copy.deepcopy(j) for j in self._execution_jobs.values()]

    def list_nonterminal_execution_jobs(self) -> list[dict[str, Any]]:
        terminal = {"succeeded", "failed", "timed-out", "cancelled"}
        with self._lock:
            return [
                copy.deepcopy(j)
                for j in self._execution_jobs.values()
                if j.get("status") not in terminal
            ]

    def list_all_produced_outputs(self) -> list[dict[str, Any]]:
        with self._lock:
            return [copy.deepcopy(o) for o in self._outputs.values()]

    def delete_execution_log_chunks(self, execution_job_id: str) -> int:
        with self._lock:
            chunks = self._execution_log_chunks.pop(execution_job_id, [])
            return len(chunks)

    # --- proposals ---
    def create_proposal(self, proposal: dict[str, Any]) -> None:
        with self._lock:
            pid = proposal["proposalId"]
            self._proposals[pid] = copy.deepcopy(proposal)
            self._proposals_by_project.setdefault(proposal["projectId"], []).append(pid)

    def get_proposal(self, proposal_id: str) -> dict[str, Any]:
        with self._lock:
            proposal = self._proposals.get(proposal_id)
            if proposal is None:
                raise ProposalNotFoundError(f"Proposal not found: {proposal_id}")
            return copy.deepcopy(proposal)

    def list_proposals(self, project_id: str) -> list[dict[str, Any]]:
        with self._lock:
            ids = self._proposals_by_project.get(project_id, [])
            return [copy.deepcopy(self._proposals[i]) for i in ids]

    def update_proposal_status(self, proposal_id: str, proposal: dict[str, Any]) -> None:
        with self._lock:
            if proposal_id not in self._proposals:
                raise ProposalNotFoundError(f"Proposal not found: {proposal_id}")
            self._proposals[proposal_id] = copy.deepcopy(proposal)

    # --- firmware patch proposals ---
    def create_firmware_patch_proposal(self, proposal: dict[str, Any]) -> None:
        with self._lock:
            pid = proposal["proposalId"]
            self._firmware_patch_proposals[pid] = copy.deepcopy(proposal)

    def get_firmware_patch_proposal(self, proposal_id: str) -> dict[str, Any]:
        with self._lock:
            proposal = self._firmware_patch_proposals.get(proposal_id)
            if proposal is None:
                raise FirmwarePatchNotFoundError(
                    f"Firmware patch proposal not found: {proposal_id}"
                )
            return copy.deepcopy(proposal)

    def update_firmware_patch_proposal(self, proposal_id: str, proposal: dict[str, Any]) -> None:
        with self._lock:
            if proposal_id not in self._firmware_patch_proposals:
                raise FirmwarePatchNotFoundError(
                    f"Firmware patch proposal not found: {proposal_id}"
                )
            self._firmware_patch_proposals[proposal_id] = copy.deepcopy(proposal)

    # --- analysis patch proposals (Phase 16C) ---
    def create_analysis_patch_proposal(self, proposal: dict[str, Any]) -> None:
        with self._lock:
            pid = proposal["proposalId"]
            self._analysis_patch_proposals[pid] = copy.deepcopy(proposal)

    def get_analysis_patch_proposal(self, proposal_id: str) -> dict[str, Any]:
        with self._lock:
            proposal = self._analysis_patch_proposals.get(proposal_id)
            if proposal is None:
                raise AnalysisPatchNotFoundError(
                    f"Analysis patch proposal not found: {proposal_id}"
                )
            return copy.deepcopy(proposal)

    def update_analysis_patch_proposal(
        self, proposal_id: str, proposal: dict[str, Any]
    ) -> None:
        with self._lock:
            if proposal_id not in self._analysis_patch_proposals:
                raise AnalysisPatchNotFoundError(
                    f"Analysis patch proposal not found: {proposal_id}"
                )
            self._analysis_patch_proposals[proposal_id] = copy.deepcopy(proposal)

    # --- command runs ---
    def append_command_run(self, command_run: dict[str, Any]) -> None:
        with self._lock:
            self._command_runs[command_run["commandRunId"]] = copy.deepcopy(command_run)

    def get_command_run(self, command_run_id: str) -> dict[str, Any]:
        with self._lock:
            run = self._command_runs.get(command_run_id)
            if run is None:
                raise ProjectPersistenceError(f"Command run not found: {command_run_id}")
            return copy.deepcopy(run)

    # --- executions ---
    def create_execution_run(self, execution_run: dict[str, Any]) -> None:
        with self._lock:
            rid = execution_run["executionRunId"]
            self._execution_runs[rid] = copy.deepcopy(execution_run)
            self._executions_by_project.setdefault(execution_run["projectId"], []).append(rid)

    def update_execution_status(self, execution_run_id: str, execution_run: dict[str, Any]) -> None:
        with self._lock:
            if execution_run_id not in self._execution_runs:
                raise ExecutionNotFoundError(f"Execution not found: {execution_run_id}")
            self._execution_runs[execution_run_id] = copy.deepcopy(execution_run)

    def get_execution_run(self, execution_run_id: str) -> dict[str, Any]:
        with self._lock:
            run = self._execution_runs.get(execution_run_id)
            if run is None:
                raise ExecutionNotFoundError(f"Execution not found: {execution_run_id}")
            return copy.deepcopy(run)

    def list_execution_runs(
        self, project_id: str, *, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        with self._lock:
            ids = list(self._executions_by_project.get(project_id, []))
            if cursor:
                try:
                    start = ids.index(cursor) + 1
                except ValueError:
                    start = 0
                ids = ids[start:]
            page = ids[:limit]
            items = [copy.deepcopy(self._execution_runs[i]) for i in page]
            next_cursor = page[-1] if len(ids) > limit else None
            return items, next_cursor

    # --- execution jobs / logs ---
    def create_execution_job(self, job: dict[str, Any]) -> None:
        with self._lock:
            job_id = job["executionJobId"]
            self._execution_jobs[job_id] = copy.deepcopy(job)
            self._execution_jobs_by_run[job["executionRunId"]] = job_id
            self._execution_log_chunks.setdefault(job_id, [])

    def update_execution_job(self, job: dict[str, Any]) -> None:
        with self._lock:
            job_id = job["executionJobId"]
            if job_id not in self._execution_jobs:
                raise ExecutionNotFoundError(f"Execution job not found: {job_id}")
            self._execution_jobs[job_id] = copy.deepcopy(job)
            self._execution_jobs_by_run[job["executionRunId"]] = job_id

    def get_execution_job(self, execution_job_id: str) -> dict[str, Any]:
        with self._lock:
            job = self._execution_jobs.get(execution_job_id)
            if job is None:
                raise ExecutionNotFoundError(f"Execution job not found: {execution_job_id}")
            return copy.deepcopy(job)

    def get_execution_job_by_run(self, execution_run_id: str) -> dict[str, Any] | None:
        with self._lock:
            job_id = self._execution_jobs_by_run.get(execution_run_id)
            if job_id is None:
                return None
            return copy.deepcopy(self._execution_jobs[job_id])

    def append_execution_log_chunk(self, chunk: dict[str, Any]) -> None:
        with self._lock:
            job_id = chunk["executionJobId"]
            if job_id not in self._execution_jobs:
                raise ExecutionNotFoundError(f"Execution job not found: {job_id}")
            self._execution_log_chunks.setdefault(job_id, []).append(copy.deepcopy(chunk))

    def list_execution_log_chunks(
        self,
        execution_job_id: str,
        *,
        after_sequence: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._lock:
            chunks = self._execution_log_chunks.get(execution_job_id, [])
            filtered = [c for c in chunks if int(c["sequence"]) > after_sequence]
            return copy.deepcopy(filtered[:limit])

    # --- outputs ---
    def create_produced_output(self, output: dict[str, Any]) -> None:
        with self._lock:
            oid = output["outputId"]
            self._outputs[oid] = copy.deepcopy(output)
            self._outputs_by_project.setdefault(output["projectId"], []).append(oid)

    def get_produced_output(self, output_id: str) -> dict[str, Any]:
        with self._lock:
            output = self._outputs.get(output_id)
            if output is None:
                raise ExecutionNotFoundError(f"Produced output not found: {output_id}")
            return copy.deepcopy(output)

    def list_produced_outputs(self, project_id: str) -> list[dict[str, Any]]:
        with self._lock:
            ids = self._outputs_by_project.get(project_id, [])
            return [copy.deepcopy(self._outputs[i]) for i in ids]

    # --- events ---
    def append_project_event(self, event: dict[str, Any]) -> None:
        with self._lock:
            eid = event["eventId"]
            if eid in self._events:
                raise ProjectPersistenceError(f"Event already exists: {eid}")
            self._events[eid] = copy.deepcopy(event)
            self._events_by_project.setdefault(event["projectId"], []).append(eid)

    def update_project_event(self, event: dict[str, Any]) -> None:
        raise LedgerImmutableError("Project events are append-only.")

    def delete_project_event(self, event_id: str) -> None:
        raise LedgerImmutableError("Project events are append-only.")

    def list_project_events(
        self, project_id: str, *, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]:
        with self._lock:
            ids = list(self._events_by_project.get(project_id, []))
            # newest first for board-facing pagination
            ids = list(reversed(ids))
            if cursor:
                try:
                    start = ids.index(cursor) + 1
                except ValueError:
                    start = 0
                ids = ids[start:]
            page = ids[:limit]
            items = [copy.deepcopy(self._events[i]) for i in page]
            next_cursor = page[-1] if len(ids) > limit else None
            return items, next_cursor

    # --- projections ---
    def upsert_board_projection(self, projection: dict[str, Any]) -> None:
        with self._lock:
            self._projections[projection["projectId"]] = copy.deepcopy(projection)

    def get_board_projection(self, project_id: str) -> dict[str, Any] | None:
        with self._lock:
            projection = self._projections.get(project_id)
            return copy.deepcopy(projection) if projection else None

    # --- graph ---
    def create_graph_node(self, node: dict[str, Any]) -> None:
        with self._lock:
            nid = node["nodeId"]
            self._graph_nodes[nid] = copy.deepcopy(node)
            self._nodes_by_project.setdefault(node["projectId"], []).append(nid)

    def create_graph_edge(self, edge: dict[str, Any]) -> None:
        with self._lock:
            eid = edge["edgeId"]
            self._graph_edges[eid] = copy.deepcopy(edge)
            self._edges_by_project.setdefault(edge["projectId"], []).append(eid)

    def list_graph_nodes(self, project_id: str) -> list[dict[str, Any]]:
        with self._lock:
            ids = self._nodes_by_project.get(project_id, [])
            return [copy.deepcopy(self._graph_nodes[i]) for i in ids]

    def list_graph_edges(self, project_id: str) -> list[dict[str, Any]]:
        with self._lock:
            ids = self._edges_by_project.get(project_id, [])
            return [copy.deepcopy(self._graph_edges[i]) for i in ids]

    def get_graph_node(self, node_id: str) -> dict[str, Any] | None:
        with self._lock:
            node = self._graph_nodes.get(node_id)
            return copy.deepcopy(node) if node else None

    def accept_proposal_transaction(self, payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            proposal = copy.deepcopy(payload["proposal"])
            new_artifact = copy.deepcopy(payload["new_artifact"])
            events = [copy.deepcopy(e) for e in payload.get("events") or []]
            graph_nodes = [copy.deepcopy(n) for n in payload.get("graph_nodes") or []]
            graph_edges = [copy.deepcopy(e) for e in payload.get("graph_edges") or []]
            projection = copy.deepcopy(payload.get("projection"))
            superseded_ids = list(payload.get("superseded_proposal_ids") or [])
            expected_art = int(proposal["baseArtifactVersion"])
            expected_proj = int(proposal["baseProjectStateVersion"])
            project_id = proposal["projectId"]

            snapshot = self._snapshot_state()
            try:
                # Concurrency against live proposal + project
                live = self._proposals.get(proposal["proposalId"])
                if live is None:
                    raise ProposalNotFoundError(f"Proposal not found: {proposal['proposalId']}")
                if live.get("status") not in {"proposed", "awaiting-approval"}:
                    raise ArtifactVersionConflictError(
                        f"Proposal is not acceptible: {live.get('status')}"
                    )

                project = self.project_store.apply_accepted_artifact_revision(
                    project_id=project_id,
                    new_artifact=new_artifact,
                    next_state_version=int(payload["next_state_version"]),
                    updated_at=payload["updated_at"],
                    expected_artifact_version=expected_art,
                    expected_project_state_version=expected_proj,
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
                self._proposals[proposal["proposalId"]] = proposal

                for sid in superseded_ids:
                    other = self._proposals.get(sid)
                    if other and other.get("status") in {"proposed", "awaiting-approval"}:
                        other = copy.deepcopy(other)
                        other["status"] = "conflicted"
                        self._proposals[sid] = other

                for event in events:
                    if event["eventId"] in self._events:
                        raise ProjectPersistenceError(f"Event already exists: {event['eventId']}")
                    self._events[event["eventId"]] = event
                    self._events_by_project.setdefault(event["projectId"], []).append(
                        event["eventId"]
                    )

                for node in graph_nodes:
                    self._graph_nodes[node["nodeId"]] = node
                    self._nodes_by_project.setdefault(node["projectId"], []).append(node["nodeId"])
                for edge in graph_edges:
                    self._graph_edges[edge["edgeId"]] = edge
                    self._edges_by_project.setdefault(edge["projectId"], []).append(edge["edgeId"])

                if projection is not None:
                    self._projections[projection["projectId"]] = projection

                return {
                    "project": project,
                    "proposal": copy.deepcopy(proposal),
                    "artifact": copy.deepcopy(new_artifact),
                }
            except (
                ProjectNotFoundError,
                ProjectStateConflictError,
                ArtifactVersionConflictError,
                ProposalNotFoundError,
                ProjectPersistenceError,
            ):
                self._restore_state(snapshot)
                raise
            except Exception as exc:  # noqa: BLE001
                self._restore_state(snapshot)
                raise ProjectPersistenceError("Accept proposal transaction failed.") from exc

    def _snapshot_state(self) -> dict[str, Any]:
        return {
            "workspaces": copy.deepcopy(self._workspaces),
            "workspace_by_project_type": copy.deepcopy(self._workspace_by_project_type),
            "drafts": copy.deepcopy(self._drafts),
            "snapshots": copy.deepcopy(self._snapshots),
            "snapshots_by_workspace": copy.deepcopy(self._snapshots_by_workspace),
            "proposals": copy.deepcopy(self._proposals),
            "proposals_by_project": copy.deepcopy(self._proposals_by_project),
            "command_runs": copy.deepcopy(self._command_runs),
            "execution_runs": copy.deepcopy(self._execution_runs),
            "executions_by_project": copy.deepcopy(self._executions_by_project),
            "execution_jobs": copy.deepcopy(self._execution_jobs),
            "execution_jobs_by_run": copy.deepcopy(self._execution_jobs_by_run),
            "execution_log_chunks": copy.deepcopy(self._execution_log_chunks),
            "outputs": copy.deepcopy(self._outputs),
            "outputs_by_project": copy.deepcopy(self._outputs_by_project),
            "events": copy.deepcopy(self._events),
            "events_by_project": copy.deepcopy(self._events_by_project),
            "projections": copy.deepcopy(self._projections),
            "graph_nodes": copy.deepcopy(self._graph_nodes),
            "graph_edges": copy.deepcopy(self._graph_edges),
            "nodes_by_project": copy.deepcopy(self._nodes_by_project),
            "edges_by_project": copy.deepcopy(self._edges_by_project),
            "project_snapshot": self.project_store._snapshot(),  # noqa: SLF001
        }

    def _restore_state(self, snapshot: dict[str, Any]) -> None:
        self._workspaces = snapshot["workspaces"]
        self._workspace_by_project_type = snapshot["workspace_by_project_type"]
        self._drafts = snapshot["drafts"]
        self._snapshots = snapshot["snapshots"]
        self._snapshots_by_workspace = snapshot["snapshots_by_workspace"]
        self._proposals = snapshot["proposals"]
        self._proposals_by_project = snapshot["proposals_by_project"]
        self._command_runs = snapshot["command_runs"]
        self._execution_runs = snapshot["execution_runs"]
        self._executions_by_project = snapshot["executions_by_project"]
        self._execution_jobs = snapshot.get("execution_jobs", {})
        self._execution_jobs_by_run = snapshot.get("execution_jobs_by_run", {})
        self._execution_log_chunks = snapshot.get("execution_log_chunks", {})
        self._outputs = snapshot["outputs"]
        self._outputs_by_project = snapshot["outputs_by_project"]
        self._events = snapshot["events"]
        self._events_by_project = snapshot["events_by_project"]
        self._projections = snapshot["projections"]
        self._graph_nodes = snapshot["graph_nodes"]
        self._graph_edges = snapshot["graph_edges"]
        self._nodes_by_project = snapshot["nodes_by_project"]
        self._edges_by_project = snapshot["edges_by_project"]
        self.project_store._restore(snapshot["project_snapshot"])  # noqa: SLF001
