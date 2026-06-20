from typing import Annotated
from uuid import UUID

import jwt
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.security import TokenType, decode_token, verify_password
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.models.user import User
from app.schemas.auth import ChangePasswordRequest, RefreshTokenRequest, Token
from app.schemas.user import UserRead
from app.services.auth import (
    authenticate_user,
    change_password,
    create_token_pair,
    get_active_session,
    revoke_session,
)

router = APIRouter()


@router.post("/login", response_model=Token)
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[Session, Depends(get_db)],
) -> Token:
    user = authenticate_user(db, email=form_data.username, password=form_data.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return create_token_pair(db, user)


@router.post("/refresh", response_model=Token)
def refresh_access_token(
    data: RefreshTokenRequest,
    db: Annotated[Session, Depends(get_db)],
) -> Token:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )
    try:
        payload = decode_token(data.refresh_token)
        if payload.get("type") != TokenType.REFRESH:
            raise credentials_error
        user_id = UUID(str(payload.get("sub")))
        session_id = UUID(str(payload.get("sid")))
    except (jwt.InvalidTokenError, TypeError, ValueError, HTTPException) as exc:
        raise credentials_error from exc

    auth_session = get_active_session(db, session_id)
    user = db.get(User, user_id)
    if (
        auth_session is None
        or auth_session.user_id != user_id
        or user is None
        or not user.is_active
    ):
        raise credentials_error

    revoke_session(db, auth_session)
    return create_token_pair(db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    data: RefreshTokenRequest,
    db: Annotated[Session, Depends(get_db)],
) -> None:
    try:
        payload = decode_token(data.refresh_token)
        if payload.get("type") != TokenType.REFRESH:
            return
        session_id = UUID(str(payload.get("sid")))
    except (jwt.InvalidTokenError, TypeError, ValueError):
        return

    auth_session = get_active_session(db, session_id)
    if auth_session is not None:
        revoke_session(db, auth_session)


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: Annotated[User, Depends(get_current_user)]) -> User:
    return current_user


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
def update_password(
    data: ChangePasswordRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    if not verify_password(data.current_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )
    if verify_password(data.new_password, current_user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different",
        )
    change_password(db, current_user, data.new_password)
