from odoo import fields, models


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    f3d_site_id = fields.Many2one(
        'f3d.site', string="Площадка конструктора", index=True, copy=False, readonly=True, ondelete='set null'
    )
    f3d_placement_uid = fields.Char(string="UID розміщення", size=32, copy=False, readonly=True)
