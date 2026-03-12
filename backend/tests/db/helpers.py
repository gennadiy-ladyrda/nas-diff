from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session


def seed_root_and_job(session: Session, *, root_path: str = "/nas/photo", job_id: str = "job-1") -> tuple[int, str]:
    root_id = session.execute(
        text("INSERT INTO scan_roots(path, enabled) VALUES (:path, 1)"),
        {"path": root_path},
    ).lastrowid

    session.execute(
        text(
            """
            INSERT INTO scan_jobs(id, mode, status)
            VALUES (:job_id, 'exact', 'queued')
            """
        ),
        {"job_id": job_id},
    )

    session.commit()
    return int(root_id), job_id
