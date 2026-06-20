from datetime import UTC, date, datetime, timedelta
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
    headers: dict[str, str],
) -> dict[str, object]:
    response = client.post(
        "/api/v1/members",
        headers=headers,
        json={
            "email": "member@example.com",
            "full_name": "Report Member",
            "password": "member-password",
            "phone_number": "+2348012345678",
        },
    )
    assert response.status_code == 201
    return response.json()


def add_book(
    client: TestClient,
    headers: dict[str, str],
    *,
    title: str,
    isbn: str,
    copies: int,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/books",
        headers=headers,
        json={
            "title": title,
            "author": "Report Author",
            "isbn": isbn,
            "category": "Reports",
            "total_copies": copies,
        },
    )
    assert response.status_code == 201
    return response.json()


def issue_book(
    client: TestClient,
    headers: dict[str, str],
    member_id: object,
    book_id: object,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/loans",
        headers=headers,
        json={"member_id": member_id, "book_id": book_id},
    )
    assert response.status_code == 201
    return response.json()


def seed_report_data(
    client: TestClient,
    db: Session,
) -> tuple[dict[str, str], dict[str, object]]:
    create_user(
        db,
        email="librarian@example.com",
        password="librarian-password",
        role=UserRole.LIBRARIAN,
    )
    headers = login_headers(client, "librarian@example.com", "librarian-password")
    member = register_member(client, headers)
    active_book = add_book(
        client,
        headers,
        title="Active Loan Book",
        isbn="9789780000011",
        copies=1,
    )
    returned_book = add_book(
        client,
        headers,
        title="Returned Loan Book",
        isbn="9789780000028",
        copies=2,
    )
    unavailable_book = add_book(
        client,
        headers,
        title="Unavailable Inventory",
        isbn="9789780000035",
        copies=0,
    )

    active_loan_data = issue_book(
        client,
        headers,
        member["id"],
        active_book["id"],
    )
    active_loan = db.get(Loan, UUID(str(active_loan_data["id"])))
    assert active_loan is not None
    active_loan.due_at = datetime.now(UTC) - timedelta(days=2)

    returned_loan_data = issue_book(
        client,
        headers,
        member["id"],
        returned_book["id"],
    )
    returned_loan = db.get(Loan, UUID(str(returned_loan_data["id"])))
    assert returned_loan is not None
    returned_loan.due_at = datetime.now(UTC) - timedelta(days=1)
    db.commit()
    return_response = client.post(
        f"/api/v1/loans/{returned_loan.id}/return",
        headers=headers,
    )
    assert return_response.status_code == 200
    assert unavailable_book["available_copies"] == 0
    return headers, member


def test_borrowed_overdue_and_member_activity_reports(
    client: TestClient,
    db: Session,
) -> None:
    headers, member = seed_report_data(client, db)

    borrowed = client.get("/api/v1/reports/borrowed-books", headers=headers)
    assert borrowed.status_code == 200
    assert borrowed.json()["total_loans"] == 2
    assert borrowed.json()["active_loans"] == 1
    assert borrowed.json()["returned_loans"] == 1
    assert borrowed.json()["items"][0]["membership_id"] == member["membership_id"]

    active_only = client.get(
        "/api/v1/reports/borrowed-books?loan_status=borrowed",
        headers=headers,
    )
    assert active_only.status_code == 200
    assert active_only.json()["total_loans"] == 1

    overdue = client.get("/api/v1/reports/overdue-items", headers=headers)
    assert overdue.status_code == 200
    assert overdue.json()["total_overdue"] == 1
    assert overdue.json()["items"][0]["overdue_days"] >= 2

    activities = client.get("/api/v1/reports/member-activities", headers=headers)
    assert activities.status_code == 200
    item = activities.json()["items"][0]
    assert item["total_loans"] == 2
    assert item["active_loans"] == 1
    assert item["returned_loans"] == 1
    assert float(item["outstanding_fines"]) > 0


def test_fines_and_inventory_reports(
    client: TestClient,
    db: Session,
) -> None:
    headers, member = seed_report_data(client, db)

    fines = client.get(
        f"/api/v1/reports/fines?member_id={member['id']}",
        headers=headers,
    )
    assert fines.status_code == 200
    fine_report = fines.json()
    assert fine_report["total_fines"] == 1
    assert fine_report["outstanding_fines"] == 1
    assert float(fine_report["total_assessed"]) > 0
    assert fine_report["items"][0]["member_name"] == "Report Member"

    inventory = client.get(
        "/api/v1/reports/inventory?low_stock_threshold=1&category=Reports",
        headers=headers,
    )
    assert inventory.status_code == 200
    inventory_report = inventory.json()
    assert inventory_report["total_titles"] == 3
    assert inventory_report["total_copies"] == 3
    assert inventory_report["borrowed_copies"] == 1
    assert inventory_report["unavailable_titles"] == 2
    assert inventory_report["low_stock_titles"] == 2


def test_report_date_range_validation_and_member_denial(
    client: TestClient,
    db: Session,
) -> None:
    headers, _ = seed_report_data(client, db)
    invalid_range = client.get(
        "/api/v1/reports/borrowed-books"
        f"?date_from={date.today().isoformat()}"
        f"&date_to={(date.today() - timedelta(days=1)).isoformat()}",
        headers=headers,
    )
    assert invalid_range.status_code == 422

    member_headers = login_headers(client, "member@example.com", "member-password")
    forbidden = client.get("/api/v1/reports/inventory", headers=member_headers)
    assert forbidden.status_code == 403
