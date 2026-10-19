"""Міст: розширення `td.energy.opportunity.rule` — детектори `preheat_early`, `ahu_recuperation`, `dock_gates` (R-B4,
FR-B3). Реєстр ядра знаходить методи `_td_detect_<code>(now)` за префіксом (A-08); формат знахідок — R-14."""

from datetime import timedelta

from odoo import api, models

from odoo.addons.td_energy.tools import dates
from odoo.addons.td_energy_resources.tools.detectors import common

from ..tools import heat

SEARCH_H = 6  # preheat_early: вікно пошуку «цех готовий» перед початком першої зміни, годин
STEP_S = 300  # крок сітки сирих показань BMS
TITLES = {
    "preheat_early": "Розігрів перед зміною починається зарано",
    "ahu_recuperation": "Рекуперація AHU-1 нижче норми",
    "dock_gates": "Ворота відвантаження відкриті довго",
}


class TdEnergyOpportunityRule(models.Model):
    _inherit = "td.energy.opportunity.rule"

    # --- preheat_early ---------------------------------------------------------------------------------------------
    @api.model
    def _td_price(self, code, now):
        return self.env["td.energy.price"].sudo()._td_price_at(code, dates.local_day(now))

    def _td_detect_preheat_early(self, now):
        """R-B4 `preheat_early` (газ): різниця між «цех досяг `t_ready`» і початком першої зміни проти `margin_min`."""
        self.ensure_one()
        env = self.sudo().env
        params = common.rule_params(self)
        balance = heat.balance(env)
        units = heat.required_units(env).filtered("indoor_signal_id")
        meter = env["td.energy.meter"].search([("code", "=", "GM-BOILER")], limit=1)
        if not balance or not units or not meter:
            return []
        win = common.Window(env, self, now)
        t_ready = balance.t_in_set
        pad = timedelta(seconds=heat.HOLD_S)
        series = common.readings(env, units.indoor_signal_id.ids, win.lo - timedelta(hours=SEARCH_H) - pad, win.hi)
        margins = {}
        for day in win.work_days():
            start = win.shifts.first_start(day)
            grid = heat.grid_between(start - timedelta(hours=SEARCH_H), start, STEP_S)
            columns = [heat.aligned(series[sid], grid) for sid in series]
            means = []
            for column in zip(*columns, strict=False):
                values = [v for v in column if v is not None]
                means.append(sum(values) / len(values) if values else None)
            if not means or means[-1] is None or means[-1] < t_ready:
                continue  # до початку зміни цех не прогрітий — день не враховується
            ready = len(means) - 1
            while ready > 0 and means[ready - 1] is not None and means[ready - 1] >= t_ready:
                ready -= 1
            margins[day] = (start - grid[ready]).total_seconds() / 60.0
        if len(margins) < common.MIN_DAYS:
            return []
        margin_med = common.median(list(margins.values()))
        excess = margin_med - params["margin_min"]
        if excess <= 0:
            return []
        rows = common.res_slots(env, [meter.id], win)
        rates = []
        for day in margins:
            start = win.shifts.first_start(day)
            lo, hi = start - timedelta(minutes=margin_med + 60), start - timedelta(minutes=margin_med)
            rates += [rate for ts, rate, _qty in rows if lo <= ts < hi]
        if not rates:
            return []
        preheat_rate = common.mean(rates)
        price = self._td_price("gas", now)
        qty = preheat_rate * (excess / 60.0) * len(margins) * win.k_month
        if qty <= 0 or price <= 0:
            return []
        last_day = max(margins)
        shift_start = dates.to_local(win.shifts.first_start(last_day))
        ready_time = shift_start - timedelta(minutes=margin_med)
        text = "Цех досягає %s °C о %s, а зміна о %s. Пізніший старт на %s хв." % (
            heat.fmt_temp(t_ready), ready_time.strftime("%H:%M"), shift_start.strftime("%H:%M"), common.fmt_int(excess),
        )  # fmt: skip
        evidence = {
            "margin_med_min": round(margin_med, 1), "margin_min": params["margin_min"], "days": len(margins),
            "preheat_rate_m3h": round(preheat_rate, 2), "t_ready": t_ready, "price_gas": round(price, 4),
        }  # fmt: skip
        return [
            common.finding(
                "preheat_early:*",
                TITLES["preheat_early"],
                text,
                qty * price,
                qty,
                evidence,
                point_code="BOILER",
            )
        ]

    # --- ahu_recuperation --------------------------------------------------------------------------------------------
    def _td_detect_ahu_recuperation(self, now):
        """R-B4 `ahu_recuperation` (тепло): середня рекуперація AHU-1 у робочі години нижче норми або брудний фільтр."""
        self.ensure_one()
        env = self.sudo().env
        balance = heat.balance(env)
        unit = heat.ahu1(env)
        if not balance or not unit:
            return []
        win = common.Window(env, self, now)
        eta_norm, dp_limit = heat.recovery_norm(env), heat.dp_limit(env)
        extract = heat.signal_by_code(env, heat.EXTRACT_SIGNAL)
        t_in_signal = extract if extract else unit.indoor_signal_id
        out_signal = heat.signal_by_code(env, heat.OUTDOOR_SIGNAL)
        signals = {
            "supply": unit.supply_signal_id, "heat": unit.heat_signal_id, "flow": unit.airflow_signal_id,
            "t_in": t_in_signal, "t_out": out_signal, "dp": unit.filter_signal_id,
        }  # fmt: skip
        if not all(signals[k] for k in ("supply", "heat", "flow", "t_in", "t_out")):
            return []
        pad = timedelta(seconds=heat.HOLD_S)
        data = common.readings(env, [s.id for s in signals.values() if s], win.lo - pad, win.hi)
        etas, flows, deltas, dps = [], [], [], []
        wh = balance.air_wh_m3k or heat.AIR_WH_M3K
        for day in win.days:
            for _name, a, b in win.shifts.windows_for(day):
                grid = heat.grid_between(a, b - timedelta(seconds=1), STEP_S)
                cols = {k: heat.aligned(data[s.id], grid) for k, s in signals.items() if s}
                for i in range(len(grid)):
                    eta = heat.recuperation(
                        cols["supply"][i], cols["heat"][i], cols["flow"][i], unit.airflow_nom, cols["t_in"][i],
                        cols["t_out"][i], wh,
                    )  # fmt: skip
                    if eta is not None:
                        etas.append(eta)
                        flows.append(cols["flow"][i])
                        deltas.append(cols["t_in"][i] - cols["t_out"][i])
                    if "dp" in cols and cols["dp"][i] is not None:
                        dps.append(cols["dp"][i])
        if not etas:
            return []
        eta_mean, dp_mean = common.mean(etas), common.mean(dps)
        if eta_mean >= eta_norm and not (dp_mean is not None and dp_mean > dp_limit):
            return []
        airflow, delta = common.mean(flows), common.mean(deltas)
        loss_kw = max(0.0, eta_norm - eta_mean) * wh * airflow * delta / 1000.0
        run_hours = win.shift_hours()
        qty = loss_kw * run_hours * win.k_month
        price = self._td_price("heat", now)
        saving = qty * price  # лише ΔP фільтра (η у нормі) → 0 → знахідку відкидає `min_saving_uah`
        dirty = dp_mean is not None and dp_mean > dp_limit
        text = "Рекуперація AHU-1 — %s %% при нормі %s %%.%s" % (
            common.fmt_dec(eta_mean * 100.0, 1), common.fmt_int(eta_norm * 100.0),
            " Перепад на фільтрі %s Па — потрібна заміна." % common.fmt_int(dp_mean) if dirty else "",
        )  # fmt: skip
        evidence = {
            "eta_mean": round(eta_mean, 4), "eta_norm": eta_norm,
            "dp_mean": None if dp_mean is None else round(dp_mean, 1), "dp_limit": dp_limit,
            "airflow_m3h": round(airflow, 1), "dt": round(delta, 2), "loss_kw": round(loss_kw, 3),
            "run_hours": round(run_hours, 2), "price_heat": round(price, 4),
        }  # fmt: skip
        if eta_mean >= eta_norm:
            evidence["warning"] = "filter_dp_only"
        return [
            common.finding(
                "ahu_recuperation:AHU-1",
                TITLES["ahu_recuperation"],
                text,
                saving,
                qty,
                evidence,
                node_code="AHU-1",
                point_code="AHU-1",
            )
        ]

    # --- dock_gates ---------------------------------------------------------------------------------------------------
    def _td_detect_dock_gates(self, now):
        """R-B4 `dock_gates` (тепло): довгі відкриття воріт відвантаження; потрібна точка `DOCK` (інакше пропуск)."""
        self.ensure_one()
        env = self.sudo().env
        params = common.rule_params(self)
        point = env["td.energy.point"].search([("resource_id.code", "=", "heat"), ("code", "=", "DOCK")], limit=1)
        if not point or not point.state_signal_id:
            return []
        win = common.Window(env, self, now)
        pad = timedelta(seconds=heat.HOLD_S)
        out_signal = heat.signal_by_code(env, (point.estimate_params or {}).get("t_out_signal") or heat.OUTDOOR_SIGNAL)
        ids = [point.state_signal_id.id] + ([out_signal.id] if out_signal else [])
        data = common.readings(env, ids, win.lo - pad, win.hi)
        state = data[point.state_signal_id.id]
        days_with_data = {dates.local_day(ts) for ts, _v in state if win.lo <= ts < win.hi}
        if len(days_with_data) < common.MIN_DAYS:
            return []
        invert = bool((point.estimate_params or {}).get("state_invert"))  # NC-контакт воріт: 0 = відкрито
        spans = [(a, b) for a, b in heat.openings(state, invert=invert) if win.lo <= a < win.hi]
        long_s = params["long_open_min"] * 60.0
        n_days = len(days_with_data)
        long_per_day = sum(1 for a, b in spans if (b - a).total_seconds() >= long_s) / n_days
        if long_per_day < params["min_events_day"]:
            return []
        open_min_day = sum((b - a).total_seconds() for a, b in spans) / 60.0 / n_days
        excess_h = max(0.0, open_min_day - params["open_norm_min_day"]) / 60.0
        temps = [v for ts, v in data.get(out_signal.id, []) if win.lo <= ts < win.hi] if out_signal else []
        t_in = (point.estimate_params or {}).get("t_in") or heat.balance(env).t_in_set or 18.0
        if not temps:
            return []
        delta = max(0.0, t_in - common.mean(temps))
        loss_kw = float((point.estimate_params or {}).get("loss_kw_per_k", heat.DOCK_LOSS_K)) * delta
        qty = loss_kw * excess_h * win.length * win.k_month
        price = self._td_price("heat", now)
        if qty <= 0 or price <= 0:
            return []
        text = "Ворота відкриті в середньому %s хв на добу (норма %s хв); довгих відкриттів %s на добу." % (
            common.fmt_int(open_min_day), common.fmt_int(params["open_norm_min_day"]), common.fmt_dec(long_per_day, 1),
        )  # fmt: skip
        evidence = {
            "long_per_day": round(long_per_day, 2), "open_min_day": round(open_min_day, 1),
            "open_norm_min_day": params["open_norm_min_day"], "excess_h_day": round(excess_h, 4),
            "loss_kw": round(loss_kw, 2), "dt": round(delta, 2), "days": n_days, "price_heat": round(price, 4),
        }  # fmt: skip
        actions = []
        if env.ref("td_yard.action_td_yard_gate", raise_if_not_found=False):
            actions.append(
                {
                    "code": "yard_gates", "label": "Показати у «Дворі»", "kind": "link", "class": None,
                    "params": {"xmlid": "td_yard.action_td_yard_gate"},
                }
            )  # fmt: skip
        return [
            common.finding(
                "dock_gates:*",
                TITLES["dock_gates"],
                text,
                qty * price,
                qty,
                evidence,
                point_code="DOCK",
                actions=actions,
            )
        ]
