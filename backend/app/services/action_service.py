from __future__ import annotations

import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import Settings
from app.db.models import ActionBatch, ActionItem, File
from app.db.repositories import ActionItemPayload, ActionRepository, FileRepository
from app.workers.queue import ActionQueueClient

_ALLOWED_ACTION_TYPES = {"move_to_trash", "delete_permanent", "restore"}


@dataclass(frozen=True)
class ActionBatchPreview:
    action_type: str
    file_ids: list[int]
    files_count: int
    total_bytes: int
    estimated_reclaimable_bytes: int


class ActionService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.actions = ActionRepository(session)
        self.files = FileRepository(session)

    def create_draft_batch(
        self,
        *,
        action_type: str,
        file_ids: list[int],
        requested_by: str = "local_admin",
        dry_run: bool = False,
        summary: str | None = None,
    ) -> ActionBatch:
        normalized_action = _normalize_action_type(action_type)

        normalized_file_ids = _normalize_file_ids(file_ids)
        if not normalized_file_ids:
            raise ValueError("file_ids must not be empty")

        items = self._build_items(action_type=normalized_action, file_ids=normalized_file_ids)

        batch = self.actions.create_batch(
            batch_id=str(uuid.uuid4()),
            action_type=normalized_action,
            requested_by=requested_by,
            dry_run=1 if dry_run else 0,
            summary=summary,
        )
        self.actions.add_items(batch_id=batch.id, items=items)
        return batch

    def preview_batch(
        self,
        *,
        action_type: str,
        file_ids: list[int],
    ) -> ActionBatchPreview:
        normalized_action = _normalize_action_type(action_type)
        normalized_file_ids = _normalize_file_ids(file_ids)
        if not normalized_file_ids:
            raise ValueError("file_ids must not be empty")

        files = self._load_files(normalized_file_ids)
        total_bytes = sum(int(file_obj.size_bytes or 0) for file_obj in files)

        if normalized_action == "restore":
            for file_obj in files:
                movement = self.actions.get_latest_unrestored_movement(file_id=file_obj.id)
                if movement is None:
                    raise LookupError(f"no unrestored movement found for file_id={file_obj.id}")

        return ActionBatchPreview(
            action_type=normalized_action,
            file_ids=[file_obj.id for file_obj in files],
            files_count=len(files),
            total_bytes=total_bytes,
            estimated_reclaimable_bytes=total_bytes if normalized_action != "restore" else 0,
        )

    def create_rollback_batch(
        self,
        *,
        source_batch_id: str,
        requested_by: str = "local_admin",
    ) -> ActionBatch:
        source_batch = self.actions.get_batch(source_batch_id)
        if source_batch is None:
            raise LookupError(f"action_batch={source_batch_id} not found")

        if source_batch.action_type != "move_to_trash":
            raise ValueError("rollback is supported only for move_to_trash batches")

        if source_batch.status not in {"executed", "partially_failed"}:
            raise ValueError("rollback is allowed only for executed/partially_failed batches")

        movements = self.actions.list_file_movements(batch_id=source_batch_id, unrestored_only=True)
        if not movements:
            raise ValueError("rollback is unavailable: no unrestored file movements found")

        restore_batch = self.actions.create_batch(
            batch_id=str(uuid.uuid4()),
            action_type="restore",
            requested_by=requested_by,
            summary=f"rollback_of={source_batch_id}",
        )

        restore_items = [
            ActionItemPayload(
                file_id=movement.file_id,
                source_path=movement.to_path,
                target_path=movement.from_path,
            )
            for movement in movements
        ]
        self.actions.add_items(batch_id=restore_batch.id, items=restore_items)
        return restore_batch

    def confirm_batch(self, *, batch_id: str, queue: ActionQueueClient) -> ActionBatch:
        batch = self.actions.get_batch(batch_id)
        if batch is None:
            raise LookupError(f"action_batch={batch_id} not found")

        if batch.status != "draft":
            raise ValueError("only draft batch can be confirmed")

        items = self.actions.list_items(batch_id=batch_id)
        if not items:
            raise ValueError("batch has no action items")

        if batch.action_type == "delete_permanent" and not self.settings.hard_delete_enabled:
            raise PermissionError("hard delete is disabled (HARD_DELETE_ENABLED=false)")

        self.actions.update_batch_status(batch_id, status="confirmed")

        try:
            queue.enqueue_action_batch(batch_id=batch_id)
        except Exception as exc:
            error_message = f"failed to enqueue action batch: {exc}"
            for item in items:
                if item.status == "pending":
                    self.actions.update_item_status(item.id, status="failed", error_message=error_message)
            self.actions.update_batch_status(batch_id, status="failed")
            raise RuntimeError(error_message) from exc

        confirmed_batch = self.actions.get_batch(batch_id)
        if confirmed_batch is None:
            raise LookupError(f"action_batch={batch_id} not found after confirm")
        return confirmed_batch

    def execute_confirmed_batch(self, *, batch_id: str) -> ActionBatch:
        batch = self.actions.get_batch(batch_id)
        if batch is None:
            raise LookupError(f"action_batch={batch_id} not found")

        if batch.status != "confirmed":
            raise ValueError("only confirmed batch can be executed")

        pending_items = self.actions.list_items(batch_id=batch_id, status="pending")
        if not pending_items:
            raise ValueError("batch has no pending items")

        done_count = 0
        failed_count = 0
        restored_source_batches: set[str] = set()

        for item in pending_items:
            try:
                if batch.action_type == "move_to_trash":
                    final_target_path = self._move_to_trash(batch=batch, item=item)
                    self.actions.update_item_status(
                        item.id,
                        status="done",
                        target_path=final_target_path,
                    )
                elif batch.action_type == "delete_permanent":
                    self._delete_permanent(item=item)
                    self.actions.update_item_status(item.id, status="done")
                else:
                    restored_movement = self._restore(item=item)
                    self.actions.update_item_status(item.id, status="done", target_path=item.target_path)
                    restored_source_batches.add(restored_movement.batch_id)
                done_count += 1
            except Exception as exc:
                failed_count += 1
                self.actions.update_item_status(item.id, status="failed", error_message=str(exc))

        if failed_count == 0:
            self.actions.update_batch_status(batch_id, status="executed")
        elif done_count > 0:
            self.actions.update_batch_status(batch_id, status="partially_failed")
        else:
            self.actions.update_batch_status(batch_id, status="failed")

        if batch.action_type == "restore" and restored_source_batches:
            self._mark_source_batches_rolled_back(restored_source_batches)

        finalized = self.actions.get_batch(batch_id)
        if finalized is None:
            raise LookupError(f"action_batch={batch_id} not found after execution")
        return finalized

    def get_batch(self, *, batch_id: str) -> ActionBatch:
        batch = self.actions.get_batch(batch_id)
        if batch is None:
            raise LookupError(f"action_batch={batch_id} not found")
        return batch

    def list_batch_items(self, *, batch_id: str) -> list[ActionItem]:
        return self.actions.list_items(batch_id=batch_id)

    def summarize_items(self, *, batch_id: str) -> dict[str, int]:
        items = self.actions.list_items(batch_id=batch_id)
        counters = {"total": len(items), "pending": 0, "done": 0, "failed": 0, "skipped": 0}
        for item in items:
            if item.status in counters:
                counters[item.status] += 1
        return counters

    def _build_items(self, *, action_type: str, file_ids: list[int]) -> list[ActionItemPayload]:
        files = self._load_files(file_ids)

        if action_type == "restore":
            payload: list[ActionItemPayload] = []
            for file_obj in files:
                movement = self.actions.get_latest_unrestored_movement(file_id=file_obj.id)
                if movement is None:
                    raise LookupError(f"no unrestored movement found for file_id={file_obj.id}")
                payload.append(
                    ActionItemPayload(
                        file_id=file_obj.id,
                        source_path=movement.to_path,
                        target_path=movement.from_path,
                    )
                )
            return payload

        return [
            ActionItemPayload(
                file_id=file_obj.id,
                source_path=file_obj.abs_path,
                target_path=self._build_default_trash_path(file_obj.abs_path) if action_type == "move_to_trash" else None,
            )
            for file_obj in files
        ]

    def _load_files(self, file_ids: list[int]) -> list[File]:
        loaded: list[File] = []
        missing: list[int] = []

        for file_id in file_ids:
            file_obj = self.files.get(file_id)
            if file_obj is None:
                missing.append(file_id)
            else:
                loaded.append(file_obj)

        if missing:
            missing_text = ", ".join(str(file_id) for file_id in missing)
            raise LookupError(f"file(s) not found: {missing_text}")

        return loaded

    def _build_default_trash_path(self, source_path: str) -> str:
        source_relative = source_path.lstrip("/")
        if not source_relative:
            raise ValueError("source path is empty")
        return str(Path(self.settings.nas_trash_dir) / source_relative)

    def _move_to_trash(self, *, batch: ActionBatch, item: ActionItem) -> str:
        source_path = Path(item.source_path)
        if not source_path.exists():
            raise FileNotFoundError(f"source file not found: {item.source_path}")
        if not source_path.is_file():
            raise ValueError(f"source path is not a file: {item.source_path}")

        target_path = Path(item.target_path or self._build_default_trash_path(item.source_path))
        self._ensure_trash_target(target_path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path = _next_available_path(target_path)

        shutil.move(str(source_path), str(target_path))
        self.actions.add_file_movement(
            file_id=item.file_id,
            batch_id=batch.id,
            from_path=item.source_path,
            to_path=str(target_path),
        )
        return str(target_path)

    def _restore(self, *, item: ActionItem):
        source_path = Path(item.source_path)
        if not source_path.exists():
            raise FileNotFoundError(f"restore source not found: {item.source_path}")
        if not source_path.is_file():
            raise ValueError(f"restore source is not a file: {item.source_path}")

        if not item.target_path:
            raise ValueError("restore target_path is required")

        target_path = Path(item.target_path)
        if target_path.exists():
            raise FileExistsError(f"restore target already exists: {item.target_path}")

        existing_movement = self.actions.find_unrestored_movement(
            file_id=item.file_id,
            from_path=str(target_path),
            to_path=item.source_path,
        )
        if existing_movement is None:
            raise LookupError(
                "restore movement record not found for file_id=%s from=%s to=%s"
                % (item.file_id, str(target_path), item.source_path)
            )

        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_path), str(target_path))

        movement = self.actions.mark_file_movement_restored(
            file_id=item.file_id,
            from_path=str(target_path),
            to_path=item.source_path,
        )
        if movement is None:
            raise RuntimeError("restore movement record disappeared during execution")

        return movement

    def _delete_permanent(self, *, item: ActionItem) -> None:
        if not self.settings.hard_delete_enabled:
            raise PermissionError("hard delete is disabled (HARD_DELETE_ENABLED=false)")

        source_path = Path(item.source_path)
        if not source_path.exists():
            raise FileNotFoundError(f"source file not found: {item.source_path}")
        if not source_path.is_file():
            raise ValueError(f"source path is not a file: {item.source_path}")

        source_path.unlink()

    def _mark_source_batches_rolled_back(self, source_batch_ids: set[str]) -> None:
        for source_batch_id in source_batch_ids:
            source_batch = self.actions.get_batch(source_batch_id)
            if source_batch is None:
                continue
            if source_batch.status not in {"executed", "partially_failed"}:
                continue
            if self.actions.count_unrestored_movements(batch_id=source_batch_id) == 0:
                self.actions.update_batch_status(source_batch_id, status="rolled_back")

    def _ensure_trash_target(self, path: Path) -> None:
        trash_root = Path(self.settings.nas_trash_dir)
        try:
            common_prefix = os.path.commonpath([str(path), str(trash_root)])
        except ValueError as exc:
            raise ValueError(f"invalid trash target path: {path}") from exc

        if common_prefix != str(trash_root):
            raise ValueError(f"target path must be inside NAS_TRASH_DIR: {path}")


def _normalize_file_ids(file_ids: list[int]) -> list[int]:
    seen: set[int] = set()
    normalized: list[int] = []
    for file_id in file_ids:
        if file_id <= 0:
            raise ValueError("file_ids must contain positive integers")
        if file_id in seen:
            continue
        seen.add(file_id)
        normalized.append(file_id)
    return normalized


def _normalize_action_type(action_type: str) -> str:
    normalized_action = action_type.strip().lower()
    if normalized_action not in _ALLOWED_ACTION_TYPES:
        raise ValueError("action_type must be one of: move_to_trash, delete_permanent, restore")
    return normalized_action


def _next_available_path(path: Path) -> Path:
    if not path.exists():
        return path

    counter = 1
    while True:
        candidate = path.with_name(f"{path.stem}.{counter}{path.suffix}")
        if not candidate.exists():
            return candidate
        counter += 1
