from typing import Annotated

from fastapi import Depends
from sqlmodel import Field, Session, SQLModel, create_engine, select

from config import settings


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


def visible_bookings(session: Session, user: User) -> list[dict]:
    """Bookings the user may see: all for admins, own otherwise."""
    query = select(Booking, User).where(Booking.user_id == User.id)
    if not user.is_admin:
        query = query.where(Booking.user_id == user.id)
    return [
        {"id": booking.id, "time_slot": booking.time_slot, "username": owner.username}
        for booking, owner in session.exec(query)
    ]
