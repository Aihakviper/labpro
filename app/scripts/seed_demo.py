from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.book import Book
from app.models.fine import FineConfig
from app.models.loan import Loan
from app.models.member import Member
from app.models.user import User, UserRole
from app.schemas.loan import LoanCreate
from app.schemas.member import MemberCreate
from app.services.fines import record_payment
from app.services.loans import issue_book, return_book
from app.services.members import register_member
from app.services.reservations import create_reservation

DEMO_PASSWORD = "DemoPassword123!"


def get_or_create_staff(
    db,
    *,
    email: str,
    full_name: str,
    role: UserRole,
) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user is not None:
        return user
    user = User(
        email=email,
        full_name=full_name,
        hashed_password=hash_password(DEMO_PASSWORD),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_or_create_member(
    db,
    *,
    email: str,
    full_name: str,
    phone_number: str,
    address: str,
) -> Member:
    user = db.scalar(select(User).where(User.email == email))
    if user is not None and user.member_profile is not None:
        return user.member_profile
    return register_member(
        db,
        MemberCreate(
            email=email,
            full_name=full_name,
            password=DEMO_PASSWORD,
            phone_number=phone_number,
            address=address,
        ),
    )


def get_or_create_book(
    db,
    *,
    title: str,
    author: str,
    isbn: str,
    category: str,
    publication_year: int,
    total_copies: int,
) -> Book:
    book = db.scalar(select(Book).where(Book.isbn == isbn))
    if book is not None:
        return book
    book = Book(
        title=title,
        author=author,
        isbn=isbn,
        category=category,
        publication_year=publication_year,
        total_copies=total_copies,
        available_copies=total_copies,
    )
    db.add(book)
    db.commit()
    db.refresh(book)
    return book


def main() -> None:
    with SessionLocal() as db:
        admin = get_or_create_staff(
            db,
            email="admin@librarianpro.ng",
            full_name="Amina Yusuf",
            role=UserRole.ADMIN,
        )
        librarian = get_or_create_staff(
            db,
            email="librarian@librarianpro.ng",
            full_name="Chinedu Okafor",
            role=UserRole.LIBRARIAN,
        )
        fatima = get_or_create_member(
            db,
            email="fatima.member@librarianpro.ng",
            full_name="Fatima Bello",
            phone_number="+2348031112233",
            address="Nassarawa GRA, Kano",
        )
        emeka = get_or_create_member(
            db,
            email="emeka.member@librarianpro.ng",
            full_name="Emeka Nwosu",
            phone_number="+2348064445566",
            address="GRA, Enugu",
        )
        zainab = get_or_create_member(
            db,
            email="zainab.member@librarianpro.ng",
            full_name="Zainab Musa",
            phone_number="+2348097778899",
            address="Wuse 2, Abuja",
        )

        books = [
            get_or_create_book(
                db,
                title="Things Fall Apart",
                author="Chinua Achebe",
                isbn="9780385474542",
                category="African Literature",
                publication_year=1958,
                total_copies=4,
            ),
            get_or_create_book(
                db,
                title="Half of a Yellow Sun",
                author="Chimamanda Ngozi Adichie",
                isbn="9780007200283",
                category="Historical Fiction",
                publication_year=2006,
                total_copies=3,
            ),
            get_or_create_book(
                db,
                title="The Famished Road",
                author="Ben Okri",
                isbn="9780385425131",
                category="Magical Realism",
                publication_year=1991,
                total_copies=1,
            ),
            get_or_create_book(
                db,
                title="The Joys of Motherhood",
                author="Buchi Emecheta",
                isbn="9780807616239",
                category="African Literature",
                publication_year=1979,
                total_copies=2,
            ),
            get_or_create_book(
                db,
                title="Stay With Me",
                author="Ayobami Adebayo",
                isbn="9780451494610",
                category="Contemporary Fiction",
                publication_year=2017,
                total_copies=2,
            ),
            get_or_create_book(
                db,
                title="Born on a Tuesday",
                author="Elnathan John",
                isbn="9780802124821",
                category="Political Fiction",
                publication_year=2015,
                total_copies=2,
            ),
        ]

        config = db.get(FineConfig, 1)
        if config is None:
            db.add(FineConfig(id=1, daily_rate=Decimal("100.00")))
            db.commit()

        existing_loans = list(db.scalars(select(Loan)))
        if not existing_loans:
            active_loan = issue_book(
                db,
                LoanCreate(member_id=fatima.id, book_id=books[0].id),
                librarian,
            )
            active_loan.due_at = datetime.now(UTC) + timedelta(days=7)
            db.commit()

            overdue_loan = issue_book(
                db,
                LoanCreate(member_id=emeka.id, book_id=books[2].id),
                librarian,
            )
            overdue_loan.due_at = datetime.now(UTC) - timedelta(days=4)
            db.commit()

            returned_loan = issue_book(
                db,
                LoanCreate(member_id=zainab.id, book_id=books[3].id),
                librarian,
            )
            returned_loan.due_at = datetime.now(UTC) - timedelta(days=2)
            db.commit()
            returned = return_book(db, returned_loan.id, librarian)
            db.refresh(returned)
            if returned.fine is not None:
                record_payment(db, returned.fine.id, Decimal("100.00"), admin)

            create_reservation(db, fatima, books[2].id)

    print("Demo data ready.")
    print("Admin: admin@librarianpro.ng / DemoPassword123!")
    print("Librarian: librarian@librarianpro.ng / DemoPassword123!")
    print("Member: fatima.member@librarianpro.ng / DemoPassword123!")


if __name__ == "__main__":
    main()
