from __future__ import annotations

from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.dedup_exact import build_exact_groups
from app.core.dedup_similar import build_similar_groups
from app.core.decision_engine import apply_auto_primary_scoring
from app.core.hasher_similar import hamming_distance_hex
from app.core.scanner import scan_and_index
from app.db.models import ExactGroupItem, File, ScanRoot, SimilarGroupItem
from app.services.decision_service import DecisionService


def _insert_scan_job(session: Session, *, job_id: str, mode: str = "both") -> None:
    session.execute(
        text(
            """
            INSERT INTO scan_jobs(id, mode, status)
            VALUES (:job_id, :mode, 'queued')
            """
        ),
        {"job_id": job_id, "mode": mode},
    )
    session.commit()


def _insert_scan_root(session: Session, *, path: str) -> int:
    root_id = session.execute(
        text("INSERT INTO scan_roots(path, enabled) VALUES (:path, 1)"),
        {"path": path},
    ).lastrowid
    session.commit()
    assert root_id is not None
    return int(root_id)


def test_incremental_scan_skips_unchanged_and_marks_missing(session: Session, tmp_path: Path) -> None:
    dataset_root = tmp_path / "scan"
    dataset_root.mkdir(parents=True, exist_ok=True)
    file_a = dataset_root / "a.jpg"
    file_b = dataset_root / "b.jpg"
    file_a.write_bytes(b"alpha")
    file_b.write_bytes(b"beta")

    root_id = _insert_scan_root(session, path=str(dataset_root))
    root = session.get(ScanRoot, root_id)
    assert root is not None

    _insert_scan_job(session, job_id="job-core-1", mode="both")
    result_full = scan_and_index(session, job_id="job-core-1", roots=[root])
    assert result_full.files_seen == 2
    assert result_full.files_indexed == 2

    _insert_scan_job(session, job_id="job-core-2", mode="both")
    result_incremental = scan_and_index(session, job_id="job-core-2", roots=[root])
    assert result_incremental.files_seen == 2
    assert result_incremental.files_indexed == 0

    file_b.unlink()
    _insert_scan_job(session, job_id="job-core-3", mode="both")
    result_after_delete = scan_and_index(session, job_id="job-core-3", roots=[root])
    assert result_after_delete.files_seen == 1

    files = list(session.scalars(select(File).where(File.root_id == root_id).order_by(File.file_name.asc())))
    assert len(files) == 2
    presence = {file.file_name: file.is_present for file in files}
    assert presence["a.jpg"] == 1
    assert presence["b.jpg"] == 0


def test_exact_similar_and_decision_flow(session: Session, tmp_path: Path) -> None:
    dataset_root = tmp_path / "dedup"
    dataset_root.mkdir(parents=True, exist_ok=True)
    (dataset_root / "x.jpg").write_bytes(b"X" * 512)
    (dataset_root / "y.jpg").write_bytes(b"X" * 512)
    (dataset_root / "z.jpg").write_bytes((b"X" * 500) + (b"Y" * 12))

    root_id = _insert_scan_root(session, path=str(dataset_root))
    root = session.get(ScanRoot, root_id)
    assert root is not None

    _insert_scan_job(session, job_id="job-core-dedup", mode="both")
    scan_result = scan_and_index(session, job_id="job-core-dedup", roots=[root])
    assert scan_result.files_seen == 3

    exact = build_exact_groups(session, job_id="job-core-dedup", root_ids=[root_id])
    assert exact.groups_found >= 1
    assert exact.reclaimable_bytes > 0

    similar = build_similar_groups(
        session,
        job_id="job-core-dedup",
        root_ids=[root_id],
        threshold=8,
    )
    assert similar.groups_found >= 1

    score_result = apply_auto_primary_scoring(session, job_id="job-core-dedup")
    assert score_result.exact_groups_updated >= 1
    assert score_result.similar_groups_updated >= 1

    exact_group_ids = list(
        session.execute(select(ExactGroupItem.group_id).distinct().order_by(ExactGroupItem.group_id.asc()))
    )
    assert exact_group_ids
    for group_id_row in exact_group_ids:
        group_id = int(group_id_row[0])
        items = list(
            session.scalars(
                select(ExactGroupItem)
                .where(ExactGroupItem.group_id == group_id)
                .order_by(ExactGroupItem.file_id.asc())
            )
        )
        assert len([item for item in items if item.is_primary == 1]) == 1

    similar_group_ids = list(
        session.execute(select(SimilarGroupItem.group_id).distinct().order_by(SimilarGroupItem.group_id.asc()))
    )
    assert similar_group_ids
    for group_id_row in similar_group_ids:
        group_id = int(group_id_row[0])
        items = list(
            session.scalars(
                select(SimilarGroupItem)
                .where(SimilarGroupItem.group_id == group_id)
                .order_by(SimilarGroupItem.file_id.asc())
            )
        )
        assert len([item for item in items if item.is_primary == 1]) == 1

    first_group_id = int(exact_group_ids[0][0])
    items = list(
        session.scalars(
            select(ExactGroupItem).where(ExactGroupItem.group_id == first_group_id).order_by(ExactGroupItem.file_id.asc())
        )
    )
    assert len(items) >= 2
    current_primary = [item.file_id for item in items if item.is_primary == 1][0]
    manual_target = [item.file_id for item in items if item.file_id != current_primary][0]

    decision_service = DecisionService(session)
    decision_row = decision_service.save_group_decision(
        group_kind="exact",
        group_id=first_group_id,
        file_id=manual_target,
        decision="keep",
        note="manual-choice",
    )
    assert decision_row.file_id == manual_target

    items_after = list(
        session.scalars(
            select(ExactGroupItem).where(ExactGroupItem.group_id == first_group_id).order_by(ExactGroupItem.file_id.asc())
        )
    )
    assert [item.file_id for item in items_after if item.is_primary == 1] == [manual_target]


def test_hamming_distance_hex() -> None:
    assert hamming_distance_hex("0", "0") == 0
    assert hamming_distance_hex("f", "0") == 4
    assert hamming_distance_hex("ff", "0f") == 4
