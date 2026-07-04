from typing import Annotated

from fastapi import APIRouter, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from auth import (
    OptionalUser,
    auth_sessions,
    create_session,
    verify_password,
)
from config import BASE_DIR, settings
from database import Booking, SessionDep, User, visible_bookings

router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "templates")


def partial(name: str) -> str:
    return f"partials/{name}.html"


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
    template = partial(page) if is_htmx else "index.html"
    return templates.TemplateResponse(request, template, context)


def redirect_to(request: Request, url: str) -> Response:
    """Redirect that works from both htmx swaps and full-page requests."""
    if request.headers.get("HX-Request"):
        return Response(headers={"HX-Redirect": url})
    return RedirectResponse(url, status_code=303)


@router.get("/")
def index(request: Request):
    return redirect_to(request, "/bookings")


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, user: OptionalUser):
    if user is not None:
        return redirect_to(request, "/bookings")
    return render_page(request, "login")


@router.post("/login", response_class=HTMLResponse)
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
            partial("login"),
            {"error": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"},
        )
    token = create_session(user)
    response = redirect_to(request, "/bookings")
    response.set_cookie("session_token", token, httponly=True)
    return response


@router.post("/logout")
def logout(request: Request):
    token = request.cookies.get("session_token")
    auth_sessions.pop(token, None)
    response = redirect_to(request, "/")
    response.delete_cookie("session_token")
    return response


@router.get("/bookings", response_class=HTMLResponse)
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
        partial("booking_list"),
        {"user": user, "bookings": visible_bookings(session, user), "error": error},
    )


@router.post("/bookings", response_class=HTMLResponse)
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


@router.delete("/bookings/{booking_id}", response_class=HTMLResponse)
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
