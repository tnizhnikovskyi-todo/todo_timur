"""Міст «Енергоресурси — Будівля»: R-B2 (формати), R-B3 (рекуперація AHU-1), R-B4 (ряди для детекторів), R-B5
(генератори тепла для backfill) — чисті функції й невеликі читання сигналів (W3-B).
"""

import math
from datetime import timedelta

from odoo.addons.td_energy_resources.tools.resource_data import fmt_dec

PARAM_NORM = "td.energy_resources_bms.recovery_norm_pct"
PARAM_DP = "td.energy_resources_bms.filter_dp_limit_pa"
DEFAULT_NORM_PCT = 70.0
DEFAULT_DP_LIMIT_PA = 250.0
OUTDOOR_SIGNAL = "ventilation/totals/outdoor_c"
EXTRACT_SIGNAL = "ventilation/units/AHU-1/extract_c"  # зарезервовано: датчика витяжки в BMS немає (A-B2)
AIR_WH_M3K = 0.34
MIN_DELTA_T = 5.0  # R-B3: |T_in − T_out| менше 5 К — η не рахується
MIN_FLOW_SHARE = 0.10  # R-B3: витрата менше 10 % номіналу — η не рахується
HOLD_S = 1800.0  # утримання значення BMS-сигналу (збереження кожні 600 с)

# R-B5: частки теплопотреби й демо-температура
RV_SHARE, AHU_SHARE = 0.585, 0.19
DOCK_LOSS_K, DOCK_OPEN_FRAC = 3.5, 0.05
ESTIMATED_CODES = ("HM-DOCK", "HM-OFFICE")


# --- параметри моста -------------------------------------------------------------------------------------------
def param(env, key, default):
    try:
        return float(env["ir.config_parameter"].sudo().get_param(key, default))
    except (TypeError, ValueError):
        return float(default)


def recovery_norm(env):
    """Норма рекуперації AHU-1, частка (`recovery_norm_pct / 100`)."""
    return param(env, PARAM_NORM, DEFAULT_NORM_PCT) / 100.0


def dp_limit(env):
    return param(env, PARAM_DP, DEFAULT_DP_LIMIT_PA)


def balance(env):
    """Тепловий баланс активної компанії або порожній набір."""
    return env["td.bms.heat.balance"].sudo().search([("company_id", "=", env.company.id)], limit=1)


def fmt_temp(x):
    """Температура з комою: 70 → «70», 18,5 → «18,5»."""
    text = fmt_dec(x, 1)
    return text[:-2] if text.endswith(",0") else text


# --- живі значення (R-B2) --------------------------------------------------------------------------------------
def live(signal, now):
    """`last_value`, якщо сигнал свіжий (`last_ts ≥ now − max(3·period, 120 с)`, не `bad`), інакше `None`."""
    if not signal or not signal.last_ts or signal.last_quality == "bad":
        return None
    if (now - signal.last_ts).total_seconds() > max(3 * (signal.period_s or 60), 120):
        return None
    return signal.last_value


def signal_by_code(env, code):
    return env["td.signal"].sudo().with_context(active_test=False).search([("code", "=", code)], limit=1)


def required_units(env):
    """Установки, що мають працювати в робочий час (RV + AHU-1)."""
    return env["td.bms.hvac.unit"].sudo().search([("required_in_work", "=", True), ("kind", "in", ("roofvent", "ahu"))])


def ahu1(env):
    return env["td.bms.hvac.unit"].sudo().search([("code", "=", "AHU-1")], limit=1)


# --- R-B3 ------------------------------------------------------------------------------------------------------
def recuperation(t_supply, q_heat_kw, airflow, airflow_nom, t_in, t_out, air_wh=AIR_WH_M3K):
    """R-B3: `η = (T_after − T_out)/(T_in − T_out)`, `T_after = T_supply − Q·1000/(air_wh·airflow)`; захист: різниця
    `T_in − T_out < 5 К`, витрата `< 10 %` номіналу, `η ∉ [0, 1]` — `None`."""
    values = (t_supply, q_heat_kw, airflow, t_in, t_out)
    if any(v is None for v in values) or not air_wh or airflow <= 0:
        return None
    if airflow_nom and airflow < MIN_FLOW_SHARE * airflow_nom:
        return None
    if t_in - t_out < MIN_DELTA_T:
        return None
    t_after = t_supply - q_heat_kw * 1000.0 / (air_wh * airflow)
    eta = (t_after - t_out) / (t_in - t_out)
    return eta if 0.0 <= eta <= 1.0 else None


