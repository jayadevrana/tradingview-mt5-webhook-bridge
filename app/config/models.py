from __future__ import annotations

from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import DEFAULT_WEBHOOK_HOST, DEFAULT_WEBHOOK_PORT
from app.core.paths import AppPaths, build_paths


class AgentSettings(BaseModel):
    host: str = Field(default=DEFAULT_WEBHOOK_HOST)
    port: int = Field(default=DEFAULT_WEBHOOK_PORT, ge=1, le=65535)
    log_level: str = Field(default="INFO")
    endpoint_token: str = Field(default="change-me-endpoint-token", min_length=8, max_length=128)
    payload_secret: str = Field(default="change-me-payload-secret", min_length=8, max_length=256)

    @field_validator("host")
    @classmethod
    def validate_localhost_binding(cls, value: str) -> str:
        allowed = {"127.0.0.1", "localhost", "::1"}
        if value not in allowed:
            raise ValueError("agent host must bind to localhost only")
        return value


class UiSettings(BaseModel):
    window_title: str = Field(default="TV2MT5 Bridge")


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TV2MT5_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    environment: str = Field(default="dev")
    app_root: Optional[Path] = None
    agent: AgentSettings = Field(default_factory=AgentSettings)
    ui: UiSettings = Field(default_factory=UiSettings)

    def paths(self) -> AppPaths:
        return build_paths(self.app_root)
