"""Create books catalog.

Revision ID: 20260620_0004
Revises: 20260620_0003
Create Date: 2026-06-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260620_0004"
down_revision: str | None = "20260620_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "books",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("author", sa.String(length=160), nullable=False),
        sa.Column("isbn", sa.String(length=17), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("publication_year", sa.Integer(), nullable=True),
        sa.Column("total_copies", sa.Integer(), nullable=False),
        sa.Column("available_copies", sa.Integer(), nullable=False),
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
        sa.CheckConstraint(
            "available_copies <= total_copies",
            name="available_copies_not_above_total",
        ),
        sa.CheckConstraint(
            "available_copies >= 0",
            name="available_copies_non_negative",
        ),
        sa.CheckConstraint(
            "total_copies >= 0",
            name="total_copies_non_negative",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_books"),
    )
    op.create_index("ix_books_author", "books", ["author"], unique=False)
    op.create_index("ix_books_category", "books", ["category"], unique=False)
    op.create_index("ix_books_isbn", "books", ["isbn"], unique=True)
    op.create_index("ix_books_title", "books", ["title"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_books_title", table_name="books")
    op.drop_index("ix_books_isbn", table_name="books")
    op.drop_index("ix_books_category", table_name="books")
    op.drop_index("ix_books_author", table_name="books")
    op.drop_table("books")
