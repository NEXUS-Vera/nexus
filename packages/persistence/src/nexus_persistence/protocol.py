"""Project package and kernel store protocols."""

from __future__ import annotations

from typing import Any, Protocol


class ProjectPackageStore(Protocol):
    def save_initialization_package(self, package: dict[str, Any]) -> None:
        """Atomically persist a validated initialization package."""
        ...

    def save_modification_package(
        self,
        package: dict[str, Any],
        *,
        dependencies: list[dict[str, Any]] | None = None,
        new_artifact_revisions: list[dict[str, Any]] | None = None,
    ) -> None:
        """Atomically persist a validated modification package and revisions."""
        ...

    def get_current_state(self, project_id: str) -> dict[str, Any]:
        """Return the current project package (ProjectCurrentState shape)."""
        ...

    def get_artifacts(self, project_id: str) -> list[dict[str, Any]]:
        """Return current artifact revisions only."""
        ...

    def get_artifact(
        self,
        project_id: str,
        artifact_type: str,
        *,
        version: int | None = None,
    ) -> dict[str, Any]:
        """Return current or specific artifact revision."""
        ...

    def get_history(self, project_id: str, *, limit: int = 100) -> dict[str, Any]:
        """Return lightweight project history."""
        ...

    def list_dependencies(self, project_id: str) -> list[dict[str, Any]]:
        """Return artifact dependency records for the project."""
        ...


class ProjectKernelStore(Protocol):
    """Persistence for workspaces, proposals, executions, ledger, graph, projections."""

    # --- workspaces ---
    def create_workspace(self, workspace: dict[str, Any], draft: dict[str, Any]) -> None: ...

    def get_workspace(self, workspace_id: str) -> dict[str, Any]: ...

    def get_workspace_by_project_artifact(
        self, project_id: str, artifact_type: str
    ) -> dict[str, Any] | None: ...

    def update_workspace(self, workspace: dict[str, Any]) -> None: ...

    # --- drafts ---
    def get_draft(self, workspace_id: str) -> dict[str, Any]: ...

    def update_draft(self, draft: dict[str, Any]) -> None: ...

    # --- snapshots (immutable) ---
    def create_snapshot(self, snapshot: dict[str, Any]) -> None: ...

    def get_snapshot(self, snapshot_id: str) -> dict[str, Any]: ...

    def list_snapshots(self, workspace_id: str) -> list[dict[str, Any]]: ...

    # --- proposals ---
    def create_proposal(self, proposal: dict[str, Any]) -> None: ...

    def get_proposal(self, proposal_id: str) -> dict[str, Any]: ...

    def list_proposals(self, project_id: str) -> list[dict[str, Any]]: ...

    def update_proposal_status(self, proposal_id: str, proposal: dict[str, Any]) -> None: ...

    # --- command runs ---
    def append_command_run(self, command_run: dict[str, Any]) -> None: ...

    def get_command_run(self, command_run_id: str) -> dict[str, Any]: ...

    # --- executions ---
    def create_execution_run(self, execution_run: dict[str, Any]) -> None: ...

    def update_execution_status(
        self, execution_run_id: str, execution_run: dict[str, Any]
    ) -> None: ...

    def get_execution_run(self, execution_run_id: str) -> dict[str, Any]: ...

    def list_execution_runs(
        self, project_id: str, *, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]: ...

    # --- produced outputs ---
    def create_produced_output(self, output: dict[str, Any]) -> None: ...

    def list_produced_outputs(self, project_id: str) -> list[dict[str, Any]]: ...

    # --- events (append-only) ---
    def append_project_event(self, event: dict[str, Any]) -> None: ...

    def list_project_events(
        self, project_id: str, *, limit: int = 50, cursor: str | None = None
    ) -> tuple[list[dict[str, Any]], str | None]: ...

    # --- projections ---
    def upsert_board_projection(self, projection: dict[str, Any]) -> None: ...

    def get_board_projection(self, project_id: str) -> dict[str, Any] | None: ...

    # --- graph ---
    def create_graph_node(self, node: dict[str, Any]) -> None: ...

    def create_graph_edge(self, edge: dict[str, Any]) -> None: ...

    def list_graph_nodes(self, project_id: str) -> list[dict[str, Any]]: ...

    def list_graph_edges(self, project_id: str) -> list[dict[str, Any]]: ...

    def get_graph_node(self, node_id: str) -> dict[str, Any] | None: ...

    # --- accept transaction ---
    def accept_proposal_transaction(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Atomically accept a proposal.

        Expected payload keys:
          - proposal, new_artifact, project_update (project dict), events,
            graph_nodes, graph_edges, projection, superseded_proposal_ids (optional)
        Validates concurrency tokens against current project state.
        Creates artifact revision via project store patterns.
        """
        ...
