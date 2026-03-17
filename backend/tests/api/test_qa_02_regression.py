from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.services.action_service import ActionService
from app.services.scan_orchestrator import run_scan_job


def test_regression_roots_jobs_bulk_preview_confirm_execute_rollback(
    api_client,
    api_session_factory: sessionmaker[Session],
    fake_scan_queue,
    fake_action_queue,
    test_settings,
    tmp_path,
) -> None:
    root_create = api_client.post("/api/v1/scan/roots", json={"path": "/nas/photo/qa-02-root"})
    assert root_create.status_code == 201
    root_id = root_create.json()["id"]

    with api_session_factory() as session:
        session.execute(
            text("INSERT INTO scan_jobs(id, mode, status) VALUES ('qa-02-root-job', 'exact', 'queued')")
        )
        session.execute(
            text("INSERT INTO scan_job_roots(job_id, root_id) VALUES ('qa-02-root-job', :root_id)"),
            {"root_id": root_id},
        )
        session.commit()

    root_delete_conflict = api_client.delete(f"/api/v1/scan/roots/{root_id}")
    assert root_delete_conflict.status_code == 409

    dataset_root = tmp_path / "qa-02-dataset"
    dataset_root.mkdir(parents=True, exist_ok=True)
    file_a = dataset_root / "a.jpg"
    file_b = dataset_root / "b.jpg"
    file_a.write_bytes(b"Q" * 256)
    file_b.write_bytes(b"Q" * 256)

    with api_session_factory() as session:
        fs_root_id = session.execute(
            text("INSERT INTO scan_roots(path, enabled) VALUES (:path, 1)"),
            {"path": str(dataset_root)},
        ).lastrowid
        session.commit()
    assert fs_root_id is not None

    create_job = api_client.post(
        "/api/v1/scan/jobs",
        json={"mode": "exact", "root_ids": [int(fs_root_id)]},
    )
    assert create_job.status_code == 201
    job_id = create_job.json()["job_id"]
    assert fake_scan_queue.enqueued_job_ids == [job_id]

    with api_session_factory() as session:
        run_scan_job(session, test_settings, job_id=job_id)

    jobs_list = api_client.get("/api/v1/scan/jobs", params={"status": "completed", "mode": "exact"})
    assert jobs_list.status_code == 200
    assert any(item["job_id"] == job_id for item in jobs_list.json()["items"])

    exact_groups = api_client.get(f"/api/v1/scan/jobs/{job_id}/groups", params={"kind": "exact"})
    assert exact_groups.status_code == 200
    group_id = exact_groups.json()["items"][0]["id"]

    details = api_client.get(f"/api/v1/groups/exact/{group_id}")
    assert details.status_code == 200
    items = details.json()["items"]
    assert len(items) == 2
    target_file_id = [item for item in items if item["is_primary"] is False][0]["file_id"]

    preview = api_client.post(
        "/api/v1/actions/batches/preview",
        json={"action_type": "move_to_trash", "file_ids": [target_file_id]},
    )
    assert preview.status_code == 200
    preview_payload = preview.json()
    assert preview_payload["files_count"] == 1
    assert preview_payload["total_bytes"] == 256

    create_batch = api_client.post(
        "/api/v1/actions/batches",
        json={"action_type": "move_to_trash", "file_ids": [target_file_id]},
    )
    assert create_batch.status_code == 201
    batch_id = create_batch.json()["batch_id"]

    confirm_batch = api_client.post(f"/api/v1/actions/batches/{batch_id}/confirm", json={})
    assert confirm_batch.status_code == 200
    assert fake_action_queue.enqueued_batch_ids == [batch_id]

    with api_session_factory() as session:
        ActionService(session, test_settings).execute_confirmed_batch(batch_id=batch_id)

    executed = api_client.get(f"/api/v1/actions/batches/{batch_id}")
    assert executed.status_code == 200
    assert executed.json()["status"] == "executed"
    moved_path = Path(executed.json()["items"][0]["target_path"])
    assert moved_path.exists()

    rollback = api_client.post(f"/api/v1/actions/batches/{batch_id}/rollback", json={"requested_by": "qa-suite"})
    assert rollback.status_code == 200
    rollback_batch_id = rollback.json()["rollback_batch_id"]
    assert fake_action_queue.enqueued_batch_ids == [batch_id, rollback_batch_id]

    with api_session_factory() as session:
        ActionService(session, test_settings).execute_confirmed_batch(batch_id=rollback_batch_id)

    source_after_rollback = api_client.get(f"/api/v1/actions/batches/{batch_id}")
    assert source_after_rollback.status_code == 200
    assert source_after_rollback.json()["status"] == "rolled_back"

    assert file_a.exists()
    assert file_b.exists()
    assert not moved_path.exists()
