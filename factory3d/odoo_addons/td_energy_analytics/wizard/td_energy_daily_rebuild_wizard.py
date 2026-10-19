"""M-16 `td.energy.daily.rebuild.wizard` — перерахунок добових фактів і EnPI (Transient; W4-B).

`action_rebuild()` викликає `td.energy.daily.action_rebuild(date_from, date_to)` (API-13: `{days, rows, seconds}`) і
`td.energy.enpi.recompute(date_from, date_to)`; діапазон ≤ 400 діб, група `group_td_energy_manager`.
"""

from datetime import timedelta

from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError

from odoo.addons.td_energy.tools import dates

MAX_DAYS = 400
MANAGER = "td_energy.group_td_energy_manager"


def _today(env):
    """Сьогоднішня київська доба (з урахуванням `f3d_now` у тестах)."""
    return dates.local_day(dates.now_utc(env))


class TdEnergyDailyRebuildWizard(models.TransientModel):
    _name = "td.energy.daily.rebuild.wizard"
    _description = "Енергетика: майстер перерахунку добових фактів"

    date_from = fields.Date(string="З", required=True, default=lambda self: _today(self.env) - timedelta(days=6))
    date_to = fields.Date(string="По", required=True, default=lambda self: _today(self.env))

    def _check_range(self):
        """Кінець не раніше початку, діапазон ≤ 400 діб (SPEC M-16)."""
        for rec in self:
            if rec.date_to < rec.date_from:
                raise UserError(_("Кінець діапазону раніше початку."))
            if (rec.date_to - rec.date_from).days + 1 > MAX_DAYS:
                raise UserError(_("Не більше 400 діб."))

    def action_rebuild(self):
        """Перерахувати факти й EnPI за `[date_from, date_to]`; результат — сповіщення, вікно закривається."""
        self.ensure_one()
        if not (self.env.is_superuser() or self.env.user.has_group(MANAGER)):
            raise AccessError(_("Перераховувати факти може лише енергетик."))
        self._check_range()
        stats = self.env["td.energy.daily"].action_rebuild(self.date_from, self.date_to)
        enpi = self.env["td.energy.enpi"].recompute(self.date_from, self.date_to)
        message = _(
            "Перераховано діб: %(days)s, рядків фактів: %(rows)s (%(sec).1f с), рядків EnPI: %(enpi)s.",
            days=stats.get("days", 0),
            rows=stats.get("rows", 0),
            sec=stats.get("seconds", 0.0),
            enpi=enpi.get("rows", 0),
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Добові факти"),
                "message": message,
                "type": "success",
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},
            },
        }
