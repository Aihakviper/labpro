# Librarian Pro API

Backend foundation and Phase 1 authentication for Librarian Pro. It includes:

- FastAPI application structure
- PostgreSQL and SQLAlchemy 2
- Alembic migrations
- JWT access and refresh tokens with server-side revocation
- Role-ready user model (`admin`, `librarian`, `member`)
- Administrator-managed user accounts
- Reusable role-based authorization dependencies
- Secure logout, refresh rotation, and password changes
- Docker Compose development environment
- Liveness and database-readiness endpoints

Catalog, member management, loans, fines, reservations, and reports are intentionally
outside this phase.

## Run with Docker

1. Create the local environment file:

   ```powershell
   Copy-Item .env.example .env
   ```

2. Replace the placeholder passwords and JWT secret in `.env`.

3. Start the API and database:

   ```powershell
   docker compose up --build
   ```

4. Create the initial administrator in another terminal:

   ```powershell
   docker compose exec api python -m app.scripts.create_admin `
     --email admin@example.com `
     --name "System Administrator"
   ```

The API documentation is available at `http://localhost:8000/docs`.

## Authentication

`POST /api/v1/auth/login` uses OAuth2 form fields:

- `username`: the user's email address
- `password`: the user's password

The response contains an access token and refresh token.

Available endpoints:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/change-password`

Refresh tokens are rotated. Refresh, logout, password changes, account deactivation,
and role changes revoke the affected session immediately.

## User and role administration

Only active administrators can access:

- `POST /api/v1/users`
- `GET /api/v1/users`
- `GET /api/v1/users/{user_id}`
- `PATCH /api/v1/users/{user_id}`

The API prevents deactivating or demoting the last active administrator.

## Member management

Administrators and librarians can register and manage members:

- `POST /api/v1/members`
- `GET /api/v1/members`
- `GET /api/v1/members/{member_id}`
- `PATCH /api/v1/members/{member_id}`
- `POST /api/v1/members/{member_id}/deactivate`
- `GET /api/v1/members/{member_id}/borrowing-history`

Members can access their own profile through `GET /api/v1/members/me` and can view only
their own borrowing history. Member deactivation disables login and revokes active sessions.

Borrowing-history responses are currently empty because loans are intentionally deferred to
the borrowing and returning phase.

## Health checks

- `GET /health/live`: confirms that the API process is running.
- `GET /health/ready`: confirms that the API can reach PostgreSQL.

## Local development without Docker

Python 3.12+ and a running PostgreSQL instance are required.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
alembic upgrade head
uvicorn app.main:app --reload
```

Run checks:

```powershell
ruff check .
pytest
```

Create new migrations after model changes:

```powershell
alembic revision --autogenerate -m "describe change"
alembic upgrade head
```
