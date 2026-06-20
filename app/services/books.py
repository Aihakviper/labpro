from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.book import Book
from app.models.loan import Loan
from app.models.reservation import Reservation
from app.schemas.book import BookCreate, BookUpdate, normalize_isbn


class IsbnAlreadyExistsError(Exception):
    pass


class InvalidInventoryReductionError(Exception):
    pass


class BookHasBorrowedCopiesError(Exception):
    pass


class BookHasLoanHistoryError(Exception):
    pass


class BookHasReservationHistoryError(Exception):
    pass


def create_book(db: Session, data: BookCreate) -> Book:
    book = Book(
        **data.model_dump(),
        available_copies=data.total_copies,
    )
    db.add(book)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise IsbnAlreadyExistsError from exc
    db.refresh(book)
    return book


def get_book(db: Session, book_id: UUID) -> Book | None:
    return db.get(Book, book_id)


def list_books(
    db: Session,
    *,
    offset: int,
    limit: int,
    query: str | None,
    title: str | None,
    author: str | None,
    isbn: str | None,
    available_only: bool,
) -> list[Book]:
    statement = select(Book).order_by(Book.title, Book.author).offset(offset).limit(limit)

    if query:
        term = query.strip()
        if term:
            statement = statement.where(
                or_(
                    Book.title.ilike(f"%{term}%"),
                    Book.author.ilike(f"%{term}%"),
                    Book.isbn.ilike(f"%{term}%"),
                )
            )
    if title:
        statement = statement.where(Book.title.ilike(f"%{title.strip()}%"))
    if author:
        statement = statement.where(Book.author.ilike(f"%{author.strip()}%"))
    if isbn:
        statement = statement.where(Book.isbn == normalize_isbn(isbn))
    if available_only:
        statement = statement.where(Book.available_copies > 0)

    return list(db.scalars(statement))


def update_book(db: Session, book: Book, data: BookUpdate) -> Book:
    changes = data.model_dump(exclude_unset=True)
    new_total = changes.pop("total_copies", None)
    if "total_copies" in data.model_fields_set:
        borrowed_copies = book.borrowed_copies
        if new_total < borrowed_copies:
            raise InvalidInventoryReductionError
        book.total_copies = new_total
        book.available_copies = new_total - borrowed_copies

    for field, value in changes.items():
        setattr(book, field, value)

    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise IsbnAlreadyExistsError from exc
    db.refresh(book)
    return book


def delete_book(db: Session, book: Book) -> None:
    if book.borrowed_copies > 0:
        raise BookHasBorrowedCopiesError
    has_loan_history = db.scalar(
        select(Loan.id).where(Loan.book_id == book.id).limit(1)
    )
    if has_loan_history is not None:
        raise BookHasLoanHistoryError
    has_reservation_history = db.scalar(
        select(Reservation.id).where(Reservation.book_id == book.id).limit(1)
    )
    if has_reservation_history is not None:
        raise BookHasReservationHistoryError
    db.delete(book)
    db.commit()
