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
The Librarian Pro dashboard is available at `http://localhost:8000/`.

Production deployments:

- Frontend: `https://labpro-seven.vercel.app`
- Backend: `https://librarian-pro-api.onrender.com`

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

## Book catalog

All authenticated users can browse the catalog and search by title, author, or ISBN:

- `GET /api/v1/books`
- `GET /api/v1/books/{book_id}`

Supported list filters include `q`, `title`, `author`, `isbn`, and `available_only`.

Administrators and librarians can manage catalog records:

- `POST /api/v1/books`
- `PATCH /api/v1/books/{book_id}`
- `DELETE /api/v1/books/{book_id}`

Availability is calculated from `total_copies` and `available_copies`. Books with borrowed
copies cannot be deleted, and total stock cannot be reduced below borrowed stock.

## Borrowing and returning

Administrators and librarians manage loans:

- `POST /api/v1/loans`
- `GET /api/v1/loans`
- `GET /api/v1/loans/{loan_id}`
- `POST /api/v1/loans/{loan_id}/return`

Issuing a book records the borrow and due dates and atomically reduces available copies.
Returning records the return date and restores one available copy. Inactive members,
unavailable books, expired due dates, duplicate returns, and members above the configured
active-loan limit are rejected.

## Fine management

Overdue fines are calculated automatically when a book is returned. The fine snapshots the
daily rate used at calculation time, so later configuration changes do not alter history.

- `GET /api/v1/fines`
- `GET /api/v1/fines/me`
- `GET /api/v1/fines/{fine_id}`
- `POST /api/v1/fines/{fine_id}/payments`
- `GET /api/v1/fines/config`
- `PATCH /api/v1/fines/config`

Administrators configure the daily rate. Administrators and librarians record partial or full
payments and can filter outstanding fines. Members can view only their own fines.

## Reservations

Active members can reserve books only when no copies are available. Reservations follow a
FIFO queue:

```text
waiting → ready → fulfilled
```

Members may cancel waiting or ready reservations. When a ready reservation is cancelled, the
held copy is transferred to the next waiting member or returned to general availability.

- `POST /api/v1/reservations`
- `GET /api/v1/reservations/me`
- `GET /api/v1/reservations/{reservation_id}`
- `PATCH /api/v1/reservations/{reservation_id}`
- `DELETE /api/v1/reservations/{reservation_id}`
- `GET /api/v1/reservations` — staff queue management

## Notifications

Members receive persistent in-app notifications for:

- successful book issue and return
- overdue loans
- reservation creation, readiness, and cancellation
- fine assessment and fine payments

Member endpoints:

- `GET /api/v1/notifications`
- `GET /api/v1/notifications/unread-count`
- `POST /api/v1/notifications/{notification_id}/read`
- `POST /api/v1/notifications/read-all`

Staff can run `POST /api/v1/notifications/process-overdue`. This endpoint is idempotent per
loan and calendar day and can later be called by a cron job or task scheduler.

## Reporting and analytics

Administrators and librarians can generate live JSON reports:

- `GET /api/v1/reports/borrowed-books`
- `GET /api/v1/reports/overdue-items`
- `GET /api/v1/reports/member-activities`
- `GET /api/v1/reports/fines`
- `GET /api/v1/reports/inventory`

Reports include aggregate totals and detailed rows. Loan, member-activity, and fine reports
support date ranges. Inventory supports category and low-stock filtering.

## Frontend

The responsive frontend is served directly by FastAPI and uses HTML, local CSS, vanilla
JavaScript, and Bootstrap. It includes:

- login and role-aware navigation
- administrator/librarian and member dashboards
- book, member, loan, fine, reservation, user, notification, and report pages
- issue, return, payment, cancellation, and reporting workflows

No Node.js build step is required.

The frontend automatically uses `/api/v1` on localhost and
`https://librarian-pro-api.onrender.com/api/v1` on deployed hosts.

Render must define:

```env
BACKEND_CORS_ORIGINS=["https://labpro-seven.vercel.app"]
```

## Demo data and browser acceptance testing

After applying migrations, populate a realistic Nigerian demo dataset:

```powershell
python -m app.scripts.seed_demo
```

Demo accounts share the password `DemoPassword123!`:

- `admin@librarianpro.ng`
- `librarian@librarianpro.ng`
- `fatima.member@librarianpro.ng`

The seed command is safe to rerun. Browser acceptance checks use installed Chrome:

```powershell
npm.cmd install --no-save --no-package-lock playwright-core
node tests\acceptance_ui.mjs
```

Acceptance screenshots are written to `.local/acceptance/`.

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
