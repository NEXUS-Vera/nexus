"""Phase 14A workspace filesystem file-index table.

Revision ID: 0003_phase14a_workspace_files
Revises: 0002_phase11_workspace_kernel
Create Date: 2026-08-10
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_phase14a_workspace_files"
down_revision: str | None = "0002_phase11_workspace_kernel"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_files",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("path", sa.String(length=1024), nullable=False),
        sa.Column("content_hash", sa.String(length=80), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("workspace_id", "path", name="uq_workspace_files_workspace_path"),
    )
    op.create_index("ix_workspace_files_workspace_id", "workspace_files", ["workspace_id"])
    op.create_index("ix_workspace_files_content_hash", "workspace_files", ["content_hash"])


def downgrade() -> None:
    op.drop_index("ix_workspace_files_content_hash", table_name="workspace_files")
    op.drop_index("ix_workspace_files_workspace_id", table_name="workspace_files")
    op.drop_table("workspace_files")
