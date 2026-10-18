"""M-12 `td.energy.analytics` — API екрана «Аналітика» (AbstractModel; W4-A): API-01…API-09, API-14.

Контроль доступу — `_td_check_access` (`group_td_energy_user`); читання таблиць — SQL/`sudo`; ключі вартості без
`group_td_energy_cost` **видаляються** з відповіді. Контракт відповіді: `contracts/api01_get_dashboard.json`.
"""

import logging
from datetime import timedelta

from odoo import _, api, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.td_energy.tools import dates

from ..tools import cuts, heatmap, kpis, periods, stack
from ..tools import enpi as enpi_tools
from ..tools.fmt import r_int

_logger = logging.getLogger(__name__)

USER = "td_energy.group_td_energy_user"
PARTS = ("kpis", "stack", "heatmap", "enpi", "budget", "cut", "opps")
COST_KEYS = frozenset(
    ("cost_uah", "save_uah_month", "plan_sum", "all_sum", "saving_uah", "plan_uah", "fact_uah", "forecast_uah")
)
SUBTITLE = "Усі ресурси, усі ділянки, у зв'язці з виробництвом"
WEEKS = 12


def strip_cost(data):
    """Видалити ключі вартості (R-07/4.4) на всіх рівнях."""
    if isinstance(data, dict):
        return {k: strip_cost(v) for k, v in data.items() if k not in COST_KEYS}
    if isinstance(data, list):
        return [strip_cost(v) for v in data]
    return data


