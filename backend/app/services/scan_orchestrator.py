from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.core.dedup_exact import build_exact_groups
from app.core.dedup_similar import build_similar_groups
from app.core.decision_engine import apply_auto_primary_scoring
from app.core.scanner import scan_and_index
from app.db.models import ScanRoot
from app.db.repositories import ScanJobRepository


class ScanOrchestrator:
    def __init__(self, session: Session, settings: Settings) -> None:
        self.session = session
        self.settings = settings
        self.jobs = ScanJobRepository(session)

    def run_job(self, job_id: str) -> None:
        scan_job = self.jobs.get(job_id)
        if scan_job is None:
            raise LookupError(f"scan_job={job_id} not found")

        root_ids = self.jobs.list_root_ids(job_id)
        if not root_ids:
            raise ValueError("scan job has no roots")

        roots = list(
            self.session.scalars(
                select(ScanRoot).where(ScanRoot.id.in_(tuple(root_ids))).order_by(ScanRoot.id.asc())
            )
        )
        if not roots:
            raise ValueError("scan job roots are missing")

        self.jobs.update_status(job_id, status="running", set_started_at=True)

        try:
            scan_result = scan_and_index(
                self.session,
                job_id=job_id,
                roots=roots,
            )

            exact_groups_found = 0
            similar_groups_found = 0
            reclaimable_bytes = 0

            if scan_job.mode in {"exact", "both"}:
                exact = build_exact_groups(
                    self.session,
                    job_id=job_id,
                    root_ids=root_ids,
                )
                exact_groups_found = exact.groups_found
                reclaimable_bytes = exact.reclaimable_bytes

            if scan_job.mode in {"similar", "both"}:
                similar = build_similar_groups(
                    self.session,
                    job_id=job_id,
                    root_ids=root_ids,
                    threshold=self.settings.phash_distance_threshold,
                )
                similar_groups_found = similar.groups_found

            apply_auto_primary_scoring(self.session, job_id=job_id)

            self.jobs.update_metrics(
                job_id,
                files_seen=scan_result.files_seen,
                files_indexed=scan_result.files_indexed,
                exact_groups_found=exact_groups_found,
                similar_groups_found=similar_groups_found,
                reclaimable_bytes=reclaimable_bytes,
            )
            self.jobs.update_status(job_id, status="completed", set_finished_at=True, error_message=None)
        except Exception as exc:
            self.jobs.update_status(
                job_id,
                status="failed",
                error_message=str(exc),
                set_finished_at=True,
            )
            raise


def run_scan_job(session: Session, settings: Settings, *, job_id: str) -> None:
    orchestrator = ScanOrchestrator(session, settings)
    orchestrator.run_job(job_id)
