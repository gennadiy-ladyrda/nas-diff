from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _parse_csv(value: str | None, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None:
        return default
    items = tuple(item.strip() for item in value.split(",") if item.strip())
    return items or default


def _default_app_data_dir() -> str:
    env_value = os.getenv("APP_DATA_DIR")
    if env_value:
        return os.path.abspath(os.path.expanduser(env_value))
    return str((Path.home() / ".nas-diff" / "data").resolve())


def _default_database_url(app_data_dir: str) -> str:
    explicit_database_url = os.getenv("DATABASE_URL")
    if explicit_database_url:
        return explicit_database_url
    return f"sqlite:///{app_data_dir}/nas_diff.db"


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    app_env: str
    log_level: str
    app_data_dir: str
    database_url: str
    redis_url: str
    nas_scan_roots: tuple[str, ...]
    nas_trash_dir: str
    default_file_action: str
    hard_delete_enabled: bool
    max_scan_workers: int
    phash_distance_threshold: int
    worker_queues: tuple[str, ...]
    db_allow_destructive_migrations: bool


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    app_data_dir = _default_app_data_dir()

    return Settings(
        app_name=os.getenv("APP_NAME", "nas-diff"),
        app_version=os.getenv("APP_VERSION", "0.1.0"),
        app_env=os.getenv("APP_ENV", "production"),
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        app_data_dir=app_data_dir,
        database_url=_default_database_url(app_data_dir),
        redis_url=os.getenv("REDIS_URL", "redis://redis:6379/0"),
        nas_scan_roots=_parse_csv(os.getenv("NAS_SCAN_ROOTS"), ("/nas/photo", "/nas/archive")),
        nas_trash_dir=os.getenv("NAS_TRASH_DIR", "/nas/.nas-diff-trash"),
        default_file_action=os.getenv("DEFAULT_FILE_ACTION", "move_to_trash"),
        hard_delete_enabled=_parse_bool(os.getenv("HARD_DELETE_ENABLED"), default=False),
        max_scan_workers=_parse_int(os.getenv("MAX_SCAN_WORKERS"), default=2),
        phash_distance_threshold=_parse_int(os.getenv("PHASH_DISTANCE_THRESHOLD"), default=8),
        worker_queues=_parse_csv(os.getenv("WORKER_QUEUES"), ("scan_queue", "action_queue")),
        db_allow_destructive_migrations=_parse_bool(
            os.getenv("DB_ALLOW_DESTRUCTIVE_MIGRATIONS"),
            default=False,
        ),
    )
