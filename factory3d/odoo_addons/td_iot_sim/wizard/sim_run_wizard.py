import json

from odoo import api, fields, models
from odoo.exceptions import UserError


class F3dSimRunWizard(models.TransientModel):
    _name = "td.sim.run.wizard"
    _description = "Запуск сценарію емулятора"

    scenario_id = fields.Many2one("td.sim.scenario", string="Сценарій", required=True)
    params_text = fields.Text(string="Параметри (JSON)")
    device_id = fields.Many2one("td.sim.device", string="Пристрій")
    zone_id = fields.Many2one("td.zone", string="Зона")
    has_device = fields.Boolean(compute="_compute_schema_flags")
    has_zone = fields.Boolean(compute="_compute_schema_flags")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        scenario = self.env["td.sim.scenario"].browse(res.get("scenario_id"))
        if scenario and "params_text" in fields_list and not res.get("params_text"):
            res["params_text"] = json.dumps(scenario.params_default or {}, indent=2, ensure_ascii=False)
        return res

    @api.onchange("scenario_id")
    def _onchange_scenario_id(self):
        self.params_text = json.dumps(self.scenario_id.params_default or {}, indent=2, ensure_ascii=False)

    @api.depends("scenario_id")
    def _compute_schema_flags(self):
        for rec in self:
            props = (rec.scenario_id.params_schema or {}).get("properties") or {}
            rec.has_device = "device" in props
            rec.has_zone = "zone" in props

    def action_confirm(self):
        self.ensure_one()
        try:
            params = json.loads(self.params_text or "{}")
        except ValueError as exc:
            raise UserError("Параметри мають бути коректним JSON: %s" % exc) from exc
        if not isinstance(params, dict):
            raise UserError("Параметри мають бути JSON-об'єктом")
        if self.device_id:
            params["device"] = self.device_id.code
        if self.zone_id:
            params["zone"] = self.zone_id.td_code
        run = self.env["td.sim.run"]._create_and_start(self.scenario_id, params)
        return {
            "type": "ir.actions.act_window",
            "name": "Запуск",
            "res_model": "td.sim.run",
            "view_mode": "form",
            "res_id": run.id,
        }
