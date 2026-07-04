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

## ระบบจองคิวนัดหมาย (Appointment Booking)

Login ที่หน้า `/login` แล้วจองช่วงเวลา (เช่น `10am-11am`) ที่หน้า `/bookings`

ผู้ใช้ทดลอง (seed อัตโนมัติตอนรันครั้งแรก):

| username | password | สิทธิ์ |
|---|---|---|
| `admin` | `admin123` | แอดมิน — เห็นและลบการจองของทุกคน |
| `alice` | `alice123` | ผู้ใช้ทั่วไป — จัดการเฉพาะการจองของตัวเอง |
| `bob` | `bob123` | ผู้ใช้ทั่วไป — จัดการเฉพาะการจองของตัวเอง |

### REST API

Login ก่อนเพื่อรับ token แล้วส่งเป็น `Authorization: Bearer <token>`:

```bash
# login → ได้ {"token": "...", "username": "alice", "is_admin": false}
curl -X POST http://127.0.0.1:8000/api/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"alice","password":"alice123"}'

# จองคิว
curl -X POST http://127.0.0.1:8000/api/bookings \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"time_slot":"10am-11am"}'

# ดูการจอง (admin เห็นทั้งหมด, ผู้ใช้ทั่วไปเห็นเฉพาะของตัวเอง)
curl http://127.0.0.1:8000/api/bookings -H "Authorization: Bearer $TOKEN"

# แก้ไขการจอง (เจ้าของหรือ admin เท่านั้น)
curl -X PUT http://127.0.0.1:8000/api/bookings/1 \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"time_slot":"15.00-16.00"}'

# ยกเลิกการจอง (เจ้าของหรือ admin เท่านั้น)
curl -X DELETE http://127.0.0.1:8000/api/bookings/1 -H "Authorization: Bearer $TOKEN"
```

Endpoints อื่น: `POST /api/logout`, `GET /api/me`

## รัน tests

```bash
uv run pytest
```

ครอบคลุม: login สำเร็จ/ล้มเหลว, ต้อง login ก่อนใช้ bookings, ผู้ใช้เห็นเฉพาะของตัวเอง,
admin เห็นทั้งหมด, สิทธิ์การแก้ไขและลบ (เจ้าของ/admin ทำได้, คนอื่นโดน 403)

## โครงสร้าง

```
├── main.py          # ประกอบ app: lifespan + seed + include routers
├── config.py        # Settings (.env)
├── database.py      # SQLModel models + engine + session
├── auth.py          # hash รหัสผ่าน, session token, auth dependencies
├── routers/
│   ├── web.py       # routes หน้าเว็บ (Jinja2 + htmx)
│   └── api.py       # routes JSON API (prefix /api)
├── templates/       # Jinja2 templates
├── static/          # CSS/JS
├── tests/           # pytest (auth + booking permissions)
└── pyproject.toml   # dependencies (จัดการด้วย uv)
```

## เพิ่ม dependency

```bash
uv add <package>
```
