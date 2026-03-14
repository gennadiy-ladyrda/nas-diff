from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker


def _insert_scan_job(
    session: Session,
    *,
    job_id: str,
    mode: str,
    status: str,
    requested_at: str,
    started_at: str | None = None,
) -> None:
    session.execute(
        text(
            """
            INSERT INTO scan_jobs(
                id, mode, status, requested_at, started_at,
                files_seen, files_indexed, exact_groups_found, similar_groups_found, reclaimable_bytes
            )
            VALUES (
                :job_id, :mode, :status, :requested_at, :started_at,
                0, 0, 0, 0, 0
            )
            """
        ),
        {
            "job_id": job_id,
            "mode": mode,
            "status": status,
            "requested_at": requested_at,
            "started_at": started_at,
        },
    )


def _insert_root(session: Session, *, path: str = "/nas/photo") -> int:
    root_id = session.execute(
        text("INSERT INTO scan_roots(path, enabled) VALUES (:path, 1)"),
        {"path": path},
    ).lastrowid
    assert root_id is not None
    return int(root_id)


def test_list_scan_jobs_supports_filters_and_pagination(
    api_client,
    api_session_factory: sessionmaker[Session],
) -> None:
    with api_session_factory() as session:
        _insert_scan_job(
            session,
            job_id="job-old",
            mode="both",
            status="completed",
            requested_at="2026-03-13 10:00:00",
        )
        _insert_scan_job(
            session,
            job_id="job-mid",
            mode="exact",
            status="failed",
            requested_at="2026-03-13 11:00:00",
        )
        _insert_scan_job(
            session,
            job_id="job-new",
            mode="both",
            status="completed",
            requested_at="2026-03-13 12:00:00",
        )
        session.commit()

    first_page = api_client.get(
        "/api/v1/scan/jobs",
        params={
            "status": "completed",
            "mode": "both",
            "page": 1,
            "page_size": 1,
            "order": "desc",
        },
    )
    assert first_page.status_code == 200
    first_payload = first_page.json()
    assert first_payload["total"] == 2
    assert len(first_payload["items"]) == 1
    assert first_payload["items"][0]["job_id"] == "job-new"

    second_page = api_client.get(
        "/api/v1/scan/jobs",
        params={
            "status": "completed",
            "mode": "both",
            "page": 2,
            "page_size": 1,
            "order": "desc",
        },
    )
    assert second_page.status_code == 200
    second_payload = second_page.json()
    assert second_payload["total"] == 2
    assert len(second_payload["items"]) == 1
    assert second_payload["items"][0]["job_id"] == "job-old"


def test_delete_scan_job_removes_metadata_when_safe(
    api_client,
    api_session_factory: sessionmaker[Session],
) -> None:
    with api_session_factory() as session:
        _insert_scan_job(
            session,
            job_id="job-delete-safe",
            mode="exact",
            status="completed",
            requested_at="2026-03-13 09:00:00",
        )
        session.commit()

    response = api_client.delete("/api/v1/scan/jobs/job-delete-safe")
    assert response.status_code == 204

    status_response = api_client.get("/api/v1/scan/jobs/job-delete-safe")
    assert status_response.status_code == 404


def test_delete_scan_job_rejects_running_status(
    api_client,
    api_session_factory: sessionmaker[Session],
) -> None:
    with api_session_factory() as session:
        _insert_scan_job(
            session,
            job_id="job-running",
            mode="both",
            status="running",
            requested_at="2026-03-13 09:30:00",
        )
        session.commit()

    response = api_client.delete("/api/v1/scan/jobs/job-running")
    assert response.status_code == 409
    assert "status='running'" in response.json()["detail"]
    assert "allow_stale_running=true" in response.json()["detail"]


