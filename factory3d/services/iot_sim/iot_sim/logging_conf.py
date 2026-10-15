"""JSON-логи і ``SecretFilter`` (SPEC §8.16, ТБ-06).

Формат: ``{"ts", "level", "logger", "msg", "device", "signal", "run", "proto"}``.
``SecretFilter`` замінює на ``***`` значення секретів (``SIM_*TOKEN*``, ``*PASS*``, ``*APIKEY*`` з
середовища/налаштувань), а також значення ``bs-session-id`` і ``Authorization`` у тексті.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from datetime import UTC, datetime
from typing import Any

MASK = "***"
MIN_SECRET_LEN = 4
_NAME_RE = re.compile(r"^SIM_.*(TOKEN|PASS|APIKEY)", re.IGNORECASE)
_HEADER_RE = re.compile(
    r"""(?ix)((?:bs-session-id|authorization)["']?\s*[:=]\s*["']?)(?:bearer\s+|basic\s+)?[^\s"',;}]+""")
_EXTRA = ("device", "signal", "run", "proto")


def collect_secrets(settings: Any = None) -> list[str]:
    found: set[str] = set()
    for name, value in os.environ.items():
        if _NAME_RE.match(name) and len(value) >= MIN_SECRET_LEN:
            found.add(value)
    if settings is not None:
        for name in ("api_token", "biostar_pass", "woodstore_apikey", "jobs_apikey", "opcua_pass",
                     "odoo_apikey", "odoo_export_token", "genset_relay_token"):
            v = getattr(settings, name, "") or ""
            if len(v) >= MIN_SECRET_LEN:
                found.add(v)
    return sorted(found, key=len, reverse=True)


class SecretFilter(logging.Filter):
    def __init__(self, secrets: list[str] | None = None) -> None:
        super().__init__()
        self.secrets: list[str] = sorted({s for s in (secrets or []) if len(s) >= MIN_SECRET_LEN},
                                         key=len, reverse=True)

    def add(self, *secrets: str) -> None:
        self.secrets = sorted({*self.secrets, *(s for s in secrets if len(s) >= MIN_SECRET_LEN)},
                              key=len, reverse=True)

    def redact(self, text: str) -> str:
        for s in self.secrets:
            text = text.replace(s, MASK)
        return _HEADER_RE.sub(lambda m: m.group(1) + MASK, text)

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self.redact(record.getMessage())
        record.args = None
        if record.exc_info and not record.exc_text:
            record.exc_text = logging.Formatter().formatException(record.exc_info)
        if record.exc_text:
            record.exc_text = self.redact(record.exc_text)
        return True


class JsonFormatter(logging.Formatter):
    def __init__(self, redactor: SecretFilter | None = None) -> None:
        super().__init__()
        self.redactor = redactor

    def format(self, record: logging.LogRecord) -> str:
        data: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname, "logger": record.name, "msg": record.getMessage()}
        for k in _EXTRA:
            data[k] = getattr(record, k, None)
        if record.exc_info:
            data["exc"] = self.formatException(record.exc_info)
        text = json.dumps(data, ensure_ascii=False, default=str)
        return self.redactor.redact(text) if self.redactor else text


def setup_logging(settings: Any = None, stream: Any = None) -> SecretFilter:
    """Налаштовує root-логер; повертає фільтр (щоб додати секрети пізніше)."""
    flt = SecretFilter(collect_secrets(settings))
    handler = logging.StreamHandler(stream or sys.stdout)
    handler.addFilter(flt)
    use_json = True if settings is None else bool(settings.log_json)
    handler.setFormatter(JsonFormatter(flt) if use_json else logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"))
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
    root.setLevel(getattr(logging, (settings.log_level if settings else "INFO").upper(), logging.INFO))
    for noisy in ("asyncua", "uvicorn", "uvicorn.error", "uvicorn.access", "httpx", "httpcore",
                  "pymodbus", "paho", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return flt
