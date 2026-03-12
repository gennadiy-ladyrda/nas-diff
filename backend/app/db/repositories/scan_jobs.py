from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ScanJob


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

    def list_recent(self, *, limit: int = 50) -> list[ScanJob]:
        stmt = select(ScanJob).order_by(ScanJob.requested_at.desc()).limit(limit)
        return list(self.session.scalars(stmt))

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
