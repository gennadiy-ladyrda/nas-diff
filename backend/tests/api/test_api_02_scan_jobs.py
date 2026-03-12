from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.services.scan_orchestrator import run_scan_job


def test_scan_job_lifecycle_create_run_status_groups(
    api_client,
    api_session_factory: sessionmaker[Session],
    fake_scan_queue,
    test_settings,
    tmp_path,
) -> None:
    dataset_root = tmp_path / "dataset"
    dataset_root.mkdir(parents=True, exist_ok=True)
    (dataset_root / "a.jpg").write_bytes(b"A" * 256)
    (dataset_root / "b.jpg").write_bytes(b"A" * 256)
    (dataset_root / "c.jpg").write_bytes((b"A" * 128) + (b"B" * 128))

    with api_session_factory() as session:
        root_id = session.execute(
            text("INSERT INTO scan_roots(path, enabled) VALUES (:path, 1)"),
            {"path": str(dataset_root)},
        ).lastrowid
        session.commit()
    assert root_id is not None

    create_response = api_client.post(
        "/api/v1/scan/jobs",
        json={"mode": "both", "root_ids": [int(root_id)]},
    )
    assert create_response.status_code == 201
    created = create_response.json()
    job_id = created["job_id"]

    assert created["status"] == "queued"
    assert created["root_ids"] == [int(root_id)]
    assert fake_scan_queue.enqueued_job_ids == [job_id]

    with api_session_factory() as session:
        run_scan_job(session, test_settings, job_id=job_id)

    status_response = api_client.get(f"/api/v1/scan/jobs/{job_id}")
    assert status_response.status_code == 200
    status_payload = status_response.json()
    assert status_payload["status"] == "completed"
    assert status_payload["files_seen"] == 3
    assert status_payload["files_indexed"] == 3
    assert status_payload["exact_groups_found"] >= 1
    assert status_payload["similar_groups_found"] >= 1

    exact_groups = api_client.get(f"/api/v1/scan/jobs/{job_id}/groups", params={"kind": "exact"})
    assert exact_groups.status_code == 200
    exact_payload = exact_groups.json()
    assert exact_payload["total"] >= 1
    assert len(exact_payload["items"]) >= 1

    similar_groups = api_client.get(f"/api/v1/scan/jobs/{job_id}/groups", params={"kind": "similar"})
    assert similar_groups.status_code == 200
    similar_payload = similar_groups.json()
    assert similar_payload["total"] >= 1
    assert len(similar_payload["items"]) >= 1


def test_scan_job_idempotency_key_returns_existing_job(
    api_client,
    api_session_factory: sessionmaker[Session],
    fake_scan_queue,
    tmp_path,
) -> None:
    dataset_root = tmp_path / "dataset-idempotent"
    dataset_root.mkdir(parents=True, exist_ok=True)
    (dataset_root / "a.jpg").write_bytes(b"content")

    with api_session_factory() as session:
        root_id = session.execute(
            text("INSERT INTO scan_roots(path, enabled) VALUES (:path, 1)"),
            {"path": str(dataset_root)},
        ).lastrowid
        session.commit()
    assert root_id is not None

    payload = {
        "mode": "exact",
        "root_ids": [int(root_id)],
        "idempotency_key": "job-key-1",
    }
    created = api_client.post("/api/v1/scan/jobs", json=payload)
    assert created.status_code == 201
    first_job_id = created.json()["job_id"]

    repeated = api_client.post("/api/v1/scan/jobs", json=payload)
    assert repeated.status_code == 201
    assert repeated.json()["job_id"] == first_job_id

    assert fake_scan_queue.enqueued_job_ids.count(first_job_id) == 1
