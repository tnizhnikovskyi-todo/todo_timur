"""Конфігурація колектора з env, префікс F3D_ (SPEC §8.2)."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

EXIT_CONFIG = 2
MIN_TOKEN_LEN = 32


def _csv(value: object) -> object:
    if isinstance(value, str):
        return [p.strip() for p in value.split(",") if p.strip()]
    return value


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="F3D_", extra="ignore", case_sensitive=False)

    odoo_url: str
    odoo_ca: str = ""
    collector_code: str
    collector_token: str
    config_poll_s: int = 60
    push_interval_s: int = 5
    push_max: int = 1000
    status_interval_s: int = 60
    commands_poll_s: int = 5
    write_enabled: bool = False
    allow_hosts: Annotated[list[str], NoDecode]
    buffer_dir: Path = Path("./state")
    buffer_max_mb: int = 200
    http_push_port: int = 8080
    http_push_allow_ips: Annotated[list[str], NoDecode] = []
    bacnet_bind: str = "0.0.0.0:47808"
    bacnet_device_id: int = 3999
    metrics_port: int = 9108
    log_level: str = "INFO"
    log_json: bool = True
    tz: str = "Europe/Kyiv"
    clock_skew_warn_s: int = 30

    @field_validator("allow_hosts", "http_push_allow_ips", mode="before")
    @classmethod
    def _split_csv(cls, v: object) -> object:
        return _csv(v)

    @field_validator("collector_token")
    @classmethod
    def _token_len(cls, v: str) -> str:
        if len(v) < MIN_TOKEN_LEN:
            raise ValueError(f"F3D_COLLECTOR_TOKEN must be at least {MIN_TOKEN_LEN} characters")
        return v

    @field_validator("odoo_url")
    @classmethod
    def _strip_url(cls, v: str) -> str:
        return v.rstrip("/")

    @property
    def state_file(self) -> Path:
        """Кеш останньої конфігурації (SPEC §8.1.1)."""
        return self.buffer_dir / "config.json"


def resolve_secret(name: str) -> str:
    """Значення секрету лише з env (`*_ref` у params); відсутній -> KeyError."""
    return os.environ[name]
