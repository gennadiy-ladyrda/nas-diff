from __future__ import annotations

import sqlite3
from typing import Any

from fastapi import APIRouter, Depends
from redis import Redis
from redis.exceptions import RedisError

from app.config import Settings, get_settings

router = APIRouter()


def _check_api() -> dict[str, str]:
    return {"status": "ok", "detail": "API reachable"}


def _check_sqlite(database_url: str) -> dict[str, str]:
    sqlite_prefix = "sqlite:///"
    if not database_url.startswith(sqlite_prefix):
        return {"status": "unsupported", "detail": "Only sqlite:/// URLs are supported in INFRA-01"}

    db_path = database_url[len(sqlite_prefix) :]
    try:
        with sqlite3.connect(db_path, timeout=1) as conn:
            conn.execute("SELECT 1")
        return {"status": "ok", "detail": "SQLite reachable"}
    except sqlite3.Error as exc:
        return {"status": "error", "detail": str(exc)}


def _check_redis(redis_url: str) -> dict[str, str]:
    try:
        client = Redis.from_url(redis_url, socket_timeout=1, socket_connect_timeout=1)
        client.ping()
        return {"status": "ok", "detail": "Redis reachable"}
    except RedisError as exc:
        return {"status": "error", "detail": str(exc)}


@router.get("/health")
def health(settings: Settings = Depends(get_settings)) -> dict[str, Any]:
    api = _check_api()
    database = _check_sqlite(settings.database_url)
    redis = _check_redis(settings.redis_url)

    overall_status = "ok"
    if any(component["status"] != "ok" for component in (api, database, redis)):
        overall_status = "degraded"

    return {
        "service": settings.app_name,
        "version": settings.app_version,
        "status": overall_status,
        "components": {
            "api": api,
            "database": database,
            "redis": redis,
        },
    }
