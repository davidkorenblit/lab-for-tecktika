from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.endpoints import chat, files
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.telemetry import setup_telemetry


app = FastAPI(
    title=settings.app_name
)

setup_telemetry(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.cors_allowed_origins.split(",")
        if origin.strip()
    ] or ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    api_router,
    prefix="/api/v1",
)
app.include_router(
    api_router,
    prefix="/api",
)

app.include_router(
    chat.router,
    prefix="/api/chat",
    tags=["chat"],
)


app.include_router(
    files.router,
    prefix="/api/files",
    tags=["files"],
)


@app.get("/health")
def health():
    return {
        "status": "ok",
        "environment": settings.environment,
    }