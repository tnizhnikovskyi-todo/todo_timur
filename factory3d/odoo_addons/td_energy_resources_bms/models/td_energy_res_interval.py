"""Міст: розширення `td.energy.res.interval` (R-B5): хук `_td_backfill_extra` — історія тепла для backfill ресурсів.

Генератори (`tools/heat.py`): `HM-BOILER = max(0, потреба − КГУ)`, `HM-CHP` — 497 кВт, коли КГУ працює, `HM-RV` =
0,585·потреба, `HM-AHU1` = 0,19·потреба; `HM-DOCK` — напряму (`open_frac` 0,05 у зміну), `HM-OFFICE` — залишок джерел.
"""

from odoo import api, models

from odoo.addons.td_energy_resources.tools import build

from ..tools import heat

HEAT_METERS = ("HM-BOILER", "HM-CHP", "HM-RV", "HM-AHU1", "HM-DOCK", "HM-OFFICE")


class TdEnergyResInterval(models.Model):
    _inherit = "td.energy.res.interval"

    @api.model
    def _td_backfill_extra(self, plan, seed, since, until):
        result = dict(super()._td_backfill_extra(plan, seed, since, until) or {})
        if plan.wanted and "heat" not in plan.wanted:
            return result
        meters = {
            m.code: m
            for m in self.env["td.energy.meter"]
            .sudo()
            .search([("active", "=", True), ("resource_id.code", "=", "heat"), ("code", "in", list(HEAT_METERS))])
        }
        if not meters:
            return result
        balance = heat.balance(self.env)
        dock = meters.get("HM-DOCK")
        t_in = balance.t_in_set if balance else 18.0
        loss = (
            (dock.point_id.estimate_params or {}).get("loss_kw_per_k", heat.DOCK_LOSS_K) if dock else heat.DOCK_LOSS_K
        )
        batch = []
        for state in plan.slot_states(seed, since, until):
            rates = heat.backfill_rates(state, t_in, loss)
            for code, meter in meters.items():
                quality = "estimated" if code in heat.ESTIMATED_CODES else "measured"
                batch.append(plan.row(meter, state.ts, rates[code] * 0.25, quality))
            if len(batch) >= build.BATCH:
                plan.write(batch)
                batch = []
        if batch:
            plan.write(batch)
        result["meter_ids"] = sorted(set(result.get("meter_ids", ())) | {m.id for m in meters.values()})
        return result
