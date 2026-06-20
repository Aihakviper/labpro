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


def login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()


def test_login_refresh_and_logout_revoke_session(
    client: TestClient,
    db: Session,
) -> None:
    create_user(
        db,
        email="member@example.com",
        password="member-password",
        role=UserRole.MEMBER,
    )

    tokens = login(client, "member@example.com", "member-password")
    access_headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    me_response = client.get("/api/v1/auth/me", headers=access_headers)
    assert me_response.status_code == 200
    assert me_response.json()["role"] == "member"

    refresh_response = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    )
    assert refresh_response.status_code == 200
    refreshed_tokens = refresh_response.json()

    old_access_response = client.get("/api/v1/auth/me", headers=access_headers)
    assert old_access_response.status_code == 401

    logout_response = client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refreshed_tokens["refresh_token"]},
    )
    assert logout_response.status_code == 204

    logged_out_headers = {
        "Authorization": f"Bearer {refreshed_tokens['access_token']}",
    }
    logged_out_response = client.get("/api/v1/auth/me", headers=logged_out_headers)
    assert logged_out_response.status_code == 401


def test_admin_can_create_user_but_member_cannot(
    client: TestClient,
    db: Session,
) -> None:
    create_user(
        db,
        email="admin@example.com",
        password="admin-password",
        role=UserRole.ADMIN,
    )
    create_user(
        db,
        email="member@example.com",
        password="member-password",
        role=UserRole.MEMBER,
    )

    admin_tokens = login(client, "admin@example.com", "admin-password")
    admin_headers = {"Authorization": f"Bearer {admin_tokens['access_token']}"}
    create_response = client.post(
        "/api/v1/users",
        headers=admin_headers,
        json={
            "email": "librarian@example.com",
            "full_name": "Library Staff",
            "password": "librarian-password",
            "role": "librarian",
        },
    )
    assert create_response.status_code == 201
    assert create_response.json()["role"] == "librarian"
    assert "hashed_password" not in create_response.json()

    member_tokens = login(client, "member@example.com", "member-password")
    member_headers = {"Authorization": f"Bearer {member_tokens['access_token']}"}
    forbidden_response = client.get("/api/v1/users", headers=member_headers)
    assert forbidden_response.status_code == 403


def test_last_active_admin_cannot_be_deactivated(
    client: TestClient,
    db: Session,
) -> None:
    admin = create_user(
        db,
        email="admin@example.com",
        password="admin-password",
        role=UserRole.ADMIN,
    )
    tokens = login(client, "admin@example.com", "admin-password")

    response = client.patch(
        f"/api/v1/users/{admin.id}",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
        json={"is_active": False},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "The last active administrator cannot be deactivated or demoted"
    )


def test_change_password_revokes_existing_session(
    client: TestClient,
    db: Session,
) -> None:
    create_user(
        db,
        email="member@example.com",
        password="member-password",
        role=UserRole.MEMBER,
    )
    tokens = login(client, "member@example.com", "member-password")
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}

    response = client.post(
        "/api/v1/auth/change-password",
        headers=headers,
        json={
            "current_password": "member-password",
            "new_password": "new-member-password",
        },
    )
    assert response.status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401

    login(client, "member@example.com", "new-member-password")
