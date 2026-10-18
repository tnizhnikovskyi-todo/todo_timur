"""Engine: цикл автоматики, режими off/hold/auto, арбітраж ресурсів, перекриття оператора (R-44)."""

from __future__ import annotations

import logging
import time
from collections import deque
from typing import Any

from collector.core.live import LiveCache
from collector.util.timeutil import Clock, to_iso_z

from . import limits
from .actuator import Actuator, Writer
from .config import Config
from .inputs import Inputs
from .model import PRIORITY, Env, Event, Output, Request
from .reporter import Reporter
from .scenarios import CARDS, ORDER
from .scenarios import chp as chp_mod
from .scenarios import common as c
from .store import Store

MODES = ("off", "hold", "auto")
FAIL_BLOCK_S = 60.0


class Engine:
    def __init__(
        self,
        *,
        store: Store,
        reporter: Reporter,
        writer: Writer,
        actuator: Actuator,
        live: LiveCache | None,
        clock: Clock,
        get_cfg: Any,
        write_enabled: Any = None,
        log: logging.Logger | None = None,
    ) -> None:
        self.store, self.reporter, self.writer, self.actuator = store, reporter, writer, actuator
        self.live, self.clock, self.get_cfg = live, clock, get_cfg
        self.write_enabled = write_enabled  # () -> bool: F3D_WRITE_ENABLED збирача
        self.log = log or logging.getLogger("collector.plugin.energy_ctl")
        eng = store.data["engine"]
        self.shared: dict[str, Any] = eng.setdefault("shared", {})
        self.scen: dict[str, dict[str, Any]] = eng.setdefault("scen", {})
        self.mode, self.reason = "off", "немає конфігурації"
        self.started_at = clock.now()
        self.ticks = 0
        self.tick_ms: deque[float] = deque(maxlen=200)
        self.last_tick_at: float | None = None
        self.hold_until = 0.0
        self.refused_until = 0.0
        self.refused_reason = ""
        self.states: dict[str, dict[str, Any]] = {}
        self.controller_remote: bool | None = None
        self.reconciled = False

    # --- перекриття оператора (R-52 п.8) -------------------------------------------------------------
    @property
    def overrides(self) -> dict[str, dict[str, Any]]:
        return self.store.data["overrides"]  # type: ignore[no-any-return]

    def active_overrides(self, now: float) -> dict[str, dict[str, Any]]:
        """Перекриття, що ще діють; прострочені (крім light/vent — їх знімає виконавець) видаляються."""
        for res, item in list(self.overrides.items()):
            if now >= float(item["until"]) and res not in ("light", "vent"):
                del self.overrides[res]
        return {r: i for r, i in self.overrides.items() if now < float(i["until"]) or r in ("light", "vent")}

    # --- режим (R-44 п.1) ----------------------------------------------------------------------------
    def _mode(self, cfg: Config | None, inp: Inputs | None, now: float) -> tuple[str, str]:
        if cfg is None:
            return "off", "немає конфігурації"
        if not cfg.automation_enabled:
            return "off", "автоматику вимкнено"
        if not cfg.write_enabled:
            return "off", "запис вимкнено"
        if self.write_enabled is not None and not self.write_enabled():
            return "off", "запис вимкнено в збирачі"
        if now < self.refused_until:
            return "off", self.refused_reason
        if now < self.hold_until:
            return "hold", "перевищено частоту записів"
        assert inp is not None
        remote = inp.v("remote")
        self.controller_remote = None if remote is None else remote == 1
        if remote is not None and remote != 1:
            return "hold", "контролер у місцевому режимі"
        age = inp.age("grid_kw")
        if age is None:  # показань ще не було: відлік від старту рушія
            if now - self.started_at.timestamp() > cfg.engine.stale_hold_s:
                return "hold", "немає даних grid_kw"
        elif age > cfg.engine.stale_hold_s:
            return "hold", "немає даних grid_kw"
        return "auto", ""

    # --- тік (R-44 п.2) ----------------------------------------------------------------------------------
    async def tick(self) -> None:
        t0 = time.perf_counter()
        now_dt = self.clock.now()
        now = now_dt.timestamp()
        self.ticks += 1
        cfg: Config | None = self.get_cfg()
        inp = Inputs(cfg, self.live, now_dt) if cfg is not None else None
        mode, reason = self._mode(cfg, inp, now)
        events: list[Event] = []
        if mode != self.mode or reason != self.reason:
            events.append(self._mode_event(mode, reason))
            self.mode, self.reason = mode, reason
        if cfg is not None and inp is not None:
            if mode == "auto":
                await self._run(cfg, inp, now_dt, events)
                if now < self.hold_until or now < self.refused_until:  # запобіжник спрацював у цьому тіку
                    mode, reason = self._mode(cfg, inp, now)
                    if (mode, reason) != (self.mode, self.reason):
                        events.append(self._mode_event(mode, reason))
                        self.mode, self.reason = mode, reason
            elif mode == "off":
                self.states = {code: {"state": "off", "ts": to_iso_z(now_dt), "facts": {}} for code in CARDS}
            else:
                self._touch_states(now_dt, reason)
            if mode != "off":
                self._remote_event(inp, events)
        for e in events:
            self.reporter.add_event(e.to_dict(now_dt))
        self.last_tick_at = now
        self.tick_ms.append((time.perf_counter() - t0) * 1000.0)
        self.store.save(now_dt, min_interval_s=5.0)

    def _mode_event(self, mode: str, reason: str) -> Event:
        text = f"Режим рушія: {self.mode} → {mode}" + (f" ({reason})" if reason else "")
        kind = "mode"
        return Event(None, kind, text, level="warn" if mode == "hold" else "info")

    def _remote_event(self, inp: Inputs, events: list[Event]) -> None:
        local_mode = inp.v("remote") is not None and inp.v("remote") != 1
        seen = self.shared.setdefault("seen", {})
        if seen.get("engine:local", False) != local_mode:  # раз на зміну (R-44 п.5)
            seen["engine:local"] = local_mode
            if local_mode:
                events.append(Event(None, "interlock", "Контролер у місцевому режимі", level="warn"))

    def _touch_states(self, now_dt: Any, reason: str) -> None:
        for code in CARDS:
            st = self.states.setdefault(code, {"state": "off", "facts": {}})
            st["ts"] = to_iso_z(now_dt)
            st["facts"] = {**st.get("facts", {}), "reason": reason}

    async def _run(self, cfg: Config, inp: Inputs, now_dt: Any, events: list[Event]) -> None:
        now = now_dt.timestamp()
        blocked = {r for r, until in (self.shared.get("blocked_until") or {}).items() if until > now}
        if inp.t("fire_state") == "alarm":  # R-44 п.8: пожежна тривога — запис vent/light припиняється
            blocked |= {"vent", "light"}
        env = Env(inp, cfg, now_dt, self.shared, self.scen, self.active_overrides(now), blocked)
        self._reconcile(env)
        events += c.housekeeping(env)
        chp_mod.sync_owner(env)
        for code, fn in ORDER:
            try:
                out = fn(env)
            except Exception as exc:  # noqa: BLE001 - збій сценарію не зупиняє решту (R-44 п.2)
                self.log.exception("сценарій %s: внутрішня помилка", code)
                out = Output("warn", {"reason": f"внутрішня помилка: {exc}"})
            env.outputs[code] = out
            events += out.events
        claimed = self._arbitrate(env, events)
        shed = c.shed_request(env)
        if shed is not None and "shed" not in blocked:
            claimed["shed"] = shed
        await self._apply(env, claimed, events)
        self._states(env, now_dt)

    def _arbitrate(self, env: Env, events: list[Event]) -> dict[str, Request]:
        """Ресурс віддається найвищому за пріоритетом; ручне перекриття сильніше за всіх (R-44 п.4)."""
        claimed: dict[str, Request] = {}
        for code in PRIORITY:
            for req in env.outputs.get(code, Output()).requests:
                why = None
                if req.resource in env.overrides:
                    why = "ручне перекриття оператора"
                elif req.resource in env.blocked:
                    why = "ресурс заблоковано"
                elif req.resource in claimed:
                    why = f"ресурс зайнято сценарієм {claimed[req.resource].scenario}"
                if why is None:
                    claimed[req.resource] = req
                elif c.once(env, f"arb:{code}:{req.resource}", why):
                    events.append(Event(code, "override", f"{code}: {req.resource} — {why}", level="warn"))
        return claimed

    async def _apply(self, env: Env, claimed: dict[str, Request], events: list[Event]) -> None:
        now = env.epoch
        for req in claimed.values():
            r = await self.actuator.apply(req, env.inp)
            if r.refused:
                self.refused_until, self.refused_reason = now + 30.0, f"запис заборонено: {r.refused}"
                events.append(Event(req.scenario or None, "interlock", f"Запис вимкнено: {r.refused}", level="warn"))
                return
            if r.rate_exceeded:
                self.hold_until = now + limits.HOLD_AFTER_RATE_S
                events.append(Event(None, "failsafe", "Перевищено частоту записів: hold на 5 хв", level="warn"))
                return
            for failed in r.failed:
                self.shared.setdefault("blocked_until", {})[failed] = now + FAIL_BLOCK_S
                self.shared.setdefault("warn", {})[req.scenario or "peak"] = {
                    "reason": f"помилка запису: {failed}",
                    "until": now + FAIL_BLOCK_S,
                }
                events.append(
                    Event(
                        req.scenario or None,
                        "failsafe",
                        f"{failed}: 3 невдалі записи поспіль, ресурс звільнено",
                        level="warn",
                    )
                )

    def _states(self, env: Env, now_dt: Any) -> None:
        warn = self.shared.get("warn") or {}
        for code in CARDS:
            out = env.outputs.get(code) or Output("off")
            state, facts = out.state, dict(out.facts)
            w = warn.get(code)
            if w and env.epoch < float(w["until"]):
                state, facts["reason"] = "warn", w["reason"]
            if "vent" in env.blocked or "light" in env.blocked:
                if code == "night" and state != "off":
                    state, facts["reason"] = "warn", "пожежна тривога"
            self.states[code] = {"state": state, "ts": to_iso_z(now_dt), "facts": facts}

    # --- відновлення після рестарту (R-44 п.9) --------------------------------------------------------
    def _reconcile(self, env: Env) -> None:
        """Розбіжність із пристроєм (читання назад) скидає володіння; принудительні режими пристрою не чіпаємо."""
        if self.reconciled:
            return
        inp = env.inp
        mode, chp = inp.v("bess_mode"), c.chp_state(env)
        if mode is None and inp.v("chp_state") is None:
            return  # ще немає свіжих показань — повторимо в наступному тіку
        self.reconciled = True
        if env.shared.get("bess_by") and mode is not None and int(mode) == 0:
            env.shared["bess_by"] = None
        state = inp.v("chp_state")
        if chp.get("owner") and state is not None and int(state) == 0:
            chp["owner"], chp["started_at"] = None, None
        lst = c.shed_list(env)
        for it in list(lst):
            cur = inp.v(it["signal"])
            if cur is not None and cur >= 100 and it["pct"] != 100:
                lst.remove(it)

    # --- звітність ---------------------------------------------------------------------------------------
    def tick_p95(self) -> int:
        data = sorted(self.tick_ms)
        return round(data[int(0.95 * (len(data) - 1))]) if data else 0

    def snapshot(self) -> dict[str, Any]:
        cfg: Config | None = self.get_cfg()
        now = self.clock.now()
        return {
            "config_version_applied": cfg.version if cfg is not None else 0,
            "engine": {
                "mode": self.mode,
                "reason": self.reason or None,
                "started_at": to_iso_z(self.started_at),
                "ticks": self.ticks,
                "tick_ms_p95": self.tick_p95(),
                "writes_last_min": self.writer.writes_last_min(now),
                "controller_remote": self.controller_remote,
            },
            "scenarios": {code: dict(self.states[code]) for code in CARDS if code in self.states},
        }
