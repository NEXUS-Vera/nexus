"""Phase 14B ExecutionJob and log chunk tables.

Revision ID: 0004_phase14b_execution_jobs
Revises: 0003_phase14a_workspace_files
Create Date: 2026-08-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_phase14b_execution_jobs"
down_revision: str | None = "0003_phase14a_workspace_files"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "execution_jobs",
        sa.Column("execution_job_id", sa.String(length=64), primary_key=True),
        sa.Column("execution_run_id", sa.String(length=64), nullable=False),
        sa.Column("project_id", sa.String(length=64), nullable=False),
        sa.Column("workspace_snapshot_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_execution_jobs_execution_run_id", "execution_jobs", ["execution_run_id"])
    op.create_index("ix_execution_jobs_project_id", "execution_jobs", ["project_id"])
    op.create_index(
        "ix_execution_jobs_workspace_snapshot_id",
        "execution_jobs",
        ["workspace_snapshot_id"],
    )
    op.create_index("ix_execution_jobs_status", "execution_jobs", ["status"])

    op.create_table(
        "execution_log_chunks",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("execution_job_id", sa.String(length=64), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("stream", sa.String(length=16), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "execution_job_id",
            "sequence",
            name="uq_execution_log_job_sequence",
        ),
    )
    op.create_index(
        "ix_execution_log_chunks_execution_job_id",
        "execution_log_chunks",
        ["execution_job_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_execution_log_chunks_execution_job_id",
        table_name="execution_log_chunks",
    )
    op.drop_table("execution_log_chunks")
    op.drop_index("ix_execution_jobs_status", table_name="execution_jobs")
    op.drop_index("ix_execution_jobs_workspace_snapshot_id", table_name="execution_jobs")
    op.drop_index("ix_execution_jobs_project_id", table_name="execution_jobs")
    op.drop_index("ix_execution_jobs_execution_run_id", table_name="execution_jobs")
    op.drop_table("execution_jobs")
