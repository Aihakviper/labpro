from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.user import User, UserRole
from app.schemas.user import UserCreate, UserUpdate


class EmailAlreadyExistsError(Exception):
    pass


class LastActiveAdminError(Exception):
    pass


def create_user(db: Session, data: UserCreate) -> User:
    user = User(
        email=str(data.email).strip().lower(),
        full_name=data.full_name.strip(),
        hashed_password=hash_password(data.password),
        role=data.role,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise EmailAlreadyExistsError from exc
    db.refresh(user)
    return user


def list_users(db: Session, *, offset: int, limit: int) -> list[User]:
    return list(
        db.scalars(select(User).order_by(User.created_at.desc()).offset(offset).limit(limit))
    )


def get_user(db: Session, user_id: UUID) -> User | None:
    return db.get(User, user_id)


def update_user(db: Session, user: User, data: UserUpdate) -> User:
    removes_admin_access = user.role == UserRole.ADMIN and (
        data.role not in (None, UserRole.ADMIN) or data.is_active is False
    )
    if removes_admin_access:
        active_admin_count = db.scalar(
            select(func.count())
            .select_from(User)
            .where(User.role == UserRole.ADMIN, User.is_active.is_(True))
        )
        if active_admin_count == 1:
            raise LastActiveAdminError

    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "full_name" and value is not None:
            value = value.strip()
        setattr(user, field, value)
    db.commit()
    db.refresh(user)
    return user
