import logging
import re

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

ROWCOL_RE = re.compile(r"^PLT-(\d{2})([A-C])")


class F3dGantryStack(models.Model):
    _name = "f3d.gantry.stack"
    _description = "Портал: стос плит"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "code"
    _rec_name = "code"
    GANTRY_TARGETS = ("SAW-1", "SAW-2", "SAW-3", "NEST-1")  # iot_sim API-25 target

    location_id = fields.Many2one(
        "stock.location",
        string="Місце",
        required=True,
        index=True,
        ondelete="cascade",
        domain="[('f3d_loc_kind', '=', 'stack')]",
    )
    code = fields.Char(related="location_id.f3d_code", store=True, index=True, string="Стос")
    capacity = fields.Float(related="location_id.f3d_capacity", string="Місткість, арк.")
    row = fields.Integer(compute="_compute_rowcol", store=True, string="Ряд")
    col = fields.Char(compute="_compute_rowcol", store=True, size=1, string="Колонка")
    orderpoint_id = fields.Many2one("stock.warehouse.orderpoint", string="Правило поповнення", ondelete="set null")
    min_qty = fields.Float(related="orderpoint_id.product_min_qty")
    max_qty = fields.Float(related="orderpoint_id.product_max_qty")
    ws_qty = fields.Integer(string="Портал, арк.", tracking=True)
    ws_product = fields.Char(string="Товар у порталі", size=32)
    ws_product_id = fields.Many2one(
        "product.product", compute="_compute_ws_product", store=True, string="Товар у порталі (Odoo)"
    )
    ws_lot = fields.Char(string="Партія в порталі", size=64)
    ws_reserved = fields.Integer(string="Зарезервовано порталом")
    ws_locked = fields.Boolean(string="Заблоковано в порталі")
    ws_updated = fields.Datetime(string="Оновлено в порталі")
    ws_seen = fields.Datetime(string="Отримано")
    odoo_qty = fields.Float(digits=(12, 1), string="Odoo, арк.")
    odoo_product_id = fields.Many2one("product.product", string="Товар в Odoo")
    odoo_lot_id = fields.Many2one("stock.lot", string="Партія в Odoo")
    fed_unconsumed = fields.Float(digits=(12, 1), string="Подано, не списано")
    expected_qty = fields.Float(digits=(12, 1), string="Має бути в порталі")
    diff = fields.Float(digits=(12, 1), string="Розбіжність, арк.")
    state = fields.Selection(
        [("ok", "Збігається"), ("pending", "Перевіряється"), ("diff", "Розбіжність"), ("unknown", "Немає даних")],
        default="unknown",
        index=True,
        tracking=True,
    )
    diff_since = fields.Datetime()
    fill = fields.Float(compute="_compute_fill", string="Заповнення")
    job_ids = fields.One2many("f3d.gantry.job", "stack_id", string="Завдання")
    note = fields.Text()

    _f3d_stack_loc_uniq = models.Constraint("UNIQUE(location_id)", "Для місця вже є стос.")
    _f3d_stack_ws_qty = models.Constraint("CHECK(ws_qty >= 0)", "Кількість у порталі не може бути від'ємною.")

    @api.depends("code")
    def _compute_rowcol(self):
        for rec in self:
            m = ROWCOL_RE.match(rec.code or "")
            rec.row = int(m.group(1)) if m else 0
            rec.col = m.group(2) if m else False

    @api.depends("ws_product")
    def _compute_ws_product(self):
        for rec in self:
            rec.ws_product_id = (
                self.env["product.product"].search([("default_code", "=", rec.ws_product)], limit=1)
                if rec.ws_product
                else False
            )

    @api.depends("ws_qty", "capacity")
    def _compute_fill(self):
        for rec in self:
            rec.fill = rec.ws_qty / rec.capacity if rec.capacity > 0 else 0.0
