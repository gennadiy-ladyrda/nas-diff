from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import File, FileHash
from app.db.repositories import ExactGroupMember, GroupRepository


@dataclass(frozen=True)
class ExactDedupResult:
    groups_found: int
    reclaimable_bytes: int


def build_exact_groups(
    session: Session,
    *,
    job_id: str,
    root_ids: Iterable[int],
) -> ExactDedupResult:
    repo = GroupRepository(session)
    repo.delete_exact_groups_for_job(job_id=job_id)

    by_signature: dict[str, list[tuple[int, int]]] = defaultdict(list)
    stmt = (
        select(File.id, File.size_bytes, FileHash.hash_hex)
        .join(FileHash, FileHash.file_id == File.id)
        .where(
            File.root_id.in_(tuple(root_ids)),
            File.is_present == 1,
            FileHash.hash_type == "blake3_full",
        )
        .order_by(File.id.asc())
    )

    for file_id, size_bytes, signature in session.execute(stmt):
        by_signature[str(signature)].append((int(file_id), int(size_bytes)))

    groups_found = 0
    reclaimable_bytes = 0

    for signature, members in sorted(by_signature.items()):
        if len(members) < 2:
            continue

        members_sorted = sorted(members, key=lambda item: item[0])
        total_bytes = sum(size_bytes for _file_id, size_bytes in members_sorted)
        max_size = max(size_bytes for _file_id, size_bytes in members_sorted)
        group_reclaimable = total_bytes - max_size
        reclaimable_bytes += group_reclaimable

        repo.create_exact_group(
            job_id=job_id,
            signature=signature,
            total_bytes=total_bytes,
            reclaimable_bytes=group_reclaimable,
            members=[
                ExactGroupMember(
                    file_id=file_id,
                    is_primary=1 if idx == 0 else 0,
                )
                for idx, (file_id, _size) in enumerate(members_sorted)
            ],
        )
        groups_found += 1

    return ExactDedupResult(groups_found=groups_found, reclaimable_bytes=reclaimable_bytes)
