from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, Numeric, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.loan import Loan
    from app.models.user import User


class FineStatus(StrEnum):
    OUTSTANDING = "outstanding"
    PAID = "paid"


class FineConfig(TimestampMixin, Base):
    __tablename__ = "fine_config"
    __table_args__ = (
        CheckConstraint("id = 1", name="singleton_row"),
        CheckConstraint("daily_rate >= 0", name="daily_rate_non_negative"),
    )

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        default=1,
        autoincrement=False,
    )
    daily_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class Fine(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fines"
    __table_args__ = (
        CheckConstraint("overdue_days > 0", name="overdue_days_positive"),
        CheckConstraint("daily_rate >= 0", name="daily_rate_non_negative"),
        CheckConstraint("amount >= 0", name="amount_non_negative"),
        CheckConstraint("amount_paid >= 0", name="amount_paid_non_negative"),
        CheckConstraint("amount_paid <= amount", name="amount_paid_not_above_amount"),
    )

    loan_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("loans.id", ondelete="RESTRICT"),
        unique=True,
        index=True,
        nullable=False,
    )
    overdue_days: Mapped[int] = mapped_column(Integer, nullable=False)
    daily_rate: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount_paid: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        default=Decimal("0.00"),
        nullable=False,
    )
    status: Mapped[FineStatus] = mapped_column(
        Enum(
            FineStatus,
            name="fine_status",
            values_callable=lambda enum_class: [item.value for item in enum_class],
        ),
        default=FineStatus.OUTSTANDING,
        server_default=FineStatus.OUTSTANDING.value,
        nullable=False,
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    loan: Mapped["Loan"] = relationship(back_populates="fine")
    payments: Mapped[list["FinePayment"]] = relationship(
        back_populates="fine",
        cascade="all, delete-orphan",
        order_by="FinePayment.paid_at",
    )

    @property
    def outstanding_amount(self) -> Decimal:
        return self.amount - self.amount_paid


class FinePayment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "fine_payments"
    __table_args__ = (CheckConstraint("amount > 0", name="amount_positive"),)

    fine_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("fines.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    recorded_by_user_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    fine: Mapped["Fine"] = relationship(back_populates="payments")
    recorded_by: Mapped["User"] = relationship()
