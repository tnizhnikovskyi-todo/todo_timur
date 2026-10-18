import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..tools import lighting

CODE_RE = re.compile(r"^LP-\d{1,3}$")


class F3dBmsLightPanel(models.Model):
    _name = "f3d.bms.light.panel"
    _description = "Будівля: щит освітлення"
    _order = "code"
    _rec_name = "name"
    _rec_names_search = ["name", "code"]

    code = fields.Char(string="Код", size=16, required=True, index=True)
    name = fields.Char(string="Назва", size=128, required=True)
    equipment_id = fields.Many2one("maintenance.equipment", string="Обладнання", ondelete="set null")
    source_id = fields.Many2one(
        "f3d.source", string="Джерело HelvarNet", domain="[('type','=','helvarnet')]", ondelete="set null"
    )
    cluster = fields.Integer(string="Кластер", required=True, default=1)
    router = fields.Integer(string="Роутер", required=True)
    x = fields.Float(string="X, м", digits=(8, 2))
    y = fields.Float(string="Y, м", digits=(8, 2))
    zone_id = fields.Many2one("f3d.zone", string="Зона розміщення", ondelete="set null")
    group_ids = fields.One2many("f3d.bms.light.group", "panel_id", string="Групи")
    group_count = fields.Integer(compute="_compute_totals", store=True)
    n_fixtures = fields.Integer(string="Світильників", compute="_compute_totals", store=True)
    p_inst_kw = fields.Float(string="Встановлена потужність, кВт", compute="_compute_totals", store=True, digits=(8, 1))
    state_signal_id = fields.Many2one("f3d.signal", string="Сигнал: стан щита", ondelete="set null")
    meter_code = fields.Char(compute="_compute_meter_code")
    p_now_kw = fields.Float(string="Потужність зараз, кВт", digits=(8, 1), compute="_compute_live")
    p_source = fields.Selection(
        [("meter", "Лічильник energy"), ("dali", "Сума груп (DALI)"), ("design", "Проєктна")], compute="_compute_live"
    )
    state = fields.Selection(
        [
            ("ok", "Норма"),
            ("fault", "Є несправні світильники"),
            ("offline", "Немає зв'язку"),
            ("unknown", "Невідомо"),
        ],
        compute="_compute_live",
    )
    is_f3d_manager = fields.Boolean(compute="_compute_is_f3d_manager")
    active = fields.Boolean(default=True)
    note = fields.Text()

    _f3d_bms_panel_code_uniq = models.Constraint("UNIQUE(code)", "Код щита має бути унікальним.")
    _f3d_bms_panel_router_uniq = models.Constraint(
        "UNIQUE(cluster, router)", "Роутер з такою адресою вже призначено іншому щиту."
    )
    _f3d_bms_panel_addr = models.Constraint(
        "CHECK(cluster BETWEEN 1 AND 253 AND router BETWEEN 1 AND 254)",
        "Адреса роутера: кластер 1…253, роутер 1…254.",
    )

    @api.constrains("code")
    def _check_code(self):
        for rec in self:
            if not rec.code or not CODE_RE.match(rec.code):
                raise ValidationError("Код щита — LP-<номер>.")

    @api.depends("group_ids.n_fixtures", "group_ids.p_inst_kw")
    def _compute_totals(self):
        for rec in self:
            rec.group_count = len(rec.group_ids)
            rec.n_fixtures = sum(rec.group_ids.mapped("n_fixtures"))
            rec.p_inst_kw = round(sum(rec.group_ids.mapped("p_inst_kw")), 1)

    @api.depends("code")
    def _compute_meter_code(self):
        for rec in self:
            rec.meter_code = "energy/consumers/%s/p_now" % rec.code if rec.code else False

    def _compute_is_f3d_manager(self):
        manager = self.env.user.has_group("factory3d_base.group_f3d_manager")
        for rec in self:
            rec.is_f3d_manager = manager

    @api.depends_context("uid")
    @api.depends(
        "group_ids.level_pct",
        "group_ids.p_now_kw",
        "source_id.state",
        "state_signal_id.last_text",
        "state_signal_id.status",
        "state_signal_id.last_value",
    )
    def _compute_live(self):
        Signal = self.env["f3d.signal"].sudo()
        for rec in self:
            groups = rec.group_ids
            vals = [g._f3d_live_values() for g in groups]
            meter = Signal.search([("code", "=", rec.meter_code)], limit=1) if rec.meter_code else Signal
            if meter and lighting.is_live(meter.status):
                rec.p_now_kw, rec.p_source = meter.last_value, "meter"
            elif any(v["power_live"] for v in vals):
                rec.p_now_kw, rec.p_source = round(sum(v["p_now_kw"] for v in vals), 1), "dali"
            else:
                rec.p_now_kw = round(sum(g._f3d_design_p_now() for g in groups), 1)
                rec.p_source = "design"
            sig = rec.state_signal_id.sudo()
            src = rec.source_id.sudo()
            if src and src.state in ("offline", "error", "disabled"):
                rec.state = "offline"
            elif not sig:
                rec.state = "unknown"
            elif sig.status == "stale":
                rec.state = "offline"
            elif lighting.is_live(sig.status) and sig.last_text in ("ok", "fault"):
                rec.state = sig.last_text
            else:
                rec.state = "unknown"

    def action_f3d_show(self):
        self.ensure_one()
        if not self.equipment_id:
            raise UserError("Щит %s не прив'язаний до обладнання з кодом сцени." % self.code)
        return self.equipment_id.action_f3d_show()

    def action_view_groups(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Групи освітлення",
            "res_model": "f3d.bms.light.group",
            "view_mode": "list,form",
            "domain": [("panel_id", "=", self.id)],
        }
