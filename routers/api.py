from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlmodel import select

from auth import CurrentUser, auth_sessions, create_session, extract_token, verify_password
from database import Booking, Item, SessionDep, User, visible_bookings

router = APIRouter(prefix="/api")


@router.get("/health")
async def health():
    return {"status": "ok"}


class EchoIn(BaseModel):
    message: str


@router.post("/echo")
async def echo(body: EchoIn):
    return {"echo": body.message}


# ---------- Items ----------

class ItemCreate(BaseModel):
    name: str
    description: str | None = None


@router.post("/items", response_model=Item)
def create_item(body: ItemCreate, session: SessionDep):
    item = Item.model_validate(body)
    session.add(item)
    session.commit()
    session.refresh(item)
    return item


@router.get("/items", response_model=list[Item])
def list_items(session: SessionDep):
    return session.exec(select(Item)).all()


@router.get("/items/{item_id}", response_model=Item)
def get_item(item_id: int, session: SessionDep):
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@router.delete("/items/{item_id}")
def delete_item(item_id: int, session: SessionDep):
    item = session.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    session.delete(item)
    session.commit()
    return {"deleted": item_id}


# ---------- Auth ----------

class LoginIn(BaseModel):
    username: str
    password: str


@router.post("/login")
def api_login(body: LoginIn, session: SessionDep):
    user = session.exec(select(User).where(User.username == body.username)).first()
    if user is None or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_session(user)
    response = JSONResponse(
        {"token": token, "username": user.username, "is_admin": user.is_admin}
    )
    response.set_cookie("session_token", token, httponly=True)
    return response


@router.post("/logout")
def api_logout(request: Request):
    auth_sessions.pop(extract_token(request), None)
    response = JSONResponse({"logged_out": True})
    response.delete_cookie("session_token")
    return response


@router.get("/me")
def api_me(user: CurrentUser):
    return {"username": user.username, "is_admin": user.is_admin}


# ---------- Bookings ----------

class BookingCreate(BaseModel):
    time_slot: str


class BookingOut(BaseModel):
    id: int
    time_slot: str
    username: str


@router.get("/bookings", response_model=list[BookingOut])
def list_bookings(user: CurrentUser, session: SessionDep):
    return visible_bookings(session, user)


@router.post("/bookings", response_model=BookingOut, status_code=201)
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


@router.put("/bookings/{booking_id}", response_model=BookingOut)
def update_booking(
    booking_id: int, body: BookingCreate, user: CurrentUser, session: SessionDep
):
    booking = session.get(Booking, booking_id)
    if booking is None:
        raise HTTPException(status_code=404, detail="Booking not found")
    if not user.is_admin and booking.user_id != user.id:
        raise HTTPException(
            status_code=403, detail="Not allowed to update this booking"
        )
    slot = body.time_slot.strip()
    if not slot:
        raise HTTPException(status_code=422, detail="time_slot must not be empty")
    booking.time_slot = slot
    session.add(booking)
    session.commit()
    session.refresh(booking)
    owner = session.get(User, booking.user_id)
    return BookingOut(
        id=booking.id, time_slot=booking.time_slot, username=owner.username
    )


@router.delete("/bookings/{booking_id}")
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
