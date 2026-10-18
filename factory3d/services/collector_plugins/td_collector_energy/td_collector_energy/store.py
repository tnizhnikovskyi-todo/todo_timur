"""Store: атомарне збереження стану плагіна (JSON, tmp + rename) і відновлення після рестарту (R-44 п.9)."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from collector.util.timeutil import parse_iso, to_iso_z

from . import limits

FILE_NAME = "td_energy_ctl.json"
VERSION = 1


def _empty() -> dict[str, Any]:
    return {"v": VERSION, "saved_at": None, "config": None, "engine": {}, "intents": {}, "overrides": {}, "memo": {}}


class Store:
    def __init__(self, state_dir: Path | None, log: logging.Logger | None = None) -> None:
        self.path = Path(state_dir) / FILE_NAME if state_dir else None
        self.log = log or logging.getLogger("collector.plugin.energy_ctl")
        self.data: dict[str, Any] = _empty()
        self.problem: str | None = None  # «пошкоджено» / «застаріло» після load()
        self.saves = 0
        self._last_save = float("-inf")

    # --- завантаження ---------------------------------------------------------------------------
    def load(self, now: datetime) -> None:
        self.data, self.problem = _empty(), None
        if self.path is None or not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            saved = parse_iso(raw["saved_at"])
            if raw.get("v") != VERSION or not isinstance(raw.get("engine"), dict):
                raise ValueError("несумісний формат")
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.problem = f"стан пошкоджено ({exc}): старт з порожнього"
            self.log.warning(self.problem)
            return
        if (now - saved).total_seconds() > limits.STATE_MAX_AGE_S:
            self.problem = "стан старший за 7 діб відкинуто"
            self.log.info(self.problem)
            return
        for key, empty in _empty().items():
            if key in raw:
                self.data[key] = raw[key]
            else:
                self.data[key] = empty

    # --- збереження -----------------------------------------------------------------------------
    def save(self, now: datetime, *, min_interval_s: float = 0.0) -> bool:
        """Атомарний запис (`tmp` → `os.replace`); без `state_dir` — нічого не робить."""
        if self.path is None:
            return False
        mono = now.timestamp()
        if mono - self._last_save < min_interval_s:
            return False
        self.data["saved_at"] = to_iso_z(now)
        self.prune(now)
        tmp = self.path.with_suffix(".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(self.data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as exc:
            self.log.warning("не вдалося зберегти стан: %s", exc)
            return False
        self._last_save = mono
        self.saves += 1
        return True

    # --- конфіг-кеш (≤ 7 діб) ---------------------------------------------------------------------
    def cache_config(self, raw: dict[str, Any], now: datetime) -> None:
        self.data["config"] = {"saved_at": to_iso_z(now), "raw": raw}

    def cached_config(self, now: datetime) -> dict[str, Any] | None:
        item = self.data.get("config")
        if not item:
            return None
        try:
            if (now - parse_iso(item["saved_at"])).total_seconds() > limits.CONFIG_CACHE_MAX_AGE_S:
                return None
            return item["raw"]  # type: ignore[no-any-return]
        except (KeyError, ValueError, TypeError):
            return None

    # --- інтенти (R-52 п.6) ----------------------------------------------------------------------
    @property
    def intents(self) -> dict[str, dict[str, Any]]:
        return self.data["intents"]  # type: ignore[no-any-return]

    def prune(self, now: datetime) -> None:
        """Інтенти зберігаються 24 год або 500 записів (найновіші)."""
        items = self.intents
        cutoff = now.timestamp() - limits.INTENT_KEEP_S
        for idem in [k for k, v in items.items() if v.get("ts", 0) < cutoff]:
            del items[idem]
        if len(items) > limits.INTENT_KEEP_N:
            for idem, _ in sorted(items.items(), key=lambda kv: kv[1].get("ts", 0))[
                : len(items) - limits.INTENT_KEEP_N
            ]:
                del items[idem]
