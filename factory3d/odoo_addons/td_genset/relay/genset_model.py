"""Стан-машина HGM6120N і фізика генератора D700 для fake_relay (SPEC td_genset §8.3, Додаток D).

Без залежності від Odoo і від fake_relay: час — симуляційні секунди (`tick(dt)`), весь стан у одному об'єкті.
Публічний REST-шар (/sim/v1/*, API-F-01…API-F-09) викликає методи `state_json`, `set_mains`, `set_remote_start`,
`set_load`, `fault`, `clear`, `set_fuel`, `set_time`, `reset`, `events_json`; помилки — `SimError(status, detail)`.
"""

import itertools
import json
import logging
import math
import os
import random
import time
from datetime import datetime, timedelta, timezone

PROFILES_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "profiles")
STATE_CODES = {
    "standby": 1,
    "mains_abnormal": 2,
    "starting": 3,
    "safety_on": 4,
    "warming": 5,
    "running": 6,
    "loaded": 7,
    "cooling": 8,
    "stopping": 9,
    "alarm_shutdown": 10,
}
MODES = ("stop", "manual", "auto", "test")
SUBSTEP_S = 0.5  # максимальний внутрішній крок, с
MAX_SUBSTEPS = 2000
TEST_S = 180.0  # «тест 3 хв» (ТР 1.2)
OVER_SPEED_RPM = 1725
# код тривоги → (назва, серйозність, одиниця)
ALARM_DEFS = {
    "low_oil_pressure": ("Low Oil Pressure", "shutdown", "bar"),
    "high_temp": ("High Temp.", "shutdown", "C"),
    "low_fuel": ("Low Fuel Level", "warning", "%"),
    "low_fuel_sd": ("Fuel Level Low", "shutdown", "%"),
    "start_fail": ("Fail to Start", "shutdown", None),
    "batt_low": ("Battery Under Voltage", "warning", "V"),
    "batt_high": ("Battery Over Voltage", "warning", "V"),
    "over_speed": ("Over Speed", "shutdown", "rpm"),
    "emergency_stop": ("Emergency Stop", "shutdown", None),
    "over_current": ("Genset Over Current", "warning", "kW"),
    "comm_lost": ("Comm Lost", "info", None),
}
FAULT_CODES = (
    "low_oil_pressure",
    "high_temp",
    "low_fuel",
    "start_fail",
    "batt_low",
    "comm_lost",
    "over_speed",
    "emergency_stop",
)
LOG = logging.getLogger("genset_model")
LOG.addHandler(logging.NullHandler())


class SimError(Exception):
    """Помилка REST емулятора: {"detail": ...} з кодом 401/404/409/422."""

    def __init__(self, status, detail):
        super().__init__(detail)
        self.status = status
        self.detail = detail


def load_profile(name):
    """Прочитати profiles/<name>.json (office | d700)."""
    key = str(name).strip().lower()
    if not key.isalnum():
        raise ValueError("bad profile name: %r" % (name,))
    with open(os.path.join(PROFILES_DIR, key + ".json"), encoding="utf-8") as fh:
        return json.load(fh)


def get_tz(name):
    """Часова зона RELAY_TZ; без бази tzdata Europe/Kyiv → фіксований +03:00."""
    try:
        from zoneinfo import ZoneInfo

        return ZoneInfo(name)
    except (ImportError, KeyError, ValueError, OSError):  # немає бази зон (ZoneInfoNotFoundError ⊂ KeyError)
        return timezone(timedelta(hours=3)) if name == "Europe/Kyiv" else timezone.utc


def is_number(val):
    return isinstance(val, (int, float)) and not isinstance(val, bool) and math.isfinite(val)


