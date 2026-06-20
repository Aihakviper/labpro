"""Create member notifications.

Revision ID: 20260621_0008
Revises: 20260620_0007
Create Date: 2026-06-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260621_0008"
down_revision: str | None = "20260620_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

notification_type = postgresql.ENUM(
    "loan_issued",
    "loan_returned",
    "loan_overdue",
    "reservation_created",
    "reservation_ready",
    "reservation_cancelled",
    "fine_assessed",
    "fine_payment",
    name="notification_type",
    create_type=False,
)


def upgrade() -> None:
    notification_type.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", notification_type, nullable=False),
        sa.Column("title", sa.String(length=160), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("event_key", sa.String(length=200), nullable=False),
        sa.Column("related_entity_type", sa.String(length=50), nullable=True),
        sa.Column("related_entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
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
            ["member_id"],
            ["members.id"],
            name="fk_notifications_member_id_members",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_notifications"),
    )
    op.create_index(
        "ix_notifications_event_key",
        "notifications",
        ["event_key"],
        unique=True,
    )
    op.create_index(
        "ix_notifications_member_id",
        "notifications",
        ["member_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_notifications_member_id", table_name="notifications")
    op.drop_index("ix_notifications_event_key", table_name="notifications")
    op.drop_table("notifications")
    notification_type.drop(op.get_bind(), checkfirst=True)
