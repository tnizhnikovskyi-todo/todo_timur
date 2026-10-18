from odoo import fields, models


class MaintenanceEquipment(models.Model):
    _inherit = 'maintenance.equipment'

    td_site_id = fields.Many2one(
        'td.site', string="Площадка конструктора", index=True, copy=False, readonly=True, ondelete='set null'
    )
    td_placement_uid = fields.Char(string="UID розміщення", size=32, copy=False, readonly=True)
