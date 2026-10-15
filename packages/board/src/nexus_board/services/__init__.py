"""Board application services."""

from __future__ import annotations

from nexus_board.services.architecture_graph import materialize_layered_architecture_graph
from nexus_board.services.command_service import ArtifactCommandService
from nexus_board.services.deletion_impact import (
    apply_functional_node_removal,
    inspect_functional_node_deletion_impact,
)
from nexus_board.services.draft_lease import (
    acquire_lease,
    assert_actor_holds_lease,
    is_lease_active,
)
from nexus_board.services.execution_service import ExecutionService
from nexus_board.services.graph_service import (
    InMemoryProjectGraphReader,
    PostgresProjectGraphReader,
    ProjectGraphReader,
    ProjectGraphService,
)
from nexus_board.services.ledger_service import ProjectLedgerService
from nexus_board.services.projection_service import ProjectBoardProjectionService
from nexus_board.services.workspace_service import WorkspaceService

__all__ = [
    "ArtifactCommandService",
    "ExecutionService",
    "InMemoryProjectGraphReader",
    "PostgresProjectGraphReader",
    "ProjectBoardProjectionService",
    "ProjectGraphReader",
    "ProjectGraphService",
    "ProjectLedgerService",
    "WorkspaceService",
    "acquire_lease",
    "apply_functional_node_removal",
    "assert_actor_holds_lease",
    "inspect_functional_node_deletion_impact",
    "is_lease_active",
    "materialize_layered_architecture_graph",
]
