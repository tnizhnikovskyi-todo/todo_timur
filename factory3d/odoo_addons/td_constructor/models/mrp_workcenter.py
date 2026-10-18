from odoo import fields, models


class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

    f3d_site_id = fields.Many2one(
        'f3d.site', string="Площадка конструктора", index=True, copy=False, readonly=True, ondelete='set null'
    )
