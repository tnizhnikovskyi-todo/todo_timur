from odoo import models


class MrpWorkcenter(models.Model):
    _name = 'mrp.workcenter'
    _inherit = ['mrp.workcenter', 'f3d.scene.mixin']

    _f3d_kind = 'workcenter'
    _rec_names_search = ['name', 'code', 'f3d_code']
