from odoo import fields, models


class F3dZone(models.Model):
    """M-15: освітлення й вентиляція зони (вкладка «Будівля»)."""

    _inherit = "td.zone"

    td_light_group_ids = fields.One2many("td.bms.light.group", "zone_id", string="Освітлення")
    td_hvac_unit_ids = fields.One2many("td.bms.hvac.unit", "zone_id", string="Вентиляція")
