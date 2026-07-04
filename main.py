import hashlib
import hmac
import secrets
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlmodel import Field, Session, SQLModel, create_engine, select

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env")

    app_name: str = "BBL Dev Fest 2026"
    debug: bool = False
    database_url: str = f"sqlite:///{BASE_DIR / 'data.db'}"


settings = Settings()


# ---------- Database ----------

class Item(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str | None = None


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)
    password_hash: str
    is_admin: bool = False


class Booking(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    time_slot: str


engine = create_engine(
    settings.database_url, connect_args={"check_same_thread": False}
)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


# ---------- Auth ----------

# Logged-in sessions live in memory: token -> user id. Restarting the
# server logs everyone out.
auth_sessions: dict[str, int] = {}

PBKDF2_ITERATIONS = 100_000


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return f"{salt}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    salt, digest = stored.split("$", 1)
    check = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), bytes.fromhex(salt), PBKDF2_ITERATIONS
    )
    return hmac.compare_digest(check.hex(), digest)


def get_optional_user(request: Request, session: SessionDep) -> User | None:
    """Resolve the logged-in user from a Bearer token (API clients) or
    the session cookie (browser)."""
    auth = request.headers.get("Authorization", "")
    token = (
        auth.removeprefix("Bearer ")
        if auth.startswith("Bearer ")
        else request.cookies.get("session_token")
    )
    user_id = auth_sessions.get(token) if token else None
    return session.get(User, user_id) if user_id is not None else None


def require_user(user: Annotated[User | None, Depends(get_optional_user)]) -> User:
    if user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user


OptionalUser = Annotated[User | None, Depends(get_optional_user)]
CurrentUser = Annotated[User, Depends(require_user)]

SEED_USERS = [
    ("admin", "admin123", True),
    ("alice", "alice123", False),
    ("bob", "bob123", False),
]

SEED_BOOKINGS = [
    ("alice", "10.00-11.00"),
    ("bob", "13.00-14.00"),
    ("alice", "13.55-17.55"),
]


def seed_data() -> None:
    with Session(engine) as session:
        if session.exec(select(User)).first() is not None:
            return
        users = {}
        for username, password, is_admin in SEED_USERS:
            user = User(
                username=username,
                password_hash=hash_password(password),
                is_admin=is_admin,
            )
            session.add(user)
            users[username] = user
        session.commit()
        for username, time_slot in SEED_BOOKINGS:
            session.add(Booking(user_id=users[username].id, time_slot=time_slot))
        session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    seed_data()
    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# ---------- Frontend ----------

def render_page(request: Request, page: str, context: dict | None = None):
    """Render a partial for htmx requests, the full page otherwise.

    History restores (HX-History-Restore-Request) need the full page even
    though htmx sends them.
    """
    context = {
        "title": settings.app_name,
        "page": page,
        "user": None,
        **(context or {}),
    }
    is_htmx = request.headers.get("HX-Request") and not request.headers.get(
        "HX-History-Restore-Request"
    )
    template = f"partials/{page}.html" if is_htmx else "index.html"
    return templates.TemplateResponse(request, template, context)


def redirect_to(request: Request, url: str) -> Response:
    """Redirect that works from both htmx swaps and full-page requests."""
    if request.headers.get("HX-Request"):
        return Response(headers={"HX-Redirect": url})
    return RedirectResponse(url, status_code=303)


@app.get("/")
def index(request: Request):
    return redirect_to(request, "/bookings")


def visible_bookings(session: Session, user: User) -> list[dict]:
    """Bookings the user may see: all for admins, own otherwise."""
    query = select(Booking, User).where(Booking.user_id == User.id)
    if not user.is_admin:
        query = query.where(Booking.user_id == user.id)
    return [
        {"id": booking.id, "time_slot": booking.time_slot, "username": owner.username}
        for booking, owner in session.exec(query)
    ]


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user: OptionalUser):
    if user is not None:
        return redirect_to(request, "/bookings")
    return render_page(request, "login")


@app.post("/login", response_class=HTMLResponse)
def login_fragment(
    request: Request,
    session: SessionDep,
    username: Annotated[str, Form()],
    password: Annotated[str, Form()],
):
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request,
            "partials/login.html",
            {"error": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"},
        )
    token = secrets.token_urlsafe(32)
    auth_sessions[token] = user.id
    response = redirect_to(request, "/bookings")
    response.set_cookie("session_token", token, httponly=True)
    return response


@app.post("/logout")
def logout(request: Request):
    token = request.cookies.get("session_token")
    auth_sessions.pop(token, None)
    response = redirect_to(request, "/")
    response.delete_cookie("session_token")
    return response


