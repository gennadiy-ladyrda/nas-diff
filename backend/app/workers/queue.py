from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from redis import Redis
from rq import Queue

from app.config import Settings, get_settings


def get_worker_queue_names(settings: Optional[Settings] = None) -> tuple[str, ...]:
    active_settings = settings or get_settings()
    return active_settings.worker_queues


class ScanQueueClient:
    def enqueue_scan_job(self, *, job_id: str) -> str:  # pragma: no cover - interface method
        raise NotImplementedError


@dataclass
class RQScanQueueClient(ScanQueueClient):
    redis_url: str
    queue_name: str

    def enqueue_scan_job(self, *, job_id: str) -> str:
        redis_conn = Redis.from_url(self.redis_url)
        queue = Queue(self.queue_name, connection=redis_conn)
        rq_job = queue.enqueue(
            "app.workers.scan_worker.process_scan_job",
            kwargs={"job_id": job_id},
            job_id=f"scan-{job_id}",
        )
        return str(rq_job.id)


def get_scan_queue_client(settings: Optional[Settings] = None) -> ScanQueueClient:
    active_settings = settings or get_settings()
    queue_name = active_settings.worker_queues[0] if active_settings.worker_queues else "scan_queue"
    return RQScanQueueClient(redis_url=active_settings.redis_url, queue_name=queue_name)
