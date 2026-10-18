from odoo import fields, models


class MaintenanceEquipment(models.Model):
    _name = 'maintenance.equipment'
    _inherit = ['maintenance.equipment', 'f3d.scene.mixin']

    _f3d_kind = 'equipment'
    _rec_names_search = ['name', 'serial_no', 'f3d_code']

    # f3d_zone_id оголошено в models/f3d_zone.py
    f3d_passport_id = fields.Many2one(
        'f3d.equipment.passport', string="Паспорт", ondelete='set null', index=True)
    f3d_component_passport_ids = fields.Many2many(
        'f3d.equipment.passport', relation='f3d_equipment_component_passport_rel',
        column1='equipment_id', column2='passport_id', string="У складі")
    f3d_role = fields.Char(related='f3d_passport_id.role', readonly=True)
    f3d_manufacturer = fields.Char(related='f3d_passport_id.manufacturer', readonly=True)
    f3d_model = fields.Char(related='f3d_passport_id.model', readonly=True)
    f3d_reason = fields.Text(related='f3d_passport_id.reason', readonly=True)
    f3d_power_kw = fields.Float(related='f3d_passport_id.power_kw', readonly=True)
    f3d_connected_kw = fields.Float(related='f3d_passport_id.connected_kw', readonly=True)
    f3d_dimensions = fields.Char(related='f3d_passport_id.dimensions', readonly=True)
    f3d_spec_ids = fields.One2many(related='f3d_passport_id.spec_ids', readonly=True)
    f3d_source_ids = fields.One2many(related='f3d_passport_id.source_ids', readonly=True)
    f3d_units = fields.Integer(
        related='f3d_passport_id.unit_count', string="Одиниць під паспортом", readonly=True)

    def f3d_get_num(self, key):
        self.ensure_one()
        return self.f3d_passport_id.get_num(key) if self.f3d_passport_id else None
