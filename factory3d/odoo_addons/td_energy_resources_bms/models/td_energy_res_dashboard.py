"""Міст: розширення `td.energy.res.dashboard` (M-B2, R-B2): хуки вкладки «Тепло» — `_td_heat_kpis`, `_td_heat_list`,
`_td_heat_chart_note`. `ctx` — словник екрана (`env, now, today, cost, resource, rate, rates, qty_today, points,
screen`); хуки не пишуть у БД й читають BMS через `sudo`."""

from odoo import api, models

from ..tools import heat

LIST_CODES = ("RV-ALL", "AHU-1", "DOCK", "OFFICE")
MEASURED = ("RV-ALL", "AHU-1")


class TdEnergyResDashboard(models.AbstractModel):
    _inherit = "td.energy.res.dashboard"

    @api.model
    def _td_heat_kpis(self, ctx):
        """R-B2 п. 1: `power.note` (подача/зворот), `indoor` (температура в цеху), `recovery` (AHU-1)."""
        env, now = ctx["env"].sudo(), ctx["now"]
        balance = heat.balance(env)
        if not balance:
            return []
        out = []
        supply, back = heat.live(balance.boiler_supply_signal_id, now), heat.live(balance.boiler_return_signal_id, now)
        if supply is not None and back is not None:
            out.append(
                {"id": "power", "note": "подача %s °C · зворот %s °C" % (heat.fmt_temp(supply), heat.fmt_temp(back))}
            )
        out.append(self._td_kpi_indoor(env, now, balance))
        out.append(self._td_kpi_recovery(env, now, balance))
        return out

    @api.model
    def _td_kpi_indoor(self, env, now, balance):
        values = [heat.live(u.indoor_signal_id, now) for u in heat.required_units(env)]
        values = [v for v in values if v is not None]
        outdoor = heat.live(heat.signal_by_code(env, heat.OUTDOOR_SIGNAL), now)
        note = "уставка %s °C" % heat.fmt_temp(balance.t_in_set)
        if outdoor is not None:
            note += " · зовні %s °C" % heat.fmt_temp(outdoor)
        value, tone = None, "neutral"
        if values:
            value = round(sum(values) / len(values), 1)
            tone = "good" if abs(value - balance.t_in_set) <= 1.0 else "bad"
        else:
            note = "—"
        return {
            "id": "indoor", "label": "Температура в цеху", "value": value, "unit": "°C", "note": note, "tone": tone,
            "quality": "measured",
        }  # fmt: skip

    @api.model
    def _td_kpi_recovery(self, env, now, balance):
        unit = heat.ahu1(env)
        norm_pct = heat.param(env, heat.PARAM_NORM, heat.DEFAULT_NORM_PCT)
        eta = None
        dirty = False
        if unit:
            eta = heat.recuperation(*heat.ahu_inputs(env, now, unit, balance))
            dp = heat.live(unit.filter_signal_id, now)
            dirty = dp is not None and dp > heat.dp_limit(env)
        norm_note = "норма ≥ %s %%" % heat.fmt_temp(norm_pct)
        note = "—" if eta is None and not dirty else norm_note + (" · фільтр брудний" if dirty else "")
        tone = "neutral" if eta is None else ("bad" if eta * 100.0 < norm_pct else "good")
        return {
            "id": "recovery", "label": "Рекуперація AHU-1", "value": None if eta is None else round(eta * 100.0, 1),
            "unit": "%", "note": note, "tone": tone, "quality": "estimated",
        }  # fmt: skip

    @api.model
    def _td_heat_list(self, ctx):
        """R-B2 п. 4: споживачі `RV-ALL`, `AHU-1`, `DOCK`, `OFFICE` (кВт зараз); `OFFICE = max(0, Σ джерел − решта)`.
        Немає жодної з теплових точок моста — `None` (ядро покаже точки ресурсу)."""
        points = {p["code"]: p for p in ctx["points"]}
        if not any(code in points for code in LIST_CODES):
            return None
        rates = ctx["rates"]
        source = ctx.get("rate")
        if source is None:
            known = [rates.get(p["code"]) for p in ctx["points"] if p["kind"] == "source"]
            known = [v for v in known if v is not None]
            source = sum(known) if known else None
        others = sum(rates.get(code) or 0.0 for code in ("RV-ALL", "AHU-1", "DOCK") if code in points)
        items = []
        for code in LIST_CODES:
            point = points.get(code)
            if not point:
                continue
            if code == "OFFICE":
                value = None if source is None else max(0.0, source - others)
            else:
                value = rates.get(code)
            items.append(
                {
                    "code": code, "name": point["name"], "value": value,
                    "quality": "measured" if code in MEASURED else "estimated",
                }
            )  # fmt: skip
        return items

    @api.model
    def _td_heat_chart_note(self, ctx):
        """R-B2: `{capacity}` у примітці графіка — `capacity_kw` активного балансу (рядком) або `None`."""
        balance = heat.balance(ctx["env"].sudo())
        return str(int(balance.capacity_kw)) if balance and balance.capacity_kw else None
