from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.repositories.actions import ActionItemPayload, ActionRepository
from app.db.repositories.decisions import UserDecisionRepository
from app.db.repositories.file_hashes import FileHashRepository
from app.db.repositories.files import FileRepository
from app.db.repositories.groups import ExactGroupMember, GroupRepository, SimilarGroupMember
from app.db.repositories.scan_jobs import ScanJobRepository
from tests.db.helpers import seed_root_and_job


def _insert_file(session: Session, *, root_id: int, rel_path: str, abs_path: str) -> int:
    file_id = session.execute(
        text(
            """
            INSERT INTO files(root_id, rel_path, abs_path, file_name, size_bytes, mtime_epoch_ns)
            VALUES (:root_id, :rel_path, :abs_path, :file_name, :size_bytes, :mtime)
            """
        ),
        {
            "root_id": root_id,
            "rel_path": rel_path,
            "abs_path": abs_path,
            "file_name": rel_path.split("/")[-1],
            "size_bytes": 100,
            "mtime": 123,
        },
    ).lastrowid
    session.commit()
    return int(file_id)


def _insert_scan_job(
    session: Session,
    *,
    job_id: str,
    mode: str,
    status: str,
    requested_at: str,
) -> None:
    session.execute(
        text(
            """
            INSERT INTO scan_jobs(
                id, mode, status, requested_at,
                files_seen, files_indexed, exact_groups_found, similar_groups_found, reclaimable_bytes
            )
            VALUES (
                :job_id, :mode, :status, :requested_at,
                0, 0, 0, 0, 0
            )
            """
        ),
        {
            "job_id": job_id,
            "mode": mode,
            "status": status,
            "requested_at": requested_at,
        },
    )


def test_scan_job_repository_crud(session: Session) -> None:
    repo = ScanJobRepository(session)

    created = repo.create(job_id="job-repo", mode="exact")
    assert created.status == "queued"

    updated = repo.update_status("job-repo", status="running", set_started_at=True)
    assert updated.status == "running"
    assert updated.started_at is not None

    metrics = repo.update_metrics(
        "job-repo",
        files_seen=11,
        files_indexed=10,
        exact_groups_found=2,
        similar_groups_found=1,
        reclaimable_bytes=500,
    )
    assert metrics.files_seen == 11
    assert metrics.reclaimable_bytes == 500


def test_scan_job_repository_list_and_delete_dependencies(session: Session) -> None:
    root_id, job_id = seed_root_and_job(session, job_id="job-deps")
    repo = ScanJobRepository(session)

    _insert_scan_job(
        session,
        job_id="job-list-old",
        mode="exact",
        status="completed",
        requested_at="2026-03-13 10:00:00",
    )
    _insert_scan_job(
        session,
        job_id="job-list-new",
        mode="both",
        status="completed",
        requested_at="2026-03-13 11:00:00",
    )

    file_id = _insert_file(session, root_id=root_id, rel_path="deps.jpg", abs_path="/nas/photo/deps.jpg")
    session.execute(
        text(
            """
            UPDATE files
            SET first_seen_job_id = :job_id, last_seen_job_id = :job_id
            WHERE id = :file_id
            """
        ),
        {"job_id": job_id, "file_id": file_id},
    )
    session.execute(
        text(
            """
            INSERT INTO exact_groups(job_id, signature, file_count, total_bytes, reclaimable_bytes)
            VALUES (:job_id, 'sig-deps', 2, 200, 100)
            """
        ),
        {"job_id": job_id},
    )
    session.execute(
        text(
            """
            INSERT INTO similar_groups(job_id, algorithm, threshold, file_count)
            VALUES (:job_id, 'phash64', 8, 2)
            """
        ),
        {"job_id": job_id},
    )
    session.execute(
        text(
            """
            INSERT INTO action_batches(id, status, action_type, requested_by, dry_run)
            VALUES ('batch-deps', 'executed', 'move_to_trash', 'local_admin', 0)
            """
        )
    )
    session.execute(
        text(
            """
            INSERT INTO action_items(batch_id, file_id, source_path, target_path, status)
            VALUES ('batch-deps', :file_id, '/nas/photo/deps.jpg', '/nas/.nas-diff-trash/deps.jpg', 'done')
            """
        ),
        {"file_id": file_id},
    )
    session.commit()

    jobs, total = repo.list_jobs(status="completed", mode=None, page=1, page_size=10, order="desc")
    assert total >= 2
    listed_ids = [job.id for job in jobs]
    assert "job-list-new" in listed_ids
    assert "job-list-old" in listed_ids
    assert listed_ids.index("job-list-new") < listed_ids.index("job-list-old")

    deps = repo.count_delete_dependencies(job_id)
    assert deps.exact_groups == 1
    assert deps.similar_groups == 1
    assert deps.action_items == 1
    assert deps.has_blockers


