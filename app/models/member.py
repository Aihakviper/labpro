from datetime import date, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, String, Uuid, true
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.loan import Loan
    from app.models.reservation import Reservation
    from app.models.user import User


class Member(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "members"

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="CASCADE"),
        unique=True,
        index=True,
        nullable=False,
    )
    membership_id: Mapped[str] = mapped_column(
        String(24),
        unique=True,
        index=True,
        nullable=False,
    )
    phone_number: Mapped[str] = mapped_column(String(32), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255))
    membership_start_date: Mapped[date] = mapped_column(
        Date,
        default=date.today,
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default=true(),
        nullable=False,
    )
    deactivated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    user: Mapped["User"] = relationship(back_populates="member_profile")
    loans: Mapped[list["Loan"]] = relationship(back_populates="member")
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="member")
