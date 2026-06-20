from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.book import Book
    from app.models.member import Member
    from app.models.user import User


class LoanStatus(StrEnum):
    BORROWED = "borrowed"
    RETURNED = "returned"


class Loan(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "loans"
    __table_args__ = (
        Index("ix_loans_member_status", "member_id", "status"),
        Index("ix_loans_book_status", "book_id", "status"),
    )

    member_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("members.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    book_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("books.id", ondelete="RESTRICT"),
        index=True,
        nullable=False,
    )
    issued_by_user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    returned_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
    )
    borrowed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[LoanStatus] = mapped_column(
        Enum(
            LoanStatus,
            name="loan_status",
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        default=LoanStatus.BORROWED,
        server_default=LoanStatus.BORROWED.value,
        nullable=False,
    )

    member: Mapped["Member"] = relationship(back_populates="loans")
    book: Mapped["Book"] = relationship(back_populates="loans")
    issued_by: Mapped["User"] = relationship(foreign_keys=[issued_by_user_id])
    returned_by: Mapped["User | None"] = relationship(foreign_keys=[returned_by_user_id])
