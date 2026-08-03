"""Initial project persistence schema.

Revision ID: 0001_initial
Revises:
Create Date: 2026-07-29
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "projects",
        sa.Column("project_id", sa.String(length=64), primary_key=True),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("domain", sa.String(length=128), nullable=False),
        sa.Column("project_phase", sa.String(length=64), nullable=False),
        sa.Column("autonomy_mode", sa.String(length=32), nullable=False),
        sa.Column("current_state_version", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "user_turns",
        sa.Column("turn_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "project_id", sa.String(length=64), sa.ForeignKey("projects.project_id"), nullable=False
        ),
        sa.Column("parent_turn_id", sa.String(length=64), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_user_turns_project_id", "user_turns", ["project_id"])
    op.create_table(
        "turn_routes",
        sa.Column("route_id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column(
            "turn_id", sa.String(length=64), sa.ForeignKey("user_turns.turn_id"), nullable=False
        ),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_turn_routes_project_id", "turn_routes", ["project_id"])
    op.create_index("ix_turn_routes_turn_id", "turn_routes", ["turn_id"])
    op.create_table(
        "workflow_runs",
        sa.Column("run_id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column(
            "turn_id", sa.String(length=64), sa.ForeignKey("user_turns.turn_id"), nullable=False
        ),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_workflow_runs_project_id", "workflow_runs", ["project_id"])
    op.create_index("ix_workflow_runs_turn_id", "workflow_runs", ["turn_id"])
    op.create_table(
        "artifact_revisions",
        sa.Column("artifact_id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("artifact_type", sa.String(length=64), nullable=False),
        sa.Column("artifact_version", sa.Integer(), nullable=False),
        sa.Column("source_turn_id", sa.String(length=64), nullable=False),
        sa.Column("workflow_run_id", sa.String(length=64), nullable=False),
        sa.Column("supersedes_artifact_id", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.UniqueConstraint(
            "project_id",
            "artifact_type",
            "artifact_version",
            name="uq_artifact_project_type_version",
        ),
    )
    op.create_index("ix_artifact_revisions_project_id", "artifact_revisions", ["project_id"])
    op.create_table(
        "validation_issues",
        sa.Column("issue_id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_validation_issues_project_id", "validation_issues", ["project_id"])
    op.create_table(
        "open_questions",
        sa.Column("question_id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_open_questions_project_id", "open_questions", ["project_id"])
    op.create_table(
        "vera_responses",
        sa.Column("response_key", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("turn_id", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    )
    op.create_index("ix_vera_responses_project_id", "vera_responses", ["project_id"])
    op.create_index("ix_vera_responses_turn_id", "vera_responses", ["turn_id"])
    op.create_table(
        "artifact_dependencies",
        sa.Column("dependency_id", sa.String(length=64), primary_key=True),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    op.create_index("ix_artifact_dependencies_project_id", "artifact_dependencies", ["project_id"])


def downgrade() -> None:
    op.drop_table("artifact_dependencies")
    op.drop_table("vera_responses")
    op.drop_table("open_questions")
    op.drop_table("validation_issues")
    op.drop_table("artifact_revisions")
    op.drop_table("workflow_runs")
    op.drop_table("turn_routes")
    op.drop_table("user_turns")
    op.drop_table("projects")
