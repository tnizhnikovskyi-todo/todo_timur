from odoo import fields, models


class MrpWorkcenter(models.Model):
    _inherit = 'mrp.workcenter'

    td_site_id = fields.Many2one(
        'td.site', string="Площадка конструктора", index=True, copy=False, readonly=True, ondelete='set null'
    )
