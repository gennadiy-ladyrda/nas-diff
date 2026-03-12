from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.db.migrations import apply_migrations


@pytest.fixture()
def db_url(tmp_path) -> str:
    db_file = tmp_path / "nas_diff_test.db"
    return f"sqlite:///{db_file}"


@pytest.fixture()
def session(db_url: str) -> Iterator[Session]:
    apply_migrations(db_url)

    engine = create_engine(
        db_url,
        future=True,
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:  # type: ignore[no-untyped-def]
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

    session_factory = sessionmaker(bind=engine, expire_on_commit=False, class_=Session)

    with session_factory() as db_session:
        yield db_session

    engine.dispose()
