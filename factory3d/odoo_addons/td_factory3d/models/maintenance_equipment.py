from odoo import fields, models


class MaintenanceEquipment(models.Model):
    _name = 'maintenance.equipment'
    _inherit = ['maintenance.equipment', 'td.scene.mixin']

    _td_kind = 'equipment'
    _rec_names_search = ['name', 'serial_no', 'td_code']

    # td_zone_id оголошено в models/td_zone.py
    td_passport_id = fields.Many2one(
        'td.equipment.passport', string="Паспорт", ondelete='set null', index=True)
    td_component_passport_ids = fields.Many2many(
        'td.equipment.passport', relation='td_equipment_component_passport_rel',
        column1='equipment_id', column2='passport_id', string="У складі")
    td_role = fields.Char(related='td_passport_id.role', readonly=True)
    td_manufacturer = fields.Char(related='td_passport_id.manufacturer', readonly=True)
    td_model = fields.Char(related='td_passport_id.model', readonly=True)
    td_reason = fields.Text(related='td_passport_id.reason', readonly=True)
    td_power_kw = fields.Float(related='td_passport_id.power_kw', readonly=True)
    td_connected_kw = fields.Float(related='td_passport_id.connected_kw', readonly=True)
    td_dimensions = fields.Char(related='td_passport_id.dimensions', readonly=True)
    td_spec_ids = fields.One2many(related='td_passport_id.spec_ids', readonly=True)
    td_source_ids = fields.One2many(related='td_passport_id.source_ids', readonly=True)
    td_units = fields.Integer(
        related='td_passport_id.unit_count', string="Одиниць під паспортом", readonly=True)

    def f3d_get_num(self, key):
        self.ensure_one()
        return self.td_passport_id.get_num(key) if self.td_passport_id else None
