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

There are no tests or linters configured yet. If you add tests, use pytest via `uv add --dev pytest` and run with `uv run pytest`.

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

Everything lives in `main.py` — a single FastAPI app with two kinds of routes:

- **Frontend**: `GET /` renders `templates/index.html` (Jinja2), which loads `static/style.css` and calls the API with inline fetch JS. Static files are mounted at `/static`.
- **API**: JSON endpoints under `/api/*` (`/api/health`, `/api/echo`), request bodies validated with Pydantic models. Swagger UI is auto-served at `/docs`.

Configuration comes from `.env` via a pydantic-settings `Settings` class in `main.py` (`.env` is gitignored; `.env.example` documents the expected keys — keep it in sync when adding settings). Settings load once at import, so `--reload` does not pick up `.env` edits — restart the server for those.

**Database**: SQLite via SQLModel (`DATABASE_URL` in `.env`). Models are SQLModel classes with `table=True`; tables are created at startup by the lifespan hook (`create_all` — no migrations, so schema changes to an existing `data.db` require deleting the file or adding Alembic). Endpoints get a session through the `SessionDep` dependency. The `data.db` file is gitignored. See the `Item` CRUD under `/api/items` as the pattern to copy.

When adding features, follow this split: page routes render templates, data routes go under `/api/` with Pydantic schemas. Split `main.py` into routers only if it grows large.
