from datetime import timedelta

from odoo import api, fields, models

from ..tools import dates


class F3dEnergyDayMixin(models.AbstractModel):
    """Пошукові фільтри за київською добою поля `day` (Y-2): рахує сервер, а не `context_today()` браузера
    (UTC на стенді: з 21:00 до 24:00 UTC київська доба вже інша)."""

    _name = "f3d.energy.day.mixin"
    _description = "Енергетика: фільтри київської доби"

    is_today = fields.Boolean(string="Сьогодні", compute="_compute_day_flags", search="_search_is_today")
    is_yesterday = fields.Boolean(string="Вчора", compute="_compute_day_flags", search="_search_is_yesterday")
    is_last_7d = fields.Boolean(string="7 днів", compute="_compute_day_flags", search="_search_is_last_7d")

    @api.depends("day")
    def _compute_day_flags(self):
        today = dates.local_day(dates.now_utc(self.env))
        for rec in self:
            rec.is_today = rec.day == today
            rec.is_yesterday = rec.day == today - timedelta(days=1)
            rec.is_last_7d = bool(rec.day) and today - timedelta(days=7) <= rec.day <= today

    def _search_is_today(self, operator, value):
        return dates.day_window_domain(operator, value, dates.now_utc(self.env))

    def _search_is_yesterday(self, operator, value):
        return dates.day_window_domain(operator, value, dates.now_utc(self.env), back_from=1, back_to=1)

    def _search_is_last_7d(self, operator, value):
        return dates.day_window_domain(operator, value, dates.now_utc(self.env), back_from=7)
