from odoo import Command, api, fields, models
from odoo.exceptions import ValidationError


class StockLocation(models.Model):
    _name = "stock.location"
    _inherit = ["stock.location", "td.scene.mixin"]
    _td_kind = "location"
    _rec_names_search = ["complete_name", "barcode", "td_code", "td_alias"]

    # td_zone_id оголошено у models/td_zone.py (W2)
    td_loc_kind = fields.Selection(
        [
            ("stack", "Стос плит"),
            ("bin", "Комірка фурнітури"),
            ("shelf", "Полиця крайки"),
            ("pallet_cell", "Комірка палет ГП"),
            ("kit", "Візок / етажерка комплекту"),
            ("area", "Майданчик"),
        ],
        string="Вид місця",
        index=True,
        help="Вид місця з макета; порожньо — не з макета (групові локації, склад, східні ворота)",
    )
    td_capacity = fields.Float(
        string="Місткість",
        digits=(12, 2),
        default=0,
        help="В одиницях, якими рахується заповненість: аркуші (стос), шт (комірка фурнітури), "
        "м (полиця крайки), палети (комірка ГП, PAL-*); 0 — не задано",
    )
    td_side = fields.Selection(
        [("west", "Захід (приймання)"), ("east", "Схід (відвантаження)")], string="Сторона воріт"
    )
    td_dock_no = fields.Integer(string="№ воріт")
    td_accepts = fields.Many2many(
        "product.category",
        "td_dock_product_categ_rel",
        "location_id",
        "categ_id",
        string="Приймає категорії",
        help="Порожньо — без обмежень",
    )
    td_x = fields.Float(string="X, м", digits=(8, 2))
    td_y = fields.Float(string="Y, м", digits=(8, 2))
    td_dock_width_m = fields.Float(string="Ширина, м", digits=(5, 2), default=3.4)
    td_dock_height_m = fields.Float(string="Висота, м", digits=(5, 2), default=4.5)
    td_dock_picking_type_ids = fields.Many2many(
        "stock.picking.type", string="Типи операцій воріт", compute="_compute_f3d_dock_picking_types"
    )

    _f3d_capacity_nonneg = models.Constraint("CHECK(td_capacity >= 0)", "Місткість місця не може бути від'ємною.")

    def _compute_f3d_dock_picking_types(self):
        PickingType = self.env["stock.picking.type"].with_context(active_test=False)
        for loc in self:
            loc.td_dock_picking_type_ids = PickingType.search([("dock_ids", "in", loc.id)]) if loc.id else PickingType

    @api.constrains("td_kind", "td_side", "td_dock_no", "usage", "td_x", "td_y")
    def _check_f3d_dock(self):
        get = self.env["ir.config_parameter"].sudo().get_param
        length = float(get("td.base.plant_length_m", 150))
        width = float(get("td.base.plant_width_m", 72))
        for loc in self:
            if loc.td_kind not in ("location", "dock"):
                raise ValidationError("Місце зберігання може бути лише «Місце зберігання» або «Ворота».")
            if loc.td_kind != "dock":
                if loc.td_side or loc.td_dock_no:
                    raise ValidationError("Сторона й номер воріт задаються лише для виду «Ворота».")
                continue
            if not loc.td_side or loc.td_dock_no < 1:
                raise ValidationError("Для воріт задайте сторону й номер.")
            if loc.usage != "internal":
                raise ValidationError("Ворота мають бути внутрішньою локацією.")
            clash = self.search(
                [
                    ("td_kind", "=", "dock"),
                    ("td_side", "=", loc.td_side),
                    ("td_dock_no", "=", loc.td_dock_no),
                    ("company_id", "=", loc.company_id.id),
                    ("id", "!=", loc.id),
                ],
                limit=1,
            )
            if clash:
                raise ValidationError(
                    "Ворота %s %s уже існують: %s" % (loc.td_side, loc.td_dock_no, clash.display_name)
                )
            if not (0 <= loc.td_x <= length and 0 <= loc.td_y <= width):
                raise ValidationError(
                    "Центр воріт (%s; %s) поза цехом: 0…%s м по X, 0…%s м по Y." % (loc.td_x, loc.td_y, length, width)
                )

    def f3d_register_dock(self):
        """Зареєструвати ворота в dock_ids типу приймання/відвантаження складу (R-10)."""
        ptypes = self.env["stock.picking.type"]
        for loc in self.filtered(lambda loc: loc.td_kind == "dock"):
            wh = loc.warehouse_id
            if not wh:
                continue
            ptype = (wh.in_type_id if loc.td_side == "west" else wh.out_type_id).sudo()
            if not ptype:
                continue
            ptype.dispatch_management = True
            if loc not in ptype.dock_ids:
                ptype.dock_ids = [Command.link(loc.id)]
            ptypes |= ptype
        return ptypes

    def write(self, vals):
        res = super().write(vals)
        if vals.get("td_kind") == "dock" or "td_side" in vals:
            self.f3d_register_dock()
        return res
