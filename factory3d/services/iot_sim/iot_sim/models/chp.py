"""КГУ TEDOM Quanto D800 NG (R-12; SPEC td_chp §8): повна модель за мокапом ``build/chp/mockup/b_sim.js``.

Штатно КГУ **в резерві** (``state = 0``). Запуск — команда ``ctl/cmd = 1`` (Modbus u72 HR 40900) або ``chp/cmd``
контролера ГРЩ (u73 HR 230), або прапор світу ``chp_run`` (раніше — ненульове «Load setpoint» у HR 40007):
послідовність із 9 кроків (R-13, 60 с; ``chp_start_s`` масштабує), далі робота (``state = 2``). Зупинка —
охолодження 60 с (``state = 4``) → резерв. Параметри — прапори світу: ``chp_permit``, ``gas_bar``, ``ctl_remote``,
``chp_start_s`` (як раніше) і прапори аварій (сценарії S-25…S-30): ``chp_temp_fault``, ``chp_ret_fault``,
``chp_gas_leak``, ``chp_fire``, ``chp_rocof``.

Регістри нової карти (``catalog/chp_registers.json``, 230 сигналів) віддає ``Chp.regs[<код>]`` в інженерних
одиницях; запис RW-регістрів — ``Chp.write_reg``; команда — ``Chp.post_command``.

Режими ``ctl/mode``: 0 — за тепловим графіком, 1 — за електричним, 2 — зрізання піку, 3 — ручний (``ctl/sp_pct``),
**4 (за замовчуванням)** — старий профіль: 0,5 вдень (``sun > 0,05`` і ``outdoor ≥ 0``), інакше 1,0; P ел. =
``800·x ± 4·r``, тепло/газ 497/109 або 856/199 рівно (без шуму й затримки). Опубліковані сигнали
``infra/totals/chp_kw``, ``infra/chp/heat_kw``, ``infra/chp/gas_m3h`` (і їхні дублі ``chp/gen/p_kw``,
``chp/ht/q_total``, ``chp/gas/flow``) відмінні від нуля лише в ``state = 2`` (поведінка до W3). Збій пристрою
(``world.fault("CHP")``) заморожує модель: ``state = 3``, потужність 0; після ``clear`` — продовження. Острів
(``blackout``): ``chp_island = false`` — зупинка (``alarm/trip = 1``), ``true`` — робота, P ≤ P_crit.
"""

from __future__ import annotations

import math
from typing import Any

from iot_sim.models import register_model
from iot_sim.models.base import Model
from iot_sim.models.meter import blackout, ctl, get, island, p_crit, remote
from iot_sim.models.pv import sun_factor

P_NOM_KW = 800.0
RUN, STARTING, COOLING, STOPPED, FAULT = 2, 1, 4, 0, 3
TRANSITION_S = 60.0
GAS_MIN_BAR = 1.5
LHV, CO2K, COOLER_CAP, LT_CAP, RET_SET, IN_GEN = 9.5, 1.98, 900.0, 150.0, 70.0, 1178.0
SUB_S = 1.0  # крок внутрішнього інтегрування, с

STEP_ID = ("vent", "warm", "lube", "proving", "crank", "ign", "idle", "sync", "load")
STEP_DUR = (5.0, 6.0, 5.0, 7.0, 6.0, 5.0, 5.0, 9.0, 12.0)  # R-13: разом 60 с
WARM_SKIP_S = 1.5
CYL = tuple(f"{row}{n}" for row in "AB" for n in range(1, 9))
CYL_DEV = (-6, 4, -2, 9, 28, -7, 3, -5, 2, -8, 5, -3, -12, 6, 1, -4)
CYL_PLUG = (2400, 2400, 2400, 2400, 3560, 2400, 2400, 2400, 2400, 2400, 2400, 2400, 2400, 2400, 2400, 2400)
HOURS0, STARTS0 = 18400.0, 612
MODE_LIMITS = {"mode": (0, 4), "sp_pct": (50, 100), "cos_set": (90, 100), "heat_dir": (0, 2), "bypass_mode": (0, 2)}
WRITABLE = {
    "chp/ctl/mode": "mode",
    "chp/ctl/sp_pct": "sp_pct",
    "chp/ctl/cos_set": "cos_set",
    "chp/ctl/heat_dir": "heat_dir",
    "chp/ctl/bypass_mode": "bypass_mode",
}
R06_TEXT = {
    1: "немає дозволу КГУ",
    2: "тиск газу нижче мінімуму",
    3: "на щиті не «Дистанційне»",
    4: "немає мережі S2",
    5: "спрацював ROCOF",
    6: "загазованість ≥ 10 % НКПР",
    7: "пожежа або гасіння",
    8: "t зворотки вище уставки",
    9: "t ОЖ ≥ 95 °C",
    10: "АКБ < 23,5 В",
    11: "рівень масла або контур аварійного стопу",
    12: "стан не допускає команду",
    13: "значення поза діапазоном",
}
GRID_TEXT = "зникла мережа S2: QF-CHP відключено, острівний режим не передбачено → охолодження"


def _clamp(v: float, lo: float, hi: float) -> float:
    return min(hi, max(lo, v))


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _approach(c: float, t: float, dt: float, tau: float) -> float:
    return c + (t - c) * (1.0 - math.exp(-dt / tau))


def _ease(p: float) -> float:
    return p * p * (3.0 - 2.0 * p)


def q_of(x: float) -> float:
    """Теплова потужність, кВт, за навантаженням ``x`` (частка P_nom)."""
    return 497.0 + (x - 0.5) * 718.0 if x >= 0.5 else _lerp(70.0, 497.0, x / 0.5)


def g_of(x: float) -> float:
    """Витрата газу, м³/год, за навантаженням ``x``."""
    return 109.0 + (x - 0.5) * 180.0 if x >= 0.5 else _lerp(22.0, 109.0, x / 0.5)


def x_from_q(q: float) -> float:
    return _clamp(0.5 + (q - 497.0) / 718.0, 0.5, 1.0)


def heat_demand(t: float) -> float:
    """Потреба котельні, кВт (``b_sim.js:heatDemand``), ``t`` — sim-секунди."""
    return 694.5 + 38.0 * math.sin(t / 480.0 * 2 * math.pi) + 12.0 * math.sin(t / 97.0 * 2 * math.pi)


def in_peak(h: float) -> bool:
    return 8.0 <= h < 11.0 or 17.0 <= h < 21.0


def _pump(run: bool, fmin: float, fmax: float, x: float, inom: float) -> tuple[float, float]:
    f = fmin + (fmax - fmin) * x if run else 0.0
    return f, (inom * (0.35 + 0.65 * (f / 50.0) ** 3) if run else 0.0)


