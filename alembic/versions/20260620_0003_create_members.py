"""Create member profiles.

Revision ID: 20260620_0003
Revises: 20260620_0002
Create Date: 2026-06-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260620_0003"
down_revision: str | None = "20260620_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "members",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("membership_id", sa.String(length=24), nullable=False),
        sa.Column("phone_number", sa.String(length=32), nullable=False),
        sa.Column("address", sa.String(length=255), nullable=True),
        sa.Column("membership_start_date", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_members_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_members"),
    )
    op.create_index("ix_members_membership_id", "members", ["membership_id"], unique=True)
    op.create_index("ix_members_user_id", "members", ["user_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_members_user_id", table_name="members")
    op.drop_index("ix_members_membership_id", table_name="members")
    op.drop_table("members")
