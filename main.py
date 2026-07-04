from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, SQLModel, select

from auth import hash_password
from config import BASE_DIR, settings
from database import Booking, User, engine
from routers import api, web

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

app.include_router(web.router)
app.include_router(api.router)
