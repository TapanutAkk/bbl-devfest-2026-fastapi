from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="BBL Dev Fest 2026")

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# ---------- Frontend ----------

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse(
        request, "index.html", {"title": "BBL Dev Fest 2026"}
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
