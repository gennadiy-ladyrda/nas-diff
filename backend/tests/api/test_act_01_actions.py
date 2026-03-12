from __future__ import annotations

from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session, sessionmaker

from app.services.action_service import ActionService


def _insert_root_and_file(
    session: Session,
    *,
    root_path: str,
    file_abs_path: str,
    rel_path: str,
) -> int:
    root_id = session.execute(
        text("INSERT INTO scan_roots(path, enabled) VALUES (:path, 1)"),
        {"path": root_path},
    ).lastrowid
    assert root_id is not None

    file_id = session.execute(
        text(
            """
            INSERT INTO files(root_id, rel_path, abs_path, file_name, size_bytes, mtime_epoch_ns)
            VALUES (:root_id, :rel_path, :abs_path, :file_name, :size_bytes, :mtime_epoch_ns)
            """
        ),
        {
            "root_id": int(root_id),
            "rel_path": rel_path,
            "abs_path": file_abs_path,
            "file_name": Path(rel_path).name,
            "size_bytes": 256,
            "mtime_epoch_ns": 123,
        },
    ).lastrowid
    assert file_id is not None

    session.commit()
    return int(file_id)


def test_actions_move_to_trash_and_rollback_flow(
    api_client,
    api_session_factory: sessionmaker[Session],
    fake_action_queue,
    test_settings,
    tmp_path,
) -> None:
    dataset_root = tmp_path / "actions-dataset"
    dataset_root.mkdir(parents=True, exist_ok=True)
    original_file = dataset_root / "a.jpg"
    original_file.write_bytes(b"A" * 256)

    with api_session_factory() as session:
        file_id = _insert_root_and_file(
            session,
            root_path=str(dataset_root),
            file_abs_path=str(original_file),
            rel_path="a.jpg",
        )

    create_response = api_client.post(
        "/api/v1/actions/batches",
        json={
            "action_type": "move_to_trash",
            "file_ids": [file_id],
        },
    )
    assert create_response.status_code == 201
    created_payload = create_response.json()
    batch_id = created_payload["batch_id"]
    assert created_payload["status"] == "draft"
    assert created_payload["stats"]["pending"] == 1

    confirm_response = api_client.post(f"/api/v1/actions/batches/{batch_id}/confirm", json={})
    assert confirm_response.status_code == 200
    assert confirm_response.json()["status"] == "confirmed"
    assert fake_action_queue.enqueued_batch_ids == [batch_id]

    with api_session_factory() as session:
        ActionService(session, test_settings).execute_confirmed_batch(batch_id=batch_id)

    executed_response = api_client.get(f"/api/v1/actions/batches/{batch_id}")
    assert executed_response.status_code == 200
    executed_payload = executed_response.json()
    assert executed_payload["status"] == "executed"
    assert executed_payload["stats"]["done"] == 1

    moved_item = executed_payload["items"][0]
    moved_path = Path(moved_item["target_path"])
    assert not original_file.exists()
    assert moved_path.exists()

    rollback_response = api_client.post(
        f"/api/v1/actions/batches/{batch_id}/rollback",
        json={"requested_by": "tester"},
    )
    assert rollback_response.status_code == 200
    rollback_batch_id = rollback_response.json()["rollback_batch_id"]
    assert fake_action_queue.enqueued_batch_ids == [batch_id, rollback_batch_id]

    with api_session_factory() as session:
        ActionService(session, test_settings).execute_confirmed_batch(batch_id=rollback_batch_id)

    source_batch_after_rollback = api_client.get(f"/api/v1/actions/batches/{batch_id}")
    assert source_batch_after_rollback.status_code == 200
    assert source_batch_after_rollback.json()["status"] == "rolled_back"

    rollback_batch = api_client.get(f"/api/v1/actions/batches/{rollback_batch_id}")
    assert rollback_batch.status_code == 200
    assert rollback_batch.json()["status"] == "executed"

    assert original_file.exists()
    assert not moved_path.exists()


def test_delete_permanent_is_blocked_when_flag_is_disabled(
    api_client,
    api_session_factory: sessionmaker[Session],
    test_settings,
    tmp_path,
) -> None:
    dataset_root = tmp_path / "actions-delete"
    dataset_root.mkdir(parents=True, exist_ok=True)
    original_file = dataset_root / "delete-me.jpg"
    original_file.write_bytes(b"B" * 64)

    with api_session_factory() as session:
        file_id = _insert_root_and_file(
            session,
            root_path=str(dataset_root),
            file_abs_path=str(original_file),
            rel_path="delete-me.jpg",
        )

    create_response = api_client.post(
        "/api/v1/actions/batches",
        json={
            "action_type": "delete_permanent",
            "file_ids": [file_id],
        },
    )
    assert create_response.status_code == 201
    batch_id = create_response.json()["batch_id"]

    confirm_response = api_client.post(
        f"/api/v1/actions/batches/{batch_id}/confirm",
        json={"confirm_delete_permanent": True},
    )
    assert confirm_response.status_code == 403
    assert "HARD_DELETE_ENABLED=false" in confirm_response.json()["detail"]

    batch_response = api_client.get(f"/api/v1/actions/batches/{batch_id}")
    assert batch_response.status_code == 200
    assert batch_response.json()["status"] == "draft"

    assert test_settings.hard_delete_enabled is False
    assert original_file.exists()


def test_action_failure_is_recorded_in_item_error_message(
    api_client,
    api_session_factory: sessionmaker[Session],
    fake_action_queue,
    test_settings,
    tmp_path,
) -> None:
    dataset_root = tmp_path / "actions-failure"
    dataset_root.mkdir(parents=True, exist_ok=True)
    missing_file = dataset_root / "missing.jpg"

    with api_session_factory() as session:
        file_id = _insert_root_and_file(
            session,
            root_path=str(dataset_root),
            file_abs_path=str(missing_file),
            rel_path="missing.jpg",
        )

    create_response = api_client.post(
        "/api/v1/actions/batches",
        json={
            "action_type": "move_to_trash",
            "file_ids": [file_id],
        },
    )
    assert create_response.status_code == 201
    batch_id = create_response.json()["batch_id"]

    confirm_response = api_client.post(f"/api/v1/actions/batches/{batch_id}/confirm", json={})
    assert confirm_response.status_code == 200
    assert fake_action_queue.enqueued_batch_ids == [batch_id]

    with api_session_factory() as session:
        ActionService(session, test_settings).execute_confirmed_batch(batch_id=batch_id)

    batch_response = api_client.get(f"/api/v1/actions/batches/{batch_id}")
    assert batch_response.status_code == 200
    payload = batch_response.json()
    assert payload["status"] == "failed"
    assert payload["stats"]["failed"] == 1
    assert payload["items"][0]["error_message"]
