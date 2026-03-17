from __future__ import annotations

import logging

from app.config import get_settings
from app.db.session import session_scope
from app.services.action_service import ActionService

logger = logging.getLogger("nas_diff.worker.action")


def process_action_batch(batch_id: str) -> None:
    settings = get_settings()
    logger.info("Processing action batch %s", batch_id)
    with session_scope(settings) as session:
        service = ActionService(session, settings)
        service.execute_confirmed_batch(batch_id=batch_id)
    logger.info("Completed action batch %s", batch_id)
