from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import require_roles
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserRead, UserUpdate
from app.services.auth import revoke_all_user_sessions
from app.services.users import (
    EmailAlreadyExistsError,
    LastActiveAdminError,
    create_user,
    get_user,
    list_users,
    update_user,
)

router = APIRouter()
admin_required = require_roles(UserRole.ADMIN)


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user_account(
    data: UserCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(admin_required)],
) -> User:
    try:
        return create_user(db, data)
    except EmailAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A user with this email already exists",
        ) from exc


@router.get("", response_model=list[UserRead])
def read_users(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(admin_required)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[User]:
    return list_users(db, offset=offset, limit=limit)


@router.get("/{user_id}", response_model=UserRead)
def read_user(
    user_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(admin_required)],
) -> User:
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.patch("/{user_id}", response_model=UserRead)
def update_user_account(
    user_id: UUID,
    data: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(admin_required)],
) -> User:
    user = get_user(db, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    was_active = user.is_active
    previous_role = user.role
    try:
        updated_user = update_user(db, user, data)
    except LastActiveAdminError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The last active administrator cannot be deactivated or demoted",
        ) from exc

    if (was_active and not updated_user.is_active) or previous_role != updated_user.role:
        revoke_all_user_sessions(db, updated_user.id)
    return updated_user
