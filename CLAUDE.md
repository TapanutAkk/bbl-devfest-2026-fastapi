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

## Architecture

Everything lives in `main.py` — a single FastAPI app with two kinds of routes:

- **Frontend**: `GET /` renders `templates/index.html` (Jinja2), which loads `static/style.css` and calls the API with inline fetch JS. Static files are mounted at `/static`.
- **API**: JSON endpoints under `/api/*` (`/api/health`, `/api/echo`), request bodies validated with Pydantic models. Swagger UI is auto-served at `/docs`.

When adding features, follow this split: page routes render templates, data routes go under `/api/` with Pydantic schemas. Split `main.py` into routers only if it grows large.