def test_file_repository_upsert(session: Session) -> None:
    root_id, job_id = seed_root_and_job(session)
    repo = FileRepository(session)

    created = repo.upsert(
        root_id=root_id,
        rel_path="album/a.jpg",
        abs_path="/nas/photo/album/a.jpg",
        file_name="a.jpg",
        size_bytes=101,
        mtime_epoch_ns=1000,
        first_seen_job_id=job_id,
        last_seen_job_id=job_id,
    )
    assert created.id is not None
    assert created.size_bytes == 101

    updated = repo.upsert(
        root_id=root_id,
        rel_path="album/a.jpg",
        abs_path="/nas/photo/album/a.jpg",
        file_name="a.jpg",
        size_bytes=202,
        mtime_epoch_ns=2000,
        last_seen_job_id=job_id,
    )
    assert updated.id == created.id
    assert updated.size_bytes == 202


def test_group_repository_exact_and_similar(session: Session) -> None:
    root_id, job_id = seed_root_and_job(session)
    file1 = _insert_file(session, root_id=root_id, rel_path="a.jpg", abs_path="/nas/photo/a.jpg")
    file2 = _insert_file(session, root_id=root_id, rel_path="b.jpg", abs_path="/nas/photo/b.jpg")

    repo = GroupRepository(session)

    exact = repo.create_exact_group(
        job_id=job_id,
        signature="abc",
        total_bytes=200,
        reclaimable_bytes=100,
        members=[
            ExactGroupMember(file_id=file1, is_primary=1),
            ExactGroupMember(file_id=file2, is_primary=0),
        ],
    )
    exact_items = repo.list_exact_items(group_id=exact.id)
    assert len(exact_items) == 2

    repo.set_exact_primary(group_id=exact.id, file_id=file2)
    exact_items = repo.list_exact_items(group_id=exact.id)
    assert [item.file_id for item in exact_items if item.is_primary == 1] == [file2]

    similar = repo.create_similar_group(
        job_id=job_id,
        algorithm="phash64",
        threshold=8,
        members=[
            SimilarGroupMember(file_id=file1, distance_to_anchor=0, is_primary=1),
            SimilarGroupMember(file_id=file2, distance_to_anchor=3),
        ],
    )
    similar_items = repo.list_similar_items(group_id=similar.id)
    assert len(similar_items) == 2


def test_action_repository_batch_and_items(session: Session) -> None:
    root_id, _ = seed_root_and_job(session)
    file_id = _insert_file(session, root_id=root_id, rel_path="c.jpg", abs_path="/nas/photo/c.jpg")

    repo = ActionRepository(session)
    batch = repo.create_batch(batch_id="batch-1", action_type="move_to_trash")
    assert batch.status == "draft"

    items = repo.add_items(
        batch_id=batch.id,
        items=[
            ActionItemPayload(
                file_id=file_id,
                source_path="/nas/photo/c.jpg",
                target_path="/nas/.nas-diff-trash/c.jpg",
            )
        ],
    )
    assert len(items) == 1
    assert items[0].status == "pending"

    updated_batch = repo.update_batch_status(batch.id, status="confirmed")
    assert updated_batch.confirmed_at is not None

    updated_item = repo.update_item_status(items[0].id, status="done")
    assert updated_item.executed_at is not None
    assert updated_item.status == "done"


def test_file_hash_repository_upsert(session: Session) -> None:
    root_id, _ = seed_root_and_job(session)
    file_id = _insert_file(session, root_id=root_id, rel_path="h.jpg", abs_path="/nas/photo/h.jpg")

    repo = FileHashRepository(session)
    created = repo.upsert(file_id=file_id, hash_type="blake3_full", hash_hex="abc")
    assert created.hash_hex == "abc"

    updated = repo.upsert(file_id=file_id, hash_type="blake3_full", hash_hex="def")
    assert updated.id == created.id
    assert updated.hash_hex == "def"


def test_user_decision_repository_upsert(session: Session) -> None:
    root_id, _ = seed_root_and_job(session)
    file_id = _insert_file(session, root_id=root_id, rel_path="d.jpg", abs_path="/nas/photo/d.jpg")

    repo = UserDecisionRepository(session)
    created = repo.upsert(
        group_kind="exact",
        group_id=1,
        file_id=file_id,
        decision="keep",
        note="first",
    )
    assert created.decision == "keep"
    assert created.note == "first"

    updated = repo.upsert(
        group_kind="exact",
        group_id=1,
        file_id=file_id,
        decision="trash",
        note="override",
    )
    assert updated.id == created.id
    assert updated.decision == "trash"