@app.get("/bookings", response_class=HTMLResponse)
def bookings_page(request: Request, session: SessionDep, user: OptionalUser):
    if user is None:
        return redirect_to(request, "/login")
    bookings = visible_bookings(session, user)
    return render_page(request, "bookings", {"user": user, "bookings": bookings})


def booking_list_fragment(
    request: Request, session: Session, user: User, error: str | None = None
):
    return templates.TemplateResponse(
        request,
        "partials/booking_list.html",
        {"user": user, "bookings": visible_bookings(session, user), "error": error},
    )


@app.post("/bookings", response_class=HTMLResponse)
def create_booking_fragment(
    request: Request,
    session: SessionDep,
    user: OptionalUser,
    start_time: Annotated[str, Form()],
    end_time: Annotated[str, Form()],
):
    if user is None:
        return redirect_to(request, "/login")
    error = None
    # <input type="time"> submits HH:MM, so string comparison is
    # also chronological comparison.
    if not start_time or not end_time:
        error = "กรุณาเลือกเวลาเริ่มต้นและสิ้นสุด"
    elif end_time <= start_time:
        error = "เวลาสิ้นสุดต้องอยู่หลังเวลาเริ่มต้น"
    else:
        session.add(Booking(user_id=user.id, time_slot=f"{start_time}-{end_time}"))
        session.commit()
    return booking_list_fragment(request, session, user, error)


@app.delete("/bookings/{booking_id}", response_class=HTMLResponse)
def delete_booking_fragment(
    request: Request, booking_id: int, session: SessionDep, user: OptionalUser
):
    if user is None:
        return redirect_to(request, "/login")
    booking = session.get(Booking, booking_id)
    if booking is not None and (user.is_admin or booking.user_id == user.id):
        session.delete(booking)
        session.commit()
    return booking_list_fragment(request, session, user)


# ---------- API ----------

class EchoIn(BaseModel):
    message: str


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/echo")
async def echo(body: EchoIn):
    return {"echo": body.message}


class ItemCreate(BaseModel):
    name: str
    description: str | None = None


@app.post("/api/items", response_model=Item)
def create_item(body: ItemCreate, session: SessionDep):
    item = Item.model_validate(body)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@app.get("/api/items", response_model=list[Item])
def list_items(session: SessionDep):
    return session.exec(select(Item)).all()


@app.get("/api/items/{item_id}", response_model=Item)
def get_item(item_id: int, session: SessionDep):
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.delete("/api/items/{item_id}")
def delete_item(item_id: int, session: SessionDep):
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    session.delete(item)
    session.commit()
    return {"deleted": item_id}


class LoginIn(BaseModel):
    username: str
    password: str


@app.post("/api/login")
def api_login(body: LoginIn, session: SessionDep):
    user = session.exec(select(User).where(User.username == body.username)).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = secrets.token_urlsafe(32)
    auth_sessions[token] = user.id
    response = JSONResponse(
        {"token": token, "username": user.username, "is_admin": user.is_admin}
    )
    response.set_cookie("session_token", token, httponly=True)
    return response


@app.post("/api/logout")
def api_logout(request: Request):
    auth = request.headers.get("Authorization", "")
    token = (
        auth.removeprefix("Bearer ")
        if auth.startswith("Bearer ")
        else request.cookies.get("session_token")
    )
    auth_sessions.pop(token, None)
    response = JSONResponse({"logged_out": True})
    response.delete_cookie("session_token")
    return response


@app.get("/api/me")
def api_me(user: CurrentUser):
    return {"username": user.username, "is_admin": user.is_admin}


class BookingCreate(BaseModel):
    time_slot: str


class BookingOut(BaseModel):
    id: int
    time_slot: str
    username: str


@app.get("/api/bookings", response_model=list[BookingOut])
def list_bookings(user: CurrentUser, session: SessionDep):
    return visible_bookings(session, user)


@app.post("/api/bookings", response_model=BookingOut, status_code=201)
def create_booking(body: BookingCreate, user: CurrentUser, session: SessionDep):
    slot = body.time_slot.strip()
    if not slot:
        raise HTTPException(status_code=422, detail="time_slot must not be empty")
    booking = Booking(user_id=user.id, time_slot=slot)
    session.add(booking)
    session.commit()
    session.refresh(booking)
    return BookingOut(
        id=booking.id, time_slot=booking.time_slot, username=user.username
    )


@app.delete("/api/bookings/{booking_id}")
def delete_booking(booking_id: int, user: CurrentUser, session: SessionDep):
    booking = session.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    if not user.is_admin and booking.user_id != user.id:
        raise HTTPException(
            status_code=403, detail="Not allowed to delete this booking"
        )
    session.delete(booking)
    session.commit()
    return {"deleted": booking_id}
