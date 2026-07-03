from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Form, HTTPException, Request
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

def render_page(request: Request, page: str, context: dict | None = None):
    """Render a partial for htmx requests, the full page otherwise.

    History restores (HX-History-Restore-Request) need the full page even
    though htmx sends them.
    """
    context = {"title": settings.app_name, "page": page, **(context or {})}
    is_htmx = request.headers.get("HX-Request") and not request.headers.get(
        "HX-History-Restore-Request"
    )
    template = f"partials/{page}.html" if is_htmx else "index.html"
    return templates.TemplateResponse(request, template, context)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return render_page(request, "echo")


@app.get("/items", response_class=HTMLResponse)
def items_page(request: Request, session: SessionDep):
    items = session.exec(select(Item)).all()
    return render_page(request, "items", {"items": items})


@app.post("/echo", response_class=HTMLResponse)
async def echo_fragment(request: Request, message: Annotated[str, Form()]):
    return templates.TemplateResponse(
        request, "partials/echo_result.html", {"message": message}
    )


def item_list_fragment(request: Request, session: Session):
    items = session.exec(select(Item)).all()
    return templates.TemplateResponse(
        request, "partials/item_list.html", {"items": items}
    )


@app.post("/items", response_class=HTMLResponse)
def create_item_fragment(
    request: Request,
    session: SessionDep,
    name: Annotated[str, Form()],
    description: Annotated[str | None, Form()] = None,
):
    session.add(Item(name=name, description=description or None))
    session.commit()
    return item_list_fragment(request, session)


@app.delete("/items/{item_id}", response_class=HTMLResponse)
def delete_item_fragment(request: Request, item_id: int, session: SessionDep):
    item = session.get(Item, item_id)
    if item is not None:
        session.delete(item)
        session.commit()
    return item_list_fragment(request, session)


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
