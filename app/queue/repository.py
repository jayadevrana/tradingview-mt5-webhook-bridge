from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import QueueItem, QueueTransition
from app.domain.enums import QueueState
from app.domain.models import QueueItemRef


class SqliteQueueRepository:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def enqueue(self, correlation_id: str, event_id: str, created_at: datetime) -> QueueItemRef:
        with self._session_factory() as session:
            item = QueueItem(
                correlation_id=correlation_id,
                event_id=event_id,
                state=QueueState.QUEUED.value,
                created_at=created_at,
                updated_at=created_at,
                attempt_count=0,
            )
            session.add(item)
            session.flush()
            transition = QueueTransition(
                queue_item_id=item.id,
                from_state=None,
                to_state=QueueState.QUEUED.value,
                reason="initial enqueue",
                created_at=created_at,
            )
            session.add(transition)
            session.commit()
            return QueueItemRef(
                queue_item_id=item.id,
                correlation_id=item.correlation_id,
                event_id=item.event_id,
                state=QueueState(item.state),
                created_at=item.created_at,
                attempt_count=item.attempt_count,
            )

    def claim_next(self, now_utc: datetime | None = None) -> QueueItemRef | None:
        claim_time = now_utc or datetime.now(timezone.utc)
        with self._session_factory() as session:
            with session.begin():
                stmt = (
                    select(QueueItem)
                    .where(QueueItem.state == QueueState.QUEUED.value)
                    .order_by(QueueItem.id.asc())
                    .limit(1)
                )
                row = session.execute(stmt).scalar_one_or_none()
                if row is None:
                    return None
                from_state = row.state
                row.state = QueueState.PROCESSING.value
                row.claimed_at = claim_time
                row.updated_at = claim_time
                row.attempt_count = row.attempt_count + 1
                transition = QueueTransition(
                    queue_item_id=row.id,
                    from_state=from_state,
                    to_state=QueueState.PROCESSING.value,
                    reason="claimed by worker",
                    created_at=claim_time,
                )
                session.add(transition)
            return QueueItemRef(
                queue_item_id=row.id,
                correlation_id=row.correlation_id,
                event_id=row.event_id,
                state=QueueState(row.state),
                created_at=row.created_at,
                attempt_count=row.attempt_count,
            )

    def transition(self, queue_item_id: int, to_state: QueueState, reason: str | None = None) -> None:
        now_utc = datetime.now(timezone.utc)
        with self._session_factory() as session:
            with session.begin():
                item = session.get(QueueItem, queue_item_id)
                if item is None:
                    raise ValueError(f"queue_item_id={queue_item_id} not found")
                from_state = item.state
                item.state = to_state.value
                item.updated_at = now_utc
                transition = QueueTransition(
                    queue_item_id=queue_item_id,
                    from_state=from_state,
                    to_state=to_state.value,
                    reason=reason,
                    created_at=now_utc,
                )
                session.add(transition)

