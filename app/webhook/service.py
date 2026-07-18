from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from hmac import compare_digest
from typing import Any, Dict, Optional
from uuid import uuid4

from pydantic import ValidationError
from sqlalchemy import insert
from sqlalchemy.orm import Session, sessionmaker

from app.db.models import AlertRecord, QueueItem, QueueTransition, WebhookReceipt
from app.domain.enums import QueueState
from app.webhook.schema import TradingViewWebhookAlert

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class IntakeResponse:
    http_status: int
    body: Dict[str, Any]


class WebhookIntakeService:
    def __init__(
        self,
        session_factory: sessionmaker[Session],
        endpoint_token: str,
        payload_secret: str,
    ) -> None:
        self._session_factory = session_factory
        self._endpoint_token = endpoint_token
        self._payload_secret = payload_secret

    def handle_request(
        self,
        endpoint_token: str,
        raw_body: bytes,
        source_ip: Optional[str],
    ) -> IntakeResponse:
        correlation_id = uuid4().hex
        received_at = datetime.now(timezone.utc)
        raw_payload = raw_body.decode("utf-8", errors="replace")
        auth_path_ok = int(compare_digest(endpoint_token, self._endpoint_token))
        if auth_path_ok == 0:
            self._persist_receipt(
                correlation_id=correlation_id,
                event_id=None,
                source_ip=source_ip,
                auth_path_ok=0,
                auth_secret_ok=0,
                schema_valid=0,
                intake_status="auth_failed",
                raw_payload_json=raw_payload,
                normalized_payload_json=None,
                validation_error="invalid endpoint token",
                received_at=received_at,
            )
            return IntakeResponse(
                http_status=401,
                body={
                    "status": "auth_failed",
                    "correlation_id": correlation_id,
                    "message": "invalid endpoint token",
                },
            )

        try:
            parsed_payload = json.loads(raw_payload)
        except json.JSONDecodeError as exc:
            self._persist_receipt(
                correlation_id=correlation_id,
                event_id=None,
                source_ip=source_ip,
                auth_path_ok=1,
                auth_secret_ok=0,
                schema_valid=0,
                intake_status="invalid_json",
                raw_payload_json=raw_payload,
                normalized_payload_json=None,
                validation_error=str(exc),
                received_at=received_at,
            )
            return IntakeResponse(
                http_status=400,
                body={
                    "status": "invalid_json",
                    "correlation_id": correlation_id,
                    "message": "request body is not valid JSON",
                },
            )

        if not isinstance(parsed_payload, dict):
            self._persist_receipt(
                correlation_id=correlation_id,
                event_id=None,
                source_ip=source_ip,
                auth_path_ok=1,
                auth_secret_ok=0,
                schema_valid=0,
                intake_status="invalid_schema",
                raw_payload_json=raw_payload,
                normalized_payload_json=None,
                validation_error="top-level JSON must be an object",
                received_at=received_at,
            )
            return IntakeResponse(
                http_status=422,
                body={
                    "status": "invalid_schema",
                    "correlation_id": correlation_id,
                    "message": "top-level JSON must be an object",
                },
            )

        try:
            alert = TradingViewWebhookAlert.model_validate(parsed_payload)
        except ValidationError as exc:
            event_id_value = parsed_payload.get("event_id")
            event_id = event_id_value if isinstance(event_id_value, str) else None
            self._persist_receipt(
                correlation_id=correlation_id,
                event_id=event_id,
                source_ip=source_ip,
                auth_path_ok=1,
                auth_secret_ok=0,
                schema_valid=0,
                intake_status="invalid_schema",
                raw_payload_json=raw_payload,
                normalized_payload_json=None,
                validation_error=exc.json(),
                received_at=received_at,
            )
            return IntakeResponse(
                http_status=422,
                body={
                    "status": "invalid_schema",
                    "correlation_id": correlation_id,
                    "message": "payload failed schema validation",
                    "errors": exc.errors(),
                },
            )

        auth_secret_ok = int(compare_digest(alert.secret, self._payload_secret))
        normalized_payload = alert.normalized_payload()
        normalized_payload_json = json.dumps(normalized_payload, separators=(",", ":"), ensure_ascii=True)
        if auth_secret_ok == 0:
            self._persist_receipt(
                correlation_id=correlation_id,
                event_id=alert.event_id,
                source_ip=source_ip,
                auth_path_ok=1,
                auth_secret_ok=0,
                schema_valid=1,
                intake_status="auth_failed",
                raw_payload_json=raw_payload,
                normalized_payload_json=normalized_payload_json,
                validation_error="invalid payload secret",
                received_at=received_at,
            )
            return IntakeResponse(
                http_status=401,
                body={
                    "status": "auth_failed",
                    "correlation_id": correlation_id,
                    "event_id": alert.event_id,
                    "message": "invalid payload secret",
                },
            )

        duplicate = self._persist_alert_and_enqueue(
            correlation_id=correlation_id,
            event_id=alert.event_id,
            source_ip=source_ip,
            raw_payload_json=raw_payload,
            normalized_payload_json=normalized_payload_json,
            received_at=received_at,
        )
        if duplicate:
            return IntakeResponse(
                http_status=200,
                body={
                    "status": "duplicate_ignored",
                    "correlation_id": correlation_id,
                    "event_id": alert.event_id,
                },
            )

        logger.info(
            "Webhook accepted and queued",
            extra={"correlation_id": correlation_id, "event_id": alert.event_id, "component": "webhook"},
        )
        return IntakeResponse(
            http_status=202,
            body={
                "status": "accepted",
                "correlation_id": correlation_id,
                "event_id": alert.event_id,
                "queue_state": QueueState.QUEUED.value,
            },
        )

    def _persist_receipt(
        self,
        correlation_id: str,
        event_id: Optional[str],
        source_ip: Optional[str],
        auth_path_ok: int,
        auth_secret_ok: int,
        schema_valid: int,
        intake_status: str,
        raw_payload_json: str,
        normalized_payload_json: Optional[str],
        validation_error: Optional[str],
        received_at: datetime,
    ) -> None:
        receipt = WebhookReceipt(
            correlation_id=correlation_id,
            event_id=event_id,
            source_ip=source_ip,
            auth_path_ok=auth_path_ok,
            auth_secret_ok=auth_secret_ok,
            schema_valid=schema_valid,
            intake_status=intake_status,
            raw_payload_json=raw_payload_json,
            normalized_payload_json=normalized_payload_json,
            validation_error=validation_error,
            received_at=received_at,
        )
        with self._session_factory() as session:
            with session.begin():
                session.add(receipt)

    def _persist_alert_and_enqueue(
        self,
        correlation_id: str,
        event_id: str,
        source_ip: Optional[str],
        raw_payload_json: str,
        normalized_payload_json: str,
        received_at: datetime,
    ) -> bool:
        with self._session_factory() as session:
            with session.begin():
                alert_insert = (
                    insert(AlertRecord)
                    .prefix_with("OR IGNORE")
                    .values(
                        correlation_id=correlation_id,
                        event_id=event_id,
                        received_at=received_at,
                        source_ip=source_ip,
                        auth_path_ok=1,
                        auth_secret_ok=1,
                        schema_valid=1,
                        dedupe_key=event_id,
                        is_duplicate=0,
                        raw_payload_json=raw_payload_json,
                        normalized_payload_json=normalized_payload_json,
                        validation_error=None,
                    )
                )
                insert_result = session.execute(alert_insert)
                inserted = insert_result.rowcount == 1
                intake_status = "accepted" if inserted else "duplicate_ignored"
                receipt = WebhookReceipt(
                    correlation_id=correlation_id,
                    event_id=event_id,
                    source_ip=source_ip,
                    auth_path_ok=1,
                    auth_secret_ok=1,
                    schema_valid=1,
                    intake_status=intake_status,
                    raw_payload_json=raw_payload_json,
                    normalized_payload_json=normalized_payload_json,
                    validation_error=None,
                    received_at=received_at,
                )
                session.add(receipt)

                if not inserted:
                    return True

                queue_item = QueueItem(
                    correlation_id=correlation_id,
                    event_id=event_id,
                    state=QueueState.QUEUED.value,
                    created_at=received_at,
                    updated_at=received_at,
                    attempt_count=0,
                )
                session.add(queue_item)
                session.flush()
                queue_transition = QueueTransition(
                    queue_item_id=queue_item.id,
                    from_state=None,
                    to_state=QueueState.QUEUED.value,
                    reason="webhook accepted",
                    created_at=received_at,
                )
                session.add(queue_transition)
                return False
