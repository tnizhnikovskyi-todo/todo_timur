"""JSON-логи і SecretFilter (SPEC §8.10)."""
from __future__ import annotations

import fnmatch
import json
import logging
import os
import re
import sys
from datetime import UTC, datetime
from typing import Any

MASK = "***"
_SECRET_ENV = ("F3D_*TOKEN*", "F3D_*PASSWORD*", "F3D_*SECRET*")
_MIN_SECRET_LEN = 4
_PATTERNS = [
    re.compile(r"(?i)(authorization|x-f3d-token)(['\"]?\s*[:=]\s*['\"]?)(bearer\s+)?[^\s,;'\"&}]+"),
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+/=\-]+"),
    re.compile(r"(?i)\b(password|token)=[^\s&'\"]+"),
]


def _secret_values() -> list[str]:
    vals = [
        v for k, v in os.environ.items()
        if len(v) >= _MIN_SECRET_LEN and any(fnmatch.fnmatchcase(k.upper(), p) for p in _SECRET_ENV)
    ]
    return sorted(set(vals), key=len, reverse=True)


def mask(text: str) -> str:
    text = _PATTERNS[0].sub(lambda m: f"{m.group(1)}{m.group(2)}{MASK}", text)
    text = _PATTERNS[1].sub(f"Bearer {MASK}", text)
    text = _PATTERNS[2].sub(lambda m: f"{m.group(1)}={MASK}", text)
    for secret in _secret_values():
        text = text.replace(secret, MASK)
    return text


class SecretFilter(logging.Filter):
    """Замінює секрети у повідомленні запису на `***` (кінцеве повідомлення, без args)."""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            msg = record.getMessage()
        except (TypeError, ValueError):
            msg = str(record.msg)
        record.msg = mask(msg)
        record.args = None
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = mask(record.exc_text)
        return True


class JsonFormatter(logging.Formatter):
    EXTRA = ("source", "code", "route", "cmd")

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z",
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key in self.EXTRA:
            if hasattr(record, key):
                data[key] = getattr(record, key)
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        return json.dumps(data, ensure_ascii=False)


def setup_logging(level: str = "INFO", json_logs: bool = True, stream: Any = None) -> logging.Handler:
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(
        JsonFormatter() if json_logs else logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
    handler.addFilter(SecretFilter())
    root = logging.getLogger()
    for h in list(root.handlers):
        if getattr(h, "_f3d", False):
            root.removeHandler(h)
    handler._f3d = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    for noisy in ("pymodbus", "paho", "bacpypes3", "asyncio", "aiohttp.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return handler
