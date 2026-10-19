from odoo import api, fields, models


class F3dSimScenario(models.Model):
    _name = "td.sim.scenario"
    _description = "Сценарій емулятора"
    _inherit = ["td.sim.client"]
    _order = "sequence, code"

    code = fields.Char(string="Код", required=True)
    name = fields.Char(string="Назва", required=True)
    description = fields.Html(string="Опис")
    group = fields.Selection(
        [
            ("production", "Виробництво"),
            ("energy", "Енергетика"),
            ("logistics", "Логістика"),
            ("safety", "Безпека"),
            ("access", "Доступ"),
            ("bms", "BMS"),
        ],
        string="Група",
        required=True,
    )
    params_schema = fields.Json(string="Схема параметрів")
    params_default = fields.Json(string="Параметри за замовчуванням")
    duration_s = fields.Integer(string="Тривалість, с", help="0 = до зупинки")
    sequence = fields.Integer(string="Послідовність", default=10)
    active = fields.Boolean(default=True)
    run_ids = fields.One2many("td.sim.run", "scenario_id", string="Запуски")
    last_run_id = fields.Many2one("td.sim.run", string="Останній запуск", compute="_compute_last_run")
    write_enabled = fields.Boolean(compute="_compute_write_enabled")

    _scenario_code_uniq = models.Constraint("UNIQUE(code)", "Код сценарію має бути унікальним")

    @api.depends("run_ids")
    def _compute_last_run(self):
        for rec in self:
            rec.last_run_id = rec.run_ids[:1]

    def _compute_write_enabled(self):
        flag = self._sim_flag("write_enabled")
        for rec in self:
            rec.write_enabled = flag

    def action_start(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Запуск сценарію",
            "res_model": "td.sim.run.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_scenario_id": self.id},
        }
