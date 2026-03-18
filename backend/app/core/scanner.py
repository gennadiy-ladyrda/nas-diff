from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.hashing import compute_file_hashes
from app.db.models import File, ScanRoot
from app.db.repositories import FileHashRepository, FileRepository

_COMMIT_BATCH_SIZE = 250


@dataclass(frozen=True)
class ScanIndexingResult:
    files_seen: int
    files_indexed: int


def scan_and_index(
    session: Session,
    *,
    job_id: str,
    roots: Iterable[ScanRoot],
) -> ScanIndexingResult:
    file_repo = FileRepository(session)
    hash_repo = FileHashRepository(session)

    files_seen = 0
    files_indexed = 0
    pending_writes = 0
    seen_paths_by_root: dict[int, set[str]] = {}

    for root in roots:
        root_path = Path(root.path)
        seen_paths_by_root[root.id] = set()

        if not root_path.exists():
            raise FileNotFoundError(f"scan root not found: {root.path}")

        for file_path in _iter_files(root_path):
            files_seen += 1
            abs_path = str(file_path)
            seen_paths_by_root[root.id].add(abs_path)

            stat = file_path.stat()
            existing = file_repo.get_by_abs_path(abs_path)
            changed = _is_changed(existing, stat)

            file_obj = file_repo.upsert(
                root_id=root.id,
                rel_path=file_path.relative_to(root_path).as_posix(),
                abs_path=abs_path,
                file_name=file_path.name,
                extension=file_path.suffix.lower() if file_path.suffix else None,
                mime_type=mimetypes.guess_type(file_path.name)[0],
                size_bytes=stat.st_size,
                mtime_epoch_ns=stat.st_mtime_ns,
                ctime_epoch_ns=getattr(stat, "st_ctime_ns", None),
                inode=getattr(stat, "st_ino", None),
                dev=getattr(stat, "st_dev", None),
                first_seen_job_id=job_id if existing is None else None,
                last_seen_job_id=job_id,
                is_present=1,
                autocommit=False,
            )
            pending_writes += 1

            if changed:
                files_indexed += 1
                computed_hashes = compute_file_hashes(file_path, size_bytes=stat.st_size)
                for hash_type, hash_hex in (
                    ("blake3_full", computed_hashes.blake3_full),
                    ("dhash64", computed_hashes.dhash64),
                    ("phash64", computed_hashes.phash64),
                ):
                    assert hash_hex is not None
                    hash_repo.upsert(
                        file_id=file_obj.id,
                        hash_type=hash_type,
                        hash_hex=hash_hex,
                        autocommit=False,
                    )
                pending_writes += 3

            if pending_writes >= _COMMIT_BATCH_SIZE:
                session.commit()
                pending_writes = 0

    if pending_writes > 0:
        session.commit()

    _mark_missing_files(
        session,
        job_id=job_id,
        seen_paths_by_root=seen_paths_by_root,
    )
    return ScanIndexingResult(files_seen=files_seen, files_indexed=files_indexed)


def _iter_files(root_path: Path) -> Iterable[Path]:
    for dirpath, _dirnames, filenames in os.walk(root_path):
        for file_name in sorted(filenames):
            candidate = Path(dirpath) / file_name
            if candidate.is_file():
                yield candidate


def _is_changed(existing: File | None, stat_result: os.stat_result) -> bool:
    if existing is None:
        return True

    if existing.size_bytes != stat_result.st_size:
        return True
    if existing.mtime_epoch_ns != stat_result.st_mtime_ns:
        return True

    inode = getattr(stat_result, "st_ino", None)
    if inode is not None and existing.inode != inode:
        return True

    dev = getattr(stat_result, "st_dev", None)
    if dev is not None and existing.dev != dev:
        return True

    if existing.is_present != 1:
        return True

    return False


def _mark_missing_files(
    session: Session,
    *,
    job_id: str,
    seen_paths_by_root: dict[int, set[str]],
) -> None:
    if not seen_paths_by_root:
        return

    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    root_ids = tuple(seen_paths_by_root.keys())
    stmt = select(File).where(File.root_id.in_(root_ids))
    for file_obj in session.scalars(stmt):
        seen_paths = seen_paths_by_root.get(file_obj.root_id, set())
        if file_obj.abs_path in seen_paths:
            continue
        if file_obj.is_present == 0:
            continue
        file_obj.is_present = 0
        file_obj.last_seen_job_id = job_id
        file_obj.updated_at = now

    session.commit()
