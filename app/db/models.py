from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class AlertRecord(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    correlation_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    received_at: Mapped[datetime] = mapped_column(nullable=False, default=utc_now)
    source_ip: Mapped[Optional[str]] = mapped_column(String(64))
    auth_path_ok: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    auth_secret_ok: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    schema_valid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    dedupe_key: Mapped[str] = mapped_column(String(128), nullable=False)
    is_duplicate: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    raw_payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_payload_json: Mapped[Optional[str]] = mapped_column(Text)
    validation_error: Mapped[Optional[str]] = mapped_column(Text)


class WebhookReceipt(Base):
    __tablename__ = "webhook_receipts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    correlation_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    event_id: Mapped[Optional[str]] = mapped_column(String(128))
    received_at: Mapped[datetime] = mapped_column(nullable=False, default=utc_now)
    source_ip: Mapped[Optional[str]] = mapped_column(String(64))
    auth_path_ok: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    auth_secret_ok: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    schema_valid: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    intake_status: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_payload_json: Mapped[Optional[str]] = mapped_column(Text)
    validation_error: Mapped[Optional[str]] = mapped_column(Text)


class QueueItem(Base):
    __tablename__ = "queue_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    correlation_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=utc_now)
    claimed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text)

    transitions: Mapped[list["QueueTransition"]] = relationship(
        back_populates="queue_item",
        cascade="all, delete-orphan",
    )
    execution_attempts: Mapped[list["ExecutionAttempt"]] = relationship(
        back_populates="queue_item",
        cascade="all, delete-orphan",
    )


class QueueTransition(Base):
    __tablename__ = "queue_transitions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    queue_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("queue_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    from_state: Mapped[Optional[str]] = mapped_column(String(32))
    to_state: Mapped[str] = mapped_column(String(32), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=utc_now)

    queue_item: Mapped["QueueItem"] = relationship(back_populates="transitions")


class ExecutionAttempt(Base):
    __tablename__ = "execution_attempts"
    __table_args__ = (UniqueConstraint("queue_item_id", "attempt_no", name="uq_execution_attempt"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    queue_item_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("queue_items.id", ondelete="CASCADE"),
        nullable=False,
    )
    attempt_no: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(nullable=False, default=utc_now)
    ended_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    mt5_request_json: Mapped[Optional[str]] = mapped_column(Text)
    mt5_response_json: Mapped[Optional[str]] = mapped_column(Text)
    retcode: Mapped[Optional[int]] = mapped_column(Integer)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    outcome: Mapped[str] = mapped_column(String(32), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text)

    queue_item: Mapped["QueueItem"] = relationship(back_populates="execution_attempts")


class AppKV(Base):
    __tablename__ = "app_kv"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(nullable=False, default=utc_now)
