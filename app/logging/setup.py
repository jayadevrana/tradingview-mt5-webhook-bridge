from __future__ import annotations

import logging
from pathlib import Path

from app.logging.json_formatter import JsonLogFormatter


def configure_logging(log_file: Path, level: str = "INFO") -> None:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger()
    logger.setLevel(level.upper())
    logger.handlers.clear()

    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(JsonLogFormatter())
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(JsonLogFormatter())
    logger.addHandler(stream_handler)