class TdEnergyAnalytics(models.AbstractModel):
    _name = "td.energy.analytics"
    _description = "Енергетика: дані аналітики"

    # --- доступ і вхідні дані -------------------------------------------------------------------------
    @api.model
    def _td_check_access(self):
        if not (self.env.is_superuser() or self.env.user.has_group(USER)):
            raise AccessError(_("Немає доступу до Енергетики."))

    @api.model
    def _td_ctx(self, period):
        if period not in periods.PERIODS:
            raise UserError(_("Невідомий період: %s.", period))
        return kpis.Context(self.env, period)

    @api.model
    def _td_check_dim(self, dim):
        if dim not in periods.DIMS:
            raise UserError(_("Невідомий розріз: %s.", dim))

    @api.model
    def _td_clean(self, ctx, data):
        return data if ctx.cost_access else strip_cost(data)

    # --- API-01 ---------------------------------------------------------------------------------------
    @api.model
    def get_dashboard(self, period="m", dim="area", parts=None):
        """API-01: JSON «Аналітика»; `parts` — підмножина `PARTS` або `None` (усе). Частина, що впала, → `{"error"}`."""
        self._td_check_access()
        self._td_check_dim(dim)
        ctx = self._td_ctx(period)
        wanted = PARTS if parts is None else tuple(p for p in PARTS if p in parts)
        builders = {
            "kpis": lambda: kpis.build_kpis(ctx),
            "stack": lambda: stack.build_stack(ctx),
            "heatmap": lambda: heatmap.build_heatmap(ctx),
            "enpi": lambda: self._td_enpi(ctx),
            "budget": lambda: self.env["td.energy.budget"].get_status(None),
            "cut": lambda: self._td_cut(ctx, dim),
            "opps": lambda: self._td_opps(),
        }
        out = {"meta": self._td_meta(ctx)}
        for part in wanted:
            try:
                with self.env.cr.savepoint():
                    out[part] = builders[part]()
            except Exception as exc:
                _logger.exception("Аналітика: частина %s", part)
                out[part] = {"error": str(exc) or exc.__class__.__name__}
        return self._td_clean(ctx, out)

    @api.model
    def _td_meta(self, ctx):
        base = ctx.meta_baseline()
        subtitle = SUBTITLE + (" · база для порівняння — %s" % base["label"] if base else " · база не задана")
        caps = {"plan": bool(ctx.manager), "report": bool(self.env["td.energy.dashboard"]._td_report_action())}
        if ctx.cost_access:
            caps = {"cost": True, **caps}
        return {
            "period": ctx.period, "period_label": periods.PERIOD_LABELS[ctx.period], "date_from": ctx.f.isoformat(),
            "date_to": ctx.t.isoformat(), "now_local": dates.to_local(ctx.now).strftime("%H:%M"), "subtitle": subtitle,
            "baseline": base, "capabilities": caps, "refresh_s": periods.param_int(self.env, "refresh_s", 300),
            "data_quality": {"days": ctx.plant["days"], "partial_days": ctx.plant["partial"]},
        }  # fmt: skip

    # --- частини --------------------------------------------------------------------------------------
    @api.model
    def _td_cut(self, ctx, dim):
        top_eq = periods.param_int(self.env, "top_equipment", 15)
        top_mo = periods.param_int(self.env, "top_mo", 20)
        return cuts.build_cut(ctx, dim, top_equipment=top_eq, top_mo=top_mo)

    @api.model
    def _td_opps(self):
        Opp = self.env["td.energy.opportunity"]
        listing = Opp.get_list(None, ("open",))
        summary = Opp.get_plan_summary()
        out = {"items": listing["items"]}
        for key in ("plan_sum", "all_sum"):
            if key in summary:
                out[key] = summary[key]
        out["plan_count"] = summary["plan_count"]
        out["open_count"] = summary["open_count"]
        return out

    @api.model
    def _td_enpi(self, ctx):
        """R-05 п. 3: 12 ковзних тижнів і підсумок за ними (вікно не залежить від періоду екрана, D-58)."""
        cr = ctx.cr
        weeks = periods.weeks(ctx.today, WEEKS)
        first = weeks[0]["date_from"]
        base = ctx.baseline("el")
        index = {}
        for i, week in enumerate(weeks):
            day = week["date_from"]
            while day <= week["date_to"]:
                index[day] = i
                day += timedelta(days=1)
        exp = [None] * WEEKS
        act = [None] * WEEKS
        if base:
            cr.execute(
                """SELECT day, actual, expected FROM td_energy_enpi
                    WHERE baseline_id = %s AND day BETWEEN %s AND %s AND expected IS NOT NULL
                      AND quality != 'no_driver'""",
                (base.id, first, ctx.today),
            )
            for day, actual, expected in cr.fetchall():
                i = index[day]
                act[i] = (act[i] or 0.0) + float(actual)
                exp[i] = (exp[i] or 0.0) + float(expected)
        else:
            cr.execute(
                "SELECT day, qty FROM td_energy_daily WHERE scope = 'plant' AND day BETWEEN %s AND %s",
                (first, ctx.today),
            )
            for day, qty in cr.fetchall():
                i = index[day]
                act[i] = (act[i] or 0.0) + float(qty)
        rows = []
        for i, week in enumerate(weeks):
            label = "12 тижнів тому" if i == 0 else "цей тиждень" if i == WEEKS - 1 else ""
            rows.append(
                {
                    "key": week["key"], "label": label,
                    "expected_mwh": None if exp[i] is None else round(exp[i] / 1000, 3),
                    "actual_mwh": None if act[i] is None else round(act[i] / 1000, 3),
                }
            )  # fmt: skip
        y_min, y_max = enpi_tools.week_axis([r["expected_mwh"] for r in rows] + [r["actual_mwh"] for r in rows])
        out = {
            "weeks": rows, "y_min": y_min, "y_max": y_max, "enpi": None, "saving_pct": None, "saving_kwh": None,
        }  # fmt: skip
        if base:
            tot = self.env["td.energy.enpi"].sudo().period_totals(base, first, ctx.today)
            if tot["enpi"] is not None:
                out.update(enpi=tot["enpi"], saving_pct=tot["saving_pct"], saving_kwh=round(tot["saving_qty"], 1))
                if ctx.cost_access and tot.get("saving_cost") is not None:
                    out["saving_uah"] = r_int(tot["saving_cost"])
        return out

    # --- API-02…API-09 --------------------------------------------------------------------------------
    @api.model
    def get_kpis(self, period):
        self._td_check_access()
        ctx = self._td_ctx(period)
        return self._td_clean(ctx, kpis.build_kpis(ctx))

    @api.model
    def get_stack(self, period):
        self._td_check_access()
        ctx = self._td_ctx(period)
        return stack.build_stack(ctx)

    @api.model
    def _td_stack_gap_pct(self, period):
        """R-08 п. 4: розрив між споживанням заводу й сумою сегментів, % (інформативно)."""
        self._td_check_access()
        return stack.gap_pct(self._td_ctx(period))

    @api.model
    def get_heatmap(self, period):
        self._td_check_access()
        return heatmap.build_heatmap(self._td_ctx(period))

    @api.model
    def get_enpi(self):
        self._td_check_access()
        ctx = self._td_ctx("m")
        return self._td_clean(ctx, self._td_enpi(ctx))

    @api.model
    def get_budget(self, month=None):
        self._td_check_access()
        return self.env["td.energy.budget"].get_status(month)

    @api.model
    def get_cut(self, dim, period):
        self._td_check_access()
        self._td_check_dim(dim)
        ctx = self._td_ctx(period)
        return self._td_clean(ctx, self._td_cut(ctx, dim))

    @api.model
    def action_open_cut(self, dim, key, period):
        """API-08: `ir.actions.act_window` деталізації рядка розрізу (R-16)."""
        self._td_check_access()
        self._td_check_dim(dim)
        ctx = self._td_ctx(period)
        return cuts.open_cut(self.env, dim, key, period, ctx.today)

    @api.model
    def get_opportunities(self):
        self._td_check_access()
        return self._td_opps()
