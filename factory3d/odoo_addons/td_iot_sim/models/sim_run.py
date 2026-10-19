import logging

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
}


def _check_value(key, value, spec):
    typ = spec.get("type")
    if typ and typ in TYPE_CHECKS and not TYPE_CHECKS[typ](value):
        raise ValidationError("Параметр «%s»: очікується тип %s" % (key, typ))
    if "enum" in spec and value not in spec["enum"]:
        raise ValidationError("Параметр «%s»: допустимі значення %s" % (key, ", ".join(map(str, spec["enum"]))))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in spec and value < spec["minimum"]:
            raise ValidationError("Параметр «%s»: мінімум %s" % (key, spec["minimum"]))
        if "maximum" in spec and value > spec["maximum"]:
            raise ValidationError("Параметр «%s»: максимум %s" % (key, spec["maximum"]))
    if isinstance(value, list) and isinstance(spec.get("items"), dict):
        for item in value:
            _check_value(key, item, spec["items"])


def validate_params(schema, params):
    """jsonschema-lite: type, enum, minimum/maximum, required, items (SPEC §2.5)."""
    schema, params = schema or {}, params or {}
    if not isinstance(params, dict):
        raise ValidationError("Параметри мають бути JSON-об'єктом")
    props = schema.get("properties") or {}
    for key in schema.get("required") or []:
        if key not in params:
            raise ValidationError("Не задано обов'язковий параметр «%s»" % key)
    for key, value in params.items():
        if key in props:
            _check_value(key, value, props[key])
    return True


class F3dSimRun(models.Model):
    _name = "td.sim.run"
    _description = "Запуск сценарію"
    _inherit = ["td.sim.client", "mail.thread"]
    _order = "start_ts desc, id desc"

    name = fields.Char(string="Номер", readonly=True, copy=False, default="/")
    panel_id = fields.Many2one(
        "td.sim.panel", string="Пульт", default=lambda self: self.env["td.sim.panel"].get_panel()
    )
    scenario_id = fields.Many2one("td.sim.scenario", string="Сценарій", required=True, ondelete="restrict")
    params = fields.Json(string="Параметри")
    user_id = fields.Many2one("res.users", string="Користувач", default=lambda self: self.env.user)
    start_ts = fields.Datetime(string="Початок", default=fields.Datetime.now)
    stop_ts = fields.Datetime(string="Завершення")
    state = fields.Selection(
        [
            ("queued", "У черзі"),
            ("running", "Виконується"),
            ("stopping", "Зупиняється"),
            ("done", "Завершено"),
            ("failed", "Невдало"),
            ("stopped", "Зупинено"),
        ],
        string="Стан",
        default="queued",
        tracking=True,
    )
    sim_run_id = fields.Char(string="Id запуску в сервісі")
    message = fields.Text(string="Результат")
    event_ids = fields.One2many("td.sim.event", "run_id", string="Події")
    duration_s = fields.Integer(string="Тривалість, с", compute="_compute_duration")

    @api.depends("start_ts", "stop_ts")
    def _compute_duration(self):
        for rec in self:
            rec.duration_s = int((rec.stop_ts - rec.start_ts).total_seconds()) if rec.stop_ts and rec.start_ts else 0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == "/":
                vals["name"] = self.env["ir.sequence"].sudo().next_by_code("td.sim.run") or "/"
        return super().create(vals_list)

    @api.model
    def _validate_params(self, schema, params):
        return validate_params(schema, params)

    @api.model
    def _check_device(self, schema, params):
        """Параметр device має вказувати на наявний пристрій емулятора (S-02/S-04/S-09/S-10)."""
        code = params.get("device")
        if (
            code
            and "device" in ((schema or {}).get("properties") or {})
            and not self.env["td.sim.device"].sudo().search_count([("code", "=", code)])
        ):
            raise ValidationError("Невідомий пристрій «%s»: такого коду немає в каталозі емулятора" % code)

    @api.model
    def _create_and_start(self, scenario, params):
        params = params or {}
        self._sim_require_write()
        self._validate_params(scenario.params_schema, params)
        self._check_device(scenario.params_schema, params)
        run = self.create({"scenario_id": scenario.id, "params": params})
        try:
            data = run.with_context(f3d_sim_run_id=run.id)._sim_post(
                "/scenario/%s/start" % scenario.code, json={"run_ref": run.name, "params": params}
            )
        except UserError as exc:
            run.write({"state": "failed", "message": str(exc.args[0]), "stop_ts": fields.Datetime.now()})
            return run
        run.write({"sim_run_id": (data or {}).get("id"), "state": "running"})
        return run

    def action_stop(self):
        for run in self:
            run._sim_require_write()
            body = {"run_id": run.sim_run_id} if run.sim_run_id else {}
            data = run.with_context(f3d_sim_run_id=run.id)._sim_post(
                "/scenario/%s/stop" % run.scenario_id.code, json=body
            )
            if (data or {}).get("state") == "stopped":
                run.write({"state": "stopped", "stop_ts": fields.Datetime.now()})
            else:
                run.state = "stopping"
