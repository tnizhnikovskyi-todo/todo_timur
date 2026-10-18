"""M-03 `td.energy.point` — точка обліку ресурсу (FR-03): ввід / гілка / споживач, метод оцінки (A-05)."""

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

ESTIMATE_METHODS = [
    ("none", "Без оцінки"),
    ("load_share", "Частка навантаження вузла"),
    ("schedule", "За розкладом"),
    ("residual", "Залишок"),
    ("gate_loss", "Втрати через ворота"),
]


class TdEnergyPoint(models.Model):
    _name = "td.energy.point"
    _description = "Енергетика: точка обліку ресурсу"
    _inherit = ["mail.thread"]
    _order = "resource_id, sequence, code"
    _parent_name = "parent_id"

    resource_id = fields.Many2one("td.energy.resource", string="Ресурс", required=True, index=True, ondelete="restrict")
    code = fields.Char(string="Код", size=32, required=True, index=True, copy=False)
    name = fields.Char(string="Назва", size=128, required=True)
    kind = fields.Selection(
        [("source", "Ввід (головний облік)"), ("branch", "Гілка"), ("consumer", "Споживач")],
        string="Вид",
        required=True,
        default="consumer",
    )
    parent_id = fields.Many2one("td.energy.point", string="Батько", ondelete="restrict")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    node_id = fields.Many2one(
        "td.energy.node", string="Електричний вузол споживача", ondelete="set null",
        help="Для оцінки `load_share` і зіставлення з обладнанням.",
    )  # fmt: skip
    cost_node_id = fields.Many2one(
        "td.energy.node", string="Вузол, чия електрика формує вартість", ondelete="set null",
        help="Повітря: COMPRESSOR (R-02 п. 4).",
    )  # fmt: skip
    equipment_id = fields.Many2one("maintenance.equipment", string="Обладнання", ondelete="set null")
    workcenter_id = fields.Many2one(related="node_id.workcenter_id", string="Робочий центр", store=False)
    rate_nominal = fields.Float(
        string="Паспортна швидкість при роботі", digits=(10, 3),
        help="Повітря: м³/хв; газ: м³/год. ПРИПУЩЕННЯ до появи паспортів (Q-02).",
    )  # fmt: skip
    min_pressure_bar = fields.Float(string="Мінімальний тиск споживача, бар", digits=(5, 2))
    hvac_ref = fields.Char(string="Код установки BMS", size=32)
    state_signal_id = fields.Many2one("td.signal", string="Сигнал стану / відкриття", ondelete="set null")
    meter_ids = fields.One2many("td.energy.meter", "point_id", string="Лічильники")
    estimate_method = fields.Selection(ESTIMATE_METHODS, string="Метод оцінки", required=True, default="none")
    estimate_params = fields.Json(string="Параметри оцінки", default=dict)
    company_id = fields.Many2one("res.company", string="Компанія", required=True, default=lambda self: self.env.company)

    _td_energy_point_code_uniq = models.Constraint(
        "UNIQUE(resource_id, company_id, code)", "Код точки має бути унікальним у межах ресурсу."
    )

    # --- перевірки ------------------------------------------------------------------------------------
    @api.constrains("parent_id", "resource_id")
    def _check_parent(self):
        if self._has_cycle():
            raise ValidationError(_("Не можна створювати циклічні зв'язки батько — дочірня точка."))
        for rec in self:
            if rec.parent_id and rec.parent_id.resource_id != rec.resource_id:
                raise ValidationError(_("Батько має бути з того самого ресурсу."))

    @api.constrains("estimate_method", "estimate_params", "node_id", "rate_nominal", "state_signal_id")
    def _check_estimate(self):
        for rec in self:
            method, params = rec.estimate_method, rec.estimate_params or {}
            if method == "load_share":
                if not rec.node_id or rec.rate_nominal <= 0:
                    raise ValidationError(
                        _("Точка %s: для оцінки за навантаженням потрібні вузол і паспортна швидкість.", rec.code)
                    )
            elif method == "schedule":
                missing = [k for k in ("from_h", "to_h", "rate") if k not in params]
                if missing:
                    raise ValidationError(
                        _("Точка %s: для оцінки за розкладом потрібні параметри from_h, to_h, rate.", rec.code)
                    )
            elif method == "residual":
                sources = params.get("from")
                if not sources or not isinstance(sources, list) or rec.code in sources:
                    raise ValidationError(
                        _("Точка %s: для оцінки за залишком потрібен непорожній список «from» (без себе).", rec.code)
                    )
            elif method == "gate_loss":
                if not rec.state_signal_id or "loss_kw_per_k" not in params:
                    raise ValidationError(
                        _("Точка %s: для втрат через ворота потрібні сигнал стану й параметр loss_kw_per_k.", rec.code)
                    )

    @api.onchange("node_id")
    def _onchange_node_id(self):
        if self.node_id and self.node_id.equipment_id and not self.equipment_id:
            self.equipment_id = self.node_id.equipment_id

    # --- хуки -----------------------------------------------------------------------------------------
    @api.model
    def _td_bind_extra(self):
        """Хук (R-B1): після `_seed_points_meters` викликається `post_init_hook` і дія V-11. У ядрі — порожній; міст
        `td_energy_resources_bms` створює теплові точки й лічильники з `td_bms`."""
        return {}
