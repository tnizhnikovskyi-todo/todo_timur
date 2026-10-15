"""Спільні помічники вбудованих плагінів: схеми A.1/A.2, валідація, EWMA, лінійний масштаб (SPEC §8.5–§8.8)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator  # type: ignore[import-untyped]

from collector.core.types import SourceCfg
from collector.util.timeutil import Clock, SystemClock, parse_iso

SCHEMA_DIR = Path(__file__).parent / "schemas"
SECRET_KEYS = ("password", "token", "secret", "api_key", "key")
EWMA_ALPHA = 0.3


@cache
def load_schema(name: str) -> dict:
    """`address.<type>` / `params.<type>` -> JSON Schema із schemas/."""
    return json.loads((SCHEMA_DIR / f"{name}.json").read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def schema_errors(schema: dict, instance: Any, prefix: str = "") -> list[str]:
    out: list[str] = []
    for err in sorted(Draft202012Validator(schema).iter_errors(instance), key=lambda e: list(map(str, e.path))):
        key = ".".join(str(p) for p in err.path) or "(root)"
        out.append(f"{prefix}{key}: {err.message[:200]}")
    return out


def validate_source(
    source: SourceCfg, address_schema: dict, params_schema: dict, signal_check: Any = None, params_check: Any = None
) -> list[str]:
    """Помилки params та address усіх сигналів джерела (порожній список = ок)."""
    errors: list[str] = []
    params = source.params
    if not isinstance(params, dict):
        return ["params: параметри мають бути об'єктом JSON"]
    for k in params:
        if k in SECRET_KEYS:
            errors.append(f"{k}: секрети не зберігаються в Odoo — використайте {k}_ref")
    errors += schema_errors(params_schema, params, "params.")
    if params_check is not None:
        errors += params_check(params)
    for sg in source.signals:
        addr = sg.address
        if not addr:  # `{}` — «не налаштовано» (A.0)
            continue
        if not isinstance(addr, dict):
            errors.append(f"{sg.code}: адреса має бути об'єктом JSON")
            continue
        errs = schema_errors(address_schema, addr)
        if not errs and signal_check is not None:
            errs = signal_check(addr, params)
        errors += [f"{sg.code}: {e}" for e in errs]
    return errors


class Ewma:
    """Експоненційне згладжування затримки (мс)."""

    def __init__(self, alpha: float = EWMA_ALPHA) -> None:
        self.alpha = alpha
        self.value: float | None = None

    def add(self, x: float) -> None:
        self.value = x if self.value is None else self.alpha * x + (1 - self.alpha) * self.value


def ctx_clock(ctx: Any) -> Clock:
    """Годинник із PluginContext (поле `clock`, якщо ядро/тест його задали), інакше системний."""
    return getattr(ctx, "clock", None) or SystemClock()


def linear(raw: float, address: dict) -> float:
    """eng = raw·scale + offset (A.0, R-02, X-63)."""
    return raw * float(address.get("scale", 1)) + float(address.get("offset", 0))


def canonical_json(obj: Any) -> str:
    """Канонічний JSON для event_id (відсортовані ключі, без пробілів, UTF-8 без екранування)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def parse_ts(value: Any) -> datetime:
    """ISO 8601 або епоха (> 1e11 -> мс, інакше с) -> tz-aware UTC; ValueError при помилці."""
    if isinstance(value, bool):
        raise ValueError("bool is not a timestamp")  # noqa: TRY004
    if isinstance(value, int | float):
        sec = value / 1000 if abs(value) > 1e11 else value
        return datetime.fromtimestamp(sec, UTC)
    if isinstance(value, str):
        txt = value.strip()
        try:
            return parse_iso(txt)
        except ValueError:
            return parse_ts(float(txt))
    raise ValueError(f"unsupported timestamp {value!r}")
