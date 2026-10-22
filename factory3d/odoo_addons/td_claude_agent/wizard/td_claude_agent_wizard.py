from odoo import fields, models


class TdClaudeAgentWizard(models.TransientModel):
    _name = "td.claude.agent.wizard"
    _description = "Агент Claude створено (одноразовий ключ)"

    agent_id = fields.Many2one("td.claude.agent", string="Агент", readonly=True)
    agent_login = fields.Char(string="Логін агента", readonly=True)
    api_key = fields.Char(string="API-ключ", readonly=True)
    api_key_expires = fields.Datetime(string="Діє до", readonly=True)
