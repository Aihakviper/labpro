from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import hash_password
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
    *,
    email: str = "member@example.com",
) -> dict[str, object]:
    response = client.post(
        "/api/v1/members",
        headers=headers,
        json={
            "email": email,
            "full_name": "Registered Member",
            "password": "member-password",
            "phone_number": "+2348012345678",
            "address": "Kano, Nigeria",
        },
    )
    assert response.status_code == 201
    return response.json()


def test_librarian_can_register_update_and_list_members(
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
    assert str(member["membership_id"]).startswith("LP-")
    assert member["user"]["role"] == "member"
    assert member["is_active"] is True

    update_response = client.patch(
        f"/api/v1/members/{member['id']}",
        headers=headers,
        json={
            "full_name": "Updated Member",
            "phone_number": "+2348099999999",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["user"]["full_name"] == "Updated Member"
    assert update_response.json()["phone_number"] == "+2348099999999"

    list_response = client.get("/api/v1/members", headers=headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1


def test_member_can_view_own_profile_and_history_only(
    client: TestClient,
    db: Session,
) -> None:
    create_user(
        db,
        email="librarian@example.com",
        password="librarian-password",
        role=UserRole.LIBRARIAN,
    )
    librarian_headers = login_headers(
        client,
        "librarian@example.com",
        "librarian-password",
    )
    first_member = register_member(client, librarian_headers)
    second_member = register_member(
        client,
        librarian_headers,
        email="second@example.com",
    )

    member_headers = login_headers(client, "member@example.com", "member-password")
    own_profile = client.get("/api/v1/members/me", headers=member_headers)
    assert own_profile.status_code == 200
    assert own_profile.json()["id"] == first_member["id"]

    history = client.get(
        f"/api/v1/members/{first_member['id']}/borrowing-history",
        headers=member_headers,
    )
    assert history.status_code == 200
    assert history.json()["total"] == 0
    assert history.json()["items"] == []

    forbidden = client.get(
        f"/api/v1/members/{second_member['id']}",
        headers=member_headers,
    )
    assert forbidden.status_code == 403


def test_deactivation_revokes_member_access(
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
    member_headers = login_headers(client, "member@example.com", "member-password")

    deactivate_response = client.post(
        f"/api/v1/members/{member['id']}/deactivate",
        headers=admin_headers,
    )
    assert deactivate_response.status_code == 200
    assert deactivate_response.json()["is_active"] is False
    assert deactivate_response.json()["user"]["is_active"] is False

    profile_response = client.get("/api/v1/members/me", headers=member_headers)
    assert profile_response.status_code == 401

    login_response = client.post(
        "/api/v1/auth/login",
        data={"username": "member@example.com", "password": "member-password"},
    )
    assert login_response.status_code == 403


def test_generic_user_endpoint_rejects_member_role(
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

    response = client.post(
        "/api/v1/users",
        headers=headers,
        json={
            "email": "member@example.com",
            "full_name": "Member",
            "password": "member-password",
            "role": "member",
        },
    )

    assert response.status_code == 409
