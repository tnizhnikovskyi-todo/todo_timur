from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.td_telemetry.tools.titles import fmt_num

from ..tools import dates

MAX_DAYS = 31


class F3dEnergyRecomputeWizard(models.TransientModel):
    _name = "td.energy.recompute.wizard"
    _description = "Енергетика: перерахунок"

    date_from = fields.Date(
        string="З", required=True, default=lambda self: fields.Date.context_today(self) - timedelta(days=1)
    )
    date_to = fields.Date(string="По", required=True, default=lambda self: fields.Date.context_today(self))
    what = fields.Selection(
        [
            ("intervals", "Інтервали лічильників"),
            ("alloc", "Розподіл на виробництво"),
            ("both", "Усе"),
        ],
        required=True,
        default="both",
    )
    meter_ids = fields.Many2many(
        "td.energy.meter", "td_energy_recompute_wizard_meter_rel", "wizard_id", "meter_id", string="Лічильники"
    )
    result = fields.Text(readonly=True)

    @api.model
    def _td_check_manager(self):
        if not self.env.user.has_group("td_energy.group_td_energy_manager"):
            raise AccessError(_("Перерахунок енергії доступний енергетику."))

    def action_run(self):
        """M-19, R-23: інтервали (`_td_rebuild`) і/або розподіл (`_td_alloc_days`); `locked` не змінюються."""
        self.ensure_one()
        self._td_check_manager()
        if self.date_to < self.date_from:
            raise UserError(_("Дата «По» раніше за дату «З»."))
        if (self.date_to - self.date_from).days > MAX_DAYS:
            raise UserError(_("Перерахунок — не більше 31 доби за раз."))
        d0 = dates.local_day_bounds(self.date_from)[0]
        d1 = dates.local_day_bounds(self.date_to)[1]
        n_iv = n_new = n_days = n_skipped = 0
        if self.what in ("intervals", "both"):
            Interval = self.env["td.energy.interval"].sudo()
            meters = (self.meter_ids or self.env["td.energy.meter"].sudo().search([])).sudo()
            domain = [("meter_id", "in", meters.ids), ("ts_start", ">=", d0), ("ts_start", "<", d1)]
            before = Interval.search_count(domain)
            n_iv = Interval._td_rebuild(meters, d0, d1)
            n_new = max(Interval.search_count(domain) - before, 0)
        if self.what in ("alloc", "both"):
            days = [self.date_from + timedelta(days=i) for i in range((self.date_to - self.date_from).days + 1)]
            stats = self.env["td.energy.alloc"].sudo()._td_alloc_days(days)
            n_days, n_skipped = stats["days"], stats["skipped"]
        self.result = _(
            "Інтервалів: %(n)s (нових %(new)s), діб розподілу: %(days)s, зафіксованих рядків пропущено: %(skipped)s",
            n=fmt_num(n_iv, 0),
            new=fmt_num(n_new, 0),
            days=n_days,
            skipped=n_skipped,
        )
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
