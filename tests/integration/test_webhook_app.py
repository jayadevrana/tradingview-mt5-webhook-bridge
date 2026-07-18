from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import AlertRecord, QueueItem, WebhookReceipt
from app.db.session import build_engine, build_session_factory, init_database
from app.webhook.app import build_test_webhook_app
from app.webhook.service import WebhookIntakeService


def _build_client(tmp_path: Path) -> tuple[TestClient, sessionmaker[Session]]:
    db_path = tmp_path / "webhook.sqlite3"
    engine = build_engine(db_path)
    init_database(engine)
    session_factory = build_session_factory(engine)
    service = WebhookIntakeService(
        session_factory=session_factory,
        endpoint_token="phase2-endpoint-token",
        payload_secret="phase2-shared-secret",
    )
    app = build_test_webhook_app(service)
    return TestClient(app), session_factory


def _valid_payload(event_id: str = "evt-0001") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "event_id": event_id,
        "sent_at": "2026-03-09T10:30:00Z",
        "source": "tradingview",
        "command": "open_market",
        "account_scope": "primary",
        "symbol": "xauusd",
        "secret": "phase2-shared-secret",
        "options": {"side": "buy", "quantity_lots": 0.01},
    }


def test_healthz(tmp_path: Path) -> None:
    client, _ = _build_client(tmp_path)
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_webhook_accepts_and_queues(tmp_path: Path) -> None:
    client, session_factory = _build_client(tmp_path)
    response = client.post("/webhook/phase2-endpoint-token", json=_valid_payload())
    assert response.status_code == 202
    payload = response.json()
    assert payload["status"] == "accepted"
    assert payload["queue_state"] == "queued"

    with session_factory() as session:
        alerts = session.execute(select(AlertRecord)).scalars().all()
        queue_items = session.execute(select(QueueItem)).scalars().all()
        receipts = session.execute(select(WebhookReceipt)).scalars().all()
        assert len(alerts) == 1
        assert len(queue_items) == 1
        assert len(receipts) == 1
        assert receipts[0].intake_status == "accepted"


def test_webhook_duplicate_event_id_is_ignored(tmp_path: Path) -> None:
    client, session_factory = _build_client(tmp_path)
    payload = _valid_payload(event_id="evt-dup-01")

    first = client.post("/webhook/phase2-endpoint-token", json=payload)
    second = client.post("/webhook/phase2-endpoint-token", json=payload)

    assert first.status_code == 202
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate_ignored"

    with session_factory() as session:
        alerts = session.execute(select(AlertRecord)).scalars().all()
        queue_items = session.execute(select(QueueItem)).scalars().all()
        receipts = session.execute(select(WebhookReceipt)).scalars().all()
        assert len(alerts) == 1
        assert len(queue_items) == 1
        assert len(receipts) == 2
        statuses = [item.intake_status for item in receipts]
        assert "accepted" in statuses
        assert "duplicate_ignored" in statuses


def test_webhook_rejects_wrong_path_token(tmp_path: Path) -> None:
    client, session_factory = _build_client(tmp_path)
    response = client.post("/webhook/wrong-token", json=_valid_payload(event_id="evt-auth-01"))
    assert response.status_code == 401
    assert response.json()["status"] == "auth_failed"

    with session_factory() as session:
        alerts = session.execute(select(AlertRecord)).scalars().all()
        queue_items = session.execute(select(QueueItem)).scalars().all()
        receipts = session.execute(select(WebhookReceipt)).scalars().all()
        assert len(alerts) == 0
        assert len(queue_items) == 0
        assert len(receipts) == 1


def test_webhook_rejects_wrong_payload_secret(tmp_path: Path) -> None:
    client, session_factory = _build_client(tmp_path)
    payload = _valid_payload(event_id="evt-auth-02")
    payload["secret"] = "wrong-secret"
    response = client.post("/webhook/phase2-endpoint-token", json=payload)
    assert response.status_code == 401
    assert response.json()["status"] == "auth_failed"

    with session_factory() as session:
        alerts = session.execute(select(AlertRecord)).scalars().all()
        queue_items = session.execute(select(QueueItem)).scalars().all()
        receipts = session.execute(select(WebhookReceipt)).scalars().all()
        assert len(alerts) == 0
        assert len(queue_items) == 0
        assert len(receipts) == 1
        assert receipts[0].auth_secret_ok == 0


def test_webhook_rejects_invalid_schema(tmp_path: Path) -> None:
    client, session_factory = _build_client(tmp_path)
    payload = _valid_payload(event_id="evt-bad-01")
    payload["command"] = "invalid_command"
    response = client.post("/webhook/phase2-endpoint-token", json=payload)
    assert response.status_code == 422
    assert response.json()["status"] == "invalid_schema"

    with session_factory() as session:
        alerts = session.execute(select(AlertRecord)).scalars().all()
        queue_items = session.execute(select(QueueItem)).scalars().all()
        receipts = session.execute(select(WebhookReceipt)).scalars().all()
        assert len(alerts) == 0
        assert len(queue_items) == 0
        assert len(receipts) == 1


def test_webhook_rejects_invalid_json_body(tmp_path: Path) -> None:
    client, session_factory = _build_client(tmp_path)
    response = client.post(
        "/webhook/phase2-endpoint-token",
        data='{"schema_version":"1.0","event_id":"evt-json"',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 400
    assert response.json()["status"] == "invalid_json"

    with session_factory() as session:
        receipts = session.execute(select(WebhookReceipt)).scalars().all()
        assert len(receipts) == 1


def test_mt5_status_endpoint_returns_provider_payload(tmp_path: Path) -> None:
    db_path = tmp_path / "webhook-status.sqlite3"
    engine = build_engine(db_path)
    init_database(engine)
    session_factory = build_session_factory(engine)
    service = WebhookIntakeService(
        session_factory=session_factory,
        endpoint_token="phase2-endpoint-token",
        payload_secret="phase2-shared-secret",
    )
    app = build_test_webhook_app(
        service,
        mt5_status_provider=lambda: {
            "ok": True,
            "selection_status": "selected",
            "selected_terminal_pid": 12345,
            "account_login": 777001,
            "account_server": "Broker-Demo",
        },
    )
    client = TestClient(app)
    response = client.get("/mt5/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["selection_status"] == "selected"
    assert payload["selected_terminal_pid"] == 12345
    assert payload["account_server"] == "Broker-Demo"
