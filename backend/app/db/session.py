from __future__ import annotations

from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings

SQLITE_URL_PREFIX = "sqlite:///"


class UnsupportedDatabaseUrlError(ValueError):
    """Raised when DATABASE_URL has unsupported format."""


def parse_sqlite_path(database_url: str) -> str:
    if not database_url.startswith(SQLITE_URL_PREFIX):
        raise UnsupportedDatabaseUrlError(
            "Only sqlite:/// URLs are supported in the current project stage"
        )
    return database_url[len(SQLITE_URL_PREFIX) :]


@lru_cache(maxsize=8)
def _build_engine(database_url: str) -> Engine:
    parse_sqlite_path(database_url)

    engine = create_engine(
        database_url,
        future=True,
        pool_pre_ping=True,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    return engine


@lru_cache(maxsize=8)
def _build_session_factory(database_url: str) -> sessionmaker[Session]:
    return sessionmaker(
        bind=_build_engine(database_url),
        autoflush=False,
        expire_on_commit=False,
        class_=Session,
    )


def get_engine(settings: Settings | None = None) -> Engine:
    active_settings = settings or get_settings()
    return _build_engine(active_settings.database_url)


def get_session_factory(settings: Settings | None = None) -> sessionmaker[Session]:
    active_settings = settings or get_settings()
    return _build_session_factory(active_settings.database_url)


@contextmanager
def session_scope(settings: Settings | None = None) -> Iterator[Session]:
    session = get_session_factory(settings)()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db_session(settings: Settings | None = None) -> Iterator[Session]:
    session = get_session_factory(settings)()
    try:
        yield session
    finally:
        session.close()
