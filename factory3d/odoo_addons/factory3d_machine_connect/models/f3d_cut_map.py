import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from .f3d_cut_part import GRAINS, MATERIAL_ROLES
from .f3d_machine import param

_logger = logging.getLogger(__name__)


class F3dCutMap(models.Model):
    _name = "f3d.cut.map"
    _description = "Розкрій: карта розкрою"
    _inherit = ["mail.thread"]
    _order = "id desc"

    name = fields.Char(
        string="Номер",
        required=True,
        copy=False,
        default=lambda s: s.env["ir.sequence"].next_by_code("f3d.cut.map"),
    )
    production_id = fields.Many2one(
        "mrp.production", string="Виробниче замовлення", required=True, index=True, ondelete="restrict"
    )
    product_id = fields.Many2one("product.product", related="production_id.product_id")
    workorder_id = fields.Many2one(
        "mrp.workorder",
        string="Завдання розкрою",
        ondelete="set null",
        domain="[('production_id', '=', production_id)]",
    )
    workcenter_id = fields.Many2one("mrp.workcenter", related="workorder_id.workcenter_id", store=True)
    machine_code = fields.Char(related="workcenter_id.f3d_code")
    material_role = fields.Selection(MATERIAL_ROLES, required=True, default="main")
    material_product_id = fields.Many2one(
        "product.product", string="Плита", required=True, domain="[('f3d_sheet_length_mm', '>', 0)]"
    )
    sheet_length_mm = fields.Integer(string="Лист: довжина, мм")
    sheet_width_mm = fields.Integer(string="Лист: ширина, мм")
    thickness_mm = fields.Integer(string="Лист: товщина, мм")
    qty = fields.Float(string="Виробів", required=True, digits=(12, 2))
    line_ids = fields.One2many("f3d.cut.map.line", "map_id", string="Деталі")
    parts_count = fields.Integer(compute="_compute_parts", store=True, string="Деталей")
    mode = fields.Selection(
        [("collector", "Через колектор"), ("manual", "Вручну")],
        required=True,
        default=lambda s: param(s.env, "cutting_mode", "manual"),
    )
    state = fields.Selection(
        [
            ("draft", "Чернетка"),
            ("exported", "Експортовано"),
            ("optimizing", "Оптимізується"),
            ("planned", "Сплановано"),
            ("released", "Випущено"),
            ("running", "Ріжеться"),
            ("done", "Виконано"),
            ("error", "Помилка"),
            ("cancel", "Скасовано"),
        ],
        required=True,
        index=True,
        default="draft",
        tracking=True,
    )
    ext_job_id = fields.Char(string="Номер в оптимізаторі", size=32, index=True, copy=False)
    job_order_id = fields.Char(string="JobOrder верстата", size=64, copy=False)
    plan_sheets = fields.Integer(string="Аркушів за планом", tracking=True)
    plan_waste_pct = fields.Float(string="Відхід, %", digits=(5, 1))
    plan_cut_length_m = fields.Float(string="Довжина різу, м", digits=(10, 1))
    plan_est_min = fields.Float(string="Оцінка часу, хв", digits=(8, 1))
    plan_json = fields.Json(string="План", copy=False)
    sheets_need = fields.Float(compute="_compute_need", string="Потреба МО, арк.")
    sheets_warning = fields.Char(compute="_compute_need")
    csv_attachment_id = fields.Many2one("ir.attachment", string="Список деталей (CSV)", ondelete="set null", copy=False)
    plan_attachment_id = fields.Many2one("ir.attachment", string="План (JSON)", ondelete="set null", copy=False)
    mpr_attachment_ids = fields.Many2many(
        "ir.attachment",
        relation="f3d_cut_map_mpr_rel",
        column1="map_id",
        column2="attachment_id",
        copy=False,
        string="Програми ЧПК",
    )
    export_token_hash = fields.Char(size=64, copy=False, groups="factory3d_base.group_f3d_admin")
    export_token_expires = fields.Datetime(copy=False, groups="factory3d_base.group_f3d_admin")
    command_ids = fields.One2many("f3d.command", "f3d_cut_map_id", string="Команди")
    gantry_job_id = fields.Many2one("f3d.gantry.job", ondelete="set null", copy=False)
    error = fields.Char(size=512, readonly=True)
    released_at = fields.Datetime(readonly=True)
    done_at = fields.Datetime(readonly=True)
    company_id = fields.Many2one("res.company", related="production_id.company_id", store=True)

    @api.depends("line_ids.qty")
    def _compute_parts(self):
        for rec in self:
            rec.parts_count = int(sum(rec.line_ids.mapped("qty")))

    @api.depends("material_product_id", "production_id.move_raw_ids.product_uom_qty", "plan_sheets")
    def _compute_need(self):
        for rec in self:
            product = rec.material_product_id
            moves = rec.production_id.move_raw_ids.filtered(
                lambda m, product=product: m.product_id == product and m.state not in ("done", "cancel")
            )
            need = sum(moves.mapped("product_uom_qty"))
            rec.sheets_need = need
            rec.sheets_warning = (
                _("За планом %d арк., у МО %g — оновіть потребу або візьміть із запасу.", rec.plan_sheets, need)
                if rec.plan_sheets > need
                else False
            )

    @api.constrains("sheet_length_mm", "sheet_width_mm", "thickness_mm", "material_product_id")
    def _check_sheet(self):
        for rec in self:
            if min(rec.sheet_length_mm, rec.sheet_width_mm, rec.thickness_mm) <= 0:
                raise ValidationError(_("Задайте розміри листа плити %s.", rec.material_product_id.display_name))

    @api.model
    def _cron_cutmap(self):
        """R-20 п. 6 (W6). Каркас: нічого не робить."""
        return True


class F3dCutMapLine(models.Model):
    _name = "f3d.cut.map.line"
    _description = "Розкрій: деталь у карті"
    _order = "map_id, sequence, id"

    map_id = fields.Many2one("f3d.cut.map", required=True, index=True, ondelete="cascade")
    sequence = fields.Integer(default=10)
    part_id = fields.Many2one("f3d.cut.part", ondelete="set null")
    part_code = fields.Char(size=16, required=True)
    name = fields.Char(size=64, required=True)
    length_mm = fields.Integer(required=True)
    width_mm = fields.Integer(required=True)
    qty = fields.Integer(required=True, default=1)
    grain = fields.Selection(GRAINS, default="0")
    edge_top = fields.Char(size=32)
    edge_bottom = fields.Char(size=32)
    edge_left = fields.Char(size=32)
    edge_right = fields.Char(size=32)
    program = fields.Char(size=64)
    mpr_attachment_id = fields.Many2one("ir.attachment", ondelete="set null")

    _f3d_line_numbers = models.Constraint(
        "CHECK(qty >= 1 AND length_mm > 0 AND width_mm > 0)", "Кількість ≥ 1, розміри > 0."
    )
