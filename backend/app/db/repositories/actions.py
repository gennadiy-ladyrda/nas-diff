from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import ActionBatch, ActionItem, FileMovement


@dataclass(frozen=True)
class ActionItemPayload:
    file_id: int
    source_path: str
    target_path: str | None = None
    status: str = "pending"


class ActionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create_batch(
        self,
        *,
        batch_id: str,
        action_type: str,
        status: str = "draft",
        requested_by: str = "local_admin",
        dry_run: int = 0,
        summary: str | None = None,
    ) -> ActionBatch:
        batch = ActionBatch(
            id=batch_id,
            action_type=action_type,
            status=status,
            requested_by=requested_by,
            dry_run=dry_run,
            summary=summary,
        )
        self.session.add(batch)
        self.session.commit()
        self.session.refresh(batch)
        return batch

    def get_batch(self, batch_id: str) -> ActionBatch | None:
        return self.session.get(ActionBatch, batch_id)

    def add_items(self, *, batch_id: str, items: list[ActionItemPayload]) -> list[ActionItem]:
        payload = [
            ActionItem(
                batch_id=batch_id,
                file_id=item.file_id,
                source_path=item.source_path,
                target_path=item.target_path,
                status=item.status,
            )
            for item in items
        ]
        self.session.add_all(payload)
        self.session.commit()

        for item in payload:
            self.session.refresh(item)

        return payload

    def get_item(self, item_id: int) -> ActionItem | None:
        return self.session.get(ActionItem, item_id)

    def list_items(self, *, batch_id: str, status: str | None = None) -> list[ActionItem]:
        stmt = select(ActionItem).where(ActionItem.batch_id == batch_id)
        if status is not None:
            stmt = stmt.where(ActionItem.status == status)
        stmt = stmt.order_by(ActionItem.id.asc())
        return list(self.session.scalars(stmt))

    def add_file_movement(
        self,
        *,
        file_id: int,
        batch_id: str,
        from_path: str,
        to_path: str,
    ) -> FileMovement:
        movement = FileMovement(
            file_id=file_id,
            batch_id=batch_id,
            from_path=from_path,
            to_path=to_path,
        )
        self.session.add(movement)
        self.session.commit()
        self.session.refresh(movement)
        return movement

    def list_file_movements(self, *, batch_id: str, unrestored_only: bool = False) -> list[FileMovement]:
        stmt = select(FileMovement).where(FileMovement.batch_id == batch_id)
        if unrestored_only:
            stmt = stmt.where(FileMovement.restored_at.is_(None))
        stmt = stmt.order_by(FileMovement.id.asc())
        return list(self.session.scalars(stmt))

    def get_latest_unrestored_movement(
        self,
        *,
        file_id: int,
        batch_id: str | None = None,
    ) -> FileMovement | None:
        stmt = select(FileMovement).where(
            FileMovement.file_id == file_id,
            FileMovement.restored_at.is_(None),
        )
        if batch_id is not None:
            stmt = stmt.where(FileMovement.batch_id == batch_id)

        stmt = stmt.order_by(FileMovement.id.desc()).limit(1)
        return self.session.scalar(stmt)

    def mark_file_movement_restored(
        self,
        *,
        file_id: int,
        from_path: str,
        to_path: str,
    ) -> FileMovement | None:
        movement = self.find_unrestored_movement(
            file_id=file_id,
            from_path=from_path,
            to_path=to_path,
        )
        if movement is None:
            return None

        movement.restored_at = _utc_iso_now()
        self.session.commit()
        self.session.refresh(movement)
        return movement

    def find_unrestored_movement(
        self,
        *,
        file_id: int,
        from_path: str,
        to_path: str,
    ) -> FileMovement | None:
        stmt = (
            select(FileMovement)
            .where(
                FileMovement.file_id == file_id,
                FileMovement.from_path == from_path,
                FileMovement.to_path == to_path,
                FileMovement.restored_at.is_(None),
            )
            .order_by(FileMovement.id.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)

    def count_unrestored_movements(self, *, batch_id: str) -> int:
        stmt = select(func.count(FileMovement.id)).where(
            FileMovement.batch_id == batch_id,
            FileMovement.restored_at.is_(None),
        )
        return int(self.session.scalar(stmt) or 0)

    def update_batch_status(self, batch_id: str, *, status: str) -> ActionBatch:
        batch = self._require_batch(batch_id)
        batch.status = status

        if status == "confirmed":
            batch.confirmed_at = _utc_iso_now()
        if status in {"executed", "partially_failed", "failed", "rolled_back"}:
            batch.executed_at = _utc_iso_now()

        self.session.commit()
        self.session.refresh(batch)
        return batch

    def update_batch_summary(self, batch_id: str, *, summary: str | None) -> ActionBatch:
        batch = self._require_batch(batch_id)
        batch.summary = summary
        self.session.commit()
        self.session.refresh(batch)
        return batch

    def update_item_status(
        self,
        item_id: int,
        *,
        status: str,
        error_message: str | None = None,
        target_path: str | None = None,
    ) -> ActionItem:
        item = self._require_item(item_id)
        item.status = status

        if error_message is not None:
            item.error_message = error_message
        if target_path is not None:
            item.target_path = target_path
        if status in {"done", "failed", "skipped"}:
            item.executed_at = _utc_iso_now()

        self.session.commit()
        self.session.refresh(item)
        return item

    def _require_batch(self, batch_id: str) -> ActionBatch:
        batch = self.get_batch(batch_id)
        if batch is None:
            raise LookupError(f"action_batch={batch_id} not found")
        return batch

    def _require_item(self, item_id: int) -> ActionItem:
        item = self.session.get(ActionItem, item_id)
        if item is None:
            raise LookupError(f"action_item={item_id} not found")
        return item


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
