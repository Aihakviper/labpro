from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from app.models.loan import Loan, LoanStatus
from app.models.notification import Notification, NotificationType


class NotificationNotFoundError(Exception):
    pass


def create_notification(
    db: Session,
    *,
    member_id: UUID,
    notification_type: NotificationType,
    title: str,
    message: str,
    event_key: str,
    related_entity_type: str | None = None,
    related_entity_id: UUID | None = None,
) -> Notification | None:
    if db.scalar(select(Notification.id).where(Notification.event_key == event_key)):
        return None

    try:
        with db.begin_nested():
            notification = Notification(
                member_id=member_id,
                type=notification_type,
                title=title,
                message=message,
                event_key=event_key,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
            )
            db.add(notification)
            db.flush()
    except IntegrityError:
        return None
    return notification


def list_member_notifications(
    db: Session,
    *,
    member_id: UUID,
    offset: int,
    limit: int,
    unread_only: bool,
) -> list[Notification]:
    statement = (
        select(Notification)
        .where(Notification.member_id == member_id)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset(offset)
        .limit(limit)
    )
    if unread_only:
        statement = statement.where(Notification.read_at.is_(None))
    return list(db.scalars(statement))


def count_unread_notifications(db: Session, member_id: UUID) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(Notification)
            .where(
                Notification.member_id == member_id,
                Notification.read_at.is_(None),
            )
        )
        or 0
    )


def mark_notification_read(
    db: Session,
    *,
    notification_id: UUID,
    member_id: UUID,
) -> Notification:
    notification = db.scalar(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.member_id == member_id,
        )
    )
    if notification is None:
        raise NotificationNotFoundError
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
        db.commit()
        db.refresh(notification)
    return notification


def mark_all_notifications_read(db: Session, member_id: UUID) -> None:
    db.execute(
        update(Notification)
        .where(
            Notification.member_id == member_id,
            Notification.read_at.is_(None),
        )
        .values(read_at=datetime.now(UTC))
    )
    db.commit()


def process_overdue_notifications(
    db: Session,
    *,
    processing_date: date | None = None,
) -> int:
    today = processing_date or datetime.now(UTC).date()
    loans = list(
        db.scalars(
            select(Loan)
            .options(joinedload(Loan.book))
            .where(
                Loan.status == LoanStatus.BORROWED,
                Loan.due_at < datetime.now(UTC),
            )
        )
    )
    created = 0
    for loan in loans:
        overdue_days = max((today - loan.due_at.date()).days, 1)
        notification = create_notification(
            db,
            member_id=loan.member_id,
            notification_type=NotificationType.LOAN_OVERDUE,
            title="Book overdue",
            message=(
                f'"{loan.book.title}" is {overdue_days} day(s) overdue. '
                "Please return it as soon as possible."
            ),
            event_key=f"loan-overdue:{loan.id}:{today.isoformat()}",
            related_entity_type="loan",
            related_entity_id=loan.id,
        )
        if notification is not None:
            created += 1
    db.commit()
    return created
