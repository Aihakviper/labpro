from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, require_roles
from app.models.fine import Fine, FineConfig
from app.models.user import User, UserRole
from app.schemas.fine import (
    FineConfigRead,
    FineConfigUpdate,
    FinePaymentCreate,
    FineRead,
)
from app.services.fines import (
    FineAlreadyPaidError,
    FineNotFoundError,
    PaymentExceedsBalanceError,
    get_fine,
    get_or_create_fine_config,
    list_fines,
    record_payment,
    update_fine_config,
)
from app.services.members import get_member_by_user_id

router = APIRouter()
staff_required = require_roles(UserRole.ADMIN, UserRole.LIBRARIAN)
admin_required = require_roles(UserRole.ADMIN)


def ensure_fine_access(current_user: User, fine: Fine) -> None:
    if current_user.role in (UserRole.ADMIN, UserRole.LIBRARIAN):
        return
    if current_user.member_profile is None or fine.loan.member_id != current_user.member_profile.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this fine",
        )


@router.get("/config", response_model=FineConfigRead)
def read_fine_config(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(staff_required)],
) -> FineConfig:
    config = get_or_create_fine_config(db)
    db.commit()
    db.refresh(config)
    return config


@router.patch("/config", response_model=FineConfigRead)
def configure_fine_rate(
    data: FineConfigUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(admin_required)],
) -> FineConfig:
    return update_fine_config(db, data.daily_rate)


@router.get("", response_model=list[FineRead])
def read_fines(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(staff_required)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    member_id: UUID | None = None,
    outstanding_only: bool = False,
) -> list[Fine]:
    return list_fines(
        db,
        offset=offset,
        limit=limit,
        member_id=member_id,
        outstanding_only=outstanding_only,
    )


@router.get("/me", response_model=list[FineRead])
def read_own_fines(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    outstanding_only: bool = False,
) -> list[Fine]:
    member = get_member_by_user_id(db, current_user.id)
    if member is None:
        raise HTTPException(status_code=404, detail="Member profile not found")
    return list_fines(
        db,
        offset=0,
        limit=100,
        member_id=member.id,
        outstanding_only=outstanding_only,
    )


@router.get("/{fine_id}", response_model=FineRead)
def read_fine(
    fine_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Fine:
    fine = get_fine(db, fine_id)
    if fine is None:
        raise HTTPException(status_code=404, detail="Fine not found")
    ensure_fine_access(current_user, fine)
    return fine


@router.post("/{fine_id}/payments", response_model=FineRead)
def pay_fine(
    fine_id: UUID,
    data: FinePaymentCreate,
    db: Annotated[Session, Depends(get_db)],
    current_staff: Annotated[User, Depends(staff_required)],
) -> Fine:
    try:
        return record_payment(db, fine_id, data.amount, current_staff)
    except FineNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Fine not found") from exc
    except FineAlreadyPaidError as exc:
        raise HTTPException(status_code=409, detail="Fine has already been paid") from exc
    except PaymentExceedsBalanceError as exc:
        raise HTTPException(
            status_code=409,
            detail="Payment amount exceeds the outstanding balance",
        ) from exc
