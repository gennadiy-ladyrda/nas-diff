from __future__ import annotations

import sqlite3
from pathlib import Path

from app.db.migrations import apply_migrations


def test_apply_init_migration_is_idempotent(db_url: str) -> None:
    applied_first = apply_migrations(db_url)
    applied_second = apply_migrations(db_url)

    assert applied_first == ["0001_init"]
    assert applied_second == []


def test_migration_creates_required_tables(db_url: str) -> None:
    apply_migrations(db_url)
    db_path = db_url.replace("sqlite:///", "", 1)

    with sqlite3.connect(db_path) as conn:
        table_names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    assert "schema_migrations" in table_names
    assert "scan_jobs" in table_names
    assert "files" in table_names
    assert "exact_groups" in table_names
    assert "similar_groups" in table_names
    assert "action_batches" in table_names
    assert "action_items" in table_names


def test_init_migration_matches_canonical_schema() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    canonical = (repo_root / "database" / "schema.sql").read_text(encoding="utf-8").strip()
    migration = (
        repo_root / "backend" / "app" / "db" / "migrations" / "sql" / "0001_init.sql"
    ).read_text(encoding="utf-8").strip()

    assert migration == canonical
