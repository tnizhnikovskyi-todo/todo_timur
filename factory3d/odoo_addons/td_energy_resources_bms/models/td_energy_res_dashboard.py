"""Міст: розширення `td.energy.res.dashboard` (M-B2, R-B2): хуки вкладки «Тепло» — `_td_heat_kpis`, `_td_heat_list`,
`_td_heat_chart_note`. `ctx` — словник екрана (`env, now, today, cost, resource, rate, rates, qty_today, points,
screen`); хуки не пишуть у БД й читають BMS через `sudo`."""

from odoo import api, models

from odoo.addons.td_energy.tools import dates

from ..tools import heat

LIST_CODES = ("RV-ALL", "AHU-1", "DOCK", "OFFICE")
MEASURED = ("RV-ALL", "AHU-1")


class TdEnergyResDashboard(models.AbstractModel):
    _inherit = "td.energy.res.dashboard"

    @api.model
    def _td_snapshot(self, ctx):
        """Читання BMS один раз на відповідь: кешується в `ctx` (хуки KPI й примітки графіка ділять його)."""
        snap = ctx.get("_bms_snapshot")
        if snap is None:
            env = ctx["env"](su=True)
            snap = ctx["_bms_snapshot"] = heat.Snapshot(env, ctx.get("now") or dates.now_utc(env))
        return snap

    @api.model
    def _td_heat_kpis(self, ctx):
        """R-B2 п. 1: `power.note` (подача/зворот), `indoor` (температура в цеху), `recovery` (AHU-1, оцінка)."""
        snap = self._td_snapshot(ctx)
        if not snap.balance:
            return []
        out = []
        supply, back = (
            snap.value(snap.balance["boiler_supply_signal_id"]),
            snap.value(snap.balance["boiler_return_signal_id"]),
        )
        if supply is not None and back is not None:
            out.append(
                {"id": "power", "note": "подача %s °C · зворот %s °C" % (heat.fmt_temp(supply), heat.fmt_temp(back))}
            )
        out.append(self._td_kpi_indoor(snap))
        out.append(self._td_kpi_recovery(snap))
        return out

    @api.model
    def _td_kpi_indoor(self, snap):
        t_set = snap.balance["t_in_set"]
        values = [snap.value(u["indoor_signal_id"]) for u in snap.required()]
        values = [v for v in values if v is not None]
        outdoor = snap.value_code(heat.OUTDOOR_SIGNAL)
        note = "уставка %s °C" % heat.fmt_temp(t_set)
        if outdoor is not None:
            note += " · зовні %s °C" % heat.fmt_temp(outdoor)
        value, tone = None, "neutral"
        if values:
            value = round(sum(values) / len(values), 1)
            tone = "good" if abs(value - t_set) <= 1.0 else "bad"
        else:
            note = "—"
        return {
            "id": "indoor", "label": "Температура в цеху", "value": value, "unit": "°C", "note": note, "tone": tone,
            "quality": "measured",
        }  # fmt: skip

    @api.model
    def _td_kpi_recovery(self, snap):
        unit = snap.ahu()
        eta = snap.eta()
        dp = snap.value(unit["filter_signal_id"]) if unit else None
        dirty = dp is not None and dp > snap.dp_limit
        norm_note = "норма ≥ %s %%" % heat.fmt_temp(snap.norm_pct)
        note = "—" if eta is None and not dirty else norm_note + (" · фільтр брудний" if dirty else "")
        tone = "neutral" if eta is None else ("bad" if eta * 100.0 < snap.norm_pct else "good")
        return {
            "id": "recovery", "label": "Рекуперація AHU-1", "value": None if eta is None else int(round(eta * 100.0)),
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
        balance = self._td_snapshot(ctx).balance
        return str(int(balance["capacity_kw"])) if balance and balance["capacity_kw"] else None
