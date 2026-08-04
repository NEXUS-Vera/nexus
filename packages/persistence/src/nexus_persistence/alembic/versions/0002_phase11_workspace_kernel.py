"""Phase 11 workspace and project-state kernel tables.

Revision ID: 0002_phase11_workspace_kernel
Revises: 0001_initial
Create Date: 2026-08-04
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_phase11_workspace_kernel"
down_revision: str | None = "0001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspaces",
        sa.Column("workspace_id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("artifact_id", sa.String(length=64), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("project_id", "artifact_type", name="uq_workspace_project_type"),
    )
    op.create_index("ix_workspaces_project_id", "workspaces", ["project_id"])
    op.create_index("ix_workspaces_artifact_id", "workspaces", ["artifact_id"])

    op.create_table(
        "workspace_drafts",
        sa.Column("workspace_id", sa.String(length=64), primary_key=True),
        sa.Column("draft_version", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "workspace_snapshots",
        sa.Column("snapshot_id", sa.String(length=64), primary_key=True),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("artifact_id", sa.String(length=64), nullable=False),
        sa.Column("snapshot_version", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workspace_snapshots_workspace_id", "workspace_snapshots", ["workspace_id"])
    op.create_index("ix_workspace_snapshots_project_id", "workspace_snapshots", ["project_id"])
    op.create_index("ix_workspace_snapshots_artifact_id", "workspace_snapshots", ["artifact_id"])

    op.create_table(
        "artifact_proposals",
        sa.Column("proposal_id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("artifact_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("proposed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_artifact_proposals_project_id", "artifact_proposals", ["project_id"])
    op.create_index("ix_artifact_proposals_artifact_id", "artifact_proposals", ["artifact_id"])
    op.create_index("ix_artifact_proposals_workspace_id", "artifact_proposals", ["workspace_id"])

    op.create_table(
        "artifact_command_runs",
        sa.Column("command_run_id", sa.String(length=64), primary_key=True),
        sa.Column("command_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_artifact_command_runs_command_id", "artifact_command_runs", ["command_id"])
    op.create_index("ix_artifact_command_runs_project_id", "artifact_command_runs", ["project_id"])
    op.create_index(
        "ix_artifact_command_runs_workspace_id", "artifact_command_runs", ["workspace_id"]
    )

    op.create_table(
        "execution_runs",
        sa.Column("execution_run_id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("artifact_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_execution_runs_project_id", "execution_runs", ["project_id"])
    op.create_index("ix_execution_runs_artifact_id", "execution_runs", ["artifact_id"])
    op.create_index("ix_execution_runs_workspace_id", "execution_runs", ["workspace_id"])
    op.create_index("ix_execution_runs_status", "execution_runs", ["status"])

    op.create_table(
        "produced_outputs",
        sa.Column("output_id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("artifact_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("execution_run_id", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_produced_outputs_project_id", "produced_outputs", ["project_id"])
    op.create_index("ix_produced_outputs_artifact_id", "produced_outputs", ["artifact_id"])
    op.create_index("ix_produced_outputs_workspace_id", "produced_outputs", ["workspace_id"])
    op.create_index(
        "ix_produced_outputs_execution_run_id", "produced_outputs", ["execution_run_id"]
    )

    op.create_table(
        "project_events",
        sa.Column("event_id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("event_type", sa.String(length=64), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_project_events_project_id", "project_events", ["project_id"])
    op.create_index(
        "ix_project_events_chronology",
        "project_events",
        ["project_id", "occurred_at", "event_id"],
    )

    op.create_table(
        "project_board_projections",
        sa.Column("project_id", sa.String(length=64), primary_key=True),
        sa.Column("projection_version", sa.Integer(), nullable=False),
        sa.Column("project_state_version", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_project_board_projections_lookup",
        "project_board_projections",
        ["project_id", "project_state_version"],
    )

    op.create_table(
        "project_graph_nodes",
        sa.Column("node_id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("node_type", sa.String(length=64), nullable=False),
        sa.Column("ref_id", sa.String(length=64), nullable=True),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_project_graph_nodes_project_id", "project_graph_nodes", ["project_id"])
    op.create_index("ix_project_graph_nodes_ref_id", "project_graph_nodes", ["ref_id"])

    op.create_table(
        "project_graph_edges",
        sa.Column("edge_id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("source_node_id", sa.String(length=64), nullable=False),
        sa.Column("target_node_id", sa.String(length=64), nullable=False),
        sa.Column("edge_type", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_project_graph_edges_project_id", "project_graph_edges", ["project_id"])
    op.create_index(
        "ix_project_graph_edges_source_node_id", "project_graph_edges", ["source_node_id"]
    )
    op.create_index(
        "ix_project_graph_edges_target_node_id", "project_graph_edges", ["target_node_id"]
    )


def downgrade() -> None:
    op.drop_table("project_graph_edges")
    op.drop_table("project_graph_nodes")
    op.drop_table("project_board_projections")
    op.drop_table("project_events")
    op.drop_table("produced_outputs")
    op.drop_table("execution_runs")
    op.drop_table("artifact_command_runs")
    op.drop_table("artifact_proposals")
    op.drop_table("workspace_snapshots")
    op.drop_table("workspace_drafts")
    op.drop_table("workspaces")
