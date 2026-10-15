import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class F3dGantryJob(models.Model):
    _name = "f3d.gantry.job"
    _description = "Портал: завдання"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char(
        string="Номер",
        required=True,
        copy=False,
        default=lambda s: s.env["ir.sequence"].next_by_code("f3d.gantry.job"),
    )
    ws_id = fields.Char(string="Номер у woodStore", size=32, index=True, copy=False)
    type = fields.Selection(
        [
            ("feed", "Подача на верстат"),
            ("restack", "Перекладання"),
            ("return", "Повернення в стос"),
            ("count", "Перерахунок"),
        ],
        required=True,
        default="feed",
    )
    origin = fields.Selection(
        [("odoo", "Odoo"), ("machine", "Портал")], required=True, default="odoo", string="Створено в"
    )
    stack_id = fields.Many2one("f3d.gantry.stack", string="Стос", ondelete="set null")
    target_workcenter_id = fields.Many2one(
        "mrp.workcenter",
        string="На верстат",
        ondelete="set null",
        domain="[('f3d_code', 'in', ('SAW-1', 'SAW-2', 'SAW-3', 'NEST-1'))]",
    )
    target_code = fields.Char(related="target_workcenter_id.f3d_code")
    sheets = fields.Integer(string="Листів", required=True, default=1)
    done = fields.Integer(string="Подано", default=0, tracking=True)
    product_id = fields.Many2one("product.product", string="Плита")
    lot_id = fields.Many2one("stock.lot", string="Партія")
    priority = fields.Integer(string="Пріоритет", default=5, help="1…9")
    external_ref = fields.Char(string="Документ", size=64, help="Назва МО")
    production_id = fields.Many2one("mrp.production", ondelete="set null", index=True)
    workorder_id = fields.Many2one("mrp.workorder", ondelete="set null")
    cut_map_id = fields.Many2one("f3d.cut.map", ondelete="set null")
    state = fields.Selection(
        [
            ("draft", "Чернетка"),
            ("to_send", "До відправки"),
            ("sent", "Надіслано"),
            ("queued", "У черзі порталу"),
            ("active", "Виконується"),
            ("done", "Виконано"),
            ("cancelled", "Скасовано"),
            ("error", "Помилка"),
        ],
        required=True,
        index=True,
        default="draft",
        tracking=True,
    )
    command_id = fields.Many2one("f3d.command", string="Команда", ondelete="set null")
    cancel_command_id = fields.Many2one("f3d.command", ondelete="set null")
    error = fields.Char(size=512, readonly=True)
    ws_created = fields.Datetime(readonly=True)
    started = fields.Datetime(readonly=True)
    finished = fields.Datetime(readonly=True)
    sheet_log = fields.Json(string="Листи", default=lambda s: [], help="[{ts, stack, lot}], ≤ 200")
    consumed_qty = fields.Float(string="Списано в МО", readonly=True)
    company_id = fields.Many2one("res.company", required=True, default=lambda s: s.env.company)

    _f3d_gjob_ws_uniq = models.Constraint("UNIQUE(ws_id)", "Завдання woodStore вже прив'язане.")
    _f3d_gjob_numbers = models.Constraint(
        "CHECK(sheets >= 1 AND done >= 0 AND priority BETWEEN 1 AND 9)",
        "Листів ≥ 1, подано ≥ 0, пріоритет 1…9.",
    )

    @api.constrains("type", "product_id", "target_workcenter_id", "state")
    def _check_feed(self):
        targets = self.env["f3d.gantry.stack"].GANTRY_TARGETS
        for rec in self:
            if rec.type != "feed" or rec.state in ("draft", "cancelled"):
                continue
            if not rec.product_id or not rec.target_workcenter_id:
                raise ValidationError(_("Для подачі задайте плиту і верстат."))
            if rec.target_code not in targets:
                raise ValidationError(_("Портал подає лише на SAW-1, SAW-2, SAW-3, NEST-1."))

    @api.model
    def _cron_gantry(self):
        """R-15, R-16, R-18 (W5). Каркас: нічого не робить."""
        return True
