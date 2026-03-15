from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import get_db_session
from app.db.models import ScanJobRoot, ScanRoot
from app.db.repositories import GroupRepository, ScanJobRepository, ScanRootRepository
from app.workers.queue import ScanQueueClient, get_scan_queue_client

router = APIRouter(prefix="/scan", tags=["scan"])


def _get_scan_queue(settings: Settings = Depends(get_settings)) -> ScanQueueClient:
    return get_scan_queue_client(settings)


class ScanJobCreateRequest(BaseModel):
    mode: Literal["exact", "similar", "both"] = "both"
    root_ids: Optional[list[int]] = None
    idempotency_key: Optional[str] = Field(default=None, max_length=128)


class ScanJobCreateResponse(BaseModel):
    job_id: str
    status: str
    mode: str
    root_ids: list[int]
    queued: bool


class ScanJobStatusResponse(BaseModel):
    job_id: str
    mode: str
    status: str
    requested_at: str
    started_at: Optional[str]
    finished_at: Optional[str]
    error_message: Optional[str]
    files_seen: int
    files_indexed: int
    exact_groups_found: int
    similar_groups_found: int
    reclaimable_bytes: int
    roots: list[dict[str, object]]


class ScanJobListItemResponse(BaseModel):
    job_id: str
    mode: str
    status: str
    requested_at: str
    started_at: Optional[str]
    finished_at: Optional[str]
    error_message: Optional[str]
    files_seen: int
    files_indexed: int
    exact_groups_found: int
    similar_groups_found: int
    reclaimable_bytes: int


class ScanJobsListResponse(BaseModel):
    page: int
    page_size: int
    total: int
    items: list[ScanJobListItemResponse]


class ScanJobGroupsResponse(BaseModel):
    job_id: str
    kind: Literal["exact", "similar"]
    page: int
    page_size: int
    total: int
    items: list[dict[str, object]]


@router.post("/jobs", response_model=ScanJobCreateResponse, status_code=status.HTTP_201_CREATED)
def create_scan_job(
    payload: ScanJobCreateRequest,
    db: Session = Depends(get_db_session),
    queue: ScanQueueClient = Depends(_get_scan_queue),
) -> ScanJobCreateResponse:
    job_repo = ScanJobRepository(db)
    root_repo = ScanRootRepository(db)

    root_ids = _resolve_root_ids(payload.root_ids, root_repo)
    if not root_ids:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="no scan roots selected")

    job_id = str(uuid.uuid4())
    if payload.idempotency_key:
        job_id = str(uuid.uuid5(uuid.NAMESPACE_URL, payload.idempotency_key))
        existing = job_repo.get(job_id)
        if existing is not None:
            existing_root_ids = job_repo.list_root_ids(job_id)
            if existing.mode != payload.mode or existing_root_ids != root_ids:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="idempotency key already used with a different payload",
                )
            return ScanJobCreateResponse(
                job_id=existing.id,
                status=existing.status,
                mode=existing.mode,
                root_ids=existing_root_ids,
                queued=existing.status in {"queued", "running"},
            )

    created = job_repo.create(job_id=job_id, mode=payload.mode, status="queued")
    job_repo.add_roots(job_id=created.id, root_ids=root_ids)

    try:
        queue.enqueue_scan_job(job_id=created.id)
    except Exception as exc:
        job_repo.update_status(created.id, status="failed", error_message=str(exc), set_finished_at=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="failed to enqueue scan job",
        ) from exc

    return ScanJobCreateResponse(
        job_id=created.id,
        status=created.status,
        mode=created.mode,
        root_ids=root_ids,
        queued=True,
    )


@router.get("/jobs", response_model=ScanJobsListResponse)
def list_scan_jobs(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    job_status: Optional[Literal["queued", "running", "completed", "failed", "canceled"]] = Query(
        default=None,
        alias="status",
    ),
    mode: Optional[Literal["exact", "similar", "both"]] = Query(default=None),
    order: Literal["asc", "desc"] = Query(default="desc"),
    db: Session = Depends(get_db_session),
) -> ScanJobsListResponse:
    job_repo = ScanJobRepository(db)
    jobs, total = job_repo.list_jobs(
        page=page,
        page_size=page_size,
        status=job_status,
        mode=mode,
        order=order,
    )
    return ScanJobsListResponse(
        page=page,
        page_size=page_size,
        total=total,
        items=[
            ScanJobListItemResponse(
                job_id=job.id,
                mode=job.mode,
                status=job.status,
                requested_at=job.requested_at,
                started_at=job.started_at,
                finished_at=job.finished_at,
                error_message=job.error_message,
                files_seen=job.files_seen,
                files_indexed=job.files_indexed,
                exact_groups_found=job.exact_groups_found,
                similar_groups_found=job.similar_groups_found,
                reclaimable_bytes=job.reclaimable_bytes,
            )
            for job in jobs
        ],
    )


