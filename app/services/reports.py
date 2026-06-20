from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.book import Book
from app.models.fine import Fine, FineStatus
from app.models.loan import Loan, LoanStatus
from app.models.member import Member
from app.models.reservation import Reservation
from app.schemas.report import (
    BorrowedBookReportItem,
    BorrowedBooksReport,
    FineReportItem,
    FinesReport,
    InventoryReportItem,
    InventoryStatusReport,
    MemberActivitiesReport,
    MemberActivityReportItem,
    OverdueItemReportItem,
    OverdueItemsReport,
    ReportMeta,
)

ZERO = Decimal("0.00")


def date_bounds(
    date_from: date | None,
    date_to: date | None,
) -> tuple[datetime | None, datetime | None]:
    start = datetime.combine(date_from, time.min, tzinfo=UTC) if date_from else None
    end = (
        datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=UTC)
        if date_to
        else None
    )
    return start, end


def apply_date_filter(statement, column, start: datetime | None, end: datetime | None):
    if start is not None:
        statement = statement.where(column >= start)
    if end is not None:
        statement = statement.where(column < end)
    return statement


def borrowed_books_report(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    member_id: UUID | None,
    status: LoanStatus | None,
) -> BorrowedBooksReport:
    start, end = date_bounds(date_from, date_to)
    statement = (
        select(Loan)
        .options(
            joinedload(Loan.book),
            joinedload(Loan.member).joinedload(Member.user),
        )
        .order_by(Loan.borrowed_at.desc())
    )
    statement = apply_date_filter(statement, Loan.borrowed_at, start, end)
    if member_id is not None:
        statement = statement.where(Loan.member_id == member_id)
    if status is not None:
        statement = statement.where(Loan.status == status)
    loans = list(db.scalars(statement))

    return BorrowedBooksReport(
        meta=ReportMeta(
            generated_at=datetime.now(UTC),
            date_from=date_from,
            date_to=date_to,
        ),
        total_loans=len(loans),
        active_loans=sum(loan.status == LoanStatus.BORROWED for loan in loans),
        returned_loans=sum(loan.status == LoanStatus.RETURNED for loan in loans),
        items=[
            BorrowedBookReportItem(
                loan_id=loan.id,
                member_id=loan.member_id,
                membership_id=loan.member.membership_id,
                member_name=loan.member.user.full_name,
                book_id=loan.book_id,
                book_title=loan.book.title,
                isbn=loan.book.isbn,
                borrowed_at=loan.borrowed_at,
                due_at=loan.due_at,
                returned_at=loan.returned_at,
                status=loan.status,
            )
            for loan in loans
        ],
    )


def overdue_items_report(db: Session) -> OverdueItemsReport:
    now = datetime.now(UTC)
    loans = list(
        db.scalars(
            select(Loan)
            .options(
                joinedload(Loan.book),
                joinedload(Loan.member).joinedload(Member.user),
            )
            .where(
                Loan.status == LoanStatus.BORROWED,
                Loan.due_at < now,
            )
            .order_by(Loan.due_at)
        )
    )
    return OverdueItemsReport(
        generated_at=now,
        total_overdue=len(loans),
        items=[
            OverdueItemReportItem(
                loan_id=loan.id,
                member_id=loan.member_id,
                membership_id=loan.member.membership_id,
                member_name=loan.member.user.full_name,
                book_id=loan.book_id,
                book_title=loan.book.title,
                due_at=loan.due_at,
                overdue_days=max((now.date() - loan.due_at.date()).days, 1),
            )
            for loan in loans
        ],
    )


