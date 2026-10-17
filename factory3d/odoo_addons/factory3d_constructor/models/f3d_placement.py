import math
import re
from uuid import uuid4

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..services import geometry as geo

CODE_RE = re.compile(r'^[A-Z0-9]+(-[A-Z0-9]+)*$')


class F3dPlacement(models.Model):
    _name = 'f3d.placement'
    _description = "Розміщення обладнання"
    _inherit = ['f3d.draft.mixin']
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

    # --- геометрія (R-02) -------------------------------------------------------------------------------
    def _f3d_obb(self):
        self.ensure_one()
        return geo.placement_obb(self.variant_id._f3d_local_geometry(), self.x_m, self.y_m, self.rotation)

    def _f3d_service_obb(self):
        self.ensure_one()
        return geo.service_obb(self.variant_id._f3d_local_geometry(), self.x_m, self.y_m, self.rotation)

    # --- R-22 / R-11 -----------------------------------------------------------------------------------
    def _f3d_normalize_vals(self, vals):
        if 'rotation' in vals and isinstance(vals['rotation'], (int, float)) and not isinstance(vals['rotation'], bool):
            vals['rotation'] = float(vals['rotation']) % 360.0
        if 'cell_code' in vals and not vals['cell_code']:
            vals['cell_code'] = False
        return vals

    @api.model
    def _f3d_check_create(self, vals_list):
        layers = self.env['f3d.layer'].browse([v['layer_id'] for v in vals_list if v.get('layer_id')])
        self._f3d_assert_layers(layers)

    def _f3d_check_write(self, vals):
        layers = self.mapped('layer_id')
        if vals.get('layer_id'):
            layers |= self.env['f3d.layer'].browse(vals['layer_id'])
        self._f3d_assert_layers(layers)

    def _f3d_check_unlink(self):
        self._f3d_assert_layers(self.mapped('layer_id'))

    # --- constraints -----------------------------------------------------------------------------------
    @api.constrains('code')
    def _check_code(self):
        for rec in self:
            if not CODE_RE.match(rec.code or '') or len(rec.code) > 32:
                raise ValidationError(
                    "Код розміщення «%s»: великі латинські літери, цифри й дефіси між групами (до 32 символів)." % rec.code)

    @api.constrains('variant_id')
    def _check_variant(self):
        for rec in self:
            if rec.variant_id.length_mm <= 0 or rec.variant_id.width_mm <= 0:
                raise ValidationError("У варіанта «%s» не задано габарити." % rec.variant_id.display_name)

    @api.constrains('slot_id', 'layer_id', 'cell_code')
    def _check_slot(self):
        for rec in self:
            if rec.slot_id and rec.slot_id.layer_id != rec.layer_id:
                raise ValidationError("Місце «%s» належить іншому шару." % rec.slot_id.code_prefix)
            if rec.cell_code:
                if not rec.slot_id:
                    raise ValidationError("Комірку %s задано без місця." % rec.cell_code)
                if rec.cell_code not in {c['code'] for c in rec.slot_id._f3d_cells()}:
                    raise ValidationError("Комірки %s немає в місці %s." % (rec.cell_code, rec.slot_id.code_prefix))

    @api.constrains('x_m', 'y_m', 'rotation')
    def _check_position(self):
        for rec in self:
            if not all(math.isfinite(v) for v in (rec.x_m, rec.y_m, rec.rotation)):
                raise ValidationError("Координати розміщення мають бути скінченними числами.")

    def action_show_in_3d(self):
        self.ensure_one()
        if not self.equipment_id:
            raise UserError("Об'єкт ще не опубліковано в Odoo.")
        return self.equipment_id.action_f3d_show()
