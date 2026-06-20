from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, require_roles
from app.models.notification import Notification
from app.models.user import User, UserRole
from app.schemas.notification import (
    NotificationRead,
    OverdueNotificationResult,
    UnreadNotificationCount,
)
from app.services.members import get_member_by_user_id
from app.services.notifications import (
    NotificationNotFoundError,
    count_unread_notifications,
    list_member_notifications,
    mark_all_notifications_read,
    mark_notification_read,
    process_overdue_notifications,
)

router = APIRouter()
staff_required = require_roles(UserRole.ADMIN, UserRole.LIBRARIAN)


def current_member_id(db: Session, current_user: User) -> UUID:
    member = get_member_by_user_id(db, current_user.id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only members have notifications",
        )
    return member.id


@router.get("", response_model=list[NotificationRead])
def read_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    unread_only: bool = False,
) -> list[Notification]:
    return list_member_notifications(
        db,
        member_id=current_member_id(db, current_user),
        offset=offset,
        limit=limit,
        unread_only=unread_only,
    )


@router.get("/unread-count", response_model=UnreadNotificationCount)
def read_unread_count(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> UnreadNotificationCount:
    return UnreadNotificationCount(
        count=count_unread_notifications(db, current_member_id(db, current_user))
    )


@router.post("/read-all", status_code=status.HTTP_204_NO_CONTENT)
def read_all_notifications(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    mark_all_notifications_read(db, current_member_id(db, current_user))


@router.post("/process-overdue", response_model=OverdueNotificationResult)
def process_overdue(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(staff_required)],
) -> OverdueNotificationResult:
    return OverdueNotificationResult(created=process_overdue_notifications(db))


@router.post("/{notification_id}/read", response_model=NotificationRead)
def read_notification(
    notification_id: UUID,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Notification:
    try:
        return mark_notification_read(
            db,
            notification_id=notification_id,
            member_id=current_member_id(db, current_user),
        )
    except NotificationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Notification not found") from exc
