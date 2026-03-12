from __future__ import annotations

from app.config import Settings, get_settings


def get_worker_queue_names(settings: Settings | None = None) -> tuple[str, ...]:
    active_settings = settings or get_settings()
    return active_settings.worker_queues
