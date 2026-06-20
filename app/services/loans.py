from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.core.config import get_settings
from app.models.book import Book
from app.models.loan import Loan, LoanStatus
from app.models.member import Member
from app.models.notification import NotificationType
from app.models.user import User
from app.schemas.loan import LoanCreate
from app.services.fines import create_overdue_fine
from app.services.notifications import create_notification
from app.services.reservations import (
    fulfill_ready_reservation,
    promote_next_waiting_reservation,
)


class MemberNotFoundError(Exception):
    pass


class InactiveMemberError(Exception):
    pass


class BookNotFoundError(Exception):
    pass


class BookUnavailableError(Exception):
    pass


class LoanLimitReachedError(Exception):
    pass


class InvalidDueDateError(Exception):
    pass


class LoanAlreadyReturnedError(Exception):
    pass


def issue_book(db: Session, data: LoanCreate, issued_by: User) -> Loan:
    settings = get_settings()
    now = datetime.now(UTC)
    due_at = data.due_at or now + timedelta(days=settings.default_loan_period_days)
    if due_at.tzinfo is None:
        due_at = due_at.replace(tzinfo=UTC)
    if due_at <= now:
        raise InvalidDueDateError

    member = db.scalar(
        select(Member).where(Member.id == data.member_id).with_for_update()
    )
    if member is None:
        raise MemberNotFoundError
    if not member.is_active or not member.user.is_active:
        raise InactiveMemberError

    active_loan_count = db.scalar(
        select(func.count())
        .select_from(Loan)
        .where(
            Loan.member_id == member.id,
            Loan.status == LoanStatus.BORROWED,
        )
    )
    if active_loan_count >= settings.max_active_loans_per_member:
        raise LoanLimitReachedError

    book = db.scalar(select(Book).where(Book.id == data.book_id).with_for_update())
    if book is None:
        raise BookNotFoundError
    ready_reservation = fulfill_ready_reservation(
        db,
        member_id=member.id,
        book_id=book.id,
    )
    if ready_reservation is None and book.available_copies <= 0:
        raise BookUnavailableError

    if ready_reservation is None:
        book.available_copies -= 1
    loan = Loan(
        member_id=member.id,
        book_id=book.id,
        issued_by_user_id=issued_by.id,
        borrowed_at=now,
        due_at=due_at,
        status=LoanStatus.BORROWED,
    )
    db.add(loan)
    db.flush()
    create_notification(
        db,
        member_id=member.id,
        notification_type=NotificationType.LOAN_ISSUED,
        title="Book issued successfully",
        message=f'"{book.title}" has been issued to you and is due on {due_at.date()}.',
        event_key=f"loan-issued:{loan.id}",
        related_entity_type="loan",
        related_entity_id=loan.id,
    )
    db.commit()
    return get_loan(db, loan.id)  # type: ignore[return-value]


def return_book(db: Session, loan_id: UUID, returned_by: User) -> Loan:
    loan = db.scalar(
        select(Loan).where(Loan.id == loan_id).with_for_update()
    )
    if loan is None:
        raise LookupError
    if loan.status == LoanStatus.RETURNED:
        raise LoanAlreadyReturnedError

    book = db.scalar(select(Book).where(Book.id == loan.book_id).with_for_update())
    if book is None:
        raise BookNotFoundError

    returned_at = datetime.now(UTC)
    loan.status = LoanStatus.RETURNED
    loan.returned_at = returned_at
    loan.returned_by_user_id = returned_by.id
    book.available_copies += 1
    promote_next_waiting_reservation(db, book)
    create_notification(
        db,
        member_id=loan.member_id,
        notification_type=NotificationType.LOAN_RETURNED,
        title="Book returned successfully",
        message=f'"{book.title}" was returned successfully.',
        event_key=f"loan-returned:{loan.id}",
        related_entity_type="loan",
        related_entity_id=loan.id,
    )
    create_overdue_fine(db, loan, returned_at)
    db.commit()
    return get_loan(db, loan.id)  # type: ignore[return-value]


def get_loan(db: Session, loan_id: UUID) -> Loan | None:
    return db.get(Loan, loan_id)


def list_loans(
    db: Session,
    *,
    offset: int,
    limit: int,
    member_id: UUID | None,
    status: LoanStatus | None,
) -> list[Loan]:
    statement = select(Loan).order_by(Loan.borrowed_at.desc()).offset(offset).limit(limit)
    if member_id is not None:
        statement = statement.where(Loan.member_id == member_id)
    if status is not None:
        statement = statement.where(Loan.status == status)
    return list(db.scalars(statement))


def get_member_loan_history(db: Session, member_id: UUID) -> list[Loan]:
    return list(
        db.scalars(
            select(Loan)
            .options(joinedload(Loan.book))
            .where(Loan.member_id == member_id)
            .order_by(Loan.borrowed_at.desc())
        )
    )
