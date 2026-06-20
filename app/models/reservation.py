from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, ClassVar
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.book import Book
    from app.models.member import Member


class ReservationStatus(StrEnum):
    WAITING = "waiting"
    READY = "ready"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class Reservation(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "reservations"
    __table_args__ = (
        Index("ix_reservations_book_status_created", "book_id", "status", "created_at"),
        Index(
            "uq_reservations_active_member_book",
            "member_id",
            "book_id",
            unique=True,
            postgresql_where=text("status IN ('waiting', 'ready')"),
            sqlite_where=text("status IN ('waiting', 'ready')"),
        ),
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
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(
            ReservationStatus,
            name="reservation_status",
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        default=ReservationStatus.WAITING,
        server_default=ReservationStatus.WAITING.value,
        nullable=False,
    )
    queued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ready_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fulfilled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    member: Mapped["Member"] = relationship(back_populates="reservations")
    book: Mapped["Book"] = relationship(back_populates="reservations")

    queue_position: ClassVar[int | None] = None
