from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.api import routes_health


def test_health_reports_api_database_and_redis(api_client, monkeypatch) -> None:
    monkeypatch.setattr(routes_health, "_check_api", lambda: {"status": "ok", "detail": "API reachable"})
    monkeypatch.setattr(
        routes_health,
        "_check_sqlite",
        lambda _database_url: {"status": "ok", "detail": "SQLite reachable"},
    )
    monkeypatch.setattr(
        routes_health,
        "_check_redis",
        lambda _redis_url: {"status": "error", "detail": "Redis unavailable"},
    )

    response = api_client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()

    assert payload["status"] == "degraded"
    assert payload["components"]["api"]["status"] == "ok"
    assert payload["components"]["database"]["status"] == "ok"
    assert payload["components"]["redis"]["status"] == "error"


def test_scan_roots_crud_and_path_validation(api_client) -> None:
    invalid_relative = api_client.post("/api/v1/scan/roots", json={"path": "nas/photo"})
    assert invalid_relative.status_code == 422
    assert invalid_relative.json()["detail"] == "path must be absolute"

    invalid_outside_mount = api_client.post("/api/v1/scan/roots", json={"path": "/tmp/photo"})
    assert invalid_outside_mount.status_code == 422
    assert invalid_outside_mount.json()["detail"] == "path must be under '/nas'"

    created = api_client.post("/api/v1/scan/roots", json={"path": "/nas/photo/../archive/"})
    assert created.status_code == 201

    created_payload = created.json()
    root_id = created_payload["id"]
    assert created_payload["path"] == "/nas/archive"
    assert created_payload["enabled"] is True

    duplicate = api_client.post("/api/v1/scan/roots", json={"path": "/nas/archive/"})
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "scan root '/nas/archive' already exists"

    listed = api_client.get("/api/v1/scan/roots")
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [root_id]

    disabled = api_client.patch(f"/api/v1/scan/roots/{root_id}", json={"enabled": False})
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False

    deleted = api_client.delete(f"/api/v1/scan/roots/{root_id}")
    assert deleted.status_code == 204

    listed_after_delete = api_client.get("/api/v1/scan/roots")
    assert listed_after_delete.status_code == 200
    assert listed_after_delete.json() == []


def test_delete_scan_root_referenced_by_scan_job_returns_conflict(
    api_client,
    api_session_factory: sessionmaker[Session],
) -> None:
    created = api_client.post("/api/v1/scan/roots", json={"path": "/nas/photo"})
    assert created.status_code == 201
    root_id = created.json()["id"]

    job_id = f"job-{uuid.uuid4().hex}"
    with api_session_factory() as session:
        session.execute(
            text(
                """
                INSERT INTO scan_jobs(id, mode, status)
                VALUES (:job_id, 'exact', 'queued')
                """
            ),
            {"job_id": job_id},
        )
        session.execute(
            text(
                """
                INSERT INTO scan_job_roots(job_id, root_id)
                VALUES (:job_id, :root_id)
                """
            ),
            {"job_id": job_id, "root_id": root_id},
        )
        session.commit()

    response = api_client.delete(f"/api/v1/scan/roots/{root_id}")
    assert response.status_code == 409
    assert response.json()["detail"] == f"scan_root={root_id} is referenced by existing scan jobs"
