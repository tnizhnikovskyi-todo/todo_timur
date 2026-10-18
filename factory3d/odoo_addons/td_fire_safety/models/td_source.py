from odoo import fields, models, api
from odoo.exceptions import ValidationError

READONLY_MSG = "Джерело пожежної сигналізації працює лише на читання (рішення D-07). Увімкнути запис неможливо."


class F3dSource(models.Model):
    _inherit = "f3d.source"

    f3d_fire_readonly = fields.Boolean(
        string="Пожежна сигналізація: лише читання", default=False, copy=False,
        help="Рішення D-07: запис у прилад неможливий; прапор не знімається")
    f3d_fire_consent_date = fields.Date(string="Дозвіл монтажника: дата", tracking=True)
    f3d_fire_consent_person = fields.Char(string="Дозвіл монтажника: особа, організація", size=128, tracking=True)
    f3d_fire_consent_doc = fields.Char(string="Дозвіл монтажника: документ", size=128)
    f3d_fire_consent_attachment_id = fields.Many2one(
        "ir.attachment", string="Скан дозволу", ondelete="set null")

    @api.constrains("write_enabled", "f3d_fire_readonly")
    def _check_f3d_fire_write(self):
        for rec in self:
            if rec.f3d_fire_readonly and rec.write_enabled:
                raise ValidationError(READONLY_MSG)

    @api.constrains("type", "params", "f3d_fire_readonly")
    def _check_f3d_fire_params(self):
        for rec in self:
            if rec.f3d_fire_readonly and rec.type == "bacnet_ip" and not (rec.params or {}).get("read_only"):
                raise ValidationError(
                    "Джерело %s: для пожежного приладу параметр read_only=true обов'язковий." % rec.code)

    @api.constrains("read_enabled", "f3d_fire_consent_date", "f3d_fire_consent_person")
    def _check_f3d_fire_consent(self):
        env_name = self.env["ir.config_parameter"].sudo().get_param("factory3d.base.environment")
        if env_name != "prod":
            return
        for rec in self:
            if rec.f3d_fire_readonly and rec.read_enabled and not (
                    rec.f3d_fire_consent_date and rec.f3d_fire_consent_person):
                raise ValidationError(
                    "Увімкнути читання приладу на проді можна лише з дозволом монтажника: заповніть дату й особу "
                    "(вкладка «Пожежна сигналізація»).")

    def write(self, vals):
        if "f3d_fire_readonly" in vals and not vals["f3d_fire_readonly"] and any(self.mapped("f3d_fire_readonly")):
            raise ValidationError(READONLY_MSG)
        return super().write(vals)
