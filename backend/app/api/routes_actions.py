from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db_session
from app.db.models import ActionItem
from app.services.action_service import ActionService
from app.workers.queue import ActionQueueClient, get_action_queue_client

router = APIRouter(prefix="/actions", tags=["actions"])


class ActionBatchCreateRequest(BaseModel):
    action_type: Optional[Literal["move_to_trash", "delete_permanent", "restore"]] = None
    file_ids: list[int] = Field(min_length=1)
    requested_by: str = Field(default="local_admin", min_length=1, max_length=128)
    dry_run: bool = False
    summary: Optional[str] = Field(default=None, max_length=1024)


class ActionBatchConfirmRequest(BaseModel):
    confirm_delete_permanent: bool = False


class ActionBatchRollbackRequest(BaseModel):
    requested_by: str = Field(default="local_admin", min_length=1, max_length=128)


class ActionItemStatusResponse(BaseModel):
    id: int
    file_id: int
    source_path: str
    target_path: Optional[str]
    status: str
    error_message: Optional[str]
    executed_at: Optional[str]


class ActionBatchStatusResponse(BaseModel):
    batch_id: str
    status: str
    action_type: str
    requested_at: str
    confirmed_at: Optional[str]
    executed_at: Optional[str]
    requested_by: str
    dry_run: bool
    summary: Optional[str]
    stats: dict[str, int]
    items: list[ActionItemStatusResponse]


class ActionBatchConfirmResponse(BaseModel):
    batch_id: str
    status: str
    queued: bool


class ActionBatchRollbackResponse(BaseModel):
    source_batch_id: str
    rollback_batch_id: str
    status: str
    queued: bool


def _get_action_queue(settings: Settings = Depends(get_settings)) -> ActionQueueClient:
    return get_action_queue_client(settings)


@router.post("/batches", response_model=ActionBatchStatusResponse, status_code=status.HTTP_201_CREATED)
def create_action_batch(
    payload: ActionBatchCreateRequest,
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> ActionBatchStatusResponse:
    service = ActionService(db, settings)

    action_type = payload.action_type or settings.default_file_action
    try:
        batch = service.create_draft_batch(
            action_type=action_type,
            file_ids=payload.file_ids,
            requested_by=payload.requested_by,
            dry_run=payload.dry_run,
            summary=payload.summary,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    return _serialize_batch(service, batch_id=batch.id)


@router.get("/batches/{batch_id}", response_model=ActionBatchStatusResponse)
def get_action_batch(
    batch_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
) -> ActionBatchStatusResponse:
    service = ActionService(db, settings)

    try:
        return _serialize_batch(service, batch_id=batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc


@router.post("/batches/{batch_id}/confirm", response_model=ActionBatchConfirmResponse)
def confirm_action_batch(
    payload: ActionBatchConfirmRequest,
    batch_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    queue: ActionQueueClient = Depends(_get_action_queue),
) -> ActionBatchConfirmResponse:
    service = ActionService(db, settings)

    try:
        batch = service.get_batch(batch_id=batch_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if batch.action_type == "delete_permanent" and not payload.confirm_delete_permanent:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="confirm_delete_permanent=true is required for delete_permanent",
        )

    try:
        confirmed_batch = service.confirm_batch(batch_id=batch_id, queue=queue)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return ActionBatchConfirmResponse(
        batch_id=confirmed_batch.id,
        status=confirmed_batch.status,
        queued=True,
    )


@router.post("/batches/{batch_id}/rollback", response_model=ActionBatchRollbackResponse)
def rollback_action_batch(
    payload: ActionBatchRollbackRequest,
    batch_id: str = Path(..., min_length=1),
    db: Session = Depends(get_db_session),
    settings: Settings = Depends(get_settings),
    queue: ActionQueueClient = Depends(_get_action_queue),
) -> ActionBatchRollbackResponse:
    service = ActionService(db, settings)

    try:
        rollback_batch = service.create_rollback_batch(
            source_batch_id=batch_id,
            requested_by=payload.requested_by,
        )
        confirmed_batch = service.confirm_batch(batch_id=rollback_batch.id, queue=queue)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return ActionBatchRollbackResponse(
        source_batch_id=batch_id,
        rollback_batch_id=confirmed_batch.id,
        status=confirmed_batch.status,
        queued=True,
    )


def _serialize_batch(service: ActionService, *, batch_id: str) -> ActionBatchStatusResponse:
    batch = service.get_batch(batch_id=batch_id)
    items = service.list_batch_items(batch_id=batch.id)
    stats = _build_stats(items)

    return ActionBatchStatusResponse(
        batch_id=batch.id,
        status=batch.status,
        action_type=batch.action_type,
        requested_at=batch.requested_at,
        confirmed_at=batch.confirmed_at,
        executed_at=batch.executed_at,
        requested_by=batch.requested_by,
        dry_run=bool(batch.dry_run),
        summary=batch.summary,
        stats=stats,
        items=[
            ActionItemStatusResponse(
                id=item.id,
                file_id=item.file_id,
                source_path=item.source_path,
                target_path=item.target_path,
                status=item.status,
                error_message=item.error_message,
                executed_at=item.executed_at,
            )
            for item in items
        ],
    )


def _build_stats(items: list[ActionItem]) -> dict[str, int]:
    counters = {"total": len(items), "pending": 0, "done": 0, "failed": 0, "skipped": 0}
    for item in items:
        if item.status in counters:
            counters[item.status] += 1
    return counters
