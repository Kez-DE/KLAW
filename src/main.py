from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.routes import router
from src.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    print(f"Starting {settings.app_name} in {settings.app_env} mode")
    yield
    print("Shutting down...")


app = FastAPI(
    title="KLAW API",
    description="AI Agent built with LangGraph",
    version="1.0.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/health")
async def health():
    # KHÔNG trả `app_env` (FastAPI review, MEDIUM): một endpoint không xác
    # thực không nên tiết lộ deployment đang chạy môi trường nào trước khi
    # Plan 4 deploy thật.
    return {"status": "ok"}


# Static frontend (Vite build output). Mounted LAST — a StaticFiles mount at
# "/" is a catch-all; every /api/* and /health route above must already be
# registered or this would shadow them.
STATIC = Path(__file__).parent / "static"
if STATIC.exists():
    app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