def ahu_inputs(env, now, unit=None, balance_rec=None):
    """Живі входи R-B3 для AHU-1 у порядку аргументів `recuperation`: `(t_supply, q_heat, airflow, airflow_nom,
    t_in, t_out, air_wh)`; `T_in` — витяжка (`extract_c`), якщо сигнал є, інакше `indoor_c`."""
    unit = unit or ahu1(env)
    balance_rec = balance_rec if balance_rec is not None else balance(env)
    extract = live(signal_by_code(env, EXTRACT_SIGNAL), now)
    t_in = extract if extract is not None else live(unit.indoor_signal_id, now)
    t_out = live(signal_by_code(env, OUTDOOR_SIGNAL), now)
    return (
        live(unit.supply_signal_id, now), live(unit.heat_signal_id, now), live(unit.airflow_signal_id, now),
        unit.airflow_nom, t_in, t_out, (balance_rec.air_wh_m3k if balance_rec else 0.0) or AIR_WH_M3K,
    )  # fmt: skip


def live_row(row, now):
    """Те саме, що `live`, для рядка `read` сигналу (`last_value`, `last_ts`, `last_quality`, `period_s`)."""
    if not row or not row["last_ts"] or row["last_quality"] == "bad":
        return None
    if (now - row["last_ts"]).total_seconds() > max(3 * (row["period_s"] or 60), 120):
        return None
    return row["last_value"]


class Snapshot:
    """Читання BMS для хуків екрана «Тепло» (R-B2) за 4 SQL: баланс, установки (RV + AHU-1), сигнали, параметри моста.
    Усе через `read(load=False)` без відображуваних імен; хуки ділять один екземпляр через `ctx`."""

    BALANCE = ("t_in_set", "capacity_kw", "air_wh_m3k", "boiler_supply_signal_id", "boiler_return_signal_id")
    UNIT = (
        "code", "kind", "required_in_work", "airflow_nom", "indoor_signal_id", "supply_signal_id", "heat_signal_id",
        "airflow_signal_id", "filter_signal_id",
    )  # fmt: skip
    SIGNAL = ("code", "last_value", "last_ts", "last_quality", "period_s")

    def __init__(self, env, now):
        self.now = now
        self.balance, self.units, self.rows, self.by_code = None, [], {}, {}
        self.norm_pct, self.dp_limit = DEFAULT_NORM_PCT, DEFAULT_DP_LIMIT_PA
        balance = env["td.bms.heat.balance"].sudo().search([("company_id", "=", env.company.id)], limit=1)
        if not balance:
            return
        self.balance = balance.read(self.BALANCE, load=False)[0]
        self.units = (
            env["td.bms.hvac.unit"].sudo().search(["|", ("required_in_work", "=", True), ("code", "=", "AHU-1")])
            .read(self.UNIT, load=False)
        )  # fmt: skip
        ids = {self.balance[k] for k in ("boiler_supply_signal_id", "boiler_return_signal_id")}
        for unit in self.units:
            ids.update(unit[k] for k in self.UNIT if k.endswith("_signal_id"))
        ids.discard(False)
        signals = env["td.signal"].sudo().with_context(active_test=False)
        rows = signals.search(["|", ("id", "in", sorted(ids)), ("code", "in", [OUTDOOR_SIGNAL, EXTRACT_SIGNAL])])
        for row in rows.read(self.SIGNAL, load=False):
            self.rows[row["id"]] = row
            self.by_code[row["code"]] = row
        params = env["ir.config_parameter"].sudo().search([("key", "in", [PARAM_NORM, PARAM_DP])])
        for rec in params:
            try:
                value = float(rec.value)
            except (TypeError, ValueError):
                continue
            if rec.key == PARAM_NORM:
                self.norm_pct = value
            else:
                self.dp_limit = value

    def value(self, signal_id):
        return live_row(self.rows.get(signal_id), self.now)

    def value_code(self, code):
        return live_row(self.by_code.get(code), self.now)

    def required(self):
        return [u for u in self.units if u["required_in_work"] and u["kind"] in ("roofvent", "ahu")]

    def ahu(self):
        return next((u for u in self.units if u["code"] == "AHU-1"), None)

    def eta(self):
        """R-B3 для AHU-1 за живими значеннями; немає установки чи сигналів — `None`."""
        unit = self.ahu()
        if not unit or not self.balance:
            return None
        extract = self.value_code(EXTRACT_SIGNAL)
        t_in = extract if extract is not None else self.value(unit["indoor_signal_id"])
        return recuperation(
            self.value(unit["supply_signal_id"]), self.value(unit["heat_signal_id"]),
            self.value(unit["airflow_signal_id"]), unit["airflow_nom"], t_in, self.value_code(OUTDOOR_SIGNAL),
            self.balance["air_wh_m3k"] or AIR_WH_M3K,
        )  # fmt: skip