@register_model("chp")
class Chp(Model):
    def attach(self) -> None:
        self.first = True
        self.kwh = 0.0
        self.hours = float(self.val("hours", 0.0) or 0.0)  # інтеграл legacy-сигналу infra/chp/hours
        self.s: dict[str, Any] = self._initial()
        self.regs: dict[str, float] = {}
        self.publish_regs(self._env(), 0.0)

    # --- початковий стан ------------------------------------------------------------------------------------------
    def _initial(self) -> dict[str, Any]:
        tamb = float(get(self.world, "ventilation/totals/outdoor_c", 9.0))
        return {
            "state": STOPPED, "mode": 4, "sp_pct": 80, "cos_set": 0.98, "heat_dir": 0, "bypass_mode": 0,
            "load": 0.0, "rpm": 0.0, "qf": False, "valves": False, "step_i": -1, "step_t": 0.0, "warm_skip": False,
            "cool_left": 0.0, "gas_p": 2.10, "lel": 0.6, "t_ret_b": 52.0, "mix_pos": 0.0, "t_ret_eff": 52.0,
            "cap": 1.0, "cap_warned": False, "ret_t": 0.0, "t_jo": 45.0, "t_ji": 43.0, "t_oil": 42.0, "p_oil": 0.0,
            "qth": 0.0, "gas": 0.0, "fan": 0.0, "fan_lt": 0.0, "bypass": 1.0, "t_e1": tamb, "t_e2": tamb,
            "t_lt": tamb + 12.0, "t_cont": tamb + 3.0, "fan_sup": 0.0, "fan_exh": 0.0, "louver": 0.0, "air_dp": 0.3,
            "bat_v": 27.2, "starter": False, "starter_i": 0.0, "oil_lvl": 66.8, "oil_fresh": 68.0,
            "oil_waste": 31.0, "topup": False, "ext": 0, "ext_level": 100.0, "ext_t": 0.0, "vp_st": 2,
            "vp_time": int(self.world.clock.epoch()) - 238 * 60, "alarm": 0, "trip": 0, "estop_loop": True,
            "sync": [0.0, 0.0, 0.0, False], "hours": HOURS0, "starts": STARTS0, "gas_total": 3940620.0,
            "e_kwh": 10912450.0, "e_kvarh": 2748320.0, "heat_tot": 9412.6, "e_day": 0.0, "q_day": 0.0,
            "g_day": 0.0, "run_day": 0.0, "day": 0,
        }  # fmt: skip

    # --- середовище -----------------------------------------------------------------------------------------------
    def wanted(self) -> bool:
        """КГУ запущено командою (``chp_run``); за замовчуванням — резерв."""
        return bool(self.world.flags.get("chp_run", False))

    def _env(self) -> dict[str, Any]:
        w = self.world
        now = w.now()
        f = w.flags
        outdoor = float(get(w, "ventilation/totals/outdoor_c", 9.0))
        isl = island(w)
        return {
            "now": now,
            "epoch": w.clock.epoch(),
            "hour": now.hour + now.minute / 60.0,
            "outdoor": outdoor,
            "half": sun_factor(w) > 0.05 and outdoor >= 0,
            "gas_bar": float(ctl(w, "gas_bar")),
            "permit": int(ctl(w, "chp_permit")) == 1,
            "remote": remote(w),
            "temp_fault": bool(f.get("chp_temp_fault")),
            "ret_fault": bool(f.get("chp_ret_fault")),
            "gas_leak": bool(f.get("chp_gas_leak")),
            "fire": bool(f.get("chp_fire")),
            "rocof": bool(f.get("chp_rocof")),
            "island": isl,
            "grid_trip": isl and not bool((blackout(w) or {}).get("chp_island", False)),
            "start_k": max(0.01, float(ctl(w, "chp_start_s")) / 60.0),
        }

    def _nz(self, key: str) -> float:
        return self.world.r(f"chp/n/{key}")

    def _ev(self, kind: str, text: str, **payload: Any) -> None:
        self.world.events.emit(kind, text, device=self.device.code, payload=payload)

    # --- цілі режимів ---------------------------------------------------------------------------------------------
    def _mode_target(self, env: dict[str, Any]) -> float:
        s, h = self.s, env["hour"]
        m = s["mode"]
        if m == 0:
            return x_from_q(heat_demand(env["epoch"]))
        if m == 1:
            return 0.88 if 7.0 <= h < 22.0 else 0.66
        if m == 2:
            return 1.0 if in_peak(h) else 0.60
        if m == 3:
            return float(s["sp_pct"]) / 100.0
        return 0.5 if env["half"] else 1.0

    def _target(self, env: dict[str, Any]) -> float:
        return min(self._mode_target(env), self.s["cap"])

    # --- стани ----------------------------------------------------------------------------------------------------
    def _step_dur(self, i: int, env: dict[str, Any]) -> float:
        base = WARM_SKIP_S if (STEP_ID[i] == "warm" and self.s["warm_skip"]) else STEP_DUR[i]
        return base * env["start_k"]

    def _enter_step(self, i: int, carry: float = 0.0) -> None:
        s = self.s
        s["step_i"], s["step_t"] = i, carry
        if STEP_ID[i] == "proving":
            s["vp_st"], s["vp_time"] = 1, 0

    def _begin_start(self) -> None:
        s = self.s
        s.update(state=STARTING, warm_skip=s["t_jo"] >= 55.0, valves=False, qf=False, load=0.0, cap=1.0)
        s.update(cap_warned=False, trip=0)
        self._enter_step(0)
        self._ev("info", "КГУ: пуск, крок 1/9 (вентиляція контейнера)", state=STARTING)

    def _begin_cool(self, reason: str) -> None:
        s = self.s
        s.update(state=COOLING, cool_left=TRANSITION_S, step_i=-1, starter=False)
        self._ev("info", f"КГУ: охолодження 60 с ({reason})", state=COOLING)

    def _to_reserve(self) -> None:
        s = self.s
        s.update(state=STOPPED, valves=False, qf=False, load=0.0, step_i=-1, starter=False)
        self._ev("info", "КГУ зупинено: стан «Резерв»", state=STOPPED)

    def _raise_alarm(self, code: int, text: str) -> None:
        s = self.s
        if s["state"] == FAULT:
            return
        s.update(state=FAULT, alarm=code, qf=False, load=0.0, valves=False, step_i=-1, starter=False)
        if code == 116:
            s["estop_loop"] = False
        self.world.set_flag("chp_run", False)
        self._ev("alarm", f"КГУ: аварія {code} — {text}", alarm=code, state=FAULT)

    def _trip(self, kind: int, text: str, *, clear_run: bool) -> None:
        s = self.s
        s.update(trip=kind, qf=False, load=0.0)
        if clear_run:
            self.world.set_flag("chp_run", False)
        self._ev("info", f"КГУ: {text}", trip=kind)
        if s["rpm"] > 50:
            self._begin_cool(text)
        else:
            self._to_reserve()

    def _settle_run(self, env: dict[str, Any]) -> None:
        """Старт сервісу з уже працюючим КГУ (``chp_run`` і номінал каталогу ``state = 2``): усталена робота."""
        s = self.s
        x = self._mode_target(env)
        tamb = env["outdoor"]
        bypass_t = 1.0 if s["bypass_mode"] == 2 else 0.0
        t_cont = tamb + 18.0 + 10.0 * x
        s.update(state=RUN, rpm=1500.0, valves=True, qf=True, load=x, step_i=-1, cap=1.0, t_jo=84.0 + 7.0 * x)
        s.update(t_oil=90.0 + 8.0 * x, p_oil=4.6, qth=q_of(x), gas=g_of(x), bypass=bypass_t, t_ret_b=58.0)
        s.update(t_ret_eff=58.0, t_e1=410.0 + 110.0 * x, t_lt=45.0, louver=100.0, t_cont=t_cont)
        s.update(fan_sup=_clamp(30.0 + (t_cont - 28.0) * 7.0, 30.0, 100.0), air_dp=5.4 + 2.6 * g_of(x) / 160.0)
        s["t_ji"] = s["t_jo"] - 9.0
        s["t_e2"] = _lerp(170.0 + 15.0 * x, s["t_e1"] + 4.0, bypass_t)
        s["fan_exh"] = s["fan_sup"]

    # --- команди --------------------------------------------------------------------------------------------------
    def post_command(self, value: int) -> None:
        """Запис у ``ctl/cmd`` (u72 HR 40900): результат — ``chp_ack`` (0 до обробки), ``chp_ack_reason``."""
        w = self.world
        w.set_flag("chp_ack", 0)
        w.set_flag("chp_ack_reason", 0)
        if value != 3 and not remote(w):
            w.set_flag("chp_ack", 2)
            w.set_flag("chp_ack_reason", 3)
            return
        w.set_flag("chp_cmd", int(value))

    def write_reg(self, code: str, raw: int) -> None:
        """Запис RW-регістра нової карти (``raw`` — значення регістра). ``ValueError`` — поза межами; у місцевому режимі
        запис приймається протоколом, але ігнорується (як у вікні керування ГРЩ)."""
        key = WRITABLE.get(code)
        if key is None:
            raise KeyError(code)
        lo, hi = MODE_LIMITS[key]
        if not lo <= raw <= hi:
            raise ValueError(raw)
        if not remote(self.world):
            return
        self.s[key] = raw / 100.0 if key == "cos_set" else int(raw)
        self.regs[code] = float(self.s[key])

    def _start_reason(self, env: dict[str, Any]) -> int:
        """Перевірки пуску R-07 №1–5, 7–14 → код ``ack_reason`` (R-06), 0 — усе гаразд."""
        s = self.s
        if s["state"] != STOPPED:
            return 12
        if not env["permit"]:
            return 1
        if min(s["gas_p"], env["gas_bar"]) < GAS_MIN_BAR:
            return 2
        if env["island"]:
            return 4
        if env["rocof"]:
            return 5
        if s["lel"] >= 10.0 or env["gas_leak"]:
            return 6
        if env["fire"] or s["ext"] != 0:
            return 7
        if s["t_ret_eff"] > RET_SET or env["ret_fault"]:
            return 8
        if s["t_jo"] >= 95.0 or env["temp_fault"]:
            return 9
        if s["bat_v"] < 23.5:
            return 10
        if s["oil_lvl"] < 40.0 or not s["estop_loop"]:
            return 11
        return 0

    def _reset_reason(self, env: dict[str, Any]) -> int:
        s = self.s
        if min(s["gas_p"], env["gas_bar"]) < GAS_MIN_BAR:
            return 2
        if s["t_jo"] >= 95.0 or env["temp_fault"]:
            return 9
        if env["ret_fault"]:
            return 8
        if env["gas_leak"]:
            return 6
        if env["fire"]:
            return 7
        return 0

    def _command(self, env: dict[str, Any]) -> None:
        w = self.world
        cmd = int(ctl(w, "chp_cmd"))
        if not cmd:
            return
        w.set_flag("chp_cmd", 0)
        ack, reason = self._execute(cmd, env)
        w.set_flag("chp_ack", ack)
        w.set_flag("chp_ack_reason", reason if ack == 2 else 0)
        verb = {1: "пуск", 2: "стоп", 3: "аварійний стоп", 4: "скидання"}.get(cmd, str(cmd))
        text = "прийнято" if ack == 1 else f"відхилено: {R06_TEXT.get(reason, reason)}"
        self._ev("info", f"КГУ: команда «{verb}» {text}", cmd=cmd, ack=ack, reason=reason)

    def _execute(self, cmd: int, env: dict[str, Any]) -> tuple[int, int]:
        s, w = self.s, self.world
        st = s["state"]
        if cmd not in (1, 2, 3, 4):
            return 2, 13
        if cmd != 3 and not env["remote"]:
            return 2, 3
        if cmd == 1:
            reason = self._start_reason(env)
            if reason:
                return 2, reason
            w.set_flag("chp_run", True)
            self._begin_start()
            return 1, 0
        if cmd == 2:
            w.set_flag("chp_run", False)
            if st == STARTING and s["rpm"] <= 50:
                self._to_reserve()
            elif st in (STARTING, RUN):
                self._begin_cool("стоп оператора")
            elif st != STOPPED:  # у резерві стоп — ack = 1 (уже зупинено; контракт до W3)
                return 2, 12
            return 1, 0
        if cmd == 3:
            if st == FAULT:
                return 2, 12
            self._raise_alarm(116, "аварійний стоп оператора")
            return 1, 0
        if st != FAULT:
            return 2, 12
        reason = self._reset_reason(env)
        if reason:
            return 2, reason
        s.update(state=STOPPED, alarm=0, estop_loop=True, ext=0, ext_level=100.0, ext_t=0.0, rpm=min(s["rpm"], 200.0))
        s["lel"] = min(s["lel"], 0.6)
        self._ev("info", "КГУ: аварію скинуто, стан «Резерв»", state=STOPPED)
        return 1, 0

    # --- крок моделі ----------------------------------------------------------------------------------------------
    def _faulted(self) -> bool:
        return self.device.fault is not None

    def tick(self, dt_s: float) -> None:
        s = self.s
        env = self._env()
        self._command(env)
        if self.first:  # старт сервісу: штатно резерв; працюючий КГУ (chp_run + номінал каталогу) — усталена робота
            self.first = False
            if s["state"] == STOPPED and self.wanted() and int(self.val("state", RUN)) == RUN and not self._faulted():
                self._settle_run(env)
        if self._faulted():  # збій пристрою: модель заморожена, state = 3, потужність 0
            self._publish(env, FAULT, 0.0, 0.0, 0.0, dt_s, accumulate=False)
            return
        if not self.wanted() and s["state"] in (STARTING, RUN):
            if s["state"] == STARTING and s["rpm"] <= 50:
                self._to_reserve()
            else:
                self._begin_cool("стоп оператора")
        elif (
            self.wanted()
            and s["state"] == STOPPED
            and not env["island"]
            and env["permit"]
            and not env["rocof"]
            and not s["alarm"]
        ):
            self._begin_start()
        n = max(1, math.ceil(dt_s / SUB_S - 1e-9))
        for _ in range(n):
            self._sub(dt_s / n, env)
        day = env["now"].toordinal()
        if s["day"] != day:
            s.update(day=day, e_day=0.0, q_day=0.0, g_day=0.0, run_day=0.0)
        p, heat, gas = self._legacy(env)
        self._publish(env, s["state"], p, heat, gas, dt_s)

    def _legacy(self, env: dict[str, Any]) -> tuple[float, float, float]:
        """Опубліковані P ел., тепло, газ: ненульові лише в ``state = 2`` (поведінка до W3)."""
        s = self.s
        if s["state"] != RUN:
            return 0.0, 0.0, 0.0
        p = max(0.0, P_NOM_KW * s["load"] + 4.0 * self.r("chp_kw"))
        if env["island"]:
            p = min(p, max(0.0, p_crit(self.world)))  # у острові СЕС = 0 (R-11)
        beff = s["bypass"] if s["bypass_mode"] == 2 else 0.0
        noise = 0.0 if s["mode"] == 4 else 1.0
        heat = max(0.0, s["qth"] * (1.0 + self._nz("qth") * 0.005 * noise)) * (1.0 - 0.45 * beff)
        gas = max(0.0, s["gas"] * (1.0 + self._nz("gas") * 0.006 * noise))
        return p, heat, gas

    def _publish(
        self, env: dict[str, Any], state: int, p: float, heat: float, gas: float, dt_s: float, accumulate: bool = True
    ) -> None:
        s = self.s
        if accumulate:
            if state == RUN:
                self.hours += dt_s / 3600.0
            self.kwh += p * dt_s / 3600.0
            h = dt_s / 3600.0
            s["hours"] += h if s["rpm"] > 50 else 0.0
            s["e_kwh"] += p * h
            s["e_kvarh"] += p * 0.2 * h
            s["e_day"] += p * h
            s["q_day"] += heat * h / 1163.0
            s["heat_tot"] += heat * h / 1163.0
            s["g_day"] += gas * h
            s["gas_total"] += gas * h
            s["run_day"] += h if p > 5.0 else 0.0
        self.set("state", state)
        self.set("chp_kw", p)
        self.set("heat_kw", heat)
        self.set("gas_m3h", gas)
        self.set("hours", self.hours)
        self.set("kwh_total", round(self.kwh, 4))
        self.publish_regs(env, dt_s, p, heat, gas, state)

    # --- один крок інтегрування (b_sim.js:step) -------------------------------------------------------------------
    def _protect_start_run(self, env: dict[str, Any]) -> None:
        if env["grid_trip"]:
            self._trip(1, GRID_TEXT, clear_run=False)
        elif env["rocof"]:
            self._trip(2, "захист ROCOF: QF-CHP відключено → охолодження", clear_run=True)
        elif not env["permit"]:
            self._trip(3, "дозвіл КГУ знято: контрольована зупинка", clear_run=True)

    def _sub(self, dt: float, env: dict[str, Any]) -> None:
        s = self.s
        s["gas_p"] = _approach(s["gas_p"], env["gas_bar"], dt, 1.4)
        s["lel"] = _approach(s["lel"], 32.0 if env["gas_leak"] else 0.6, dt, 2.0 if env["gas_leak"] else 3.0)
        ret_t = 84.0 if env["ret_fault"] else (52.0 if (s["heat_dir"] == 2 or s["state"] != RUN) else 58.0)
        s["t_ret_b"] = _approach(s["t_ret_b"], ret_t, dt, 2.5 if env["ret_fault"] else 5.0)
        s["mix_pos"] = _approach(s["mix_pos"], _clamp((s["t_ret_b"] - 60.0) * 8.0, 0.0, 100.0), dt, 1.2)
        s["t_ret_eff"] = s["t_ret_b"] - 8.0 * s["mix_pos"] / 100.0
        st = s["state"]
        if st == STARTING:
            self._sub_start(dt, env)
            if s["state"] == STARTING:
                self._protect_start_run(env)
        elif st == RUN:
            s["rpm"] = _approach(s["rpm"], 1500.0, dt, 0.5)
            s.update(valves=True, qf=True)
            tg = self._target(env)
            if s["mode"] == 4:
                s["load"] = tg  # старий профіль день/ніч: без обмеження швидкості
            else:
                s["load"] += _clamp(tg - s["load"], -0.04 * dt, 0.04 * dt)
            self._protect_start_run(env)
        elif st == COOLING:
            s["cool_left"] -= dt
            s["load"] = max(0.0, s["load"] - 0.35 * dt)
            if s["load"] < 0.02:
                s["load"] = 0.0
                s["qf"] = False
            if s["cool_left"] > 0:
                s["rpm"] = _approach(s["rpm"], 1500.0, dt, 0.4)
                s["valves"] = True
            else:
                s["cool_left"] = 0.0
                self._to_reserve()
        else:  # резерв або аварія
            s["rpm"] = _approach(s["rpm"], 0.0, dt, 1.3 if st == FAULT else 1.0)
            if s["rpm"] < 8.0:
                s["rpm"] = 0.0
            s.update(load=0.0, qf=False, valves=False)
            if st == STOPPED and s["trip"] and self._trip_cleared(env):
                s["trip"] = 0
        if s["state"] != STARTING:
            s["starter"] = False
        self._protections(dt, env)
        self._subsystems(dt, env)

    def _trip_cleared(self, env: dict[str, Any]) -> bool:
        t = self.s["trip"]
        return (t == 1 and not env["island"]) or (t == 2 and not env["rocof"]) or (t == 3 and env["permit"])

    def _sub_start(self, dt: float, env: dict[str, Any]) -> None:
        s = self.s
        s["step_t"] += dt
        for _ in range(len(STEP_ID) + 1):  # залишок часу переходить у наступний крок
            i = s["step_i"]
            sid, dur = STEP_ID[i], self._step_dur(i, env)
            p = _clamp(s["step_t"] / dur, 0.0, 1.0)
            if sid in ("vent", "lube"):
                s["rpm"] = 0.0
            elif sid == "warm":
                s["rpm"] = 0.0
                if not s["warm_skip"]:
                    s["t_jo"] = min(58.0, s["t_jo"] + 3.0 * dt)
            elif sid == "proving":
                s.update(rpm=0.0, valves=False)
            elif sid == "crank":
                s.update(starter=True, rpm=_lerp(0.0, 250.0, p))
            elif sid == "ign":
                s.update(starter=p < 0.45, valves=True, rpm=_lerp(250.0, 900.0, p))
            elif sid == "idle":
                s.update(valves=True, rpm=_lerp(900.0, 1500.0, p))
            elif sid == "sync":
                s["rpm"] = 1500.0
                self._sync_calc(p)
            else:  # load
                s.update(rpm=1500.0, qf=True, load=self._target(env) * _ease(p))
            if s["step_t"] < dur:
                return
            carry = s["step_t"] - dur
            if sid == "proving":
                s["vp_st"], s["vp_time"] = 2, int(env["epoch"])
            if sid == "sync":
                s["qf"] = True
            if i + 1 >= len(STEP_ID):
                s.update(state=RUN, step_i=-1, load=self._target(env))
                s["starts"] += 1
                self._ev("info", f"КГУ: пуск завершено, P ел. = {P_NOM_KW * s['load']:.0f} кВт", state=RUN)
                return
            self._enter_step(i + 1, carry)

    def _sync_calc(self, p: float) -> None:
        dp = 150.0 * math.exp(-3.2 * p) * math.cos(2 * math.pi * (1.2 * p + 0.5 * p * p))
        du = 2.4 * math.exp(-3.0 * p) + 0.2
        df = 0.30 * math.exp(-3.4 * p) + 0.01
        self.s["sync"] = [du, df, dp, bool(p > 0.8 and abs(dp) < 10.0 and du < 1.0 and df < 0.05)]

    def _protections(self, dt: float, env: dict[str, Any]) -> None:
        s = self.s
        if s["state"] in (STARTING, RUN, COOLING):
            if s["gas_p"] < GAS_MIN_BAR:
                self._raise_alarm(111, f"низький тиск газу {s['gas_p']:.2f} бар")
            elif s["t_jo"] >= 97.0:
                self._raise_alarm(112, f"перегрів ОЖ {s['t_jo']:.1f} °C")
            else:
                over = s["t_ret_eff"] - RET_SET
                s["cap"] = _clamp(1.0 - over / 6.0 * 0.5, 0.5, 1.0) if over > 0 else 1.0
                if s["cap"] >= 1.0 and s["t_ret_eff"] < RET_SET - 1.0:
                    s["cap_warned"] = False
                if s["cap"] < 1.0 and not s["cap_warned"]:
                    s["cap_warned"] = True
                    self._ev("info", f"КГУ: висока t зворотки {s['t_ret_eff']:.1f} °C, зниження потужності")
                s["ret_t"] = s["ret_t"] + dt if s["t_ret_eff"] >= 75.5 else 0.0
                if s["ret_t"] >= 2.0:
                    self._raise_alarm(113, f"висока температура зворотки {s['t_ret_eff']:.1f} °C")
        else:
            s["cap"] = _approach(s["cap"], 1.0, dt, 2.0)
            s["ret_t"] = 0.0
        if s["lel"] >= 20.0 and s["state"] != FAULT:
            self._raise_alarm(114, f"загазованість {s['lel']:.0f} % НКПР")
        if env["fire"] and s["state"] != FAULT:
            self._raise_alarm(115, "пожежа в контейнері")
        if env["fire"]:
            s["ext_t"] += dt
            if s["ext"] == 0 and s["ext_t"] > 3.0:
                s["ext"] = 1
                self._ev("alarm", "КГУ: автоматичне гасіння, випуск вогнегасної речовини", ext=1)
            if s["ext"] == 1:
                s["ext_level"] = max(0.0, s["ext_level"] - 25.0 * dt)
                if s["ext_level"] <= 0.0:
                    s["ext"] = 2

    def _subsystems(self, dt: float, env: dict[str, Any]) -> None:
        s = self.s
        tamb, st = env["outdoor"], s["state"]
        x, rpm = s["load"], s["rpm"]
        rpm_f = rpm / 1500.0
        valves = s["valves"]
        hi = rpm > 1200.0 and valves
        mid = rpm > 200.0 and valves
        q_t = q_of(x) if hi else (30.0 if mid else 0.0)
        g_t = 0.0 if not valves else (22.0 * _clamp(rpm / 1200.0, 0.3, 1.0) if rpm < 1200.0 else g_of(x))
        if st == RUN and s["mode"] == 4:  # старий профіль: тепло й газ без затримки
            s["qth"], s["gas"] = q_t, g_t
        else:
            s["qth"], s["gas"] = _approach(s["qth"], q_t, dt, 2.5), _approach(s["gas"], g_t, dt, 1.2)
        if env["temp_fault"]:
            tj_t = 107.0
        elif st == RUN:
            tj_t = 84.0 + 7.0 * x
        elif st == STARTING:
            tj_t = (66.0 if s["warm_skip"] else 55.0) + 22.0 * rpm_f
        elif st == COOLING:
            tj_t = 70.0
        else:
            tj_t = 60.0 if st == FAULT else 45.0
        s["t_jo"] = _approach(s["t_jo"], tj_t, dt, 4.5 if env["temp_fault"] else 11.0)
        s["t_ji"] = s["t_jo"] - (9.0 if rpm > 200 else 2.0)
        s["t_oil"] = _approach(s["t_oil"], 90.0 + 8.0 * x if rpm > 200 else 42.0, dt, 14.0)
        cur = STEP_ID[s["step_i"]] if st == STARTING and s["step_i"] >= 0 else ""
        lube = cur in ("lube", "proving", "warm")
        po_t = 4.6 if rpm > 1000 else (1.6 if lube else (1.5 + 3.0 * rpm_f if rpm > 10 else 0.0))
        s["p_oil"] = _approach(s["p_oil"], po_t, dt, 0.8)
        bm = s["bypass_mode"]
        by_t = 1.0 if bm == 2 else (0.0 if bm == 1 else (0.0 if st == RUN else 1.0))
        s["bypass"] = _approach(s["bypass"], by_t, dt, 2.0)
        s["t_e1"] = _approach(s["t_e1"], 410.0 + 110.0 * x if hi else (190.0 if mid else tamb), dt, 3.0)
        e2_t = _lerp(170.0 + 15.0 * x, s["t_e1"] + 4.0, s["bypass"]) if hi else (90.0 if mid else tamb)
        s["t_e2"] = _approach(s["t_e2"], e2_t, dt, 3.0)
        s["t_lt"] = _approach(s["t_lt"], 45.0 if rpm > 50 else tamb + 12.0, dt, 12.0)
        if rpm > 50:  # масло: розхід (повільніше за мокап), автодолив
            s["oil_lvl"] -= 0.00025 * (0.5 + x) * dt
        if not s["topup"] and s["oil_lvl"] < 66.0 and rpm > 50:
            s["topup"] = True
            self._ev("info", f"КГУ: автодолив масла, рівень картера {s['oil_lvl']:.1f} % < 66 %")
        if s["topup"]:
            s["oil_lvl"] += 0.12 * dt
            s["oil_fresh"] = max(0.0, s["oil_fresh"] - 0.02 * dt)
            if s["oil_lvl"] >= 74.0:
                s["topup"] = False
        if env["fire"]:
            f_t = l_t = 0.0
        elif s["lel"] >= 10.0 or cur == "vent":
            f_t = l_t = 100.0
        elif st == RUN:
            f_t, l_t = _clamp(30.0 + (s["t_cont"] - 28.0) * 7.0, 30.0, 100.0), 100.0
        elif st in (COOLING, STARTING):
            f_t, l_t = 60.0, 100.0
        elif st == FAULT:
            f_t, l_t = 40.0, 100.0
        else:
            f_t = 60.0 if s["t_cont"] > 38.0 else 0.0
            l_t = 100.0 if f_t > 0 else 0.0
        s["fan_sup"] = _approach(s["fan_sup"], f_t, dt, 1.0)
        s["fan_exh"] = _approach(s["fan_exh"], f_t, dt, 1.0)
        s["louver"] = _approach(s["louver"], l_t, dt, 1.0)
        if s["fan_sup"] < 0.5 and f_t == 0.0:
            s["fan_sup"] = s["fan_exh"] = 0.0
        cont_t = tamb + (18.0 + 10.0 * x if rpm > 50 else 3.0) - 0.08 * s["fan_sup"] + (30.0 if env["fire"] else 0.0)
        s["t_cont"] = _approach(s["t_cont"], cont_t, dt, 15.0)
        s["air_dp"] = _approach(s["air_dp"], 5.4 + 2.6 * s["gas"] / 160.0 if rpm > 50 else 0.3, dt, 3.0)
        if s["starter"]:
            bat_t, bat_tau = 22.6 + 0.4 * (1.0 - _clamp(s["step_t"] / 2.0, 0.0, 1.0)), 0.35
            i_t = 380.0 * math.exp(-s["step_t"] * 0.6) + 140.0
            s["starter_i"] = _approach(s["starter_i"], i_t, dt, 0.25)
        else:
            bat_t, bat_tau = 27.2, 2.5
            s["starter_i"] = _approach(s["starter_i"], 0.0, dt, 0.2)
        s["bat_v"] = _approach(s["bat_v"], bat_t, dt, bat_tau)

    # --- регістри нової карти (b_sim.js:computeV) -----------------------------------------------------------------
    def publish_regs(
        self,
        env: dict[str, Any],
        dt: float,
        p_pub: float = 0.0,
        heat_pub: float = 0.0,
        gas_pub: float = 0.0,
        state: int = 0,
    ) -> None:
        s, nz, w = self.s, self._nz, self.world
        tamb, st = env["outdoor"], s["state"]
        x, rpm, valves = s["load"], s["rpm"], s["valves"]
        hi = rpm > 1200.0
        run = st == RUN
        noise = 0.0 if s["mode"] == 4 else 1.0
        pel = p_pub if run else (max(0.0, P_NOM_KW * x + 4.0 * self.r("chp_kw")) if s["qf"] else 0.0)
        p_shaft = pel / 0.96
        q_raw = max(0.0, s["qth"] * (1.0 + nz("qth") * 0.005 * noise))
        gas_v = max(0.0, s["gas"] * (1.0 + nz("gas") * 0.006 * noise))
        cos = _clamp(s["cos_set"] + nz("cos") * 0.002, 0.85, 1.0) if s["qf"] else 0.0
        q_kvar = pel * math.tan(math.acos(cos)) if s["qf"] else 0.0
        u = 400.0 + 1.4 * nz("u") if rpm >= 1400 else (400.0 * rpm / 1500.0 if (rpm > 250 and st != FAULT) else 0.0)
        amp = pel * 1000.0 / (math.sqrt(3) * u * cos) if (s["qf"] and u > 50 and cos > 0) else 0.0
        exc_i = 5.5 + 14.0 * x + (1.0 - cos) * 20.0 + nz("u") * 0.15 if rpm >= 1400 else 0.0
        t_oil = s["t_oil"] + nz("tj") * 0.15
        q_phe, q_exh = 0.55 * q_raw, 0.45 * q_raw * (1.0 - s["bypass"])
        q_sum = q_phe + q_exh
        dem = heat_demand(env["epoch"]) + nz("dem") * 4.0
        if not run:
            b, c = 0.0, q_sum
        elif s["heat_dir"] == 1:
            b, c = q_sum, 0.0
        elif s["heat_dir"] == 2:
            b, c = 0.0, q_sum
        else:
            b = min(q_sum, dem)
            c = q_sum - b
            if c < 8.0:
                b, c = q_sum, 0.0
        pump = st != STOPPED and not (st == FAULT and s["t_jo"] < 60.0)
        flow = max(14.0, q_sum / (1.163 * 20.0)) if pump else 0.0
        t_ret_raw, t_ret = s["t_ret_b"] + nz("tx") * 0.2, s["t_ret_eff"] + nz("tx") * 0.2
        t_mid = t_ret + q_phe / (1.163 * flow) if flow > 0 else t_ret
        t_sup = t_mid + q_exh / (1.163 * flow) if flow > 0 else t_ret
        flow_c = c / (1.163 * 15.0) if c > 3 else 0.0
        t_cool_out = t_ret_raw - (c / (1.163 * flow_c) if flow_c > 0 else 0.0)
        fan_t = max(12.0, c / COOLER_CAP * 100.0) if c > 3 else 0.0
        s["fan"] = _approach(s["fan"], fan_t, max(dt, 1e-6), 2.0)
        if s["fan"] < 0.5 and fan_t == 0.0:
            s["fan"] = 0.0
        p_loop = 3.2 + nz("p") * 0.04
        q_lt = 40.0 + 85.0 * x if hi else (10.0 if rpm > 200 else 0.0)
        flow_lt = max(8.0, q_lt / (1.163 * 5.0)) if rpm > 50 else 0.0
        t_lt_in = 40.0 + nz("tx") * 0.2
        t_lt_out = t_lt_in + q_lt / (1.163 * flow_lt) if flow_lt > 0 else t_lt_in
        f_lt = _clamp(20.0 + q_lt / LT_CAP * 60.0, 0.0, 100.0) if q_lt > 3 else 0.0
        s["fan_lt"] = _approach(s["fan_lt"], f_lt, max(dt, 1e-6), 2.0)
        if f_lt == 0.0 and s["fan_lt"] < 0.5:
            s["fan_lt"] = 0.0
        ht_f, ht_a = _pump(pump, 38.0, 48.0, x, 14.5)
        he_f, he_a = _pump(flow > 0.5, 34.0, 46.0, x, 6.2)
        lt_f, lt_a = _pump(rpm > 50, 40.0, 47.0, x, 4.1)
        t_e1 = s["t_e1"] + nz("tx") * 1.5
        t_e2 = s["t_e2"] + nz("tx") * 0.8
        cur_step = STEP_ID[s["step_i"]] if st == STARTING and s["step_i"] >= 0 else ""
        du, df, dphi, sync_ok = s["sync"]
        step_left = max(0.0, self._step_dur(s["step_i"], env) - s["step_t"]) if cur_step else 0.0
        grid_ok = not env["island"]
        v: dict[str, float] = {
            "ctl/state": state if state == FAULT and st != FAULT else st,
            "ctl/cmd": int(ctl(w, "chp_cmd")), "ctl/ack": int(ctl(w, "chp_ack")),
            "ctl/ack_reason": int(w.flags.get("chp_ack_reason", 0)),
            "ctl/mode": s["mode"], "ctl/sp_pct": s["sp_pct"], "ctl/cos_set": s["cos_set"],
            "ctl/heat_dir": s["heat_dir"], "ctl/bypass_mode": s["bypass_mode"],
            "ctl/step": s["step_i"] + 1 if cur_step else 0, "ctl/step_left": step_left,
            "ctl/cool_left": s["cool_left"] if st == COOLING else 0.0,
            "ctl/sync_du": du if cur_step == "sync" else 0.0, "ctl/sync_df": df if cur_step == "sync" else 0.0,
            "ctl/sync_dphi": dphi if cur_step == "sync" else 0.0, "ctl/sync_ok": int(sync_ok and cur_step == "sync"),
            "ctl/warm_skip": int(s["warm_skip"] and st == STARTING), "ctl/target_pct": self._mode_target(env) * 100.0,
            "ctl/heat_demand": dem, "ctl/remote": int(env["remote"]), "ctl/permit": int(env["permit"]),
            "alarm/code": s["alarm"], "alarm/trip": s["trip"],
            "eng/rpm": rpm + nz("rpm") * 2.5 if hi else rpm,
            "eng/torque": p_shaft / (rpm * 2 * math.pi / 60.0) if (rpm > 50 and p_shaft > 0) else 0.0,
            "eng/shaft_kw": p_shaft, "eng/t_jacket_out": s["t_jo"] + nz("tj") * 0.15,
            "eng/t_jacket_in": s["t_ji"] + nz("tj") * 0.12,
            "eng/p_oil": s["p_oil"] + (nz("oil") * 0.08 if s["p_oil"] > 3 else 0.0), "eng/t_oil": t_oil,
            "eng/t_bearing": 50.0 + (6.0 + 8.0 * x if rpm > 50 else 0.0) + nz("tj") * 0.3,
            "eng/vib": 1.6 + 0.8 * x + nz("p") * 0.1 if rpm > 50 else 0.0,
            "eng/tc_rpm": 30000.0 + 22000.0 * x + nz("k1") * 200.0 if hi else (9000.0 if rpm > 200 else 0.0),
            "eng/p_boost": 1.1 + 1.2 * x if hi else 1.0, "eng/t_turb_in": t_e1 + (60.0 if hi else 0.0),
            "eng/t_air_in": 150.0 + 30.0 * x if hi else tamb, "eng/t_air_out": 52.0 + 6.0 * x if hi else tamb,
            "eng/throttle": (18.0 + 62.0 * x + nz("k1") if hi else 12.0) if valves else 0.0,
            "eng/lambda": 1.62 - 0.1 * x + nz("k2") * 0.005 if hi else 0.0,
            "eng/p_mix": 1.0 + 1.15 * x if hi else 0.0,
            "eng/hours": s["hours"], "eng/starts": s["starts"], "eng/starter_a": s["starter_i"],
            "eng/bat_v": s["bat_v"] + nz("u") * 0.03,
            "eng/bat_a": 0.0 if s["starter"] else _clamp((27.2 - s["bat_v"]) * 8.0 + 1.3 + nz("k2") * 0.1, 0.8, 30.0),
            "eng/starter_on": int(s["starter"]),
            "oil/level": s["oil_lvl"], "oil/t_out": t_oil - 9.0 if rpm > 200 else t_oil,
            "oil/dp_filter": 0.45 + 0.1 * nz("oil") if rpm > 200 else 0.0,
            "oil/cons": 0.22 + 0.012 * nz("oil") if rpm > 50 else 0.0, "oil/fresh": s["oil_fresh"],
            "oil/waste": s["oil_waste"], "oil/topup": int(s["topup"]),
            "gen/p_kw": p_pub, "gen/u_v": u, "gen/i_a": amp, "gen/cos": cos, "gen/q_kvar": q_kvar,
            "gen/f_hz": rpm / 30.0 + (nz("f") * 0.015 if rpm > 1200 else 0.0), "gen/i_pct": amp / IN_GEN * 100.0,
            "gen/exc_a": exc_i, "gen/exc_v": exc_i * 3.6, "gen/load_pct": x * 100.0,
            "gas/flow": gas_pub, "gas/p_in": s["gas_p"] + nz("p") * 0.01,
            "gas/p_reg": 98.0 + nz("p") * 1.5 if valves else 0.0,
            "gas/dp_filter": 11.0 + gas_v / 40.0 if valves else 0.0,
            "gas/yv1": 2 if cur_step == "proving" else int(valves),
            "gas/yv2": 2 if cur_step == "proving" else int(valves),
            "gas/vp_state": s["vp_st"], "gas/vp_leak": 0.3 if s["vp_st"] == 2 else 0.0, "gas/vp_ts": s["vp_time"],
            "gas/total": s["gas_total"], "gas/day": s["g_day"], "gas/psl": int(s["gas_p"] < GAS_MIN_BAR),
            "gas/psh": 0, "gas/inlet_valve": int(st != FAULT),
            "ht/q_total": heat_pub, "ht/t_sup": t_sup, "ht/t_mid": t_mid, "ht/t_ret": t_ret,
            "ht/t_ret_raw": t_ret_raw, "ht/flow": flow, "ht/q_phe": q_phe, "ht/q_exh": q_exh,
            "ht/q_boiler": b, "ht/q_cooler": c, "ht/mix_pos": s["mix_pos"], "ht/cap_pct": s["cap"] * 100.0,
            "ht/p_loop": p_loop, "ht/p_exp_ht": 1.6 + 0.012 * (s["t_jo"] - 45.0) + nz("p") * 0.01,
            "ht/p_exp_lt": 1.4 + 0.008 * (s["t_lt"] - 20.0) + nz("p") * 0.01, "ht/p_exp_h": p_loop - 0.3,
            "ht/pump_ht_f": ht_f, "ht/pump_he_f": he_f, "ht/pump_ht_a": ht_a, "ht/pump_he_a": he_a,
            "ht/p_dis_ht": 2.4 + 0.5 * x if pump else 0.0, "ht/cooler_fan": s["fan"], "ht/t_cool_out": t_cool_out,
            "ht/flow_cool": flow_c, "ht/heat_total": s["heat_tot"], "ht/heat_day": s["q_day"],
            "ht/pump_ht_run": int(pump), "ht/pump_he_run": int(flow > 0.5),
            "lt/q_kw": q_lt, "lt/flow": flow_lt, "lt/t_in": t_lt_in, "lt/t_out": t_lt_out, "lt/fan": s["fan_lt"],
            "lt/pump_f": lt_f, "lt/pump_a": lt_a, "lt/p_dis": 1.9 + 0.2 * x if rpm > 50 else 0.0,
            "lt/pump_run": int(rpm > 50),
            "exh/t_e1": t_e1, "exh/t_cat_out": t_e1 + (16.0 + nz("k1") * 1.5 if hi else 0.0), "exh/t_e2": t_e2,
            "exh/t_stack": max(tamb, t_e2 - 12.0),
            "exh/dp_cat": 6.0 + 6.0 * gas_v / 160.0 + nz("k3") * 0.3 if hi else (2.0 if rpm > 200 else 0.0),
            "exh/nox": 150.0 + 80.0 * x + nz("k1") * 4.0 if hi else 0.0,
            "exh/co": 38.0 + 55.0 * (1.0 - x) + nz("k2") * 3.0 if hi else 0.0,
            "exh/co_raw": 520.0 - 220.0 * x + nz("k2") * 10.0 if hi else 0.0,
            "exh/o2": 8.4 - 0.8 * x + nz("k3") * 0.05 if hi else 0.0,
            "exh/bypass_pct": s["bypass"] * 100.0, "exh/back_p": 12.0 + 6.0 * x if rpm > 200 else 0.0,
            "air/dp_filter": s["air_dp"] + nz("k3") * 0.05, "air/t_cont": s["t_cont"], "air/fan_sup": s["fan_sup"],
            "air/fan_exh": s["fan_exh"], "air/louver": s["louver"], "air/t_amb": tamb,
            "safe/lel": s["lel"] + (nz("k1") * 0.1 if s["lel"] < 5 else 0.0), "safe/fire": int(env["fire"]),
            "safe/ext_state": s["ext"], "safe/ext_level": s["ext_level"], "safe/estop_loop": int(s["estop_loop"]),
            "safe/rocof": int(env["rocof"]), "safe/rocof_dfdt": 2.4 if env["rocof"] else 0.03 + abs(nz("f")) * 0.05,
            "safe/rocof_dphi": 14.0 if env["rocof"] else 0.6 + abs(nz("f")), "safe/grid_ok": int(grid_ok),
            "safe/u_grid": 400.0 + nz("u") if grid_ok else 0.0, "safe/qf_closed": int(s["qf"]),
            "safe/ctrl_v": 24.1 + nz("u") * 0.05, "safe/es_cab": 0, "safe/es_door": 0,
            "safe/es_ext": int(s["alarm"] == 116),
            "em/kwh": s["e_kwh"], "em/kvarh": s["e_kvarh"], "em/kwh_day": s["e_day"], "em/runh_day": s["run_day"],
        }  # fmt: skip
        regs = {f"chp/{k}": float(val) for k, val in v.items()}
        base = s["t_e1"] + 55.0 if hi else s["t_e1"]
        temps = [base + (CYL_DEV[i] + nz("k1" if i % 2 else "k2") * 1.5 if hi else 0.0) for i in range(16)]
        for i, name in enumerate(CYL):
            k = f"chp/cyl/{name}/"
            regs[k + "t"] = temps[i]
            regs[k + "knock"] = (
                6.0
                + 9.0 * x
                + (9.0 if i == 4 else 0.0)
                + abs(CYL_DEV[i]) * 0.1
                + abs(nz("k1" if i % 3 else "k3")) * 2.5
                if hi
                else 0.0
            )
            regs[k + "kv"] = (
                22.5
                + 4.0 * x
                + (3.4 if i == 4 else 0.0)
                + (0.6 if CYL_DEV[i] > 8 else 0.0)
                + nz("k2" if i % 2 else "k3") * 0.3
                if hi
                else 0.0
            )
            regs[k + "ms"] = (
                1.38 - 0.2 * x - (0.26 if i == 4 else 0.0) + nz("k3" if i % 2 else "k1") * 0.02 if hi else 0.0
            )
            regs[k + "plug_h"] = CYL_PLUG[i] + (s["hours"] - HOURS0)
        self.regs = regs

    # --- знімок ---------------------------------------------------------------------------------------------------
    def get_state(self) -> dict[str, Any]:
        s = dict(self.s)
        s["sync"] = list(s["sync"])
        return {"s": s, "kwh": self.kwh, "hours": self.hours}

    def set_state(self, d: dict[str, Any]) -> None:
        self.kwh = float(d.get("kwh", 0.0))
        self.hours = float(d.get("hours", self.hours))
        s = d.get("s")
        if isinstance(s, dict):
            self.first = False
            for k, v in s.items():
                if k in self.s:
                    self.s[k] = list(v) if k == "sync" else v
