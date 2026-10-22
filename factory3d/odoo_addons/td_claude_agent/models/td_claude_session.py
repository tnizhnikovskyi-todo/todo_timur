from odoo import api, fields, models


class TdClaudeSession(models.Model):
    _name = "td.claude.session"
    _description = "Сесія Claude (запис Odoo ↔ сесія)"
    _order = "last_message_at desc, id desc"

    agent_id = fields.Many2one("td.claude.agent", string="Агент", required=True, ondelete="cascade", index=True)
    owner_id = fields.Many2one(related="agent_id.owner_id", store=True, index=True)
    agent_user_id = fields.Many2one(related="agent_id.agent_user_id", store=True, index=True)
    res_model = fields.Char(string="Модель", required=True)
    res_id = fields.Integer(string="ID запису", required=True)
    record_name = fields.Char(string="Запис")
    session_id = fields.Char(string="ID сесії")
    session_url = fields.Char(string="Посилання на сесію")
    state = fields.Selection(
        [("active", "Активна"), ("closed", "Закрита")], string="Стан", default="active", required=True
    )
    last_message_at = fields.Datetime(string="Останнє повідомлення")

    _agent_record_uniq = models.Constraint(
        "UNIQUE(agent_id, res_model, res_id)", "Для запису вже є сесія цього агента."
    )

    @api.depends("record_name", "res_model", "res_id")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = rec.record_name or f"{rec.res_model},{rec.res_id}"

    def action_open_session(self):
        self.ensure_one()
        return {"type": "ir.actions.act_url", "url": self.session_url, "target": "new"}
