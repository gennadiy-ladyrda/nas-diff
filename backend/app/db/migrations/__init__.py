from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from app.config import Settings, get_settings
from app.db.session import parse_sqlite_path

_DESTRUCTIVE_SQL_PATTERN = re.compile(
    r"\b(DROP\s+TABLE|DROP\s+INDEX|DROP\s+VIEW|TRUNCATE|DELETE\s+FROM)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Migration:
    version: str
    sql_path: Path


MIGRATIONS_DIR = Path(__file__).resolve().parent / "sql"
MIGRATIONS: tuple[Migration, ...] = (
    Migration(version="0001_init", sql_path=MIGRATIONS_DIR / "0001_init.sql"),
)


class MigrationError(RuntimeError):
    """Raised when migrations cannot be applied safely."""


def _read_sql(path: Path) -> str:
    if not path.exists():
        raise MigrationError(f"Migration file not found: {path}")
    return path.read_text(encoding="utf-8")


def _contains_destructive_sql(sql_script: str) -> bool:
    return bool(_DESTRUCTIVE_SQL_PATTERN.search(sql_script))


def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
          version TEXT PRIMARY KEY,
          checksum TEXT NOT NULL,
          applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )


def _load_applied_migrations(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT version, checksum FROM schema_migrations").fetchall()
    return {version: checksum for version, checksum in rows}


def _apply_single_migration(
    conn: sqlite3.Connection,
    *,
    migration: Migration,
    allow_destructive: bool,
) -> bool:
    sql_script = _read_sql(migration.sql_path)
    if _contains_destructive_sql(sql_script) and not allow_destructive:
        raise MigrationError(
            f"Migration {migration.version} contains destructive SQL. "
            "Set DB_ALLOW_DESTRUCTIVE_MIGRATIONS=true only after explicit confirmation."
        )

    checksum = hashlib.sha256(sql_script.encode("utf-8")).hexdigest()
    applied = _load_applied_migrations(conn)
    current_checksum = applied.get(migration.version)

    if current_checksum is not None:
        if current_checksum != checksum:
            raise MigrationError(
                f"Migration {migration.version} was applied with a different checksum."
            )
        return False

    conn.executescript(sql_script)
    conn.execute(
        "INSERT INTO schema_migrations(version, checksum) VALUES (?, ?)",
        (migration.version, checksum),
    )
    return True


def apply_migrations(database_url: str, *, allow_destructive: bool = False) -> list[str]:
    db_path = parse_sqlite_path(database_url)

    if db_path != ":memory:":
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    applied_versions: list[str] = []

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys = ON")
        _ensure_migrations_table(conn)

        for migration in MIGRATIONS:
            applied_now = _apply_single_migration(
                conn,
                migration=migration,
                allow_destructive=allow_destructive,
            )
            if applied_now:
                applied_versions.append(migration.version)

        conn.commit()

    return applied_versions


def apply_migrations_from_settings(settings: Settings | None = None) -> list[str]:
    active_settings = settings or get_settings()
    return apply_migrations(
        active_settings.database_url,
        allow_destructive=active_settings.db_allow_destructive_migrations,
    )
