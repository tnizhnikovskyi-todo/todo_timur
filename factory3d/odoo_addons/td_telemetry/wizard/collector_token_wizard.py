from odoo import api, fields, models


class F3dCollectorTokenWizard(models.TransientModel):
    _name = "td.collector.token.wizard"
    _description = "Телеметрія: показ токена колектора"

    collector_id = fields.Many2one("td.collector", required=True, readonly=True)
    token = fields.Char(string="Токен (скопіюйте зараз — більше не показується)", readonly=True)
    env_line = fields.Text(string="Рядки для .env", compute="_compute_env_line")

    @api.depends("collector_id.code", "token")
    def _compute_env_line(self):
        for rec in self:
            rec.env_line = "F3D_COLLECTOR_CODE=%s\nF3D_COLLECTOR_TOKEN=%s" % (rec.collector_id.code, rec.token)
