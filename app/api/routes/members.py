from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, require_roles
from app.models.member import Member
from app.models.user import User, UserRole
from app.schemas.member import (
    BorrowingHistoryRead,
    MemberCreate,
    MemberRead,
    MemberUpdate,
)
from app.services.members import (
    MemberEmailAlreadyExistsError,
    deactivate_member,
    get_member,
    get_member_by_user_id,
    list_members,
    register_member,
    update_member,
)
from app.services.loans import get_member_loan_history

router = APIRouter()
staff_required = require_roles(UserRole.ADMIN, UserRole.LIBRARIAN)


def member_or_404(db: Session, member_id: UUID) -> Member:
    member = get_member(db, member_id)
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    return member


def ensure_member_access(current_user: User, member: Member) -> None:
    is_staff = current_user.role in (UserRole.ADMIN, UserRole.LIBRARIAN)
    if not is_staff and member.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this member",
        )


@router.post("", response_model=MemberRead, status_code=status.HTTP_201_CREATED)
def create_member(
    data: MemberCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(staff_required)],
) -> Member:
    try:
        return register_member(db, data)
    except MemberEmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        ) from exc


@router.get("", response_model=list[MemberRead])
def read_members(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(staff_required)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    active_only: bool = False,
) -> list[Member]:
    return list_members(db, offset=offset, limit=limit, active_only=active_only)


@router.get("/me", response_model=MemberRead)
def read_own_member_profile(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Member:
    member = get_member_by_user_id(db, current_user.id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member profile not found",
        )
    return member


@router.get("/{member_id}", response_model=MemberRead)
def read_member(
    member_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Member:
    member = member_or_404(db, member_id)
    ensure_member_access(current_user, member)
    return member


@router.patch("/{member_id}", response_model=MemberRead)
def update_member_details(
    member_id: UUID,
    data: MemberUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(staff_required)],
) -> Member:
    member = member_or_404(db, member_id)
    try:
        return update_member(db, member, data)
    except MemberEmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        ) from exc


@router.post("/{member_id}/deactivate", response_model=MemberRead)
def deactivate_member_account(
    member_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(staff_required)],
) -> Member:
    return deactivate_member(db, member_or_404(db, member_id))


@router.get("/{member_id}/borrowing-history", response_model=BorrowingHistoryRead)
def read_borrowing_history(
    member_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> BorrowingHistoryRead:
    member = member_or_404(db, member_id)
    ensure_member_access(current_user, member)
    loans = get_member_loan_history(db, member.id)
    return BorrowingHistoryRead(
        member_id=member.id,
        membership_id=member.membership_id,
        total=len(loans),
        items=[
            {
                "loan_id": loan.id,
                "book_id": loan.book_id,
                "book_title": loan.book.title,
                "borrowed_at": loan.borrowed_at,
                "due_at": loan.due_at,
                "returned_at": loan.returned_at,
                "status": loan.status,
            }
            for loan in loans
        ],
    )
