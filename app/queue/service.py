from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from app.queue.repository import SqliteQueueRepository

logger = logging.getLogger(__name__)


class QueueService:
    def __init__(self, queue_repo: SqliteQueueRepository) -> None:
        self._queue_repo = queue_repo

    def enqueue_event(self, event_id: str) -> str:
        correlation_id = uuid4().hex
        now_utc = datetime.now(timezone.utc)
        self._queue_repo.enqueue(correlation_id=correlation_id, event_id=event_id, created_at=now_utc)
        logger.info(
            "Event queued",
            extra={"correlation_id": correlation_id, "event_id": event_id, "component": "queue"},
        )
        return correlation_id
