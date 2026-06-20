from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, require_roles
from app.models.reservation import Reservation, ReservationStatus
from app.models.user import User, UserRole
from app.schemas.reservation import (
    ReservationCreate,
    ReservationRead,
    ReservationUpdate,
)
from app.services.members import get_member_by_user_id
from app.services.reservations import (
    BookAvailableError,
    DuplicateReservationError,
    InvalidReservationTransitionError,
    cancel_reservation,
    create_reservation,
    get_reservation,
    list_reservations,
)

router = APIRouter()
staff_required = require_roles(UserRole.ADMIN, UserRole.LIBRARIAN)


def reservation_or_404(db: Session, reservation_id: UUID) -> Reservation:
    reservation = get_reservation(db, reservation_id)
    if reservation is None:
        raise HTTPException(status_code=404, detail="Reservation not found")
    return reservation


def ensure_reservation_access(current_user: User, reservation: Reservation) -> None:
    if current_user.role in (UserRole.ADMIN, UserRole.LIBRARIAN):
        return
    if (
        current_user.member_profile is None
        or reservation.member_id != current_user.member_profile.id
    ):
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this reservation",
        )


@router.post("", response_model=ReservationRead, status_code=status.HTTP_201_CREATED)
def reserve_book(
    data: ReservationCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Reservation:
    member = get_member_by_user_id(db, current_user.id)
    if member is None:
        raise HTTPException(status_code=403, detail="Only members can reserve books")
    try:
        return create_reservation(db, member, data.book_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail="Book not found") from exc
    except BookAvailableError as exc:
        raise HTTPException(
            status_code=409,
            detail="Available books cannot be reserved",
        ) from exc
    except DuplicateReservationError as exc:
        raise HTTPException(
            status_code=409,
            detail="Member already has an active reservation for this book",
        ) from exc
    except InvalidReservationTransitionError as exc:
        raise HTTPException(status_code=409, detail="Member account is inactive") from exc


@router.get("", response_model=list[ReservationRead])
def read_reservations(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(staff_required)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    book_id: UUID | None = None,
    member_id: UUID | None = None,
    reservation_status: ReservationStatus | None = None,
) -> list[Reservation]:
    return list_reservations(
        db,
        offset=offset,
        limit=limit,
        book_id=book_id,
        member_id=member_id,
        status=reservation_status,
    )


@router.get("/me", response_model=list[ReservationRead])
def read_own_reservations(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    reservation_status: ReservationStatus | None = None,
) -> list[Reservation]:
    member = get_member_by_user_id(db, current_user.id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member profile not found")
    return list_reservations(
        db,
        offset=0,
        limit=100,
        book_id=None,
        member_id=member.id,
        status=reservation_status,
    )


@router.get("/{reservation_id}", response_model=ReservationRead)
def read_reservation(
    reservation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Reservation:
    reservation = reservation_or_404(db, reservation_id)
    ensure_reservation_access(current_user, reservation)
    return reservation


@router.patch("/{reservation_id}", response_model=ReservationRead)
def update_reservation_status(
    reservation_id: UUID,
    data: ReservationUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Reservation:
    reservation = reservation_or_404(db, reservation_id)
    ensure_reservation_access(current_user, reservation)
    if data.status != ReservationStatus.CANCELLED:
        raise HTTPException(
            status_code=409,
            detail="Reservation status is updated automatically; only cancellation is manual",
        )
    try:
        return cancel_reservation(db, reservation)
    except InvalidReservationTransitionError as exc:
        raise HTTPException(
            status_code=409,
            detail="Only waiting or ready reservations can be cancelled",
        ) from exc
    except LookupError as exc:
        raise HTTPException(status_code=409, detail="Associated book no longer exists") from exc


@router.delete("/{reservation_id}", response_model=ReservationRead)
def cancel_book_reservation(
    reservation_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Reservation:
    reservation = reservation_or_404(db, reservation_id)
    ensure_reservation_access(current_user, reservation)
    try:
        return cancel_reservation(db, reservation)
    except InvalidReservationTransitionError as exc:
        raise HTTPException(
            status_code=409,
            detail="Only waiting or ready reservations can be cancelled",
        ) from exc
    except LookupError as exc:
        raise HTTPException(status_code=409, detail="Associated book no longer exists") from exc
