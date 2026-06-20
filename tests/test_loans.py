from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.book import Book
from app.models.member import Member
from app.models.user import User, UserRole


def create_user(
    db: Session,
    *,
    email: str,
    password: str,
    role: UserRole,
) -> User:
    user = User(
        email=email,
        full_name="Test User",
        hashed_password=hash_password(password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login_headers(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def register_member(client: TestClient, headers: dict[str, str]) -> dict[str, object]:
    response = client.post(
        "/api/v1/members",
        headers=headers,
        json={
            "email": "member@example.com",
            "full_name": "Library Member",
            "password": "member-password",
            "phone_number": "+2348012345678",
            "address": "Kaduna, Nigeria",
        },
    )
    assert response.status_code == 201
    return response.json()


def add_book(
    client: TestClient,
    headers: dict[str, str],
    *,
    total_copies: int,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/books",
        headers=headers,
        json={
            "title": "Purple Hibiscus",
            "author": "Chimamanda Ngozi Adichie",
            "isbn": "9780007189885",
            "category": "Fiction",
            "total_copies": total_copies,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_issue_and_return_book_updates_inventory_and_history(
    client: TestClient,
    db: Session,
) -> None:
    create_user(
        db,
        email="librarian@example.com",
        password="librarian-password",
        role=UserRole.LIBRARIAN,
    )
    staff_headers = login_headers(client, "librarian@example.com", "librarian-password")
    member = register_member(client, staff_headers)
    book = add_book(client, staff_headers, total_copies=2)
    due_at = datetime.now(UTC) + timedelta(days=10)

    issue_response = client.post(
        "/api/v1/loans",
        headers=staff_headers,
        json={
            "member_id": member["id"],
            "book_id": book["id"],
            "due_at": due_at.isoformat(),
        },
    )
    assert issue_response.status_code == 201
    loan = issue_response.json()
    assert loan["status"] == "borrowed"
    assert loan["returned_at"] is None

    stored_book = db.get(Book, UUID(str(book["id"])))
    assert stored_book is not None
    db.refresh(stored_book)
    assert stored_book.available_copies == 1

    member_headers = login_headers(client, "member@example.com", "member-password")
    history_response = client.get(
        f"/api/v1/members/{member['id']}/borrowing-history",
        headers=member_headers,
    )
    assert history_response.status_code == 200
    assert history_response.json()["total"] == 1
    assert history_response.json()["items"][0]["book_title"] == "Purple Hibiscus"
    assert history_response.json()["items"][0]["status"] == "borrowed"

    return_response = client.post(
        f"/api/v1/loans/{loan['id']}/return",
        headers=staff_headers,
    )
    assert return_response.status_code == 200
    assert return_response.json()["status"] == "returned"
    assert return_response.json()["returned_at"] is not None

    db.refresh(stored_book)
    assert stored_book.available_copies == 2

    returned_history = client.get(
        f"/api/v1/members/{member['id']}/borrowing-history",
        headers=member_headers,
    )
    assert returned_history.json()["items"][0]["status"] == "returned"


def test_unavailable_book_cannot_be_borrowed(
    client: TestClient,
    db: Session,
) -> None:
    create_user(
        db,
        email="admin@example.com",
        password="admin-password",
        role=UserRole.ADMIN,
    )
    headers = login_headers(client, "admin@example.com", "admin-password")
    member = register_member(client, headers)
    book = add_book(client, headers, total_copies=0)

    response = client.post(
        "/api/v1/loans",
        headers=headers,
        json={"member_id": member["id"], "book_id": book["id"]},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Book is not available"


def test_same_loan_cannot_be_returned_twice(
    client: TestClient,
    db: Session,
) -> None:
    create_user(
        db,
        email="librarian@example.com",
        password="librarian-password",
        role=UserRole.LIBRARIAN,
    )
    headers = login_headers(client, "librarian@example.com", "librarian-password")
    member = register_member(client, headers)
    book = add_book(client, headers, total_copies=1)
    issue_response = client.post(
        "/api/v1/loans",
        headers=headers,
        json={"member_id": member["id"], "book_id": book["id"]},
    )
    loan_id = issue_response.json()["id"]

    assert client.post(f"/api/v1/loans/{loan_id}/return", headers=headers).status_code == 200
    second_return = client.post(f"/api/v1/loans/{loan_id}/return", headers=headers)
    assert second_return.status_code == 409


def test_inactive_member_cannot_borrow(
    client: TestClient,
    db: Session,
) -> None:
    create_user(
        db,
        email="admin@example.com",
        password="admin-password",
        role=UserRole.ADMIN,
    )
    headers = login_headers(client, "admin@example.com", "admin-password")
    member_data = register_member(client, headers)
    book = add_book(client, headers, total_copies=1)

    member = db.get(Member, UUID(str(member_data["id"])))
    assert member is not None
    member.is_active = False
    member.user.is_active = False
    db.commit()

    response = client.post(
        "/api/v1/loans",
        headers=headers,
        json={"member_id": member_data["id"], "book_id": book["id"]},
    )
    assert response.status_code == 409
    assert response.json()["detail"] == "Member account is inactive"


def test_member_cannot_issue_or_return_books(
    client: TestClient,
    db: Session,
) -> None:
    create_user(
        db,
        email="admin@example.com",
        password="admin-password",
        role=UserRole.ADMIN,
    )
    admin_headers = login_headers(client, "admin@example.com", "admin-password")
    member = register_member(client, admin_headers)
    book = add_book(client, admin_headers, total_copies=1)
    member_headers = login_headers(client, "member@example.com", "member-password")

    response = client.post(
        "/api/v1/loans",
        headers=member_headers,
        json={"member_id": member["id"], "book_id": book["id"]},
    )
    assert response.status_code == 403
