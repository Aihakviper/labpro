from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.member import Member
from app.models.notification import NotificationType
from app.models.reservation import Reservation, ReservationStatus
from app.services.notifications import create_notification


class ReservationNotFoundError(Exception):
    pass


class BookAvailableError(Exception):
    pass


class DuplicateReservationError(Exception):
    pass


class InvalidReservationTransitionError(Exception):
    pass


def create_reservation(db: Session, member: Member, book_id: UUID) -> Reservation:
    if not member.is_active or not member.user.is_active:
        raise InvalidReservationTransitionError

    book = db.scalar(select(Book).where(Book.id == book_id).with_for_update())
    if book is None:
        raise LookupError
    if book.available_copies > 0:
        raise BookAvailableError

    existing = db.scalar(
        select(Reservation).where(
            Reservation.member_id == member.id,
            Reservation.book_id == book.id,
            Reservation.status.in_(
                [ReservationStatus.WAITING, ReservationStatus.READY]
            ),
        )
    )
    if existing is not None:
        raise DuplicateReservationError

    reservation = Reservation(
        member_id=member.id,
        book_id=book.id,
        status=ReservationStatus.WAITING,
        queued_at=datetime.now(UTC),
    )
    db.add(reservation)
    try:
        db.flush()
        create_notification(
            db,
            member_id=member.id,
            notification_type=NotificationType.RESERVATION_CREATED,
            title="Reservation confirmed",
            message=f'You joined the reservation queue for "{book.title}".',
            event_key=f"reservation-created:{reservation.id}",
            related_entity_type="reservation",
            related_entity_id=reservation.id,
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DuplicateReservationError from exc
    db.refresh(reservation)
    assign_queue_positions(db, [reservation])
    return reservation


def get_reservation(db: Session, reservation_id: UUID) -> Reservation | None:
    reservation = db.get(Reservation, reservation_id)
    if reservation is not None:
        assign_queue_positions(db, [reservation])
    return reservation


def list_reservations(
    db: Session,
    *,
    offset: int,
    limit: int,
    book_id: UUID | None,
    member_id: UUID | None,
    status: ReservationStatus | None,
) -> list[Reservation]:
    statement = (
        select(Reservation)
        .order_by(Reservation.queued_at, Reservation.id)
        .offset(offset)
        .limit(limit)
    )
    if book_id is not None:
        statement = statement.where(Reservation.book_id == book_id)
    if member_id is not None:
        statement = statement.where(Reservation.member_id == member_id)
    if status is not None:
        statement = statement.where(Reservation.status == status)
    reservations = list(db.scalars(statement))
    assign_queue_positions(db, reservations)
    return reservations


def assign_queue_positions(db: Session, reservations: list[Reservation]) -> None:
    for reservation in reservations:
        if reservation.status == ReservationStatus.READY:
            reservation.queue_position = 0
        elif reservation.status == ReservationStatus.WAITING:
            waiting_ids = list(
                db.scalars(
                    select(Reservation.id)
                    .where(
                        Reservation.book_id == reservation.book_id,
                        Reservation.status == ReservationStatus.WAITING,
                    )
                    .order_by(Reservation.queued_at, Reservation.id)
                )
            )
            reservation.queue_position = waiting_ids.index(reservation.id) + 1
        else:
            reservation.queue_position = None


def promote_next_waiting_reservation(
    db: Session,
    book: Book,
) -> Reservation | None:
    if book.available_copies <= 0:
        return None
    reservation = db.scalar(
        select(Reservation)
        .where(
            Reservation.book_id == book.id,
            Reservation.status == ReservationStatus.WAITING,
        )
        .order_by(Reservation.queued_at, Reservation.id)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if reservation is None:
        return None

    reservation.status = ReservationStatus.READY
    reservation.ready_at = datetime.now(UTC)
    book.available_copies -= 1
    create_notification(
        db,
        member_id=reservation.member_id,
        notification_type=NotificationType.RESERVATION_READY,
        title="Reserved book available",
        message=f'"{book.title}" is now ready for collection.',
        event_key=f"reservation-ready:{reservation.id}",
        related_entity_type="reservation",
        related_entity_id=reservation.id,
    )
    return reservation


def cancel_reservation(
    db: Session,
    reservation: Reservation,
) -> Reservation:
    if reservation.status not in (
        ReservationStatus.WAITING,
        ReservationStatus.READY,
    ):
        raise InvalidReservationTransitionError

    was_ready = reservation.status == ReservationStatus.READY
    reservation.status = ReservationStatus.CANCELLED
    reservation.cancelled_at = datetime.now(UTC)
    create_notification(
        db,
        member_id=reservation.member_id,
        notification_type=NotificationType.RESERVATION_CANCELLED,
        title="Reservation cancelled",
        message="Your book reservation was cancelled successfully.",
        event_key=f"reservation-cancelled:{reservation.id}",
        related_entity_type="reservation",
        related_entity_id=reservation.id,
    )

    if was_ready:
        book = db.scalar(
            select(Book).where(Book.id == reservation.book_id).with_for_update()
        )
        if book is None:
            raise LookupError
        book.available_copies += 1
        promote_next_waiting_reservation(db, book)

    db.commit()
    db.refresh(reservation)
    assign_queue_positions(db, [reservation])
    return reservation


def fulfill_ready_reservation(
    db: Session,
    *,
    member_id: UUID,
    book_id: UUID,
) -> Reservation | None:
    reservation = db.scalar(
        select(Reservation)
        .where(
            Reservation.member_id == member_id,
            Reservation.book_id == book_id,
            Reservation.status == ReservationStatus.READY,
        )
        .with_for_update()
    )
    if reservation is None:
        return None
    reservation.status = ReservationStatus.FULFILLED
    reservation.fulfilled_at = datetime.now(UTC)
    return reservation


def cancel_member_active_reservations(db: Session, member_id: UUID) -> None:
    reservations = list(
        db.scalars(
            select(Reservation).where(
                Reservation.member_id == member_id,
                Reservation.status.in_(
                    [ReservationStatus.WAITING, ReservationStatus.READY]
                ),
            )
        )
    )
    for reservation in reservations:
        cancel_reservation(db, reservation)
