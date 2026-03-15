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
    size_bytes: int = 256,
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
            "size_bytes": size_bytes,
            "mtime_epoch_ns": 123,
        },
    ).lastrowid
    assert file_id is not None

    session.commit()
    return int(file_id)


def _insert_scan_job(session: Session, *, job_id: str, mode: str = "both", status: str = "completed") -> None:
    session.execute(
        text(
            """
            INSERT INTO scan_jobs(
                id, mode, status, requested_at,
                files_seen, files_indexed, exact_groups_found, similar_groups_found, reclaimable_bytes
            )
            VALUES (
                :job_id, :mode, :status, '2026-03-15 10:00:00',
                0, 0, 0, 0, 0
            )
            """
        ),
        {
            "job_id": job_id,
            "mode": mode,
            "status": status,
        },
    )


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


def test_actions_preview_returns_counts_and_bytes(
    api_client,
    api_session_factory: sessionmaker[Session],
    tmp_path,
) -> None:
    dataset_root_a = tmp_path / "actions-preview-a"
    dataset_root_b = tmp_path / "actions-preview-b"
    dataset_root_a.mkdir(parents=True, exist_ok=True)
    dataset_root_b.mkdir(parents=True, exist_ok=True)
    file_a = dataset_root_a / "a.jpg"
    file_b = dataset_root_b / "b.jpg"
    file_a.write_bytes(b"A" * 128)
    file_b.write_bytes(b"B" * 512)

    with api_session_factory() as session:
        file_id_a = _insert_root_and_file(
            session,
            root_path=str(dataset_root_a),
            file_abs_path=str(file_a),
            rel_path="a.jpg",
            size_bytes=128,
        )
        file_id_b = _insert_root_and_file(
            session,
            root_path=str(dataset_root_b),
            file_abs_path=str(file_b),
            rel_path="b.jpg",
            size_bytes=512,
        )

    preview_response = api_client.post(
        "/api/v1/actions/batches/preview",
        json={
            "action_type": "move_to_trash",
            "file_ids": [file_id_a, file_id_b],
        },
    )
    assert preview_response.status_code == 200
    payload = preview_response.json()
    assert payload["action_type"] == "move_to_trash"
    assert payload["files_count"] == 2
    assert payload["total_bytes"] == 640
    assert payload["estimated_reclaimable_bytes"] == 640


def test_actions_preview_restore_requires_unrestored_movements(
    api_client,
    api_session_factory: sessionmaker[Session],
    tmp_path,
) -> None:
    dataset_root = tmp_path / "actions-preview-restore"
    dataset_root.mkdir(parents=True, exist_ok=True)
    file_restore = dataset_root / "restore-me.jpg"
    file_restore.write_bytes(b"R" * 32)

    with api_session_factory() as session:
        file_id = _insert_root_and_file(
            session,
            root_path=str(dataset_root),
            file_abs_path=str(file_restore),
            rel_path="restore-me.jpg",
            size_bytes=32,
        )

    preview_response = api_client.post(
        "/api/v1/actions/batches/preview",
        json={
            "action_type": "restore",
            "file_ids": [file_id],
        },
    )
    assert preview_response.status_code == 404
    assert "no unrestored movement found" in preview_response.json()["detail"]


