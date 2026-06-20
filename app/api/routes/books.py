from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user, require_roles
from app.models.book import Book
from app.models.user import User, UserRole
from app.schemas.book import BookCreate, BookRead, BookUpdate
from app.services.books import (
    BookHasBorrowedCopiesError,
    InvalidInventoryReductionError,
    IsbnAlreadyExistsError,
    create_book,
    delete_book,
    get_book,
    list_books,
    update_book,
)

router = APIRouter()
staff_required = require_roles(UserRole.ADMIN, UserRole.LIBRARIAN)


def book_or_404(db: Session, book_id: UUID) -> Book:
    book = get_book(db, book_id)
    if book is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Book not found")
    return book


@router.post("", response_model=BookRead, status_code=status.HTTP_201_CREATED)
def add_book(
    data: BookCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(staff_required)],
) -> Book:
    try:
        return create_book(db, data)
    except IsbnAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A book with this ISBN already exists",
        ) from exc


@router.get("", response_model=list[BookRead])
def read_books(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    q: Annotated[str | None, Query(max_length=200)] = None,
    title: Annotated[str | None, Query(max_length=200)] = None,
    author: Annotated[str | None, Query(max_length=160)] = None,
    isbn: Annotated[str | None, Query(max_length=24)] = None,
    available_only: bool = False,
) -> list[Book]:
    try:
        return list_books(
            db,
            offset=offset,
            limit=limit,
            query=q,
            title=title,
            author=author,
            isbn=isbn,
            available_only=available_only,
        )
    except (ValidationError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid ISBN search value",
        ) from exc


@router.get("/{book_id}", response_model=BookRead)
def read_book(
    book_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(get_current_user)],
) -> Book:
    return book_or_404(db, book_id)


@router.patch("/{book_id}", response_model=BookRead)
def update_book_record(
    book_id: UUID,
    data: BookUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(staff_required)],
) -> Book:
    try:
        return update_book(db, book_or_404(db, book_id), data)
    except IsbnAlreadyExistsError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A book with this ISBN already exists",
        ) from exc
    except InvalidInventoryReductionError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Total copies cannot be lower than the number of borrowed copies",
        ) from exc


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_book(
    book_id: UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(staff_required)],
) -> None:
    try:
        delete_book(db, book_or_404(db, book_id))
    except BookHasBorrowedCopiesError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A book with borrowed copies cannot be deleted",
        ) from exc
