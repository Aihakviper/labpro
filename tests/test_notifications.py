from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models.loan import Loan
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
    email: str = "member@example.com",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/members",
        headers=staff_headers,
        json={
            "email": email,
            "full_name": "Library Member",
            "password": "member-password",
            "phone_number": "+2348012345678",
        },
    )
    assert response.status_code == 201
    return response.json()


def add_book(
    client: TestClient,
    staff_headers: dict[str, str],
    *,
    isbn: str = "9789780266707",
    title: str = "The Famished Road",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/books",
        headers=staff_headers,
        json={
            "title": title,
            "author": "Ben Okri",
            "isbn": isbn,
            "category": "Fiction",
            "total_copies": 1,
        },
    )
    assert response.status_code == 201
    return response.json()


def issue_book(
    client: TestClient,
    staff_headers: dict[str, str],
    member_id: object,
    book_id: object,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/loans",
        headers=staff_headers,
        json={"member_id": member_id, "book_id": book_id},
    )
    assert response.status_code == 201
    return response.json()


def notification_types(
    client: TestClient,
    member_headers: dict[str, str],
) -> list[str]:
    response = client.get("/api/v1/notifications", headers=member_headers)
    assert response.status_code == 200
    return [item["type"] for item in response.json()]


def test_successful_loan_transactions_create_readable_notifications(
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
    book = add_book(client, staff_headers)
    loan = issue_book(client, staff_headers, member["id"], book["id"])
    member_headers = login_headers(client, "member@example.com", "member-password")

    assert "loan_issued" in notification_types(client, member_headers)

    return_response = client.post(
        f"/api/v1/loans/{loan['id']}/return",
        headers=staff_headers,
    )
    assert return_response.status_code == 200
    assert "loan_returned" in notification_types(client, member_headers)

    unread_response = client.get(
        "/api/v1/notifications/unread-count",
        headers=member_headers,
    )
    assert unread_response.status_code == 200
    assert unread_response.json()["count"] == 2

    notifications = client.get(
        "/api/v1/notifications",
        headers=member_headers,
    ).json()
    mark_response = client.post(
        f"/api/v1/notifications/{notifications[0]['id']}/read",
        headers=member_headers,
    )
    assert mark_response.status_code == 200
    assert mark_response.json()["is_read"] is True

    assert client.post(
        "/api/v1/notifications/read-all",
        headers=member_headers,
    ).status_code == 204
    assert client.get(
        "/api/v1/notifications/unread-count",
        headers=member_headers,
    ).json()["count"] == 0


def test_reservation_created_and_ready_notifications(
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
    waiting_member = register_member(client, staff_headers)
    book = add_book(client, staff_headers)
    loan = issue_book(client, staff_headers, borrower["id"], book["id"])
    member_headers = login_headers(client, "member@example.com", "member-password")

    reservation_response = client.post(
        "/api/v1/reservations",
        headers=member_headers,
        json={"book_id": book["id"]},
    )
    assert reservation_response.status_code == 201
    assert "reservation_created" in notification_types(client, member_headers)

    client.post(f"/api/v1/loans/{loan['id']}/return", headers=staff_headers)
    types = notification_types(client, member_headers)
    assert "reservation_ready" in types
    assert waiting_member["id"] == reservation_response.json()["member_id"]


def test_overdue_processing_is_idempotent_per_day(
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
    book = add_book(client, staff_headers)
    loan_data = issue_book(client, staff_headers, member["id"], book["id"])

    loan = db.get(Loan, UUID(str(loan_data["id"])))
    assert loan is not None
    loan.due_at = datetime.now(UTC) - timedelta(days=2)
    db.commit()

    first_process = client.post(
        "/api/v1/notifications/process-overdue",
        headers=staff_headers,
    )
    second_process = client.post(
        "/api/v1/notifications/process-overdue",
        headers=staff_headers,
    )
    assert first_process.status_code == 200
    assert first_process.json()["created"] == 1
    assert second_process.json()["created"] == 0

    member_headers = login_headers(client, "member@example.com", "member-password")
    types = notification_types(client, member_headers)
    assert types.count("loan_overdue") == 1


def test_fine_assessment_and_payment_create_notifications(
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
    member = register_member(client, staff_headers)
    book = add_book(client, staff_headers)
    loan_data = issue_book(client, staff_headers, member["id"], book["id"])

    loan = db.get(Loan, UUID(str(loan_data["id"])))
    assert loan is not None
    loan.due_at = datetime.now(UTC) - timedelta(days=1)
    db.commit()
    client.post(f"/api/v1/loans/{loan.id}/return", headers=staff_headers)

    fines_response = client.get("/api/v1/fines", headers=staff_headers)
    fine = fines_response.json()[0]
    payment_response = client.post(
        f"/api/v1/fines/{fine['id']}/payments",
        headers=staff_headers,
        json={"amount": fine["outstanding_amount"]},
    )
    assert payment_response.status_code == 200

    member_headers = login_headers(client, "member@example.com", "member-password")
    types = notification_types(client, member_headers)
    assert "fine_assessed" in types
    assert "fine_payment" in types


def test_staff_account_cannot_read_member_notification_feed(
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
    response = client.get("/api/v1/notifications", headers=headers)
    assert response.status_code == 403
