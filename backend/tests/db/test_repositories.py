from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.repositories.actions import ActionItemPayload, ActionRepository
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
