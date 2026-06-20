"""Create borrowing and returning records.

Revision ID: 20260620_0005
Revises: 20260620_0004
Create Date: 2026-06-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260620_0005"
down_revision: str | None = "20260620_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

loan_status = postgresql.ENUM(
    "borrowed",
    "returned",
    name="loan_status",
    create_type=False,
)


def upgrade() -> None:
    loan_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "loans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("book_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("issued_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("returned_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("borrowed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", loan_status, server_default="borrowed", nullable=False),
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
            name="fk_loans_book_id_books",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["issued_by_user_id"],
            ["users.id"],
            name="fk_loans_issued_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name="fk_loans_member_id_members",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["returned_by_user_id"],
            ["users.id"],
            name="fk_loans_returned_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_loans"),
    )
    op.create_index("ix_loans_book_id", "loans", ["book_id"], unique=False)
    op.create_index("ix_loans_book_status", "loans", ["book_id", "status"], unique=False)
    op.create_index("ix_loans_member_id", "loans", ["member_id"], unique=False)
    op.create_index(
        "ix_loans_member_status",
        "loans",
        ["member_id", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_loans_member_status", table_name="loans")
    op.drop_index("ix_loans_member_id", table_name="loans")
    op.drop_index("ix_loans_book_status", table_name="loans")
    op.drop_index("ix_loans_book_id", table_name="loans")
    op.drop_table("loans")
    loan_status.drop(op.get_bind(), checkfirst=True)
