from datetime import date
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import require_roles
from app.models.fine import FineStatus
from app.models.loan import LoanStatus
from app.models.user import User, UserRole
from app.schemas.report import (
    BorrowedBooksReport,
    FinesReport,
    InventoryStatusReport,
    MemberActivitiesReport,
    OverdueItemsReport,
)
from app.services.reports import (
    borrowed_books_report,
    fines_report,
    inventory_status_report,
    member_activities_report,
    overdue_items_report,
)

router = APIRouter()
staff_required = require_roles(UserRole.ADMIN, UserRole.LIBRARIAN)


def validate_date_range(date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="date_from cannot be later than date_to",
        )


@router.get("/borrowed-books", response_model=BorrowedBooksReport)
def report_borrowed_books(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(staff_required)],
    date_from: date | None = None,
    date_to: date | None = None,
    member_id: UUID | None = None,
    loan_status: LoanStatus | None = None,
) -> BorrowedBooksReport:
    validate_date_range(date_from, date_to)
    return borrowed_books_report(
        db,
        date_from=date_from,
        date_to=date_to,
        member_id=member_id,
        status=loan_status,
    )


@router.get("/overdue-items", response_model=OverdueItemsReport)
def report_overdue_items(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(staff_required)],
) -> OverdueItemsReport:
    return overdue_items_report(db)


@router.get("/member-activities", response_model=MemberActivitiesReport)
def report_member_activities(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(staff_required)],
    date_from: date | None = None,
    date_to: date | None = None,
    active_only: bool = False,
) -> MemberActivitiesReport:
    validate_date_range(date_from, date_to)
    return member_activities_report(
        db,
        date_from=date_from,
        date_to=date_to,
        active_only=active_only,
    )


@router.get("/fines", response_model=FinesReport)
def report_fines(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(staff_required)],
    date_from: date | None = None,
    date_to: date | None = None,
    member_id: UUID | None = None,
    fine_status: FineStatus | None = None,
) -> FinesReport:
    validate_date_range(date_from, date_to)
    return fines_report(
        db,
        date_from=date_from,
        date_to=date_to,
        member_id=member_id,
        status=fine_status,
    )


@router.get("/inventory", response_model=InventoryStatusReport)
def report_inventory(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(staff_required)],
    low_stock_threshold: Annotated[int, Query(ge=0, le=100_000)] = 1,
    category: Annotated[str | None, Query(max_length=100)] = None,
) -> InventoryStatusReport:
    return inventory_status_report(
        db,
        low_stock_threshold=low_stock_threshold,
        category=category,
    )