def test_scan_job_action_preview_aggregates_non_primary_files_across_group_kinds(
    api_client,
    api_session_factory: sessionmaker[Session],
    tmp_path,
) -> None:
    dataset_root = tmp_path / "actions-job-preview"
    root_a = dataset_root / "root-a"
    root_b = dataset_root / "root-b"
    root_c = dataset_root / "root-c"
    root_a.mkdir(parents=True, exist_ok=True)
    root_b.mkdir(parents=True, exist_ok=True)
    root_c.mkdir(parents=True, exist_ok=True)
    file_a = root_a / "a.jpg"
    file_b = root_b / "b.jpg"
    file_c = root_c / "c.jpg"
    file_a.write_bytes(b"A" * 100)
    file_b.write_bytes(b"B" * 200)
    file_c.write_bytes(b"C" * 300)

    with api_session_factory() as session:
        _insert_scan_job(session, job_id="job-action-source")
        file_id_a = _insert_root_and_file(
            session,
            root_path=str(root_a),
            file_abs_path=str(file_a),
            rel_path="a.jpg",
            size_bytes=100,
        )
        file_id_b = _insert_root_and_file(
            session,
            root_path=str(root_b),
            file_abs_path=str(file_b),
            rel_path="b.jpg",
            size_bytes=200,
        )
        file_id_c = _insert_root_and_file(
            session,
            root_path=str(root_c),
            file_abs_path=str(file_c),
            rel_path="c.jpg",
            size_bytes=300,
        )

        exact_group_id = session.execute(
            text(
                """
                INSERT INTO exact_groups(job_id, signature, file_count, total_bytes, reclaimable_bytes)
                VALUES ('job-action-source', 'sig-1', 2, 300, 200)
                """
            )
        ).lastrowid
        similar_group_id = session.execute(
            text(
                """
                INSERT INTO similar_groups(job_id, algorithm, threshold, file_count)
                VALUES ('job-action-source', 'phash64', 8, 2)
                """
            )
        ).lastrowid
        assert exact_group_id is not None
        assert similar_group_id is not None

        session.execute(
            text(
                """
                INSERT INTO exact_group_items(group_id, file_id, is_primary)
                VALUES (:group_id, :file_primary, 1), (:group_id, :file_secondary, 0)
                """
            ),
            {
                "group_id": int(exact_group_id),
                "file_primary": file_id_a,
                "file_secondary": file_id_b,
            },
        )
        session.execute(
            text(
                """
                INSERT INTO similar_group_items(group_id, file_id, distance_to_anchor, is_primary)
                VALUES
                    (:group_id, :file_existing_secondary, 0, 0),
                    (:group_id, :file_new_secondary, 4, 0)
                """
            ),
            {
                "group_id": int(similar_group_id),
                "file_existing_secondary": file_id_b,
                "file_new_secondary": file_id_c,
            },
        )
        session.commit()

    preview_response = api_client.post(
        "/api/v1/actions/jobs/job-action-source/preview",
        json={"action_type": "move_to_trash"},
    )
    assert preview_response.status_code == 200
    payload = preview_response.json()
    assert payload["job_id"] == "job-action-source"
    assert payload["file_ids"] == [file_id_b, file_id_c]
    assert payload["files_count"] == 2
    assert payload["total_bytes"] == 500
    assert payload["estimated_reclaimable_bytes"] == 500


def test_scan_job_action_batch_creates_draft_from_aggregated_file_scope(
    api_client,
    api_session_factory: sessionmaker[Session],
    tmp_path,
) -> None:
    dataset_root = tmp_path / "actions-job-batch"
    root_a = dataset_root / "root-a"
    root_b = dataset_root / "root-b"
    root_a.mkdir(parents=True, exist_ok=True)
    root_b.mkdir(parents=True, exist_ok=True)
    file_a = root_a / "dup-a.jpg"
    file_b = root_b / "dup-b.jpg"
    file_a.write_bytes(b"A" * 64)
    file_b.write_bytes(b"B" * 96)

    with api_session_factory() as session:
        _insert_scan_job(session, job_id="job-action-batch")
        file_id_a = _insert_root_and_file(
            session,
            root_path=str(root_a),
            file_abs_path=str(file_a),
            rel_path="dup-a.jpg",
            size_bytes=64,
        )
        file_id_b = _insert_root_and_file(
            session,
            root_path=str(root_b),
            file_abs_path=str(file_b),
            rel_path="dup-b.jpg",
            size_bytes=96,
        )

        exact_group_id = session.execute(
            text(
                """
                INSERT INTO exact_groups(job_id, signature, file_count, total_bytes, reclaimable_bytes)
                VALUES ('job-action-batch', 'sig-2', 2, 160, 96)
                """
            )
        ).lastrowid
        assert exact_group_id is not None
        session.execute(
            text(
                """
                INSERT INTO exact_group_items(group_id, file_id, is_primary)
                VALUES (:group_id, :file_primary, 1), (:group_id, :file_secondary, 0)
                """
            ),
            {
                "group_id": int(exact_group_id),
                "file_primary": file_id_a,
                "file_secondary": file_id_b,
            },
        )
        session.commit()

    create_response = api_client.post(
        "/api/v1/actions/jobs/job-action-batch/batches",
        json={"action_type": "move_to_trash"},
    )
    assert create_response.status_code == 201
    payload = create_response.json()
    assert payload["action_type"] == "move_to_trash"
    assert payload["status"] == "draft"
    assert payload["stats"]["total"] == 1
    assert payload["items"][0]["file_id"] == file_id_b
    assert payload["summary"] == "scan_job=job-action-batch;scope=all_non_primary_groups"
