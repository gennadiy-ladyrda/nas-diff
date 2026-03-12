from __future__ import annotations

import logging

from redis import Redis
from rq import Queue, Worker

from app.config import get_settings
from app.log_setup import configure_logging
from app.workers.queue import get_worker_queue_names

logger = logging.getLogger("nas_diff.worker")


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    queue_names = get_worker_queue_names(settings)
    redis_conn = Redis.from_url(settings.redis_url)
    queues = [Queue(name, connection=redis_conn) for name in queue_names]

    logger.info("Worker startup complete. Queues: %s", ", ".join(queue_names))
    logger.info("Worker event loop started and ready to process jobs")

    worker = Worker(queues, connection=redis_conn)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
