from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import require_roles
from app.models.loan import Loan, LoanStatus
from app.models.user import User, UserRole
from app.schemas.loan import LoanCreate, LoanRead
from app.services.loans import (
    BookNotFoundError,
    BookUnavailableError,
    InactiveMemberError,
    InvalidDueDateError,
    LoanAlreadyReturnedError,
    LoanLimitReachedError,
    MemberNotFoundError,
    get_loan,
    issue_book,
    list_loans,
    return_book,
)

router = APIRouter()
staff_required = require_roles(UserRole.ADMIN, UserRole.LIBRARIAN)


@router.post("", response_model=LoanRead, status_code=status.HTTP_201_CREATED)
def issue_book_to_member(
    data: LoanCreate,
    db: Annotated[Session, Depends(get_db)],
    current_staff: Annotated[User, Depends(staff_required)],
) -> Loan:
    try:
        return issue_book(db, data, current_staff)
    except MemberNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Member not found") from exc
    except InactiveMemberError as exc:
        raise HTTPException(status_code=409, detail="Member account is inactive") from exc
    except BookNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Book not found") from exc
    except BookUnavailableError as exc:
        raise HTTPException(status_code=409, detail="Book is not available") from exc
    except LoanLimitReachedError as exc:
        raise HTTPException(
            status_code=409,
            detail="Member has reached the active loan limit",
        ) from exc
    except InvalidDueDateError as exc:
        raise HTTPException(status_code=422, detail="Due date must be in the future") from exc


@router.get("", response_model=list[LoanRead])
def read_loans(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(staff_required)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    member_id: UUID | None = None,
    loan_status: LoanStatus | None = None,
) -> list[Loan]:
    return list_loans(
        db,
        offset=offset,
        limit=limit,
        member_id=member_id,
        status=loan_status,
    )


@router.get("/{loan_id}", response_model=LoanRead)
def read_loan(
    loan_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(staff_required)],
) -> Loan:
    loan = get_loan(db, loan_id)
    if loan is None:
        raise HTTPException(status_code=404, detail="Loan not found")
    return loan


@router.post("/{loan_id}/return", response_model=LoanRead)
def return_loaned_book(
    loan_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    current_staff: Annotated[User, Depends(staff_required)],
) -> Loan:
    try:
        return return_book(db, loan_id, current_staff)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Loan not found") from exc
    except LoanAlreadyReturnedError as exc:
        raise HTTPException(status_code=409, detail="Loan has already been returned") from exc
    except BookNotFoundError as exc:
        raise HTTPException(status_code=409, detail="Associated book no longer exists") from exc
