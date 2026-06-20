from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models.fine import Fine, FineConfig, FinePayment, FineStatus
from app.models.loan import Loan
from app.models.user import User

MONEY_QUANTUM = Decimal("0.01")


class FineNotFoundError(Exception):
    pass


class FineAlreadyPaidError(Exception):
    pass


class PaymentExceedsBalanceError(Exception):
    pass


def get_or_create_fine_config(db: Session) -> FineConfig:
    config = db.get(FineConfig, 1)
    if config is None:
        config = FineConfig(
            id=1,
            daily_rate=get_settings().default_fine_rate_per_day.quantize(MONEY_QUANTUM),
        )
        db.add(config)
        db.flush()
    return config


def update_fine_config(db: Session, daily_rate: Decimal) -> FineConfig:
    config = get_or_create_fine_config(db)
    config.daily_rate = daily_rate.quantize(MONEY_QUANTUM)
    db.commit()
    db.refresh(config)
    return config


def create_overdue_fine(db: Session, loan: Loan, returned_at: datetime) -> Fine | None:
    overdue_days = (returned_at.date() - loan.due_at.date()).days
    if overdue_days <= 0:
        return None

    existing_fine = db.scalar(select(Fine).where(Fine.loan_id == loan.id))
    if existing_fine is not None:
        return existing_fine

    daily_rate = get_or_create_fine_config(db).daily_rate
    amount = (daily_rate * overdue_days).quantize(MONEY_QUANTUM)
    if amount <= 0:
        return None
    fine = Fine(
        loan_id=loan.id,
        overdue_days=overdue_days,
        daily_rate=daily_rate,
        amount=amount,
        amount_paid=Decimal("0.00"),
        status=FineStatus.OUTSTANDING,
    )
    db.add(fine)
    return fine


def get_fine(db: Session, fine_id: UUID) -> Fine | None:
    return (
        db.execute(
        select(Fine)
        .options(joinedload(Fine.payments), joinedload(Fine.loan))
        .where(Fine.id == fine_id)
        )
        .unique()
        .scalar_one_or_none()
    )


def list_fines(
    db: Session,
    *,
    offset: int,
    limit: int,
    member_id: UUID | None,
    outstanding_only: bool,
) -> list[Fine]:
    statement = (
        select(Fine)
        .join(Fine.loan)
        .options(joinedload(Fine.payments))
        .order_by(Fine.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if member_id is not None:
        statement = statement.where(Loan.member_id == member_id)
    if outstanding_only:
        statement = statement.where(Fine.status == FineStatus.OUTSTANDING)
    return list(db.scalars(statement).unique())


def record_payment(
    db: Session,
    fine_id: UUID,
    amount: Decimal,
    recorded_by: User,
) -> Fine:
    fine = (
        db.execute(
            select(Fine)
            .options(joinedload(Fine.payments))
            .where(Fine.id == fine_id)
            .with_for_update()
        )
        .unique()
        .scalar_one_or_none()
    )
    if fine is None:
        raise FineNotFoundError
    if fine.status == FineStatus.PAID:
        raise FineAlreadyPaidError

    payment_amount = amount.quantize(MONEY_QUANTUM)
    if payment_amount > fine.outstanding_amount:
        raise PaymentExceedsBalanceError

    paid_at = datetime.now(UTC)
    payment = FinePayment(
        fine_id=fine.id,
        amount=payment_amount,
        recorded_by_user_id=recorded_by.id,
        paid_at=paid_at,
    )
    fine.payments.append(payment)
    fine.amount_paid = (fine.amount_paid + payment_amount).quantize(MONEY_QUANTUM)
    if fine.amount_paid == fine.amount:
        fine.status = FineStatus.PAID
        fine.paid_at = paid_at
    db.commit()
    return get_fine(db, fine.id)  # type: ignore[return-value]
