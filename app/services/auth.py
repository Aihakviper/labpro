from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import TokenType, create_token, hash_password, verify_password
from app.models.auth_session import AuthSession
from app.models.user import User
from app.schemas.auth import Token


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    normalized_email = email.strip().lower()
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None or not verify_password(password, user.hashed_password):
        return None
    return user


def create_token_pair(db: Session, user: User) -> Token:
    settings = get_settings()
    refresh_lifetime = timedelta(days=settings.refresh_token_expire_days)
    auth_session = AuthSession(
        user_id=user.id,
        expires_at=datetime.now(UTC) + refresh_lifetime,
    )
    db.add(auth_session)
    db.flush()

    access_token = create_token(
        subject=str(user.id),
        token_type=TokenType.ACCESS,
        session_id=auth_session.id,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    refresh_token = create_token(
        subject=str(user.id),
        token_type=TokenType.REFRESH,
        session_id=auth_session.id,
        expires_delta=refresh_lifetime,
    )
    db.commit()
    return Token(access_token=access_token, refresh_token=refresh_token)


def get_active_session(db: Session, session_id: UUID) -> AuthSession | None:
    auth_session = db.get(AuthSession, session_id)
    if auth_session is None or auth_session.revoked_at is not None:
        return None
    expires_at = auth_session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= datetime.now(UTC):
        return None
    return auth_session


def revoke_session(db: Session, auth_session: AuthSession) -> None:
    auth_session.revoked_at = datetime.now(UTC)
    db.commit()


def revoke_all_user_sessions(db: Session, user_id: UUID) -> None:
    active_sessions = db.scalars(
        select(AuthSession).where(
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
        )
    )
    revoked_at = datetime.now(UTC)
    for auth_session in active_sessions:
        auth_session.revoked_at = revoked_at
    db.commit()


def change_password(db: Session, user: User, new_password: str) -> None:
    user.hashed_password = hash_password(new_password)
    revoke_all_user_sessions(db, user.id)
