"""Persist guarded firmware patch proposals on SQLite and PostgreSQL."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_phase15c_firmware_patches"
down_revision: str | None = "0004_phase14b_execution_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "firmware_patch_proposals",
        sa.Column("proposal_id", sa.String(64), primary_key=True),
        sa.Column("project_id", sa.String(64), nullable=False),
        sa.Column("workspace_id", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column(
            "payload", sa.JSON().with_variant(postgresql.JSONB(), "postgresql"), nullable=False
        ),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
    )
    for field in ("project_id", "workspace_id"):
        op.create_index(f"ix_firmware_patch_proposals_{field}", "firmware_patch_proposals", [field])


def downgrade() -> None:
    op.drop_table("firmware_patch_proposals")
