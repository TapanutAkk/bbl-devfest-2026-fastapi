# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

FastAPI app for a BBL Dev Fest 2026 live test. Serves both a Jinja2-rendered frontend and a JSON API from a single app — the test task may require either or both, so keep both paths working.

## Commands

Dependencies are managed with **uv** (not pip/poetry). Python 3.12 is pinned via `.python-version`; the system Python is 3.9 — always run through `uv run`.

```bash
uv run uvicorn main:app --reload   # run dev server at http://127.0.0.1:8000
uv add <package>                   # add a dependency
uv sync                            # install deps from lockfile
```

If `uv` is not on PATH, it lives at `~/.local/bin/uv`.

Tests live in `tests/` (pytest + TestClient); run with `uv run pytest`. No linters are configured.

## Commits

Use Conventional Commits: `<type>: <description>` — description in imperative mood, lowercase, no trailing period (e.g. `feat: add appointment booking with auth`).

Types:

- `feat:` — new feature or endpoint
- `fix:` — bug fix
- `refactor:` — code change that neither fixes a bug nor adds a feature
- `test:` — add or update tests
- `docs:` — documentation only (README, CLAUDE.md)
- `style:` — CSS/template tweaks with no logic change
- `chore:` — dependencies, config, tooling

## Architecture

A single FastAPI app split into modules:

- `main.py` — app assembly only: lifespan (create_all + seed data), static mount, router includes. `uvicorn main:app` is the entrypoint.
- `config.py` — pydantic-settings `Settings` + `BASE_DIR`.
- `database.py` — SQLModel models (`Item`, `User`, `Booking`), engine, `SessionDep`, shared query helpers.
- `auth.py` — PBKDF2 password hashing, in-memory session-token store (`auth_sessions`), `OptionalUser`/`CurrentUser` dependencies (token from Bearer header or `session_token` cookie).
- `routers/web.py` — frontend router: Jinja2 pages + htmx fragments (login, bookings). `render_page` returns a partial for htmx requests, the full `index.html` otherwise.
- `routers/api.py` — JSON router with prefix `/api` (health, echo, items CRUD, login/logout/me, bookings). Request bodies validated with Pydantic models; Swagger UI is auto-served at `/docs`.

**Authorization rule**: admins see/edit/delete all bookings; regular users only their own — enforced via `visible_bookings` and ownership checks, in both routers.

Configuration comes from `.env` via a pydantic-settings `Settings` class in `config.py` (`.env` is gitignored; `.env.example` documents the expected keys — keep it in sync when adding settings). Settings load once at import, so `--reload` does not pick up `.env` edits — restart the server for those.

**Database**: SQLite via SQLModel (`DATABASE_URL` in `.env`). Models are SQLModel classes with `table=True`; tables are created at startup by the lifespan hook (`create_all` — no migrations, so schema changes to an existing `data.db` require deleting the file or adding Alembic). Endpoints get a session through the `SessionDep` dependency. The `data.db` file is gitignored. See the `Item` CRUD under `/api/items` as the pattern to copy.

**Seed data**: `SEED_USERS` and `SEED_BOOKINGS` in `main.py`, inserted by the lifespan hook only when the user table is empty. To re-seed, delete `data.db` and restart the server. Login credentials for manual testing: `admin/admin123` (admin), `alice/alice123`, `bob/bob123`.

**Tests**: `tests/conftest.py` points `DATABASE_URL` at a throwaway temp file *before* importing `main` (settings load once at import), so tests never touch `data.db`. The `client` fixture wipes bookings before each test.

When adding features, follow this split: page routes and htmx fragments go in `routers/web.py`, data routes go in `routers/api.py` under `/api/` with Pydantic schemas.