class GensetModel:
    """HGM6120N + агрегат + мережа + ATS/реле. Усі зміни — під зовнішнім замком (його тримає fake_relay)."""

    def __init__(self, profile, preset=None, seed=None, noise=True, tz="Europe/Kyiv", sim_ts=None):
        self.profile = json.loads(json.dumps(profile))
        self.initial_preset = preset if preset == "plant" else None
        self.rng = random.Random(seed)
        self.noise = noise
        self.tz = get_tz(tz) if isinstance(tz, str) else tz
        self.sim_ts = time.time() if sim_ts is None else float(sim_ts)
        self.event_seq = 0
        self.events = []
        self.test_on_load = False
        self.reset(self.initial_preset)

    # ------------------------------------------------------------------ допоміжне
    def iso(self, ts=None):
        return datetime.fromtimestamp(self.sim_ts if ts is None else ts, self.tz).isoformat(timespec="seconds")

    def _log(self, level, msg, event=None):
        LOG.log(
            level,
            msg,
            extra={
                "sim": {
                    "state": self.state,
                    "mode": self.mode,
                    "p_kw": round(self.p_kw, 1),
                    "fuel_l": round(self.fuel_l, 2),
                    "event": event,
                }
            },
        )

    @property
    def tank_l(self):
        return float(self.profile["tank_l"])

    @property
    def kw_prp(self):
        return float(self.profile["rated"]["kw_prp"])

    @property
    def kw_esp(self):
        return float(self.profile["rated"]["kw_esp"])

    def fuel_pct(self):
        return self.fuel_l / self.tank_l * 100.0

    def load_pct(self, kw=None):
        return (self.p_kw if kw is None else kw) / self.kw_prp * 100.0

    def fuel_lph(self, load_pct):
        """Витрата, л/год: кусково-лінійна по 25/50/75/100 %/ESP (R-01)."""
        table = self.profile["fuel_lph"]
        pts = {float(k): float(v) for k, v in table.items() if k != "esp"}
        pts[self.kw_esp / self.kw_prp * 100.0] = float(table["esp"])
        xs = sorted(pts)
        if len(xs) == 1 or load_pct >= xs[-1]:
            return pts[xs[-1]]
        if load_pct <= xs[0]:
            slope = (pts[xs[1]] - pts[xs[0]]) / (xs[1] - xs[0])
            return max(0.0, pts[xs[0]] + slope * (load_pct - xs[0]))
        for lo, hi in itertools.pairwise(xs):
            if lo <= load_pct <= hi:
                return pts[lo] + (pts[hi] - pts[lo]) * (load_pct - lo) / (hi - lo)
        return pts[xs[-1]]

    # ------------------------------------------------------------------ скидання
    def reset(self, preset=None):
        """Повернути `start` профілю; журнал очищається, id подій продовжує рости."""
        if preset not in (None, "default", "plant"):
            raise SimError(422, "unknown preset: %r (default | plant)" % (preset,))
        self.preset = preset if preset == "plant" else None
        timers = dict(self.profile["timers"])
        if self.preset == "plant":
            timers.update(self.profile.get("timers_plant", {}))
        self.timers = timers
        s, sens = self.profile["start"], self.profile["sensors"]
        self.events = []
        self.mode = s["mode"]
        self.mains_ok = bool(s["mains_ok"])
        self.mains_u, self.mains_f = float(sens["u_v"]), float(sens["f_hz"])
        self.remote_start = False
        self.load_kw = float(s["load_kw"])
        self.load_explicit = False
        self.fuel_l = self.tank_l * float(s["fuel_pct"]) / 100.0
        self.hours, self.kwh, self.starts = float(s["hours"]), float(s["kwh"]), int(s["starts"])
        self.last_test = s.get("last_test")
        self.state, self.engine, self.breaker = "standby", "stopped", "mains"
        self.timer_name, self.timer_left, self._over = None, 0.0, 0.0
        self.sub, self.attempt, self.start_reason, self.cool_phase, self.stop_pending = None, 0, None, None, None
        self.alarms, self.armed_start_fail = {}, False
        self.oc_s, self.test_left = 0.0, 0.0
        self.p_kw, self.coolant_c, self.oil_bar = 0.0, float(sens["coolant_idle_c"]), 0.0
        self.batt_v, self.charger_v, self.rpm = float(sens["batt_v"]), 0.0, 0
        self.u_v, self.f_hz = 0.0, 0.0
        self._step(0.0)

    # ------------------------------------------------------------------ тік
    def tick(self, dt):
        """Просунути модель на dt симуляційних секунд (внутрішні кроки ≤ 0.5 с)."""
        if dt <= 0:
            return
        n = min(MAX_SUBSTEPS, max(1, math.ceil(dt / SUBSTEP_S)))
        for _ in range(n):
            self._step(dt / n)

    def _step(self, dt):
        if dt > 0:
            self._physics(dt)
            self.sim_ts += dt
            if self.mode == "test" and self.state in ("running", "loaded"):
                self.test_left -= dt
                if self.test_left <= 0:
                    self.mode = "auto"
            if self.timer_name:
                self.timer_left -= dt
        for _ in range(20):  # ланцюжок нульових таймерів
            if not (self.timer_name and self.timer_left <= 0):
                break
            name, self._over = self.timer_name, self.timer_left
            self.timer_name = None
            self._on_timer(name)
        self._over = 0.0
        for _ in range(3):
            before = (self.state, self.timer_name, self.breaker)
            self._decide()
            self._alarm_checks(dt)
            if before == (self.state, self.timer_name, self.breaker):
                break

    def _noise(self, amp):
        return self.rng.uniform(-amp, amp) if self.noise else 0.0

    def _physics(self, dt):
        sens = self.profile["sensors"]
        running = self.engine == "running"
        gen_ok = running and self.state in ("running", "loaded", "cooling")
        if running and self.state in ("running", "loaded") and (self.breaker == "gen" or self.load_explicit):
            self.p_kw = self.load_kw
        else:
            self.p_kw = 0.0
        if running:
            self.fuel_l = max(0.0, self.fuel_l - self.fuel_lph(self.load_pct()) * dt / 3600.0)
            self.hours += dt / 3600.0
            self.kwh += self.p_kw * dt / 3600.0
        target = float(sens["coolant_run_c"] if running else sens["coolant_idle_c"])
        self.coolant_c += (target - self.coolant_c) * (1.0 - math.exp(-dt / float(sens["coolant_tau_s"])))
        if running:
            self.oil_bar = max(0.0, float(sens["oil_run_bar"]) + self._noise(0.1))
            self.rpm = round(float(sens["rpm_run"]) + self._noise(5))
            self.charger_v = float(sens["charger_v"])
            self.batt_v = float(sens["batt_v"]) + 0.1 + self._noise(0.05)
        else:
            self.oil_bar = float(sens["oil_idle_bar"])
            self.rpm = 250 if self.engine == "cranking" else 0
            self.charger_v = 0.0
            self.batt_v = float(sens["batt_v"]) - (1.0 if self.engine == "cranking" else 0.0)
        if gen_ok:
            self.u_v = float(sens["u_v"]) + self._noise(2)
            self.f_hz = float(sens["f_hz"]) + self._noise(0.1)
        else:
            self.u_v = self.f_hz = 0.0

    # ------------------------------------------------------------------ таймери і переходи
    def _timer(self, name, duration):
        self.timer_name, self.timer_left = name, float(duration) + self._over

    def _set_state(self, state):
        if state != self.state:
            self.state = state
            self._log(logging.INFO, "state -> %s" % state, event="state")

    def _on_timer(self, name):
        t = self.timers
        if name == "mains_abnormal_s":
            if self.state == "mains_abnormal":
                self._begin_start("amf")
        elif name == "start_delay_s":
            self._begin_crank()
        elif name == "crank_fire_s":
            self.starts += 1
            self.engine = "running"
            self.sub = None
            self._set_state("safety_on")
            self._timer("safety_on_s", t["safety_on_s"])
        elif name == "crank_s":  # невдала прокрутка (start_fail)
            self.engine = "stopped"
            self.attempt += 1
            if self.attempt < int(t["start_times"]):
                self.sub = "rest"
                self._timer("crank_rest_s", t["crank_rest_s"])
            else:
                self.armed_start_fail = False
                self._raise("start_fail", value=self.attempt, threshold=int(t["start_times"]))
        elif name == "crank_rest_s":
            self._begin_crank()
        elif name == "safety_on_s":
            self._set_state("warming")
            self._timer("warming_s", t["warming_s"])
        elif name == "warming_s":
            self._set_state("running")
        elif name == "transfer_s":
            self._on_transfer()
        elif name == "mains_normal_s":
            self.stop_pending = "stop_delay"
            self._timer("stop_delay_s", t["stop_delay_s"])
        elif name == "stop_delay_s":
            self.stop_pending = None
            self._begin_cooling()
        elif name == "cooling_s":
            self._begin_stopping()
        elif name == "ets_hold_s":
            self._to_standby()

    def _on_transfer(self):
        if self.state in ("running", "loaded"):
            if self._want_gen():
                self.breaker = "gen"
        elif self.state == "cooling" and self.cool_phase == "transfer":
            self.breaker = "mains" if self.mains_ok else "none"
            self.cool_phase = "cool"
            self._timer("cooling_s", self.timers["cooling_s"])

    def _has_shutdown(self):
        return any(a["severity"] == "shutdown" for a in self.alarms.values())

    def _to_standby(self):
        self.engine, self.breaker = "stopped", "mains"
        self.timer_name, self.sub, self.cool_phase, self.stop_pending = None, None, None, None
        self.attempt, self.load_explicit, self.start_reason = 0, False, None
        self._set_state("standby")

    def _begin_start(self, reason):
        if self._has_shutdown():
            return
        self.start_reason = reason
        self.attempt, self.sub, self.engine = 0, "delay", "stopped"
        self.load_explicit = False
        if reason == "amf":
            self.breaker = "none"  # мережу відкрито
        self._set_state("starting")
        self._timer("start_delay_s", self.timers["start_delay_s"])

    def _begin_crank(self):
        self.sub, self.engine = "crank", "cranking"
        t = self.timers
        if self.armed_start_fail:
            self._timer("crank_s", t["crank_s"])
        else:
            self._timer("crank_fire_s", t["crank_fire_s"])

    def _begin_cooling(self):
        if self.start_reason in ("remote", "test"):
            self.last_test = self.iso()
        self._set_state("cooling")
        if self.breaker == "mains":
            self.cool_phase = "cool"
            self._timer("cooling_s", self.timers["cooling_s"])
        else:
            self.breaker, self.cool_phase = "none", "transfer"  # реле генератора відкрито
            self._timer("transfer_s", self.timers["transfer_s"])

    def _begin_stopping(self):
        self.engine = "stopped"
        self.breaker = "mains" if self.mains_ok else "none"
        self.load_explicit, self.stop_pending, self.cool_phase = False, None, None
        self._set_state("stopping")
        self._timer("ets_hold_s", self.timers["ets_hold_s"])

    def _shutdown(self):
        self.engine = "stopped"
        self.breaker = "mains" if self.mains_ok else "none"
        self.timer_name, self.sub, self.cool_phase, self.stop_pending = None, None, None, None
        self.load_explicit, self.test_left = False, 0.0
        self.p_kw = 0.0
        self._set_state("alarm_shutdown")

    def _want_gen(self):
        return (self.mode == "auto" and not self.mains_ok) or (self.mode == "test" and self.test_on_load)

    def _want_run(self):
        if self.mode == "manual":
            return True
        if self.mode == "test":
            return self.test_left > 0
        return self.remote_start or not self.mains_ok

    def _decide(self):
        st = self.state
        if st in ("alarm_shutdown", "cooling", "stopping"):
            return
        if st == "standby":
            if self.mode == "auto":
                if not self.mains_ok:
                    self._set_state("mains_abnormal")
                    self._timer("mains_abnormal_s", self.timers["mains_abnormal_s"])
                elif self.remote_start:
                    self._begin_start("remote")
            elif self.mode == "test":
                self.test_left = TEST_S if self.test_left <= 0 else self.test_left
                self._begin_start("test")
        elif st == "mains_abnormal":
            if self.mode != "auto" or self.mains_ok:
                self.timer_name = None
                self._set_state("standby")
            elif self.remote_start:
                self._begin_start("amf")
        elif st == "starting":
            if self.mode == "stop":
                self.engine, self.timer_name, self.sub = "stopped", None, None
                self._set_state("standby")
                self.breaker = "mains"
        elif st in ("safety_on", "warming"):
            if self.mode == "stop":
                self._begin_stopping()
        else:  # running / loaded
            self._run_logic()

    def _run_logic(self):
        if self.mode == "stop":
            self._begin_stopping()
            return
        if self.timer_name == "transfer_s":
            return
        if self._want_run():
            if self.stop_pending:
                self.stop_pending, self.timer_name = None, None
            if self.breaker != "gen" and self._want_gen():
                self._timer("transfer_s", self.timers["transfer_s"])
        elif not self.stop_pending:
            if self.breaker == "gen" or self.start_reason == "amf":
                self.stop_pending = "mains_normal"
                self._timer("mains_normal_s", self.timers["mains_normal_s"])
            else:
                self.stop_pending = "stop_delay"
                self._timer("stop_delay_s", self.timers["stop_delay_s"])
        if self.state in ("running", "loaded"):
            loaded = self.breaker == "gen" or (self.load_explicit and self.load_kw > 0)
            self._set_state("loaded" if loaded else "running")

    # ------------------------------------------------------------------ тривоги
    def _alarm_value(self, code):
        al = self.profile["alarms"]
        return {
            "low_oil_pressure": (self.oil_bar, al["oil_low_bar"]),
            "high_temp": (self.coolant_c, al["coolant_high_c"]),
            "low_fuel": (self.fuel_pct(), al["low_fuel_warn_pct"]),
            "low_fuel_sd": (self.fuel_pct(), al["low_fuel_sd_pct"]),
            "batt_low": (self.batt_v, al["batt_low_v"]),
            "batt_high": (self.batt_v, al["batt_high_v"]),
            "over_speed": (self.rpm, OVER_SPEED_RPM),
            "over_current": (self.p_kw, self.kw_prp),
        }.get(code, (None, None))

    def _raise(self, code, forced=False, value=None, threshold=None):
        if code in self.alarms:
            return
        name, severity, unit = ALARM_DEFS[code]
        if value is None and threshold is None:
            value, threshold = self._alarm_value(code)
        self.alarms[code] = {"name": name, "severity": severity, "since": self.iso(), "forced": forced}
        if severity != "info":
            self.event_seq += 1
            self.events.append(
                {
                    "id": self.event_seq,
                    "ts": self.iso(),
                    "code": code,
                    "severity": severity,
                    "name": name,
                    "value": None if value is None else round(float(value), 2),
                    "unit": unit,
                    "threshold": None if threshold is None else round(float(threshold), 2),
                    "text": "%s (%s)" % (name, severity),
                }
            )
            self._log(logging.WARNING, "alarm %s" % name, event=code)
        if severity == "shutdown":
            self._shutdown()

    def _natural(self, code, active):
        if active:
            self._raise(code)
        elif code in self.alarms and not self.alarms[code]["forced"] and self.alarms[code]["severity"] == "warning":
            del self.alarms[code]

    def _alarm_checks(self, dt):
        al = self.profile["alarms"]
        pct = self.fuel_pct()
        self._natural("low_fuel", pct < al["low_fuel_warn_pct"])
        self._natural("low_fuel_sd", pct < al["low_fuel_sd_pct"])
        self._natural("high_temp", self.coolant_c > al["coolant_high_c"])
        if self.engine == "running" and self.state in ("warming", "running", "loaded", "cooling"):
            self._natural("low_oil_pressure", self.oil_bar < al["oil_low_bar"])
        self._natural("batt_low", self.batt_v < al["batt_low_v"])
        self._natural("batt_high", self.batt_v > al["batt_high_v"])
        if self.state in ("running", "loaded") and self.p_kw > self.kw_prp:
            self.oc_s += dt
            if self.oc_s >= float(self.timers["over_current_delay_s"]):
                self._raise("over_current")
        else:
            self.oc_s = 0.0
            self._natural("over_current", False)

    def alarm_list(self, with_info=False):
        return [
            {"code": c, "name": a["name"], "severity": a["severity"], "since": a["since"]}
            for c, a in self.alarms.items()
            if with_info or a["severity"] != "info"
        ]

    @property
    def comm_lost(self):
        return "comm_lost" in self.alarms

    # ------------------------------------------------------------------ API-F-*
    def timers_info(self):
        remaining = round(max(0.0, self.timer_left), 1) if self.timer_name else 0
        return {"active": self.timer_name, "remaining_s": remaining}

    def state_json(self, factor=1.0):
        pf = float(self.profile["sensors"]["pf"])
        gen_ok = self.engine == "running" and self.state in ("running", "loaded", "cooling")
        amps = self.p_kw * 1000.0 / (math.sqrt(3) * float(self.profile["sensors"]["u_v"]) * pf)
        levels = [a["severity"] for a in self.alarms.values()]
        return {
            "profile": self.profile["profile"],
            "sim_time": self.iso(),
            "factor": float(factor),
            "mode": self.mode,
            "state": self.state,
            "state_code": STATE_CODES[self.state],
            "engine": self.engine,
            "mains_ok": self.mains_ok,
            "gen_ok": gen_ok,
            "breaker": self.breaker,
            "remote_start": self.remote_start,
            "p_kw": round(self.p_kw, 1),
            "load_pct": round(self.load_pct(), 1),
            "u_v": round(self.u_v, 1),
            "f_hz": round(self.f_hz, 1),
            "i_a": round(amps, 1),
            "pf": pf,
            "kwh": round(self.kwh, 2),
            "fuel_l": round(self.fuel_l, 2),
            "fuel_pct": round(self.fuel_pct(), 2),
            "fuel_lph": round(self.fuel_lph(self.load_pct()), 1) if self.engine == "running" else 0.0,
            "hours": round(self.hours, 3),
            "starts": self.starts,
            "coolant_c": round(self.coolant_c, 1),
            "oil_bar": round(self.oil_bar, 1),
            "batt_v": round(self.batt_v, 1),
            "charger_v": round(self.charger_v, 1),
            "rpm": self.rpm,
            "alarms": self.alarm_list(),
            "alarm_level": 2 if "shutdown" in levels else (1 if "warning" in levels else 0),
            "timers": self.timers_info(),
            "last_test": self.last_test,
        }

    def set_mains(self, available, u_v=None, f_hz=None):
        if not isinstance(available, bool):
            raise SimError(422, "available must be boolean")
        if u_v is not None and not (is_number(u_v) and 0 < u_v <= 500):
            raise SimError(422, "u_v must be a number in (0, 500]")
        if f_hz is not None and not (is_number(f_hz) and 40 <= f_hz <= 70):
            raise SimError(422, "f_hz must be a number in [40, 70]")
        self.mains_ok = available
        if available:
            self.mains_u = float(u_v) if u_v is not None else self.mains_u
            self.mains_f = float(f_hz) if f_hz is not None else self.mains_f
        self._log(logging.INFO, "mains %s" % ("ok" if available else "lost"), event="mains")
        self._step(0.0)
        return {"mains_ok": self.mains_ok, "state": self.state, "timers": self.timers_info()}

    def set_remote_start(self, on):
        if not isinstance(on, bool):
            raise SimError(422, "on must be boolean")
        if self.mode != "auto":
            raise SimError(409, "remote start is possible only in mode auto (now: %s)" % self.mode)
        self.remote_start = on
        self._log(logging.INFO, "remote_start %s" % on, event="remote_start")
        self._step(0.0)
        return {"remote_start": self.remote_start, "state": self.state}

    def set_load(self, kw):
        if not is_number(kw) or kw < 0:
            raise SimError(422, "kw must be a non-negative number")
        if kw > self.kw_esp:
            raise SimError(422, "kw exceeds ESP rating (%s kW)" % self.kw_esp)
        self.load_kw, self.load_explicit = float(kw), True
        self._step(0.0)
        shown = int(kw) if float(kw).is_integer() else float(kw)
        return {"load_kw": shown, "load_pct": round(self.load_pct(self.load_kw), 1)}

    def fault(self, alarm):
        if alarm not in FAULT_CODES:
            raise SimError(422, "unknown alarm: %r, allowed: %s" % (alarm, ", ".join(FAULT_CODES)))
        if alarm == "start_fail":
            self.armed_start_fail = True
        else:
            self._raise(alarm, forced=True)
        self._step(0.0)
        return {"alarms": self.alarm_list(with_info=True)}

    def clear(self, alarm=None):
        if alarm is not None and alarm not in ALARM_DEFS:
            raise SimError(422, "unknown alarm: %r" % (alarm,))
        if alarm is None:
            self.alarms.clear()
            self.armed_start_fail = False
        else:
            self.alarms.pop(alarm, None)
            if alarm == "start_fail":
                self.armed_start_fail = False
        if self.state == "alarm_shutdown" and not self._has_shutdown():
            self._to_standby()
        self._step(0.0)
        return {"alarms": self.alarm_list(with_info=True)}

    def set_fuel(self, data):
        keys = [k for k in ("liters", "pct", "add_liters") if k in data]
        if len(keys) != 1:
            raise SimError(422, "exactly one of liters / pct / add_liters is required")
        val = data[keys[0]]
        if not is_number(val) or val < 0:
            raise SimError(422, "%s must be a non-negative number" % keys[0])
        liters = {"liters": val, "pct": val * self.tank_l / 100.0, "add_liters": self.fuel_l + val}[keys[0]]
        if liters > self.tank_l + 1e-9:
            raise SimError(422, "exceeds tank volume (%s l)" % self.tank_l)
        self.fuel_l = float(liters)
        self._step(0.0)
        return {"fuel_l": round(self.fuel_l, 2), "fuel_pct": round(self.fuel_pct(), 2)}

    def set_time(self, data, current_factor):
        """Повертає (новий factor | None, відповідь); сам factor зберігає fake_relay."""
        if "factor" not in data and "set" not in data:
            raise SimError(422, "factor and/or set is required")
        factor = None
        if "factor" in data:
            val = data["factor"]
            if not is_number(val) or not 0.1 <= val <= 60:
                raise SimError(422, "factor must be a number in [0.1, 60]")
            factor = float(val)
        new_ts = None
        if "set" in data:
            try:
                parsed = datetime.fromisoformat(str(data["set"]))
            except ValueError:
                raise SimError(422, "set must be an ISO 8601 time with zone") from None
            if parsed.tzinfo is None:
                raise SimError(422, "set must contain a time zone")
            new_ts = parsed.timestamp()
        if new_ts is not None:
            self.sim_ts = new_ts
        return factor, {"factor": factor if factor is not None else float(current_factor), "sim_time": self.iso()}

    def events_json(self, since=0, limit=500):
        items = [e for e in self.events if e["id"] > since][: max(0, limit)]
        return {"items": items, "next": items[-1]["id"] if items else since}

    # ------------------------------------------------------------------ пульт (команди relay_api.md)
    def set_mode(self, mode):
        if mode not in MODES:
            raise ValueError(mode)
        self.mode = mode
        self.test_left = TEST_S if mode == "test" else 0.0
        self._log(logging.INFO, "mode %s" % mode, event="mode")
        self._step(0.0)

    def manual_start(self):
        if self.mode == "manual" and self.state == "standby":
            self._begin_start("manual")
            self._step(0.0)

    def toggle_breaker(self, which):
        """Команди gen_close_open / mains_close_open."""
        if which == "gen" and self.engine == "running":
            self.breaker = "none" if self.breaker == "gen" else "gen"
        elif which == "mains":
            self.breaker = "none" if self.breaker == "mains" else ("mains" if self.mains_ok else "none")
        self._step(0.0)
