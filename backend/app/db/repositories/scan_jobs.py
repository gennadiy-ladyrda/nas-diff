from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import ActionItem, ExactGroup, File, ScanJob, ScanJobRoot, SimilarGroup


@dataclass(frozen=True)
class ScanJobDeleteDependencies:
    exact_groups: int
    similar_groups: int
    action_items: int

    @property
    def has_blockers(self) -> bool:
        return (self.exact_groups + self.similar_groups + self.action_items) > 0


class ScanJobRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, job_id: str, mode: str, status: str = "queued") -> ScanJob:
        scan_job = ScanJob(id=job_id, mode=mode, status=status)
        self.session.add(scan_job)
        self.session.commit()
        self.session.refresh(scan_job)
        return scan_job

    def get(self, job_id: str) -> ScanJob | None:
        return self.session.get(ScanJob, job_id)

    def add_roots(self, job_id: str, *, root_ids: list[int]) -> None:
        payload = [ScanJobRoot(job_id=job_id, root_id=root_id) for root_id in root_ids]
        self.session.add_all(payload)
        self.session.commit()

    def list_root_ids(self, job_id: str) -> list[int]:
        stmt = (
            select(ScanJobRoot.root_id)
            .where(ScanJobRoot.job_id == job_id)
            .order_by(ScanJobRoot.root_id.asc())
        )
        return list(self.session.scalars(stmt))

    def list_recent(self, *, limit: int = 50) -> list[ScanJob]:
        stmt = select(ScanJob).order_by(ScanJob.requested_at.desc()).limit(limit)
        return list(self.session.scalars(stmt))

    def list_jobs(
        self,
        *,
        page: int = 1,
        page_size: int = 50,
        status: str | None = None,
        mode: str | None = None,
        order: str = "desc",
    ) -> tuple[list[ScanJob], int]:
        filters = []
        if status is not None:
            filters.append(ScanJob.status == status)
        if mode is not None:
            filters.append(ScanJob.mode == mode)

        order_by = ScanJob.requested_at.desc() if order == "desc" else ScanJob.requested_at.asc()
        tie_breaker = ScanJob.id.desc() if order == "desc" else ScanJob.id.asc()
        offset = (page - 1) * page_size

        stmt = (
            select(ScanJob)
            .where(*filters)
            .order_by(order_by, tie_breaker)
            .offset(offset)
            .limit(page_size)
        )
        total_stmt = select(func.count()).select_from(ScanJob).where(*filters)
        total = int(self.session.scalar(total_stmt) or 0)
        return list(self.session.scalars(stmt)), total

    def count_delete_dependencies(self, job_id: str) -> ScanJobDeleteDependencies:
        exact_groups = int(
            self.session.scalar(
                select(func.count()).select_from(ExactGroup).where(ExactGroup.job_id == job_id)
            )
            or 0
        )
        similar_groups = int(
            self.session.scalar(
                select(func.count()).select_from(SimilarGroup).where(SimilarGroup.job_id == job_id)
            )
            or 0
        )
        action_items = int(
            self.session.scalar(
                select(func.count())
                .select_from(ActionItem)
                .join(File, File.id == ActionItem.file_id)
                .where(
                    or_(
                        File.first_seen_job_id == job_id,
                        File.last_seen_job_id == job_id,
                    )
                )
            )
            or 0
        )
        return ScanJobDeleteDependencies(
            exact_groups=exact_groups,
            similar_groups=similar_groups,
            action_items=action_items,
        )

    def delete(self, job_id: str) -> None:
        self._require(job_id)
        self.session.execute(delete(ScanJob).where(ScanJob.id == job_id))
        self.session.commit()

    def update_status(
        self,
        job_id: str,
        *,
        status: str,
        error_message: str | None = None,
        set_started_at: bool = False,
        set_finished_at: bool = False,
    ) -> ScanJob:
        scan_job = self._require(job_id)

        scan_job.status = status
        if error_message is not None:
            scan_job.error_message = error_message
        if set_started_at:
            scan_job.started_at = _utc_iso_now()
        if set_finished_at:
            scan_job.finished_at = _utc_iso_now()

        self.session.commit()
        self.session.refresh(scan_job)
        return scan_job

    def update_metrics(
        self,
        job_id: str,
        *,
        files_seen: int | None = None,
        files_indexed: int | None = None,
        exact_groups_found: int | None = None,
        similar_groups_found: int | None = None,
        reclaimable_bytes: int | None = None,
    ) -> ScanJob:
        scan_job = self._require(job_id)

        if files_seen is not None:
            scan_job.files_seen = files_seen
        if files_indexed is not None:
            scan_job.files_indexed = files_indexed
        if exact_groups_found is not None:
            scan_job.exact_groups_found = exact_groups_found
        if similar_groups_found is not None:
            scan_job.similar_groups_found = similar_groups_found
        if reclaimable_bytes is not None:
            scan_job.reclaimable_bytes = reclaimable_bytes

        self.session.commit()
        self.session.refresh(scan_job)
        return scan_job

    def _require(self, job_id: str) -> ScanJob:
        scan_job = self.get(job_id)
        if scan_job is None:
            raise LookupError(f"scan_job={job_id} not found")
        return scan_job


def _utc_iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
