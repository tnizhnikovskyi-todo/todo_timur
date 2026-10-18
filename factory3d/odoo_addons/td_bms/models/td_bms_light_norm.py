import re

from odoo import api, fields, models
from odoo.exceptions import ValidationError

KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,47}$")


class F3dBmsLightNorm(models.Model):
    _name = "td.bms.light.norm"
    _description = "Будівля: норма освітленості"
    _order = "sequence, key"
    _rec_name = "name"
    _rec_names_search = ["name", "key"]

    key = fields.Char(
        string="Ключ",
        size=48,
        required=True,
        index=True,
        help="Вид робіт з plant/lux_norms.json: woodworking_machine, spraying…",
    )
    name = fields.Char(string="Вид робіт", size=128, required=True)
    sequence = fields.Integer(default=10)
    lux = fields.Integer(string="Норма, лк", required=True)
    ugr = fields.Integer(string="UGR, не більше")
    ra = fields.Integer(string="Ra, не менше")
    ref_en = fields.Char(string="EN 12464-1", size=256)
    ref_dbn = fields.Char(
        string="ДБН В.2.5-28",
        size=256,
        default="ДБН В.2.5-28:2018 (зі Зміною № 1) — звірити розряд зорових робіт (Q-03)",
    )
    note = fields.Text(string="Примітка")
    sources = fields.Text(string="Джерела", help="URL по рядку")
    group_ids = fields.One2many("td.bms.light.group", "norm_id", string="Групи")
    group_count = fields.Integer(compute="_compute_group_count")
    active = fields.Boolean(default=True)

    _f3d_bms_norm_key_uniq = models.Constraint("UNIQUE(key)", "Ключ норми має бути унікальним.")
    _f3d_bms_norm_lux_pos = models.Constraint("CHECK(lux > 0)", "Норма освітленості має бути більшою за 0 лк.")

    @api.depends("group_ids")
    def _compute_group_count(self):
        for rec in self:
            rec.group_count = len(rec.group_ids)

    @api.constrains("key")
    def _check_key(self):
        for rec in self:
            if not rec.key or not KEY_RE.match(rec.key):
                raise ValidationError("Ключ норми: латиниця, цифри, підкреслення.")
