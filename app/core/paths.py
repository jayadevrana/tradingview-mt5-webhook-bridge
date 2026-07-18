from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path

from app.core.constants import APP_SLUG


@dataclass(frozen=True)
class AppPaths:
    root_dir: Path
    data_dir: Path
    logs_dir: Path
    db_path: Path


def resolve_data_root() -> Path:
    if platform.system() == "Windows":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "TV2MT5Bridge"
    return Path.home() / f".{APP_SLUG}"


def build_paths(explicit_root: Path | None = None) -> AppPaths:
    root = explicit_root or resolve_data_root()
    data_dir = root / "data"
    logs_dir = root / "logs"
    db_path = data_dir / "tv2mt5.sqlite3"
    data_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)
    return AppPaths(root_dir=root, data_dir=data_dir, logs_dir=logs_dir, db_path=db_path)
