from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.core.security import hash_password
from app.models.member import Member
from app.models.user import User, UserRole
from app.schemas.member import MemberCreate, MemberUpdate
from app.services.auth import revoke_all_user_sessions


class MemberEmailAlreadyExistsError(Exception):
    pass


def generate_membership_id() -> str:
    year = datetime.now(UTC).year
    suffix = uuid4().hex[:12].upper()
    return f"LP-{year}-{suffix}"


def register_member(db: Session, data: MemberCreate) -> Member:
    user = User(
        email=str(data.email).strip().lower(),
        full_name=data.full_name.strip(),
        hashed_password=hash_password(data.password),
        role=UserRole.MEMBER,
    )
    member = Member(
        user=user,
        membership_id=generate_membership_id(),
        phone_number=data.phone_number.strip(),
        address=data.address.strip() if data.address else None,
    )
    db.add(member)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise MemberEmailAlreadyExistsError from exc
    db.refresh(member)
    return get_member(db, member.id)  # type: ignore[return-value]


def list_members(
    db: Session,
    *,
    offset: int,
    limit: int,
    active_only: bool,
) -> list[Member]:
    statement = (
        select(Member)
        .options(joinedload(Member.user))
        .order_by(Member.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    if active_only:
        statement = statement.where(Member.is_active.is_(True))
    return list(db.scalars(statement))


def get_member(db: Session, member_id: UUID) -> Member | None:
    return db.scalar(
        select(Member)
        .options(joinedload(Member.user))
        .where(Member.id == member_id)
    )


def get_member_by_user_id(db: Session, user_id: UUID) -> Member | None:
    return db.scalar(
        select(Member)
        .options(joinedload(Member.user))
        .where(Member.user_id == user_id)
    )


def update_member(db: Session, member: Member, data: MemberUpdate) -> Member:
    changes = data.model_dump(exclude_unset=True)
    if "email" in changes:
        member.user.email = str(changes.pop("email")).strip().lower()
    if "full_name" in changes:
        member.user.full_name = changes.pop("full_name").strip()
    if "phone_number" in changes:
        changes["phone_number"] = changes["phone_number"].strip()
    if "address" in changes and changes["address"] is not None:
        changes["address"] = changes["address"].strip() or None
    for field, value in changes.items():
        setattr(member, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise MemberEmailAlreadyExistsError from exc
    return get_member(db, member.id)  # type: ignore[return-value]


def deactivate_member(db: Session, member: Member) -> Member:
    from app.services.reservations import cancel_member_active_reservations

    cancel_member_active_reservations(db, member.id)
    if member.is_active:
        member.is_active = False
        member.deactivated_at = datetime.now(UTC)
    member.user.is_active = False
    db.commit()
    revoke_all_user_sessions(db, member.user_id)
    return get_member(db, member.id)  # type: ignore[return-value]
