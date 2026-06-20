"""Create reservation queue.

Revision ID: 20260620_0007
Revises: 20260620_0006
Create Date: 2026-06-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260620_0007"
down_revision: str | None = "20260620_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

reservation_status = postgresql.ENUM(
    "waiting",
    "ready",
    "fulfilled",
    "cancelled",
    name="reservation_status",
    create_type=False,
)


def upgrade() -> None:
    reservation_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            reservation_status,
            server_default="waiting",
            nullable=False,
        ),
        sa.Column("queued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fulfilled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
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
            ["book_id"],
            ["books.id"],
            name="fk_reservations_book_id_books",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name="fk_reservations_member_id_members",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_reservations"),
    )
    op.create_index("ix_reservations_book_id", "reservations", ["book_id"], unique=False)
    op.create_index(
        "ix_reservations_book_status_created",
        "reservations",
        ["book_id", "status", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_reservations_member_id",
        "reservations",
        ["member_id"],
        unique=False,
    )
    op.create_index(
        "uq_reservations_active_member_book",
        "reservations",
        ["member_id", "book_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('waiting', 'ready')"),
    )


def downgrade() -> None:
    op.drop_index("uq_reservations_active_member_book", table_name="reservations")
    op.drop_index("ix_reservations_member_id", table_name="reservations")
    op.drop_index("ix_reservations_book_status_created", table_name="reservations")
    op.drop_index("ix_reservations_book_id", table_name="reservations")
    op.drop_table("reservations")
    reservation_status.drop(op.get_bind(), checkfirst=True)
