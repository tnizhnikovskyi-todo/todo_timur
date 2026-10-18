from odoo import models


class MrpWorkcenter(models.Model):
    _name = 'mrp.workcenter'
    _inherit = ['mrp.workcenter', 'td.scene.mixin']

    _f3d_kind = 'workcenter'
    _rec_names_search = ['name', 'code', 'td_code']
