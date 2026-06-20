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


def add_book(
    client: TestClient,
    headers: dict[str, str],
    *,
    title: str = "Things Fall Apart",
    author: str = "Chinua Achebe",
    isbn: str = "978-0-385-47454-2",
    total_copies: int = 3,
) -> dict[str, object]:
    response = client.post(
        "/api/v1/books",
        headers=headers,
        json={
            "title": title,
            "author": author,
            "isbn": isbn,
            "category": "African Literature",
            "description": "A Nigerian literary classic.",
            "publication_year": 1958,
            "total_copies": total_copies,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_librarian_can_add_update_search_and_delete_books(
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

    book = add_book(client, headers)
    assert book["isbn"] == "9780385474542"
    assert book["available_copies"] == 3
    assert book["borrowed_copies"] == 0
    assert book["is_available"] is True

    update_response = client.patch(
        f"/api/v1/books/{book['id']}",
        headers=headers,
        json={"category": "Fiction", "total_copies": 5},
    )
    assert update_response.status_code == 200
    assert update_response.json()["category"] == "Fiction"
    assert update_response.json()["available_copies"] == 5

    title_search = client.get("/api/v1/books?title=things", headers=headers)
    assert title_search.status_code == 200
    assert len(title_search.json()) == 1

    author_search = client.get("/api/v1/books?q=achebe", headers=headers)
    assert author_search.status_code == 200
    assert len(author_search.json()) == 1

    isbn_search = client.get(
        "/api/v1/books?isbn=978-0-385-47454-2",
        headers=headers,
    )
    assert isbn_search.status_code == 200
    assert isbn_search.json()[0]["id"] == book["id"]

    delete_response = client.delete(f"/api/v1/books/{book['id']}", headers=headers)
    assert delete_response.status_code == 204
    assert client.get(f"/api/v1/books/{book['id']}", headers=headers).status_code == 404


def test_member_can_browse_but_cannot_modify_catalog(
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
    admin_headers = login_headers(client, "admin@example.com", "admin-password")
    member_headers = login_headers(client, "member@example.com", "member-password")
    book = add_book(client, admin_headers)

    list_response = client.get("/api/v1/books", headers=member_headers)
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    create_response = client.post(
        "/api/v1/books",
        headers=member_headers,
        json={
            "title": "No Longer at Ease",
            "author": "Chinua Achebe",
            "isbn": "9780385474559",
            "category": "Fiction",
            "total_copies": 1,
        },
    )
    assert create_response.status_code == 403

    delete_response = client.delete(f"/api/v1/books/{book['id']}", headers=member_headers)
    assert delete_response.status_code == 403


def test_duplicate_isbn_is_rejected(
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
    add_book(client, headers)

    duplicate_response = client.post(
        "/api/v1/books",
        headers=headers,
        json={
            "title": "Duplicate",
            "author": "Another Author",
            "isbn": "9780385474542",
            "category": "Fiction",
            "total_copies": 1,
        },
    )
    assert duplicate_response.status_code == 409


def test_inventory_cannot_be_reduced_below_borrowed_copies(
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
    created = add_book(client, headers, total_copies=3)

    book = db.get(Book, UUID(str(created["id"])))
    assert book is not None
    book.available_copies = 1
    db.commit()

    response = client.patch(
        f"/api/v1/books/{created['id']}",
        headers=headers,
        json={"total_copies": 1},
    )
    assert response.status_code == 409

    delete_response = client.delete(
        f"/api/v1/books/{created['id']}",
        headers=headers,
    )
    assert delete_response.status_code == 409


def test_available_only_filter(
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
    add_book(client, headers, total_copies=0)
    add_book(
        client,
        headers,
        title="Half of a Yellow Sun",
        author="Chimamanda Ngozi Adichie",
        isbn="9780007200283",
        total_copies=2,
    )

    response = client.get("/api/v1/books?available_only=true", headers=headers)
    assert response.status_code == 200
    assert len(response.json()) == 1
    assert response.json()[0]["title"] == "Half of a Yellow Sun"
