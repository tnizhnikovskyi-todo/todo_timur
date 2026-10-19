"""BESS LUNA2000 і баланс електроенергії (R-13).

Модель BESS рахується першою серед агрегатів (код ``BESS`` < ``Q1``), тому саме вона веде баланс:
``load = Σ p_now`` споживачів, ``gen = pv + chp``, ``surplus = gen − load``,
``bess_kw = clamp(surplus, −200, +200)`` (розряд — лише понад поріг піку, див. нижче) з обмеженням за SOC (заряд при ``SOC < 100``, розряд при
``SOC > 10``), ``export = max(0, surplus − bess_kw)``, ``grid = max(0, load − gen − max(0, −bess_kw))``.
``bess_kw > 0`` — заряд. Розряд на дефіцит — пік-шейвінг: лише та частина дефіциту, що перевищує
``bess_shave_kw`` (прапор світу, за замовчуванням 600 кВт = параметр ``peak_shave_kw`` td_energy); штатно BESS в очікуванні
(0 кВт), тож у робочу добу імпорт ``Q1 + Q2`` додатний, як у макеті; ``bess_shave_kw = 0`` — розряд на будь-який дефіцит (R-13 макета). Острів (``blackout``): ``grid = export = 0``; до переключення ATyS у II розряд
``−min(200, P_crit)`` (лише при ``SOC > 10``), після — 0. ``grid_kw``/``export_kw`` належать пристрою
``EMS-1`` (пасивний) — пишемо їх за повним кодом сигналу.

W2 (SPEC §8.2, R-59): режими контролера (прапор ``bess_mode``): ``0`` авто (вище; ``bess_auto_idle`` → 0 кВт),
``1`` примусовий заряд ``+min(setpoint, 200)`` до ``until_soc`` (0 — до 100 %), ``2`` примусовий розряд
``−min(setpoint, 200)``, поки SOC > ``max(until_soc, reserve_pct)``, ``3`` утримання 0 кВт. Сторожовий таймер
``bess_valid_s``: у примусовому режимі зменшується на ``dt`` (час світу); на 0 → режим ``0``. Відмова ``ack = 2`` —
у ``try_set_mode`` (розряд при SOC ≤ ``reserve_pct`` або температурі шафи > 40 °C): режим не змінюється. Баланс із
примусовим зарядом: імпорт ``grid = max(0, load + заряд − gen − розряд)``, експорт — навпаки.
"""

from __future__ import annotations

from typing import Any

from iot_sim.models import register_model
from iot_sim.models.base import AGGREGATE, Model
from iot_sim.models.meter import (
    BESS_TEMP_MAX_C,
    bess_temp_c,
    ctl,
    gen_kw,
    get,
    island,
    p_crit,
    put,
    total_load,
    update_rv_all,
)

BESS_KW_MAX = 200.0
BESS_SHAVE_KW = 600.0  # поріг пік-шейвінгу, кВт (td_energy: peak_shave_kw)
BESS_KWH = 387.0
SOC_MIN, SOC_MAX = 10.0, 100.0
ATS_POSITION = "infra/ats/position"


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def try_set_mode(world: Any, mode: int) -> bool:
    """Запис ``bess/mode`` контролером: ``False`` (``ack = 2``) — відмова, режим не змінюється (R-59)."""
    if mode == 2:
        soc = float(get(world, "infra/totals/bess_soc", 0.0))
        if soc <= float(ctl(world, "bess_reserve_pct")) or bess_temp_c(world) > BESS_TEMP_MAX_C:
            world.set_flag("bess_ack", 2)
            return False
    world.set_flag("bess_mode", mode)
    world.set_flag("bess_ack", 0)
    return True


