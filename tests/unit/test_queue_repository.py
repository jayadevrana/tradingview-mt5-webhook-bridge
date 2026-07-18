from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.db.session import build_engine, build_session_factory, init_database
from app.domain.enums import QueueState
from app.queue.repository import SqliteQueueRepository


def _make_repo(tmp_path: Path) -> SqliteQueueRepository:
    db_path = tmp_path / "test.sqlite3"
    engine = build_engine(db_path)
    init_database(engine)
    session_factory = build_session_factory(engine)
    return SqliteQueueRepository(session_factory)


def test_claim_next_follows_enqueue_order(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    now = datetime.now(timezone.utc)
    first = repo.enqueue(correlation_id="c1", event_id="e1", created_at=now)
    second = repo.enqueue(correlation_id="c2", event_id="e2", created_at=now)
    third = repo.enqueue(correlation_id="c3", event_id="e3", created_at=now)

    claim1 = repo.claim_next(now_utc=now)
    claim2 = repo.claim_next(now_utc=now)
    claim3 = repo.claim_next(now_utc=now)
    claim4 = repo.claim_next(now_utc=now)

    assert claim1 is not None and claim1.queue_item_id == first.queue_item_id
    assert claim2 is not None and claim2.queue_item_id == second.queue_item_id
    assert claim3 is not None and claim3.queue_item_id == third.queue_item_id
    assert claim4 is None


def test_transition_updates_state(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    now = datetime.now(timezone.utc)
    item = repo.enqueue(correlation_id="c10", event_id="e10", created_at=now)
    claimed = repo.claim_next(now_utc=now)
    assert claimed is not None
    repo.transition(item.queue_item_id, QueueState.SUCCEEDED, reason="unit-test")
