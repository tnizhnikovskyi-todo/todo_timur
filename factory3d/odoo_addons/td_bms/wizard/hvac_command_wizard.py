from odoo import api, fields, models
from odoo.exceptions import ValidationError

from ..tools import hvac
from . import command_common as common

MODES = ("VE", "VEL", "AQ", "REC", "EA", "SA", "ST", "Off")
FIELDS = {"mode": "mode_signal_id", "setpoint_day": "sp_day_signal_id", "setpoint_night": "sp_night_signal_id"}


class F3dBmsHvacCommandWizard(models.TransientModel):
    """M-09b: режим або уставка дахових установок і AHU-1 (FR-18, R-25)."""

    _name = "td.bms.hvac.command.wizard"
    _description = "Будівля: команда установкам"

    unit_ids = fields.Many2many(
        "td.bms.hvac.unit", string="Установки", required=True, domain="[('kind', 'in', ('roofvent', 'ahu'))]"
    )
    action = fields.Selection(
        [("mode", "Режим"), ("setpoint_day", "Уставка день"), ("setpoint_night", "Уставка ніч")],
        string="Дія",
        required=True,
        default="mode",
    )
    mode = fields.Selection([(m, "%s — %s" % (m, hvac.MODE_LABELS[m])) for m in MODES], string="Режим")
    value_c = fields.Float(string="Уставка, °C", digits=(4, 1))
    expires_min = fields.Integer(string="Дійсна, хв", default=10)
    note = fields.Char(string="Примітка", size=256)

    @api.model
    def _f3d_bms_check_operator(self):
        common.check_operator(self.env)

    def _validate(self):
        self.ensure_one()
        if self.action == "mode" and self.mode not in MODES:
            raise ValidationError("Оберіть режим.")
        if self.action != "mode" and not 5.0 <= self.value_c <= 30.0:
            raise ValidationError("Уставка має бути в межах 5,0…30,0 °C.")
        if not 1 <= self.expires_min <= 60:
            raise ValidationError("Строк дії команди — 1…60 хв.")

    def action_apply(self):
        self.ensure_one()
        self._f3d_bms_check_operator()
        common.check_switches(self.env)
        field = FIELDS[self.action]
        units = self.unit_ids.sudo()
        if any(u.kind not in ("roofvent", "ahu") for u in units):
            raise ValidationError("Керування вентиляторами EF не передбачено (ARCH §1.4).")
        common.check_signals([(u.code, u[field]) for u in units])
        self._validate()
        if self.action == "mode":
            value, text, label = False, self.mode, "режим %s" % self.mode
        else:
            value, text = self.value_c, False
            label = "%s %.1f °C" % (dict(self._fields["action"].selection)[self.action].lower(), self.value_c)
        return common.send(self.env, [(u, u[field], value, text) for u in units], self.expires_min, self.note, label)
