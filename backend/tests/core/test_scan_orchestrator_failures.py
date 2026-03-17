from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import Settings
from app.services import scan_orchestrator


def _build_test_settings(tmp_path) -> Settings:
    return Settings(
        app_name="nas-diff-test",
        app_version="0.1.0-test",
        app_env="test",
        log_level="INFO",
        app_data_dir=str(tmp_path),
        database_url=f"sqlite:///{tmp_path / 'db.sqlite'}",
        redis_url="redis://127.0.0.1:1/0",
        nas_scan_roots=("/nas/photo",),
        nas_trash_dir="/nas/.nas-diff-trash",
        default_file_action="move_to_trash",
        hard_delete_enabled=False,
        max_scan_workers=1,
        phash_distance_threshold=8,
        scan_job_timeout_seconds=3600,
        worker_queues=("scan_queue", "action_queue"),
        db_allow_destructive_migrations=False,
    )


def test_scan_job_marks_failed_after_flush_error(session: Session, tmp_path, monkeypatch) -> None:
    root_path = tmp_path / "dataset"
    root_path.mkdir(parents=True, exist_ok=True)

    root_id = session.execute(
        text("INSERT INTO scan_roots(path, enabled) VALUES (:path, 1)"),
        {"path": str(root_path)},
    ).lastrowid
    assert root_id is not None

    job_id = "job-fail-rollback"
    session.execute(
        text("INSERT INTO scan_jobs(id, mode, status) VALUES (:job_id, 'exact', 'queued')"),
        {"job_id": job_id},
    )
    session.execute(
        text("INSERT INTO scan_job_roots(job_id, root_id) VALUES (:job_id, :root_id)"),
        {"job_id": job_id, "root_id": int(root_id)},
    )
    session.commit()

    def _broken_scan_and_index(db_session: Session, *, job_id: str, roots):
        # Force a DB transaction error and leave session in rollback-required state.
        db_session.execute(
            text("INSERT INTO scan_jobs(id, mode, status) VALUES (:job_id, 'exact', 'queued')"),
            {"job_id": job_id},
        )
        db_session.commit()
        raise AssertionError("unreachable")

    monkeypatch.setattr(scan_orchestrator, "scan_and_index", _broken_scan_and_index)

    settings = _build_test_settings(tmp_path)
    with pytest.raises(IntegrityError):
        scan_orchestrator.run_scan_job(session, settings, job_id=job_id)

    row = session.execute(
        text(
            "SELECT status, error_message, finished_at "
            "FROM scan_jobs WHERE id = :job_id"
        ),
        {"job_id": job_id},
    ).mappings().one()

    assert row["status"] == "failed"
    assert row["finished_at"] is not None
    assert row["error_message"] is not None
    assert "UNIQUE" in row["error_message"]
