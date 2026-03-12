from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.hasher_similar import hamming_distance_hex
from app.db.models import File, FileHash
from app.db.repositories import GroupRepository, SimilarGroupMember


@dataclass(frozen=True)
class SimilarDedupResult:
    groups_found: int


def build_similar_groups(
    session: Session,
    *,
    job_id: str,
    root_ids: Iterable[int],
    threshold: int,
) -> SimilarDedupResult:
    repo = GroupRepository(session)
    repo.delete_similar_groups_for_job(job_id=job_id)

    rows = session.execute(
        select(File.id, FileHash.hash_hex)
        .join(FileHash, FileHash.file_id == File.id)
        .where(
            File.root_id.in_(tuple(root_ids)),
            File.is_present == 1,
            FileHash.hash_type == "phash64",
        )
        .order_by(File.id.asc())
    ).all()

    if len(rows) < 2:
        return SimilarDedupResult(groups_found=0)

    file_ids = [int(file_id) for file_id, _hash_hex in rows]
    hashes = {int(file_id): str(hash_hex) for file_id, hash_hex in rows}
    adjacency: dict[int, set[int]] = defaultdict(set)

    for index, file_id_a in enumerate(file_ids):
        hash_a = hashes[file_id_a]
        for file_id_b in file_ids[index + 1 :]:
            distance = hamming_distance_hex(hash_a, hashes[file_id_b])
            if distance <= threshold:
                adjacency[file_id_a].add(file_id_b)
                adjacency[file_id_b].add(file_id_a)

    groups_found = 0
    visited: set[int] = set()

    for root_file_id in file_ids:
        if root_file_id in visited:
            continue

        component = _walk_component(root_file_id, adjacency, visited)
        if len(component) < 2:
            continue

        anchor = min(component)
        anchor_hash = hashes[anchor]
        members = []
        for file_id in sorted(component):
            distance = hamming_distance_hex(anchor_hash, hashes[file_id])
            members.append(
                SimilarGroupMember(
                    file_id=file_id,
                    distance_to_anchor=distance,
                    confidence=round(max(0.0, 1.0 - distance / 64.0), 4),
                    is_primary=1 if file_id == anchor else 0,
                )
            )

        repo.create_similar_group(
            job_id=job_id,
            algorithm="phash64",
            threshold=threshold,
            members=members,
        )
        groups_found += 1

    return SimilarDedupResult(groups_found=groups_found)


def _walk_component(root: int, adjacency: dict[int, set[int]], visited: set[int]) -> set[int]:
    queue: deque[int] = deque([root])
    component: set[int] = set()
    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)
        component.add(current)
        for neighbor in adjacency.get(current, set()):
            if neighbor not in visited:
                queue.append(neighbor)
    return component
