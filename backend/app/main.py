from __future__ import annotations

from fastapi import APIRouter, FastAPI

from app.api.routes_health import router as health_router
from app.config import get_settings
from app.log_setup import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(
    title="NAS Diff API",
    version=settings.app_version,
)

api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(health_router)
app.include_router(api_v1)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "service": settings.app_name,
        "docs": "/docs",
    }
