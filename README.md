# BBL Dev Fest 2026

FastAPI + Jinja2 frontend + SQLite (SQLModel), จัดการด้วย [uv](https://docs.astral.sh/uv/)

## วิธีรัน

```bash
cp .env.example .env   # ครั้งแรกครั้งเดียว
uv run uvicorn main:app --reload
```

แล้วเปิด:

- หน้าเว็บ: http://127.0.0.1:8000
- API docs (Swagger UI): http://127.0.0.1:8000/docs

## โครงสร้าง

```
├── main.py          # FastAPI app (routes ทั้ง frontend และ API)
├── templates/       # Jinja2 templates
├── static/          # CSS/JS
└── pyproject.toml   # dependencies (จัดการด้วย uv)
```

## เพิ่ม dependency

```bash
uv add <package>
```
