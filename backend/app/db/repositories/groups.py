from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from app.db.models import ExactGroup, ExactGroupItem, SimilarGroup, SimilarGroupItem


@dataclass(frozen=True)
class ExactGroupMember:
    file_id: int
    is_primary: int = 0
    keep_score: float | None = None
    reason: str | None = None


@dataclass(frozen=True)
class SimilarGroupMember:
    file_id: int
    distance_to_anchor: int
    confidence: float | None = None
    is_primary: int = 0
    keep_score: float | None = None
    reason: str | None = None


class GroupRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_exact_group(
        self,
        *,
        job_id: str,
        signature: str,
        total_bytes: int,
        reclaimable_bytes: int,
        members: list[ExactGroupMember],
    ) -> ExactGroup:
        group = ExactGroup(
            job_id=job_id,
            signature=signature,
            file_count=len(members),
            total_bytes=total_bytes,
            reclaimable_bytes=reclaimable_bytes,
        )
        self.session.add(group)
        self.session.flush()

        self.session.add_all(
            ExactGroupItem(
                group_id=group.id,
                file_id=member.file_id,
                is_primary=member.is_primary,
                keep_score=member.keep_score,
                reason=member.reason,
            )
            for member in members
        )

        self.session.commit()
        self.session.refresh(group)
        return group

    def create_similar_group(
        self,
        *,
        job_id: str,
        algorithm: str,
        threshold: int,
        members: list[SimilarGroupMember],
    ) -> SimilarGroup:
        group = SimilarGroup(
            job_id=job_id,
            algorithm=algorithm,
            threshold=threshold,
            file_count=len(members),
        )
        self.session.add(group)
        self.session.flush()

        self.session.add_all(
            SimilarGroupItem(
                group_id=group.id,
                file_id=member.file_id,
                distance_to_anchor=member.distance_to_anchor,
                confidence=member.confidence,
                is_primary=member.is_primary,
                keep_score=member.keep_score,
                reason=member.reason,
            )
            for member in members
        )

        self.session.commit()
        self.session.refresh(group)
        return group

    def list_exact_groups(self, *, job_id: str) -> list[ExactGroup]:
        stmt = select(ExactGroup).where(ExactGroup.job_id == job_id).order_by(ExactGroup.id.asc())
        return list(self.session.scalars(stmt))

    def list_similar_groups(self, *, job_id: str) -> list[SimilarGroup]:
        stmt = select(SimilarGroup).where(SimilarGroup.job_id == job_id).order_by(SimilarGroup.id.asc())
        return list(self.session.scalars(stmt))

    def list_exact_items(self, *, group_id: int) -> list[ExactGroupItem]:
        stmt = select(ExactGroupItem).where(ExactGroupItem.group_id == group_id).order_by(ExactGroupItem.file_id.asc())
        return list(self.session.scalars(stmt))

    def list_similar_items(self, *, group_id: int) -> list[SimilarGroupItem]:
        stmt = (
            select(SimilarGroupItem)
            .where(SimilarGroupItem.group_id == group_id)
            .order_by(SimilarGroupItem.file_id.asc())
        )
        return list(self.session.scalars(stmt))

    def set_exact_primary(self, *, group_id: int, file_id: int) -> None:
        self.session.execute(
            update(ExactGroupItem)
            .where(ExactGroupItem.group_id == group_id)
            .values(is_primary=0)
        )
        self.session.execute(
            update(ExactGroupItem)
            .where(ExactGroupItem.group_id == group_id, ExactGroupItem.file_id == file_id)
            .values(is_primary=1)
        )
        self.session.commit()

    def set_similar_primary(self, *, group_id: int, file_id: int) -> None:
        self.session.execute(
            update(SimilarGroupItem)
            .where(SimilarGroupItem.group_id == group_id)
            .values(is_primary=0)
        )
        self.session.execute(
            update(SimilarGroupItem)
            .where(SimilarGroupItem.group_id == group_id, SimilarGroupItem.file_id == file_id)
            .values(is_primary=1)
        )
        self.session.commit()

    def delete_groups_for_job(self, *, job_id: str) -> None:
        self.session.execute(delete(ExactGroup).where(ExactGroup.job_id == job_id))
        self.session.execute(delete(SimilarGroup).where(SimilarGroup.job_id == job_id))
        self.session.commit()
