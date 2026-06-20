from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.book import Book
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


def register_member(
    client: TestClient,
    staff_headers: dict[str, str],
    *,
    email: str,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/members",
        headers=staff_headers,
        json={
            "email": email,
            "full_name": email.split("@")[0].title(),
            "password": "member-password",
            "phone_number": "+2348012345678",
        },
    )
    assert response.status_code == 201
    return response.json()


def add_book(client: TestClient, headers: dict[str, str]) -> dict[str, object]:
    response = client.post(
        "/api/v1/books",
        headers=headers,
        json={
            "title": "Arrow of God",
            "author": "Chinua Achebe",
            "isbn": "9780385014809",
            "category": "Fiction",
            "total_copies": 1,
        },
    )
    assert response.status_code == 201
    return response.json()


def reserve(
    client: TestClient,
    member_headers: dict[str, str],
    book_id: object,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/reservations",
        headers=member_headers,
        json={"book_id": book_id},
    )
    assert response.status_code == 201
    return response.json()


def test_fifo_queue_promotes_and_fulfills_ready_reservation(
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
    borrower = register_member(client, staff_headers, email="borrower@example.com")
    first = register_member(client, staff_headers, email="first@example.com")
    second = register_member(client, staff_headers, email="second@example.com")
    book = add_book(client, staff_headers)

    issue_response = client.post(
        "/api/v1/loans",
        headers=staff_headers,
        json={"member_id": borrower["id"], "book_id": book["id"]},
    )
    assert issue_response.status_code == 201
    loan_id = issue_response.json()["id"]

    first_headers = login_headers(client, "first@example.com", "member-password")
    second_headers = login_headers(client, "second@example.com", "member-password")
    first_reservation = reserve(client, first_headers, book["id"])
    second_reservation = reserve(client, second_headers, book["id"])
    assert first_reservation["queue_position"] == 1
    assert second_reservation["queue_position"] == 2

    return_response = client.post(
        f"/api/v1/loans/{loan_id}/return",
        headers=staff_headers,
    )
    assert return_response.status_code == 200

    queue_response = client.get(
        f"/api/v1/reservations?book_id={book['id']}",
        headers=staff_headers,
    )
    queue = queue_response.json()
    assert queue[0]["status"] == "ready"
    assert queue[0]["member_id"] == first["id"]
    assert queue[0]["queue_position"] == 0
    assert queue[1]["status"] == "waiting"
    assert queue[1]["member_id"] == second["id"]
    assert queue[1]["queue_position"] == 1

    stored_book = db.get(Book, UUID(str(book["id"])))
    assert stored_book is not None
    db.refresh(stored_book)
    assert stored_book.available_copies == 0

    fulfill_response = client.post(
        "/api/v1/loans",
        headers=staff_headers,
        json={"member_id": first["id"], "book_id": book["id"]},
    )
    assert fulfill_response.status_code == 201

    first_state = client.get(
        f"/api/v1/reservations/{first_reservation['id']}",
        headers=first_headers,
    )
    assert first_state.json()["status"] == "fulfilled"
    assert first_state.json()["fulfilled_at"] is not None
    db.refresh(stored_book)
    assert stored_book.available_copies == 0


def test_cancelling_ready_reservation_promotes_next_member(
    client: TestClient,
    db: Session,
) -> None:
    create_user(
        db,
        email="admin@example.com",
        password="admin-password",
        role=UserRole.ADMIN,
    )
    staff_headers = login_headers(client, "admin@example.com", "admin-password")
    borrower = register_member(client, staff_headers, email="borrower@example.com")
    register_member(client, staff_headers, email="first@example.com")
    register_member(client, staff_headers, email="second@example.com")
    book = add_book(client, staff_headers)
    loan = client.post(
        "/api/v1/loans",
        headers=staff_headers,
        json={"member_id": borrower["id"], "book_id": book["id"]},
    ).json()

    first_headers = login_headers(client, "first@example.com", "member-password")
    second_headers = login_headers(client, "second@example.com", "member-password")
    first_reservation = reserve(client, first_headers, book["id"])
    second_reservation = reserve(client, second_headers, book["id"])
    client.post(f"/api/v1/loans/{loan['id']}/return", headers=staff_headers)

    cancel_response = client.delete(
        f"/api/v1/reservations/{first_reservation['id']}",
        headers=first_headers,
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "cancelled"

    second_state = client.get(
        f"/api/v1/reservations/{second_reservation['id']}",
        headers=second_headers,
    )
    assert second_state.status_code == 200
    assert second_state.json()["status"] == "ready"
    assert second_state.json()["queue_position"] == 0


def test_available_book_and_duplicate_reservation_are_rejected(
    client: TestClient,
    db: Session,
) -> None:
    create_user(
        db,
        email="admin@example.com",
        password="admin-password",
        role=UserRole.ADMIN,
    )
    staff_headers = login_headers(client, "admin@example.com", "admin-password")
    borrower = register_member(client, staff_headers, email="borrower@example.com")
    register_member(client, staff_headers, email="member@example.com")
    book = add_book(client, staff_headers)
    member_headers = login_headers(client, "member@example.com", "member-password")

    available_response = client.post(
        "/api/v1/reservations",
        headers=member_headers,
        json={"book_id": book["id"]},
    )
    assert available_response.status_code == 409

    client.post(
        "/api/v1/loans",
        headers=staff_headers,
        json={"member_id": borrower["id"], "book_id": book["id"]},
    )
    reserve(client, member_headers, book["id"])
    duplicate_response = client.post(
        "/api/v1/reservations",
        headers=member_headers,
        json={"book_id": book["id"]},
    )
    assert duplicate_response.status_code == 409


def test_member_sees_only_own_reservations_and_cannot_force_ready_status(
    client: TestClient,
    db: Session,
) -> None:
    create_user(
        db,
        email="admin@example.com",
        password="admin-password",
        role=UserRole.ADMIN,
    )
    staff_headers = login_headers(client, "admin@example.com", "admin-password")
    borrower = register_member(client, staff_headers, email="borrower@example.com")
    register_member(client, staff_headers, email="first@example.com")
    register_member(client, staff_headers, email="second@example.com")
    book = add_book(client, staff_headers)
    client.post(
        "/api/v1/loans",
        headers=staff_headers,
        json={"member_id": borrower["id"], "book_id": book["id"]},
    )

    first_headers = login_headers(client, "first@example.com", "member-password")
    second_headers = login_headers(client, "second@example.com", "member-password")
    first_reservation = reserve(client, first_headers, book["id"])
    second_reservation = reserve(client, second_headers, book["id"])

    own_response = client.get("/api/v1/reservations/me", headers=first_headers)
    assert own_response.status_code == 200
    assert len(own_response.json()) == 1
    assert own_response.json()[0]["id"] == first_reservation["id"]

    forbidden = client.get(
        f"/api/v1/reservations/{second_reservation['id']}",
        headers=first_headers,
    )
    assert forbidden.status_code == 403

    forced_status = client.patch(
        f"/api/v1/reservations/{first_reservation['id']}",
        headers=first_headers,
        json={"status": "ready"},
    )
    assert forced_status.status_code == 409
