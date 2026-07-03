from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
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


engine = create_engine(
    settings.database_url, connect_args={"check_same_thread": False}
)


def get_session():
    with Session(engine) as session:
        yield session


SessionDep = Annotated[Session, Depends(get_session)]


@asynccontextmanager
async def lifespan(app: FastAPI):
    SQLModel.metadata.create_all(engine)
    yield


app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# ---------- Frontend ----------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request, "index.html", {"title": settings.app_name}
    )


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