@router.get("/jobs/latest/processed", response_model=ScanJobStatusResponse)
def get_latest_processed_scan_job(db: Session = Depends(get_db_session)) -> ScanJobStatusResponse:
    job_repo = ScanJobRepository(db)
    job = job_repo.get_latest_processed()
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="no processed scan jobs found")
    return _serialize_scan_job_status(db, job)


@router.get("/jobs/{job_id}", response_model=ScanJobStatusResponse)
def get_scan_job_status(job_id: str, db: Session = Depends(get_db_session)) -> ScanJobStatusResponse:
    job_repo = ScanJobRepository(db)
    job = job_repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"scan_job={job_id} not found")

    return _serialize_scan_job_status(db, job)


def _serialize_scan_job_status(db: Session, job) -> ScanJobStatusResponse:
    roots_rows = db.execute(
        select(ScanRoot.id, ScanRoot.path, ScanRoot.enabled)
        .join(ScanJobRoot, ScanJobRoot.root_id == ScanRoot.id)
        .where(ScanJobRoot.job_id == job.id)
        .order_by(ScanRoot.id.asc())
    ).all()

    return ScanJobStatusResponse(
        job_id=job.id,
        mode=job.mode,
        status=job.status,
        requested_at=job.requested_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        error_message=job.error_message,
        files_seen=job.files_seen,
        files_indexed=job.files_indexed,
        exact_groups_found=job.exact_groups_found,
        similar_groups_found=job.similar_groups_found,
        reclaimable_bytes=job.reclaimable_bytes,
        roots=[
            {"id": int(root_id), "path": path, "enabled": bool(enabled)}
            for root_id, path, enabled in roots_rows
        ],
    )


@router.get("/jobs/{job_id}/groups", response_model=ScanJobGroupsResponse)
def get_scan_job_groups(
    job_id: str,
    kind: Literal["exact", "similar"] = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db_session),
) -> ScanJobGroupsResponse:
    job_repo = ScanJobRepository(db)
    if job_repo.get(job_id) is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"scan_job={job_id} not found")

    group_repo = GroupRepository(db)
    if kind == "exact":
        groups = group_repo.list_exact_groups(job_id=job_id)
        serialized = [
            {
                "id": group.id,
                "signature": group.signature,
                "file_count": group.file_count,
                "total_bytes": group.total_bytes,
                "reclaimable_bytes": group.reclaimable_bytes,
            }
            for group in groups
        ]
    else:
        groups = group_repo.list_similar_groups(job_id=job_id)
        serialized = [
            {
                "id": group.id,
                "algorithm": group.algorithm,
                "threshold": group.threshold,
                "file_count": group.file_count,
            }
            for group in groups
        ]

    total = len(serialized)
    start = (page - 1) * page_size
    end = start + page_size
    return ScanJobGroupsResponse(
        job_id=job_id,
        kind=kind,
        page=page,
        page_size=page_size,
        total=total,
        items=serialized[start:end],
    )


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scan_job(
    job_id: str = Path(..., min_length=1),
    allow_stale_running: bool = Query(default=False),
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db_session),
) -> Response:
    job_repo = ScanJobRepository(db)
    job = job_repo.get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"scan_job={job_id} not found")

    if job.status in {"queued", "running"}:
        if not allow_stale_running:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"scan_job={job_id} with status='{job.status}' cannot be deleted; "
                    "use allow_stale_running=true only for stale jobs"
                ),
            )
        if not _is_stale_job(job.started_at or job.requested_at, settings.scan_job_timeout_seconds):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"scan_job={job_id} with status='{job.status}' is not stale yet; "
                    "metadata deletion is blocked for active jobs"
                ),
            )

    dependencies = job_repo.count_delete_dependencies(job_id)
    if dependencies.has_blockers:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"cannot delete scan_job={job_id}: dependent metadata exists "
                f"(exact_groups={dependencies.exact_groups}, "
                f"similar_groups={dependencies.similar_groups}, "
                f"action_items={dependencies.action_items})"
            ),
        )

    job_repo.delete(job_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _is_stale_job(reference_timestamp: Optional[str], timeout_seconds: int) -> bool:
    if not reference_timestamp:
        return False
    parsed = _parse_datetime(reference_timestamp)
    if parsed is None:
        return False
    threshold = max(int(timeout_seconds), 60)
    age_seconds = (datetime.now(timezone.utc) - parsed).total_seconds()
    return age_seconds >= threshold


def _parse_datetime(value: str) -> Optional[datetime]:
    raw = value.strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _resolve_root_ids(requested_root_ids: Optional[list[int]], root_repo: ScanRootRepository) -> list[int]:
    if requested_root_ids:
        unique_ids = sorted(set(requested_root_ids))
        roots = [root_repo.get(root_id) for root_id in unique_ids]
        if any(root is None for root in roots):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="one or more scan roots were not found")
        if any(root.enabled != 1 for root in roots if root is not None):
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="disabled scan root selected")
        return unique_ids

    return [root.id for root in root_repo.list_all(enabled=True)]
