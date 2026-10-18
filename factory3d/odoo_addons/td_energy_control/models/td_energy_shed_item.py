"""M-30 `td.energy.shed.item` — приоритет скидання навантаження (порядок = пріоритет)."""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from .. import tools
from ..tools import bus, kinds

ACTIONS = [("off", "Вимкнути"), ("reduce", "Знизити"), ("pause", "Пауза"), ("defer", "Відкласти")]
CONDITIONS = [
    ("none", "Без умов"),
    ("air_pressure_min", "Тиск повітря не нижче уставки"),
    ("no_active_cycle", "Без втрати циклу"),
]


class TdEnergyShedItem(models.Model):
    _name = "td.energy.shed.item"
    _description = "Енергетика: пріоритет скидання"
    _order = "sequence, id"

    sequence = fields.Integer(string="Порядок", required=True, default=10)
    name = fields.Char(string="Назва", size=96, required=True)
    node_id = fields.Many2one(
        "td.energy.node", string="Вузол", required=True, ondelete="restrict", domain="[('kind', '=', 'consumer')]"
    )
    action = fields.Selection(ACTIONS, string="Дія", required=True)
    param_value = fields.Float(string="Параметр")
    kw_reducible = fields.Float(string="Можна зняти, кВт")
    condition = fields.Selection(CONDITIONS, string="Умова", default="none", required=True)
    condition_value = fields.Float(string="Значення умови")
    how = fields.Char(string="Як", compute="_compute_how")
    signal_id = fields.Many2one(
        "td.signal", string="Сигнал ліміту", domain="[('module', '=', 'energy_control')]", ondelete="set null"
    )
    active = fields.Boolean(default=True)
    p_now_kw = fields.Float(string="Зараз, кВт", compute="_compute_p_now")
    critical = fields.Boolean(string="Критичний вузол", related="node_id.is_critical")

    # --- обчислювані -----------------------------------------------------------------------------------------
    @api.depends("action", "param_value", "condition", "condition_value")
    def _compute_how(self):
        for rec in self:
            n, cond = kinds.fmt(rec.param_value), rec.condition
            if rec.action == "defer":
                how = "відкласти заряд до %s хв" % n
            elif rec.action == "pause":
                how = "пауза до %s хв" % n + (", без втрати циклу" if cond == "no_active_cycle" else "")
            elif rec.action == "reduce":
                how = "знизити до %s %%" % n
            else:
                how = "вимкнути" + (
                    ", тиск ≥ %s бар" % kinds.fmt(rec.condition_value, 1) if cond == "air_pressure_min" else ""
                )
            rec.how = how

    def _compute_p_now(self):
        for rec in self:
            rec.p_now_kw = rec.node_id.p_now if rec.node_id else 0.0

    # --- перевірки -------------------------------------------------------------------------------------------
    @api.constrains("node_id", "action", "condition", "param_value", "active")
    def _check_item(self):
        for rec in self:
            node = rec.node_id
            if node.kind != "consumer":
                raise ValidationError(_("Пріоритет скидання: вузол %s не є споживачем.", node.code))
            if node.is_critical and rec.action == "off" and rec.condition == "none":
                raise ValidationError(
                    _("Критичний вузол %s не можна вимикати без умови: оберіть «Знизити» або умову.", node.code)
                )
            if node.workcenter_id and rec.condition != "no_active_cycle":
                raise ValidationError(
                    _("Виробниче обладнання %s скидається лише з умовою «Без втрати циклу».", node.code)
                )
            lo, hi = {"reduce": (1, 99), "pause": (1, 120), "defer": (1, 120), "off": (0, 0)}[rec.action]
            if not lo <= rec.param_value <= hi:
                raise ValidationError(_("Параметр дії поза межами %(lo)s…%(hi)s.", lo=lo, hi=hi))
            if rec.active and self.search_count(
                [("node_id", "=", node.id), ("active", "=", True), ("id", "!=", rec.id)]
            ):
                raise ValidationError(_("Для вузла %s уже є активний пріоритет скидання.", node.code))

    @api.constrains("signal_id", "active")
    def _check_signal(self):
        if self.env.context.get("install_mode"):
            return
        for rec in self:
            if rec.active and not rec.signal_id:
                raise ValidationError(_("Для активного пріоритету потрібен сигнал ліміту."))

    # --- журнал і публікація конфігурації (M-34/M-30: кожна зміна chief — дія класу B) -----------------------
    def _td_can_edit(self):
        user = self.env.user
        if not (user.has_group("td_energy.group_td_energy_chief") or user.has_group("td_factory3d.group_td_admin")):
            raise AccessError(_("Змінювати пріоритети скидання може лише головний енергетик."))

    def _td_log_edit(self, what):
        if tools.is_internal(self.env):
            return
        self.env["td.energy.action"]._td_log_config("shed_edit", "Пріоритети скидання: %s" % what)
        bus.tick(self.env, "shed")

    @api.model_create_multi
    def create(self, vals_list):
        if not tools.is_internal(self.env):
            self._td_can_edit()
        Signal, Node = self.env["td.signal"].sudo(), self.env["td.energy.node"].sudo()
        for vals in vals_list:
            if not vals.get("signal_id") and vals.get("node_id"):
                code = "energy_control/shed/%s/limit_pct" % Node.browse(vals["node_id"]).code
                vals["signal_id"] = Signal.search([("code", "=", code)], limit=1).id or False
        recs = super().create(vals_list)
        recs._td_log_edit("створено «%s»" % ", ".join(recs.mapped("name")))
        return recs

    def write(self, vals):
        if not tools.is_internal(self.env):
            self._td_can_edit()
        res = super().write(vals)
        self._td_log_edit("змінено «%s»" % ", ".join(self.mapped("name")))
        if tools.is_internal(self.env):
            bus.tick(self.env, "shed")
        return res

    def unlink(self):
        if not tools.is_internal(self.env):
            self._td_can_edit()
        names = ", ".join(self.mapped("name"))
        res = super().unlink()
        self._td_log_edit("видалено «%s»" % names)
        return res

    def _td_link_signal(self):
        Signal = self.env["td.signal"].sudo()
        for rec in self:
            sig = Signal.search([("code", "=", "energy_control/shed/%s/limit_pct" % rec.node_id.code)], limit=1)
            if sig:
                rec.sudo().with_context(td_energy_control_internal=True).signal_id = sig.id
