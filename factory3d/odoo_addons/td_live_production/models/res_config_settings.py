"""Налаштування модуля й кнопки керування (res.config.settings): параметри `td.live_production.*`."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

PREFIX = "td.live_production."


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    td_live_enabled = fields.Boolean(
        string="Живе виробництво увімкнено",
        compute="_compute_td_live_enabled",
        help="Статус головного вимикача (`td.live_production.enabled`). Міняється кнопками «Запустити» і «Зупинити»: "
        "це не поле налаштувань, щоб збереження форми не перезаписало вимикач застарілим значенням.",
    )
    td_live_jobs = fields.Text(
        string="Фонові задачі",
        compute="_compute_td_live_jobs",
        help="Останні фонові задачі: прогрес і підсумок. Оновіть сторінку, щоб побачити поточний стан.",
    )
    td_live_orders = fields.Integer(string="Замовлень на добу", config_parameter=PREFIX + "orders_per_day", default=8)
    td_live_shift_start = fields.Float(string="Початок зміни", config_parameter=PREFIX + "shift_start", default=7.0)
    td_live_shift_end = fields.Float(string="Кінець зміни", config_parameter=PREFIX + "shift_end", default=15.5)
    td_live_workdays = fields.Char(
        string="Робочі дні тижня",
        config_parameter=PREFIX + "workdays",
        default="0123456",
        help="Цифри днів тижня, 0 — понеділок. Демо-стенд працює щодня: «0123456».",
    )
    td_live_hot_section = fields.Char(
        string="Перевантажена ділянка",
        config_parameter=PREFIX + "hot_section",
        default="Присадка",
        help="Назва мітки-дільниці верстатів (`mrp.workcenter.tag`). Порожньо — «Присадка»; «-» — без перевантаження.",
    )
    td_live_hot_factor = fields.Float(
        string="Складність операцій ділянки, ×",
        config_parameter=PREFIX + "hot_factor",
        default=3.5,
        help="У стільки разів довшими плануються операції перевантаженої ділянки: звідси черга для «Вузького місця».",
    )
    td_live_downtime_pct = fields.Float(
        string="Частка простоїв, %",
        config_parameter=PREFIX + "downtime_pct",
        default=6.0,
        help="Середня частка робочого часу верстатів, що йде на простої з причинами.",
    )

    def _compute_td_live_jobs(self):
        text = self.env["td.live.job"].td_status_text()
        for rec in self:
            rec.td_live_jobs = text

    def _compute_td_live_enabled(self):
        enabled = self.env["ir.config_parameter"].sudo().get_param(PREFIX + "enabled") == "True"
        for rec in self:
            rec.td_live_enabled = enabled

    @api.constrains("td_live_orders", "td_live_shift_start", "td_live_shift_end", "td_live_downtime_pct")
    def _check_td_live(self):
        for rec in self:
            if not 0 <= rec.td_live_orders <= 200:
                raise ValidationError(_("Замовлень на добу: від 0 до 200."))
            if not 0 <= rec.td_live_shift_start < rec.td_live_shift_end <= 24:
                raise ValidationError(_("Зміна: початок має бути раніше за кінець (0…24 год)."))
            if not 0 <= rec.td_live_downtime_pct <= 60:
                raise ValidationError(_("Частка простоїв: від 0 до 60 %."))

    # --- кнопки: кожна зберігає форму (клієнт) і викликає двигун ----------------------------------------
    def _td_live_notify(self, message, level="success"):
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Живе виробництво"), "message": message, "type": level, "sticky": True},
        }

    def action_td_live_prepare(self):
        """LP-07: підготувати демо-компанію."""
        return self._td_live_notify(self.env["td.live.engine"].td_prepare_company())

    def action_td_live_generate_today(self):
        """Згенерувати сьогодні: план на поточну добу й диспетчер, у фоні (повертається одразу)."""
        return self._td_live_notify(self.env["td.live.engine"].td_queue_generate(0))

    def action_td_live_generate_tomorrow(self):
        """Згенерувати завтра: план на наступну добу, у фоні."""
        return self._td_live_notify(self.env["td.live.engine"].td_queue_generate(1))

    def action_td_live_catch_up(self):
        """LP-04: завершити МО й наряди минулих діб датами їхніх планів, у фоні."""
        return self._td_live_notify(self.env["td.live.engine"].td_queue_catch_up())

    def action_td_live_start(self):
        """LP-06: запустити живе виробництво (крони, вимкнути демо-годинник)."""
        return self._td_live_notify(self.env["td.live.engine"].td_start())

    def action_td_live_stop(self):
        """Зупинити живе виробництво: крони вимкнено, демо-годинник повернуто."""
        return self._td_live_notify(self.env["td.live.engine"].td_stop())