@register_model("bess")
class Bess(Model):
    phase = AGGREGATE

    def attach(self) -> None:
        self.charge_kwh = 0.0
        self.discharge_kwh = 0.0

    def balance(self) -> tuple[float, float, float]:
        """``(bess_kw, grid_kw, export_kw)`` за поточними значеннями сигналів."""
        w = self.world
        soc = float(self.val("bess_soc", 76.0))
        if island(w):
            crit = p_crit(w)
            switched = get(w, ATS_POSITION, 2) == 3
            bess = 0.0 if switched or soc <= SOC_MIN else -min(BESS_KW_MAX, crit)
            return bess, 0.0, 0.0
        load = total_load(w)
        gen = gen_kw(w)
        surplus = gen - load
        forced = self._forced(soc)
        if forced is not None:
            bess = forced
        elif ctl(w, "bess_auto_idle"):
            bess = 0.0
        else:
            shave = float(w.flags.get("bess_shave_kw", BESS_SHAVE_KW))
            bess = clamp(surplus, 0.0, BESS_KW_MAX) if surplus >= 0 else -clamp(-surplus - shave, 0.0, BESS_KW_MAX)
            if (bess > 0 and soc >= SOC_MAX) or (bess < 0 and soc <= SOC_MIN):
                bess = 0.0
        net = load - gen + bess  # імпорт з мережі (> 0) або експорт (< 0); заряд збільшує імпорт
        return bess, max(0.0, net), max(0.0, -net)

    def _watchdog(self) -> None:
        """Сторожовий таймер ``valid_s``: у примусовому режимі зменшується на ``dt``; на 0 → режим «авто»."""
        w = self.world
        if int(ctl(w, "bess_mode")) == 0:
            return
        left = float(ctl(w, "bess_valid_left")) - self.dt_s
        if left > 0:
            w.set_flag("bess_valid_left", left)
            return
        w.set_flag("bess_mode", 0)
        w.set_flag("bess_valid_left", 0.0)
        w.events.emit("info", "BESS: сторожовий таймер valid_s — режим «авто»", device=self.device.code)

    def _forced(self, soc: float) -> float | None:
        """Потужність примусового режиму контролера (``bess_mode`` 1…3), ``None`` — авто."""
        w = self.world
        mode = int(ctl(w, "bess_mode"))
        if mode == 0:
            return None
        setpoint = clamp(float(ctl(w, "bess_setpoint_kw")), 0.0, BESS_KW_MAX)
        until = float(ctl(w, "bess_until_soc"))
        if mode == 1:
            return setpoint if soc < (until if until > 0 else SOC_MAX) and soc < SOC_MAX else 0.0
        if mode == 2:
            floor = max(until, float(ctl(w, "bess_reserve_pct")))
            return -setpoint if soc > floor else 0.0
        return 0.0

    def tick(self, dt_s: float) -> None:
        update_rv_all(self.world)
        self._watchdog()
        failed = self.device.fault is not None
        bess, grid, export = self.balance()
        if failed:
            bess = 0.0
        soc = float(self.val("bess_soc", 76.0))
        soc = clamp(soc + bess * dt_s / 3600.0 / BESS_KWH * 100.0, 0.0, SOC_MAX)
        self.set("bess_soc", soc)
        self.set("bess_kw", bess)
        put(self.world, "infra/totals/grid_kw", grid)
        put(self.world, "infra/totals/export_kw", export)
        self.charge_kwh += max(0.0, bess) * dt_s / 3600.0
        self.discharge_kwh += max(0.0, -bess) * dt_s / 3600.0
        self.set("kwh_charge_total", round(self.charge_kwh, 4))
        self.set("kwh_discharge_total", round(self.discharge_kwh, 4))
        self.set("state", 3 if failed else (2 if abs(bess) > 0.0 else 1))

    def get_state(self) -> dict[str, Any]:
        return {"charge_kwh": self.charge_kwh, "discharge_kwh": self.discharge_kwh}

    def set_state(self, d: dict[str, Any]) -> None:
        self.charge_kwh = float(d.get("charge_kwh", 0.0))
        self.discharge_kwh = float(d.get("discharge_kwh", 0.0))
