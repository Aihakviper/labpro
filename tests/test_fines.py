from datetime import UTC, datetime, timedelta
from decimal import Decimal
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


def register_member(client: TestClient, headers: dict[str, str]) -> dict[str, object]:
    response = client.post(
        "/api/v1/members",
        headers=headers,
        json={
            "email": "member@example.com",
            "full_name": "Library Member",
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
            "title": "The Joys of Motherhood",
            "author": "Buchi Emecheta",
            "isbn": "9780807616239",
            "category": "Fiction",
            "total_copies": 1,
        },
    )
    assert response.status_code == 201
    return response.json()


def create_overdue_fine(
    client: TestClient,
    db: Session,
    headers: dict[str, str],
    member_id: object,
    book_id: object,
    *,
    overdue_days: int,
) -> dict[str, object]:
    issue_response = client.post(
        "/api/v1/loans",
        headers=headers,
        json={"member_id": member_id, "book_id": book_id},
    )
    assert issue_response.status_code == 201
    loan_id = issue_response.json()["id"]

    loan = db.get(Loan, UUID(loan_id))
    assert loan is not None
    loan.due_at = datetime.now(UTC) - timedelta(days=overdue_days)
    db.commit()

    return_response = client.post(f"/api/v1/loans/{loan_id}/return", headers=headers)
    assert return_response.status_code == 200

    fines_response = client.get(
        f"/api/v1/fines?member_id={member_id}",
        headers=headers,
    )
    assert fines_response.status_code == 200
    assert len(fines_response.json()) == 1
    return fines_response.json()[0]


def test_overdue_return_calculates_fine_using_configured_rate(
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
    book = add_book(client, headers)

    config_response = client.patch(
        "/api/v1/fines/config",
        headers=headers,
        json={"daily_rate": "150.00"},
    )
    assert config_response.status_code == 200
    assert Decimal(config_response.json()["daily_rate"]) == Decimal("150.00")

    fine = create_overdue_fine(
        client,
        db,
        headers,
        member["id"],
        book["id"],
        overdue_days=3,
    )
    assert fine["overdue_days"] == 3
    assert Decimal(str(fine["daily_rate"])) == Decimal("150.00")
    assert Decimal(str(fine["amount"])) == Decimal("450.00")
    assert fine["status"] == "outstanding"


def test_partial_and_full_payments_update_outstanding_balance(
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
    book = add_book(client, headers)
    fine = create_overdue_fine(
        client,
        db,
        headers,
        member["id"],
        book["id"],
        overdue_days=2,
    )

    partial_response = client.post(
        f"/api/v1/fines/{fine['id']}/payments",
        headers=headers,
        json={"amount": "50.00"},
    )
    assert partial_response.status_code == 200
    partial = partial_response.json()
    assert partial["status"] == "outstanding"
    assert Decimal(str(partial["amount_paid"])) == Decimal("50.00")
    assert len(partial["payments"]) == 1

    remaining = Decimal(str(partial["outstanding_amount"]))
    full_response = client.post(
        f"/api/v1/fines/{fine['id']}/payments",
        headers=headers,
        json={"amount": str(remaining)},
    )
    assert full_response.status_code == 200
    paid = full_response.json()
    assert paid["status"] == "paid"
    assert Decimal(str(paid["outstanding_amount"])) == Decimal("0.00")
    assert paid["paid_at"] is not None
    assert len(paid["payments"]) == 2


def test_payment_cannot_exceed_outstanding_balance(
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
    book = add_book(client, headers)
    fine = create_overdue_fine(
        client,
        db,
        headers,
        member["id"],
        book["id"],
        overdue_days=1,
    )

    response = client.post(
        f"/api/v1/fines/{fine['id']}/payments",
        headers=headers,
        json={"amount": "999999.00"},
    )
    assert response.status_code == 409


def test_member_can_view_only_own_fines(
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
    book = add_book(client, admin_headers)
    fine = create_overdue_fine(
        client,
        db,
        admin_headers,
        member["id"],
        book["id"],
        overdue_days=1,
    )

    member_headers = login_headers(client, "member@example.com", "member-password")
    own_fines = client.get(
        "/api/v1/fines/me?outstanding_only=true",
        headers=member_headers,
    )
    assert own_fines.status_code == 200
    assert own_fines.json()[0]["id"] == fine["id"]

    member_config_update = client.patch(
        "/api/v1/fines/config",
        headers=member_headers,
        json={"daily_rate": "10.00"},
    )
    assert member_config_update.status_code == 403


def test_on_time_return_does_not_create_fine(
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
    book = add_book(client, headers)
    issue_response = client.post(
        "/api/v1/loans",
        headers=headers,
        json={"member_id": member["id"], "book_id": book["id"]},
    )
    loan_id = issue_response.json()["id"]

    assert client.post(f"/api/v1/loans/{loan_id}/return", headers=headers).status_code == 200
    fines_response = client.get("/api/v1/fines", headers=headers)
    assert fines_response.status_code == 200
    assert fines_response.json() == []
