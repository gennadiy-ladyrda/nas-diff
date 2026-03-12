from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import UserDecision


class UserDecisionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(
        self,
        *,
        group_kind: str,
        group_id: int,
        file_id: int,
        decision: str,
        note: Optional[str] = None,
    ) -> UserDecision:
        existing = self.get(group_kind=group_kind, group_id=group_id, file_id=file_id)
        if existing is None:
            record = UserDecision(
                group_kind=group_kind,
                group_id=group_id,
                file_id=file_id,
                decision=decision,
                note=note,
            )
            self.session.add(record)
        else:
            record = existing
            record.decision = decision
            record.note = note

        self.session.commit()
        self.session.refresh(record)
        return record

    def get(self, *, group_kind: str, group_id: int, file_id: int) -> UserDecision | None:
        stmt = select(UserDecision).where(
            UserDecision.group_kind == group_kind,
            UserDecision.group_id == group_id,
            UserDecision.file_id == file_id,
        )
        return self.session.scalar(stmt)

    def list_for_group(self, *, group_kind: str, group_id: int) -> list[UserDecision]:
        stmt = (
            select(UserDecision)
            .where(UserDecision.group_kind == group_kind, UserDecision.group_id == group_id)
            .order_by(UserDecision.file_id.asc())
        )
        return list(self.session.scalars(stmt))
