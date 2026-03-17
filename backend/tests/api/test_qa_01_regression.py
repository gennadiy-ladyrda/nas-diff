from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.services.action_service import ActionService
from app.services.scan_orchestrator import run_scan_job


def test_regression_scan_review_actions_rollback(
    api_client,
    api_session_factory: sessionmaker[Session],
    fake_scan_queue,
    fake_action_queue,
    test_settings,
    tmp_path,
) -> None:
    dataset_root = tmp_path / "qa-regression"
    dataset_root.mkdir(parents=True, exist_ok=True)
    file_a = dataset_root / "a.jpg"
    file_b = dataset_root / "b.jpg"
    file_a.write_bytes(b"R" * 256)
    file_b.write_bytes(b"R" * 256)

    with api_session_factory() as session:
        root_id = session.execute(
            text("INSERT INTO scan_roots(path, enabled) VALUES (:path, 1)"),
            {"path": str(dataset_root)},
        ).lastrowid
        session.commit()
    assert root_id is not None

    create_job = api_client.post(
        "/api/v1/scan/jobs",
        json={"mode": "both", "root_ids": [int(root_id)]},
    )
    assert create_job.status_code == 201
    job_id = create_job.json()["job_id"]
    assert fake_scan_queue.enqueued_job_ids == [job_id]

    with api_session_factory() as session:
        run_scan_job(session, test_settings, job_id=job_id)

    groups = api_client.get(f"/api/v1/scan/jobs/{job_id}/groups", params={"kind": "exact"})
    assert groups.status_code == 200
    group_id = groups.json()["items"][0]["id"]

    details_before = api_client.get(f"/api/v1/groups/exact/{group_id}")
    assert details_before.status_code == 200
    items_before = details_before.json()["items"]
    assert len(items_before) == 2

    current_primary = [item for item in items_before if item["is_primary"] is True][0]["file_id"]
    new_primary = [item for item in items_before if item["file_id"] != current_primary][0]["file_id"]

    decision_response = api_client.post(
        f"/api/v1/groups/exact/{group_id}/decision",
        json={"file_id": new_primary, "decision": "keep", "note": "qa regression"},
    )
    assert decision_response.status_code == 200

    details_after = api_client.get(f"/api/v1/groups/exact/{group_id}")
    assert details_after.status_code == 200
    primary_after = [item for item in details_after.json()["items"] if item["is_primary"] is True][0]["file_id"]
    assert primary_after == new_primary

    # Move the non-primary file and then rollback it.
    target_file_id = [item for item in details_after.json()["items"] if item["file_id"] != new_primary][0]["file_id"]

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

    executed_batch = api_client.get(f"/api/v1/actions/batches/{batch_id}")
    assert executed_batch.status_code == 200
    executed_payload = executed_batch.json()
    assert executed_payload["status"] == "executed"
    moved_path = Path(executed_payload["items"][0]["target_path"])

    rollback = api_client.post(
        f"/api/v1/actions/batches/{batch_id}/rollback",
        json={"requested_by": "qa-suite"},
    )
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