def member_activities_report(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    active_only: bool,
) -> MemberActivitiesReport:
    start, end = date_bounds(date_from, date_to)
    member_statement = (
        select(Member)
        .options(joinedload(Member.user))
        .order_by(Member.membership_id)
    )
    if active_only:
        member_statement = member_statement.where(Member.is_active.is_(True))
    members = list(db.scalars(member_statement))
    items: list[MemberActivityReportItem] = []

    for member in members:
        loan_statement = select(Loan).where(Loan.member_id == member.id)
        loan_statement = apply_date_filter(
            loan_statement,
            Loan.borrowed_at,
            start,
            end,
        )
        loans = list(db.scalars(loan_statement))

        reservation_statement = select(func.count()).select_from(Reservation).where(
            Reservation.member_id == member.id
        )
        reservation_statement = apply_date_filter(
            reservation_statement,
            Reservation.created_at,
            start,
            end,
        )
        reservation_count = int(db.scalar(reservation_statement) or 0)

        fine_statement = (
            select(Fine)
            .join(Loan)
            .where(
                Loan.member_id == member.id,
                Fine.status == FineStatus.OUTSTANDING,
            )
        )
        fine_statement = apply_date_filter(fine_statement, Fine.created_at, start, end)
        outstanding = sum(
            (fine.outstanding_amount for fine in db.scalars(fine_statement)),
            ZERO,
        )
        items.append(
            MemberActivityReportItem(
                member_id=member.id,
                membership_id=member.membership_id,
                member_name=member.user.full_name,
                is_active=member.is_active,
                total_loans=len(loans),
                active_loans=sum(
                    loan.status == LoanStatus.BORROWED for loan in loans
                ),
                returned_loans=sum(
                    loan.status == LoanStatus.RETURNED for loan in loans
                ),
                total_reservations=reservation_count,
                outstanding_fines=outstanding,
            )
        )

    return MemberActivitiesReport(
        meta=ReportMeta(
            generated_at=datetime.now(UTC),
            date_from=date_from,
            date_to=date_to,
        ),
        total_members=len(items),
        active_members=sum(item.is_active for item in items),
        members_with_active_loans=sum(item.active_loans > 0 for item in items),
        items=items,
    )


def fines_report(
    db: Session,
    *,
    date_from: date | None,
    date_to: date | None,
    member_id: UUID | None,
    status: FineStatus | None,
) -> FinesReport:
    start, end = date_bounds(date_from, date_to)
    statement = (
        select(Fine)
        .join(Fine.loan)
        .options(
            joinedload(Fine.loan)
            .joinedload(Loan.member)
            .joinedload(Member.user)
        )
        .order_by(Fine.created_at.desc())
    )
    statement = apply_date_filter(statement, Fine.created_at, start, end)
    if member_id is not None:
        statement = statement.where(Loan.member_id == member_id)
    if status is not None:
        statement = statement.where(Fine.status == status)
    fines = list(db.scalars(statement))

    return FinesReport(
        meta=ReportMeta(
            generated_at=datetime.now(UTC),
            date_from=date_from,
            date_to=date_to,
        ),
        total_fines=len(fines),
        outstanding_fines=sum(fine.status == FineStatus.OUTSTANDING for fine in fines),
        paid_fines=sum(fine.status == FineStatus.PAID for fine in fines),
        total_assessed=sum((fine.amount for fine in fines), ZERO),
        total_paid=sum((fine.amount_paid for fine in fines), ZERO),
        total_outstanding=sum(
            (fine.outstanding_amount for fine in fines),
            ZERO,
        ),
        items=[
            FineReportItem(
                fine_id=fine.id,
                loan_id=fine.loan_id,
                member_id=fine.loan.member_id,
                membership_id=fine.loan.member.membership_id,
                member_name=fine.loan.member.user.full_name,
                amount=fine.amount,
                amount_paid=fine.amount_paid,
                outstanding_amount=fine.outstanding_amount,
                status=fine.status,
                overdue_days=fine.overdue_days,
                created_at=fine.created_at,
                paid_at=fine.paid_at,
            )
            for fine in fines
        ],
    )


def inventory_status_report(
    db: Session,
    *,
    low_stock_threshold: int,
    category: str | None,
) -> InventoryStatusReport:
    statement = select(Book).order_by(Book.title)
    if category:
        statement = statement.where(Book.category.ilike(f"%{category.strip()}%"))
    books = list(db.scalars(statement))
    items = [
        InventoryReportItem(
            book_id=book.id,
            title=book.title,
            author=book.author,
            isbn=book.isbn,
            category=book.category,
            total_copies=book.total_copies,
            available_copies=book.available_copies,
            borrowed_copies=book.borrowed_copies,
            is_available=book.is_available,
            is_low_stock=book.available_copies <= low_stock_threshold,
        )
        for book in books
    ]
    return InventoryStatusReport(
        generated_at=datetime.now(UTC),
        low_stock_threshold=low_stock_threshold,
        total_titles=len(items),
        total_copies=sum(item.total_copies for item in items),
        available_copies=sum(item.available_copies for item in items),
        borrowed_copies=sum(item.borrowed_copies for item in items),
        unavailable_titles=sum(not item.is_available for item in items),
        low_stock_titles=sum(item.is_low_stock for item in items),
        items=items,
    )
