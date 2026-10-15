from odoo import fields, models


class F3dZone(models.Model):
    """M-15: освітлення й вентиляція зони (вкладка «Будівля»)."""

    _inherit = "f3d.zone"

    f3d_light_group_ids = fields.One2many("f3d.bms.light.group", "zone_id", string="Освітлення")
    f3d_hvac_unit_ids = fields.One2many("f3d.bms.hvac.unit", "zone_id", string="Вентиляція")
