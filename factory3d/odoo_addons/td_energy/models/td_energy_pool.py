import re

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{0,31}$")


class F3dEnergyPool(models.Model):
    _name = "td.energy.pool"
    _description = "Енергетика: пул спільних споживачів"
    _inherit = ["mail.thread"]
    _order = "sequence, code"

    code = fields.Char(string="Код", size=32, required=True, copy=False)
    name = fields.Char(string="Назва", size=128, required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    node_ids = fields.One2many("td.energy.node", "pool_id", string="Споживачі пулу")
    driver = fields.Selection(
        [("kwh", "Пропорційно прямим кВт·год"), ("time", "Пропорційно машинному часу")],
        required=True,
        default="kwh",
        tracking=True,
    )
    workcenter_ids = fields.Many2many(
        "mrp.workcenter",
        "td_energy_pool_workcenter_rel",
        "pool_id",
        "workcenter_id",
        string="Обслуговує робочі центри",
        help="Порожньо — усі робочі центри з прямим лічильником",
    )
    note = fields.Text(string="Примітка")
    kwh_today = fields.Float(string="Сьогодні, кВт·год", compute="_compute_kwh_today")

    _f3d_energy_pool_code_uniq = models.Constraint("UNIQUE(code)", "Код пулу має бути унікальним.")

    @api.constrains("code")
    def _check_code(self):
        for rec in self:
            if not rec.code or not CODE_RE.match(rec.code):
                raise ValidationError(
                    _("Код пулу %s: великі латинські літери, цифри, дефіс (напр. POOL-AIR).", rec.code)
                )

    @api.depends("node_ids")
    def _compute_kwh_today(self):
        for rec in self:
            rec.kwh_today = sum(rec.node_ids.mapped("kwh_today"))
