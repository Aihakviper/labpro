# Librarian Pro API

Phase 0 backend foundation for Librarian Pro. It includes:

- FastAPI application structure
- PostgreSQL and SQLAlchemy 2
- Alembic migrations
- JWT access-token authentication
- Role-ready user model (`admin`, `librarian`, `member`)
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

Use the returned bearer token with `GET /api/v1/auth/me`.

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