# --- ряди для детекторів (R-B4) --------------------------------------------------------------------------------
def aligned(points, grid, hold_s=HOLD_S):
    """Значення ступінчастого ряду `points` (`[(ts, v)]` за часом) на вузлах `grid` (за часом): останнє `≤ ts`, не
    старше `hold_s` секунд; інакше `None`."""
    out, i, last = [], 0, None
    n = len(points)
    for ts in grid:
        while i < n and points[i][0] <= ts:
            last = points[i]
            i += 1
        out.append(last[1] if last and (ts - last[0]).total_seconds() <= hold_s else None)
    return out


def grid_between(lo, hi, step_s=300):
    """Вузли сітки `[lo, hi]` з кроком `step_s` секунд (включно з `hi`, якщо він на сітці)."""
    out, t = [], lo
    while t <= hi:
        out.append(t)
        t += timedelta(seconds=step_s)
    return out


def openings(points, hold_s=HOLD_S, threshold=0.5, invert=False):
    """Відкриття воріт: неперервні інтервали зі значенням `≥ threshold` (`invert=True`, контакт NC, — `< threshold`) →
    `[(start, end)]`. Розрив між показаннями понад `hold_s` або незакрите відкриття обрізається `hold_s` після
    останнього показання."""
    out, start, last = [], None, None
    hold = timedelta(seconds=hold_s)
    for ts, value in points:
        if (value >= threshold) != invert:
            if start is None:
                start = ts
            elif last is not None and ts - last > hold:
                out.append((start, last + hold))
                start = ts
        elif start is not None:
            out.append((start, ts))
            start = None
        last = ts
    if start is not None:
        out.append((start, last + hold))
    return out


# --- R-B5: генератори тепла для backfill -------------------------------------------------------------------------
def t_out_demo(doy, hour):
    """Демо-температура зовні (R-B5): `7 + 8·cos(2π(doy − 200)/365) + 3·sin(π(h − 9)/12)`."""
    return 7.0 + 8.0 * math.cos(2 * math.pi * (doy - 200) / 365.0) + 3.0 * math.sin(math.pi * (hour - 9) / 12.0)


def backfill_rates(state, t_in=18.0, loss_kw_per_k=DOCK_LOSS_K):
    """Швидкості (кВт) слота `state` (`SlotState` ядра: `heat_need`, `heat_chp`, `shift`, `local`, `hs`):
    котельня = `max(0, потреба − КГУ)`, КГУ, RV = 0,585·потреба, AHU-1 = 0,19·потреба, ворота = `k·ΔT·0,05` у зміну,
    офіс = залишок джерел (≥ 0)."""
    boiler = max(0.0, state.heat_need - state.heat_chp)
    chp = state.heat_chp
    rv, ahu = RV_SHARE * state.heat_need, AHU_SHARE * state.heat_need
    delta = max(0.0, t_in - t_out_demo(state.local.timetuple().tm_yday, state.hs))
    dock = loss_kw_per_k * delta * (DOCK_OPEN_FRAC if state.shift else 0.0)
    office = max(0.0, boiler + chp - rv - ahu - dock)
    return {"HM-BOILER": boiler, "HM-CHP": chp, "HM-RV": rv, "HM-AHU1": ahu, "HM-DOCK": dock, "HM-OFFICE": office}