def test_delete_scan_job_allows_stale_running_with_explicit_flag(
    api_client,
    api_session_factory: sessionmaker[Session],
) -> None:
    stale_started_at = (datetime.now(timezone.utc) - timedelta(hours=8)).replace(microsecond=0).isoformat()

    with api_session_factory() as session:
        _insert_scan_job(
            session,
            job_id="job-running-stale",
            mode="both",
            status="running",
            requested_at="2026-03-13 00:00:00",
            started_at=stale_started_at,
        )
        session.commit()

    blocked = api_client.delete("/api/v1/scan/jobs/job-running-stale")
    assert blocked.status_code == 409

    response = api_client.delete(
        "/api/v1/scan/jobs/job-running-stale",
        params={"allow_stale_running": "true"},
    )
    assert response.status_code == 204

    status_response = api_client.get("/api/v1/scan/jobs/job-running-stale")
    assert status_response.status_code == 404


def test_delete_scan_job_rejects_recent_running_even_with_force_flag(
    api_client,
    api_session_factory: sessionmaker[Session],
) -> None:
    fresh_started_at = (datetime.now(timezone.utc) - timedelta(minutes=5)).replace(microsecond=0).isoformat()

    with api_session_factory() as session:
        _insert_scan_job(
            session,
            job_id="job-running-fresh",
            mode="both",
            status="running",
            requested_at="2026-03-13 00:00:00",
            started_at=fresh_started_at,
        )
        session.commit()

    response = api_client.delete(
        "/api/v1/scan/jobs/job-running-fresh",
        params={"allow_stale_running": "true"},
    )
    assert response.status_code == 409
    assert "not stale yet" in response.json()["detail"]


def test_delete_scan_job_rejects_when_groups_exist(
    api_client,
    api_session_factory: sessionmaker[Session],
) -> None:
    with api_session_factory() as session:
        _insert_scan_job(
            session,
            job_id="job-with-groups",
            mode="exact",
            status="completed",
            requested_at="2026-03-13 08:00:00",
        )
        session.execute(
            text(
                """
                INSERT INTO exact_groups(job_id, signature, file_count, total_bytes, reclaimable_bytes)
                VALUES (:job_id, :signature, 2, 200, 100)
                """
            ),
            {"job_id": "job-with-groups", "signature": "sig-1"},
        )
        session.commit()

    response = api_client.delete("/api/v1/scan/jobs/job-with-groups")
    assert response.status_code == 409
    assert "exact_groups=1" in response.json()["detail"]


def test_delete_scan_job_rejects_when_action_items_exist(
    api_client,
    api_session_factory: sessionmaker[Session],
) -> None:
    with api_session_factory() as session:
        _insert_scan_job(
            session,
            job_id="job-with-actions",
            mode="both",
            status="completed",
            requested_at="2026-03-13 07:00:00",
        )
        root_id = _insert_root(session, path="/nas/photo/api-03")
        file_id = session.execute(
            text(
                """
                INSERT INTO files(
                    root_id, rel_path, abs_path, file_name, size_bytes, mtime_epoch_ns,
                    first_seen_job_id, last_seen_job_id
                )
                VALUES (
                    :root_id, :rel_path, :abs_path, :file_name, :size_bytes, :mtime_epoch_ns,
                    :first_seen_job_id, :last_seen_job_id
                )
                """
            ),
            {
                "root_id": root_id,
                "rel_path": "album/a.jpg",
                "abs_path": "/nas/photo/api-03/album/a.jpg",
                "file_name": "a.jpg",
                "size_bytes": 128,
                "mtime_epoch_ns": 123456,
                "first_seen_job_id": "job-with-actions",
                "last_seen_job_id": "job-with-actions",
            },
        ).lastrowid
        assert file_id is not None

        session.execute(
            text(
                """
                INSERT INTO action_batches(id, status, action_type, requested_by, dry_run)
                VALUES ('batch-api-03', 'executed', 'move_to_trash', 'local_admin', 0)
                """
            )
        )
        session.execute(
            text(
                """
                INSERT INTO action_items(batch_id, file_id, source_path, target_path, status)
                VALUES (:batch_id, :file_id, :source_path, :target_path, :status)
                """
            ),
            {
                "batch_id": "batch-api-03",
                "file_id": int(file_id),
                "source_path": "/nas/photo/api-03/album/a.jpg",
                "target_path": "/nas/.nas-diff-trash/album/a.jpg",
                "status": "done",
            },
        )
        session.commit()

    response = api_client.delete("/api/v1/scan/jobs/job-with-actions")
    assert response.status_code == 409
    assert "action_items=1" in response.json()["detail"]
