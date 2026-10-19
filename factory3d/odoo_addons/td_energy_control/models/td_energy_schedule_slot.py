"""M-34 `td.energy.schedule.slot` — слот розкладу (план, сценарій, ручні); R-54: план дня й вивід `get_schedule`."""

import logging
from datetime import date as date_cls
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from odoo.addons.td_energy.tools import dates, forecast
from odoo.addons.td_energy.tools.tariff import to_local

from .. import tools
from ..tools import bus, planner

_logger = logging.getLogger(__name__)

RESOURCES = [(r, planner.RESOURCE_TITLES[r]) for r in planner.RESOURCES]
MODES = [
    ("charge", "заряд"),
    ("discharge", "розряд"),
    ("run", "пуск"),
    ("night", "ніч"),
    ("day", "день"),
    ("duty", "черговий"),
    ("work", "робочий"),
    ("test", "тест"),
]


class TdEnergyScheduleSlot(models.Model):
    _name = "td.energy.schedule.slot"
    _description = "Енергетика: слот розкладу"
    _order = "resource, time_from, id"

    resource = fields.Selection(RESOURCES, string="Ресурс", required=True, index=True)
    date = fields.Date(string="Дата", help="Порожньо — повторюється за днями тижня")
    weekdays = fields.Char(string="Дні тижня", size=7, default="1111111", help="пн…нд; лише коли дата порожня")
    time_from = fields.Float(string="З", required=True)
    time_to = fields.Float(string="До", required=True)
    mode = fields.Selection(MODES, string="Режим", required=True)
    label = fields.Char(string="Підпис", size=48)
    setpoint_kw = fields.Float(string="Уставка, кВт")
    source = fields.Selection(
        [("plan", "План (прогноз)"), ("scenario", "Сценарій"), ("manual", "Вручну"), ("genset", "td_genset")],
        string="Джерело",
        default="manual",
        index=True,
    )
    executes = fields.Boolean(string="Виконується рушієм", compute="_compute_executes", store=True)
    bar_class = fields.Selection(
        [("c", "c"), ("d", "d"), ("n", "n"), ("g", "g"), ("o", "o")], string="Клас смуги", compute="_compute_bar_class"
    )
    scenario_id = fields.Many2one("td.energy.scenario", string="Сценарій", ondelete="set null")
    active = fields.Boolean(default=True)

    # --- обчислювані / перевірки -------------------------------------------------------------------------------
    @api.depends("source", "resource")
    def _compute_executes(self):
        for rec in self:
            rec.executes = rec.source == "manual" and rec.resource in ("bess", "chp")

    @api.depends("mode")
    def _compute_bar_class(self):
        for rec in self:
            rec.bar_class = planner.BAR_CLASS.get(rec.mode, "o")

    @api.constrains("time_from", "time_to", "weekdays")
    def _check_times(self):
        for rec in self:
            if not (0 <= rec.time_from <= 24 and 0 <= rec.time_to <= 24) or rec.time_to <= rec.time_from:
                raise ValidationError(_("Слот не може перетинати північ: розділіть його."))
            if rec.weekdays and (len(rec.weekdays) != 7 or set(rec.weekdays) - {"0", "1"}):
                raise ValidationError(_("Дні тижня: сім символів 0/1 (пн…нд)."))

    # --- права й журнал (M-34) ---------------------------------------------------------------------------------
    def _td_check_manual(self, sources):
        if tools.is_internal(self.env):
            return False
        user = self.env.user
        if not (user.has_group("td_energy.group_td_energy_chief") or user.has_group("td_factory3d.group_td_admin")):
            raise AccessError(_("Ручні слоти розкладу змінює лише головний енергетик."))
        if set(sources) - {"manual"}:
            raise AccessError(_("Слоти плану й сценаріїв створює лише планувальник."))
        return True

    def _td_log(self, what):
        self.env["td.energy.action"]._td_log_config("schedule_edit", "Розклад: %s" % what)
        bus.tick(self.env, "schedule")

    @api.model_create_multi
    def create(self, vals_list):
        manual = self._td_check_manual([v.get("source", "manual") for v in vals_list])
        recs = super().create(vals_list)
        if manual:
            recs._td_log("додано слот %s" % ", ".join(recs.mapped("resource")))
        return recs

    def write(self, vals):
        manual = self._td_check_manual(
            set(self.mapped("source")) | {vals["source"]} if "source" in vals else self.mapped("source")
        )
        res = super().write(vals)
        if manual:
            self._td_log("змінено слот %s" % ", ".join(self.mapped("resource")))
        return res

    def unlink(self):
        manual = self._td_check_manual(self.mapped("source"))
        names = ", ".join(self.mapped("resource"))
        res = super().unlink()
        if manual:
            self._td_log("видалено слот %s" % names)
        return res

    def action_rebuild_plan(self):
        """V-42 «Перебудувати план» (головний енергетик)."""
        user = self.env.user
        if not (user.has_group("td_energy.group_td_energy_chief") or user.has_group("td_factory3d.group_td_admin")):
            raise AccessError(_("Перебудувати план може лише головний енергетик."))
        self.sudo()._td_plan_all()
        return True

    # --- планувальник (R-54) -----------------------------------------------------------------------------------
    @api.model
    def _td_scenario_params(self):
        out = {}
        for sc in self.env["td.energy.scenario"].sudo().search([]):
            out[sc.code] = (sc.enabled, sc._td_params())
        return out

    @api.model
    def _td_plan_all(self):
        today = dates.local_day(dates.now_utc(self.env))
        horizon = max(1, tools.cparam_int(self.env, "plan_horizon_days", 2))
        for k in range(horizon):
            self._td_plan_day(today + timedelta(days=k))
        old = (
            self.sudo()
            .with_context(td_energy_control_internal=True)
            .search([("source", "in", ("plan", "scenario", "genset")), ("date", "<", today - timedelta(days=2))])
        )
        old.unlink()
        bus.tick(self.env, "schedule")

    @api.model
    def _td_plan_day(self, day):
        """Перебудувати `plan`/`scenario` слоти доби `day` (ідемпотентно)."""
        env = self.env
        Slot = self.sudo().with_context(td_energy_control_internal=True)
        scen = self._td_scenario_params()
        peak, self_p = scen["peak"][1], scen["self"][1]
        night_enabled, night = scen["night"]
        chp_enabled, chp = scen["chp"]
        Slot.search([("date", "=", day), ("source", "in", ("plan", "scenario"))]).unlink()
        typ = forecast.typical_day(
            env.cr, day, dates.param_float(env, "forecast_weeks", 4), dates.param_float(env, "forecast_min_days", 3)
        )
        bars = {r: [] for r in ("bess", "chp", "vent", "light")}
        if typ["ok"]:
            bess = planner.bess_plan(typ["cons"], typ["pv"], peak, self_p)
        else:
            bess = planner.fallback_bess(peak)
        for f, t, mode, label, kw in bess:
            bars["bess"].append((f, t, mode, label, kw, "plan"))
        nb = planner.night_bars(night, night_enabled, day.weekday())
        for res in ("vent", "light"):
            for f, t, mode, label in nb[res]:
                bars[res].append((f, t, mode, label, 0.0, "scenario"))
        if chp_enabled:
            tariff = env["td.energy.tariff"].sudo()._td_tariff_at(dates.to_utc(_noon(day)))
            zones = [
                {"from": z.hour_from, "to": z.hour_to, "price": z.price}
                for z in (tariff.zone_ids if tariff else [])
                if str(day.weekday()) in (z.weekdays or "0123456")
            ]
            gas_cost = chp["gas_price_uah_m3"] * chp["gas_m3_per_kwh"]
            for f, t, mode, label in planner.chp_bars(zones, gas_cost, chp["price_margin_uah_kwh"]):
                bars["chp"].append((f, t, mode, label, 0.0, "scenario"))
        vals = []
        for res, items in bars.items():
            for f, t, mode, label, kw, source in items:
                vals.append(
                    {"resource": res, "date": day, "time_from": f, "time_to": t, "mode": mode, "label": label,
                     "setpoint_kw": kw, "source": source}
                )  # fmt: skip
        return Slot.create(vals)

    @api.model
    def _cron_plan(self):
        if not dates.param_bool(self.env, "read_enabled"):
            return False
        try:
            with self.env.cr.savepoint():
                self._td_plan_all()
        except Exception:
            _logger.exception("td_energy_control: крон плану дня")
        return True

    # --- вивід (R-54 п.8, API-23) --------------------------------------------------------------------------------
    @api.model
    def _td_schedule_rows(self, day):
        """Рядки `[{"resource","name","bars":[…]}]` для доби `day` (Київ)."""
        slots = self.sudo().search([("active", "=", True)])
        wd = day.weekday()
        mine = slots.filtered(lambda s: (s.date == day) or (not s.date and planner.weekday_flag(s.weekdays, wd)))
        rows = []
        for res in planner.RESOURCES:
            items = mine.filtered(lambda s, r=res: s.resource == r)
            manual = [(s.time_from, s.time_to) for s in items if s.source == "manual"]
            bars = []
            for s in items.sorted(lambda s: (s.time_from, s.id)):
                if s.source == "manual":
                    segs = [(s.time_from, s.time_to)]
                else:
                    segs = planner.subtract((s.time_from, s.time_to), manual)
                for f, t in segs:
                    bars.append({"from": f, "to": t, "label": s.label or "", "cls": s.bar_class, "source": s.source})
            rows.append(
                {"resource": res, "name": planner.RESOURCE_TITLES[res], "bars": sorted(bars, key=lambda b: b["from"])}
            )
        return rows

    @api.model
    def _td_now_hours(self, now=None):
        local = to_local(now or dates.now_utc(self.env))
        return round(local.hour + local.minute / 60.0 + local.second / 3600.0, 3)


def _noon(day):
    from datetime import datetime, time

    return datetime.combine(day if isinstance(day, date_cls) else day, time(12, 0))
