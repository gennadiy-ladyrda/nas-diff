from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ExactGroupItem, SimilarGroupItem
from app.db.repositories import GroupRepository, UserDecisionRepository


class DecisionService:
    def __init__(self, session: Session) -> None:
        self.session = session
        self.groups = GroupRepository(session)
        self.decisions = UserDecisionRepository(session)

    def save_group_decision(
        self,
        *,
        group_kind: str,
        group_id: int,
        file_id: int,
        decision: str,
        note: Optional[str] = None,
    ):
        self._ensure_group_file_membership(group_kind=group_kind, group_id=group_id, file_id=file_id)

        decision_row = self.decisions.upsert(
            group_kind=group_kind,
            group_id=group_id,
            file_id=file_id,
            decision=decision,
            note=note,
        )

        if decision == "keep":
            if group_kind == "exact":
                self.groups.set_exact_primary(group_id=group_id, file_id=file_id)
            else:
                self.groups.set_similar_primary(group_id=group_id, file_id=file_id)

        return decision_row

    def _ensure_group_file_membership(self, *, group_kind: str, group_id: int, file_id: int) -> None:
        if group_kind == "exact":
            stmt = select(ExactGroupItem).where(
                ExactGroupItem.group_id == group_id,
                ExactGroupItem.file_id == file_id,
            )
        elif group_kind == "similar":
            stmt = select(SimilarGroupItem).where(
                SimilarGroupItem.group_id == group_id,
                SimilarGroupItem.file_id == file_id,
            )
        else:
            raise ValueError("group_kind must be 'exact' or 'similar'")

        item = self.session.scalar(stmt)
        if item is None:
            raise LookupError(f"group item not found: kind={group_kind} group_id={group_id} file_id={file_id}")
