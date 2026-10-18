import re

from odoo import api, fields, models, tools
from odoo.exceptions import ValidationError

KEY_RE = re.compile(r"^[A-Za-z0-9_]+$")  # у макеті є ключ evac_distance_prod_B


class F3dFireNorm(models.Model):
    _name = "f3d.fire.norm"
    _description = "Пожежна безпека: норма"
    _order = "group, sequence, key"
    _rec_name = "name"

    key = fields.Char(string="Ключ", size=48, required=True, index=True)
    name = fields.Char(string="Назва", size=128, required=True)
    group = fields.Selection(
        [("detection", "Виявлення"), ("alerting", "Оповіщення"), ("evacuation", "Евакуація"),
         ("smoke", "Димовидалення"), ("other", "Інше")], required=True, default="other")
    sequence = fields.Integer(default=10)
    value = fields.Float(string="Значення", digits=(12, 3))
    value_set = fields.Boolean(string="Значення задано", default=False)
    unit = fields.Char(string="Одиниця", size=64)
    ref = fields.Text(string="Норма (пункт, таблиця)", required=True)
    note = fields.Text(string="Примітка")
    sources = fields.Text(string="Джерела (URL, по одному в рядку)")
    active = fields.Boolean(default=True)

    @api.constrains("key")
    def _check_key(self):
        for rec in self:
            if not rec.key or not KEY_RE.match(rec.key):
                raise ValidationError("Ключ норми — латиниця, цифри, підкреслення")

    # --- читання ----------------------------------------------------------------------------------------
    @tools.ormcache("key")
    def _get_cached(self, key):
        rec = self.sudo().search([("key", "=", key), ("active", "=", True)], limit=1)
        return (rec.value, rec.ref) if rec and rec.value_set else (None, rec.ref if rec else "")

    @api.model
    def get(self, key, default=None):
        """Значення норми або `default`, якщо норму не задано (`value_set=False`) чи не знайдено."""
        value = self._get_cached(key)[0]
        return default if value is None else value

    @api.model
    def get_ref(self, key):
        return self._get_cached(key)[1] or ""

    # --- запис ------------------------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        self._after_change({"value"})
        return records

    def write(self, vals):
        res = super().write(vals)
        self._after_change(set(vals))
        return res

    def unlink(self):
        res = super().unlink()
        self._after_change({"value"})
        return res

    @api.model
    def _after_change(self, changed):
        self.env.registry.clear_cache()
        if changed & {"value", "value_set", "active", "key"}:
            self.env["f3d.fire.panel"]._schedule_compliance()
