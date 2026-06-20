"""Create fine configuration, fines, and payments.

Revision ID: 20260620_0006
Revises: 20260620_0005
Create Date: 2026-06-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260620_0006"
down_revision: str | None = "20260620_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

fine_status = postgresql.ENUM(
    "outstanding",
    "paid",
    name="fine_status",
    create_type=False,
)


def upgrade() -> None:
    fine_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "fine_config",
        sa.Column("id", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("daily_rate", sa.Numeric(precision=12, scale=2), nullable=False),
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
        sa.CheckConstraint("daily_rate >= 0", name="daily_rate_non_negative"),
        sa.CheckConstraint("id = 1", name="singleton_row"),
        sa.PrimaryKeyConstraint("id", name="pk_fine_config"),
    )
    op.create_table(
        "fines",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("loan_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("overdue_days", sa.Integer(), nullable=False),
        sa.Column("daily_rate", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("amount_paid", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("status", fine_status, server_default="outstanding", nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("amount >= 0", name="amount_non_negative"),
        sa.CheckConstraint("amount_paid >= 0", name="amount_paid_non_negative"),
        sa.CheckConstraint("amount_paid <= amount", name="amount_paid_not_above_amount"),
        sa.CheckConstraint("daily_rate >= 0", name="daily_rate_non_negative"),
        sa.CheckConstraint("overdue_days > 0", name="overdue_days_positive"),
        sa.ForeignKeyConstraint(
            ["loan_id"],
            ["loans.id"],
            name="fk_fines_loan_id_loans",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_fines"),
    )
    op.create_index("ix_fines_loan_id", "fines", ["loan_id"], unique=True)
    op.create_table(
        "fine_payments",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("fine_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("recorded_by_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.CheckConstraint("amount > 0", name="amount_positive"),
        sa.ForeignKeyConstraint(
            ["fine_id"],
            ["fines.id"],
            name="fk_fine_payments_fine_id_fines",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recorded_by_user_id"],
            ["users.id"],
            name="fk_fine_payments_recorded_by_user_id_users",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_fine_payments"),
    )
    op.create_index(
        "ix_fine_payments_fine_id",
        "fine_payments",
        ["fine_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_fine_payments_fine_id", table_name="fine_payments")
    op.drop_table("fine_payments")
    op.drop_index("ix_fines_loan_id", table_name="fines")
    op.drop_table("fines")
    op.drop_table("fine_config")
    fine_status.drop(op.get_bind(), checkfirst=True)
