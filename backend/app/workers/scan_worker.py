from __future__ import annotations

import logging

from app.config import get_settings
from app.db.session import session_scope
from app.services.scan_orchestrator import run_scan_job

logger = logging.getLogger("nas_diff.worker.scan")


def process_scan_job(job_id: str) -> None:
    settings = get_settings()
    logger.info("Processing scan job %s", job_id)
    with session_scope(settings) as session:
        run_scan_job(session, settings, job_id=job_id)
    logger.info("Completed scan job %s", job_id)
