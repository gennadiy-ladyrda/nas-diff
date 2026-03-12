from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.api.routes_health import router as health_router
from app.api.routes_scan_roots import router as scan_roots_router
from app.config import Settings, get_settings
from app.db import get_db_session
from app.db.migrations import apply_migrations
from app.db.session import get_session_factory


@pytest.fixture()
def test_settings(tmp_path) -> Settings:
    db_file = tmp_path / "nas_diff_api_test.db"
    return Settings(
        app_name="nas-diff-test",
        app_version="0.1.0-test",
        app_env="test",
        log_level="INFO",
        app_data_dir=str(tmp_path),
        database_url=f"sqlite:///{db_file}",
        redis_url="redis://127.0.0.1:1/0",
        nas_scan_roots=("/nas/photo", "/nas/archive"),
        nas_trash_dir="/nas/.nas-diff-trash",
        default_file_action="move_to_trash",
        hard_delete_enabled=False,
        max_scan_workers=1,
        phash_distance_threshold=8,
        worker_queues=("scan_queue", "action_queue"),
        db_allow_destructive_migrations=False,
    )


@pytest.fixture()
def api_session_factory(test_settings: Settings) -> sessionmaker[Session]:
    apply_migrations(test_settings.database_url)
    return get_session_factory(test_settings)


@pytest.fixture()
def api_client(
    test_settings: Settings,
    api_session_factory: sessionmaker[Session],
) -> Iterator[TestClient]:
    app = FastAPI()
    api_v1 = APIRouter(prefix="/api/v1")
    api_v1.include_router(health_router)
    api_v1.include_router(scan_roots_router)
    app.include_router(api_v1)

    def _override_settings() -> Settings:
        return test_settings

    def _override_db() -> Iterator[Session]:
        with api_session_factory() as session:
            yield session

    app.dependency_overrides[get_settings] = _override_settings
    app.dependency_overrides[get_db_session] = _override_db

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
