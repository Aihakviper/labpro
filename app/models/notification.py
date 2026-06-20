from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.member import Member


class NotificationType(StrEnum):
    LOAN_ISSUED = "loan_issued"
    LOAN_RETURNED = "loan_returned"
    LOAN_OVERDUE = "loan_overdue"
    RESERVATION_CREATED = "reservation_created"
    RESERVATION_READY = "reservation_ready"
    RESERVATION_CANCELLED = "reservation_cancelled"
    FINE_ASSESSED = "fine_assessed"
    FINE_PAYMENT = "fine_payment"


class Notification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "notifications"

    member_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("members.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    type: Mapped[NotificationType] = mapped_column(
        Enum(
            NotificationType,
            name="notification_type",
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    event_key: Mapped[str] = mapped_column(
        String(200),
        unique=True,
        index=True,
        nullable=False,
    )
    related_entity_type: Mapped[str | None] = mapped_column(String(50))
    related_entity_id: Mapped[UUID | None] = mapped_column(Uuid)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    member: Mapped["Member"] = relationship(back_populates="notifications")

    @property
    def is_read(self) -> bool:
        return self.read_at is not None
