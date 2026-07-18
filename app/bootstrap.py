from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app.config.loader import get_settings
from app.config.models import AppSettings
from app.db.session import build_engine, build_session_factory, init_database
from app.logging.setup import configure_logging
from app.queue.repository import SqliteQueueRepository

logger = logging.getLogger(__name__)


@dataclass
class AppContainer:
    settings: AppSettings
    session_factory: sessionmaker[Session]
    queue_repo: SqliteQueueRepository
    logs_dir: Path


def build_container() -> AppContainer:
    settings = get_settings()
    paths = settings.paths()
    configure_logging(paths.logs_dir / "app.log", settings.agent.log_level)
    engine = build_engine(paths.db_path)
    init_database(engine)
    session_factory = build_session_factory(engine)
    queue_repo = SqliteQueueRepository(session_factory)
    return AppContainer(
        settings=settings,
        session_factory=session_factory,
        queue_repo=queue_repo,
        logs_dir=paths.logs_dir,
    )


class AgentProcessController:
    def __init__(self) -> None:
        self._proc: subprocess.Popen[str] | None = None

    def start(self) -> bool:
        if self._proc is not None and self._proc.poll() is None:
            return True
        self._proc = subprocess.Popen(
            [sys.executable, "-m", "app.main", "--agent"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        logger.info("Agent process started", extra={"component": "bootstrap"})
        return True

    def stop(self) -> None:
        if self._proc is None:
            return
        if self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        logger.info("Agent process stopped", extra={"component": "bootstrap"})
        self._proc = None

    def is_running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

