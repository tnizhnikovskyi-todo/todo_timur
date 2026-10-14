from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError


class StockLocation(models.Model):
    _name = 'stock.location'
    _inherit = ['stock.location', 'f3d.scene.mixin']
    _f3d_kind = 'location'
    _rec_names_search = ['complete_name', 'barcode', 'f3d_code', 'f3d_alias']

    # f3d_zone_id оголошено у models/f3d_zone.py (W2)
    f3d_loc_kind = fields.Selection(
        [('stack', 'Стос плит'), ('bin', 'Комірка фурнітури'), ('shelf', 'Полиця крайки'),
         ('pallet_cell', 'Комірка палет ГП'), ('kit', 'Візок / етажерка комплекту'),
         ('area', 'Майданчик')],
        string='Вид місця', index=True,
        help="Вид місця з макета; порожньо — не з макета (групові локації, склад, східні ворота)")
    f3d_capacity = fields.Float(
        string='Місткість', digits=(12, 2), default=0,
        help="В одиницях, якими рахується заповненість: аркуші (стос), шт (комірка фурнітури), "
             "м (полиця крайки), палети (комірка ГП, PAL-*); 0 — не задано")
    f3d_side = fields.Selection(
        [('west', 'Захід (приймання)'), ('east', 'Схід (відвантаження)')], string='Сторона воріт')
    f3d_dock_no = fields.Integer(string='№ воріт')
    f3d_accepts = fields.Many2many(
        'product.category', 'f3d_dock_product_categ_rel', 'location_id', 'categ_id',
        string='Приймає категорії', help='Порожньо — без обмежень')
    f3d_x = fields.Float(string='X, м', digits=(8, 2))
    f3d_y = fields.Float(string='Y, м', digits=(8, 2))
    f3d_dock_width_m = fields.Float(string='Ширина, м', digits=(5, 2), default=3.4)
    f3d_dock_height_m = fields.Float(string='Висота, м', digits=(5, 2), default=4.5)
    f3d_dock_picking_type_ids = fields.Many2many(
        'stock.picking.type', string='Типи операцій воріт',
        compute='_compute_f3d_dock_picking_types')

    _f3d_capacity_nonneg = models.Constraint(
        'CHECK(f3d_capacity >= 0)', "Місткість місця не може бути від'ємною.")

    def _compute_f3d_dock_picking_types(self):
        PickingType = self.env['stock.picking.type'].with_context(active_test=False)
        for loc in self:
            loc.f3d_dock_picking_type_ids = (
                PickingType.search([('dock_ids', 'in', loc.id)]) if loc.id else PickingType)

    @api.constrains('f3d_kind', 'f3d_side', 'f3d_dock_no', 'usage', 'f3d_x', 'f3d_y')
    def _check_f3d_dock(self):
        get = self.env['ir.config_parameter'].sudo().get_param
        length = float(get('factory3d.base.plant_length_m', 150))
        width = float(get('factory3d.base.plant_width_m', 72))
        for loc in self:
            if loc.f3d_kind not in ('location', 'dock'):
                raise ValidationError("Місце зберігання може бути лише «Місце зберігання» або «Ворота».")
            if loc.f3d_kind != 'dock':
                if loc.f3d_side or loc.f3d_dock_no:
                    raise ValidationError("Сторона й номер воріт задаються лише для виду «Ворота».")
                continue
            if not loc.f3d_side or loc.f3d_dock_no < 1:
                raise ValidationError("Для воріт задайте сторону й номер.")
            if loc.usage != 'internal':
                raise ValidationError("Ворота мають бути внутрішньою локацією.")
            clash = self.search([
                ('f3d_kind', '=', 'dock'), ('f3d_side', '=', loc.f3d_side),
                ('f3d_dock_no', '=', loc.f3d_dock_no), ('company_id', '=', loc.company_id.id),
                ('id', '!=', loc.id)], limit=1)
            if clash:
                raise ValidationError("Ворота %s %s уже існують: %s" % (
                    loc.f3d_side, loc.f3d_dock_no, clash.display_name))
            if not (0 <= loc.f3d_x <= length and 0 <= loc.f3d_y <= width):
                raise ValidationError(
                    "Центр воріт (%s; %s) поза цехом: 0…%s м по X, 0…%s м по Y." % (
                        loc.f3d_x, loc.f3d_y, length, width))

    def f3d_register_dock(self):
        """Зареєструвати ворота в dock_ids типу приймання/відвантаження складу (R-10)."""
        ptypes = self.env['stock.picking.type']
        for loc in self.filtered(lambda loc: loc.f3d_kind == 'dock'):
            wh = loc.warehouse_id
            if not wh:
                continue
            ptype = (wh.in_type_id if loc.f3d_side == 'west' else wh.out_type_id).sudo()
            if not ptype:
                continue
            ptype.dispatch_management = True
            if loc not in ptype.dock_ids:
                ptype.dock_ids = [Command.link(loc.id)]
            ptypes |= ptype
        return ptypes

    def write(self, vals):
        res = super().write(vals)
        if vals.get('f3d_kind') == 'dock' or 'f3d_side' in vals:
            self.f3d_register_dock()
        return res
