from __future__ import annotations

from functools import lru_cache

from app.config.models import AppSettings


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    return AppSettings()
