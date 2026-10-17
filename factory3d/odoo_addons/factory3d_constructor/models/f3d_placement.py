from uuid import uuid4

from odoo import fields, models
from odoo.exceptions import UserError


class F3dPlacement(models.Model):
    _name = 'f3d.placement'
    _description = "Розміщення обладнання"
    _order = 'layer_id, code'
    _rec_name = 'code'

    uid = fields.Char(string="UID", size=32, default=lambda self: uuid4().hex, copy=False, index=True, readonly=True)
    layer_id = fields.Many2one('f3d.layer', string="Шар", required=True, ondelete='cascade', index=True)
    site_id = fields.Many2one('f3d.site', related='layer_id.site_id', store=True, index=True)
    company_id = fields.Many2one('res.company', related='site_id.company_id', store=True, index=True)
    variant_id = fields.Many2one(
        'f3d.equipment.variant', string="Варіант", required=True, ondelete='restrict', index=True)
    slot_id = fields.Many2one(
        'f3d.slot', string="Місце", ondelete='set null', help="Місце під верстат або стелаж, в який поставлено")
    cell_code = fields.Char(string="Комірка", size=32, help="Комірка стелажа місця (для перевірок fits і load)")
    code = fields.Char(
        string="Код", size=32, required=True,
        help="Майбутній f3d_code обладнання: великі латинські літери, цифри, дефіси між групами")
    name = fields.Char(string="Назва", required=True, help="Майбутня назва maintenance.equipment")
    x_m = fields.Float(string="X, м", digits=(10, 3))
    y_m = fields.Float(string="Y, м", digits=(10, 3))
    rotation = fields.Float(string="Поворот, °", digits=(6, 2), default=0.0)
    note = fields.Text(string="Примітка")
    equipment_id = fields.Many2one(
        'maintenance.equipment', string="Обладнання Odoo", readonly=True, copy=False, ondelete='set null')
    workcenter_id = fields.Many2one(
        'mrp.workcenter', string="Робочий центр", readonly=True, copy=False, ondelete='set null')
    published_at = fields.Datetime(string="Опубліковано", readonly=True, copy=False)
    active = fields.Boolean(default=True)

    _f3d_placement_uid_uniq = models.Constraint(
        'UNIQUE(site_id, uid)', "UID розміщення має бути унікальним на площадці.")
    _f3d_placement_code_uniq = models.Constraint(
        'UNIQUE(site_id, code)', "Код розміщення має бути унікальним на площадці.")

    def action_show_in_3d(self):
        self.ensure_one()
        if not self.equipment_id:
            raise UserError("Об'єкт ще не опубліковано в Odoo.")
        return self.equipment_id.action_f3d_show()
