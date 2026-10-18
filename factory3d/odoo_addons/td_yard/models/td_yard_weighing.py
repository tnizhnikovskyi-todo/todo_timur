from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .td_yard_visit import GRP_SEC, _f3d_yard_require

KIND_LABELS = {"in": "В'їзд", "out": "Виїзд", "check": "Контрольне"}


class F3dYardWeighing(models.Model):
    _name = "td.yard.weighing"
    _description = "Двір: зважування"
    _inherit = ["mail.thread"]
    _order = "ts desc, id desc"
    _check_company_auto = True

    name = fields.Char(string="Номер", size=32, required=True, readonly=True, copy=False, default="/")
    company_id = fields.Many2one(
        "res.company", string="Компанія", required=True, default=lambda s: s.env.company, index=True
    )
    scale_id = fields.Many2one(
        "td.yard.scale",
        string="Ваги",
        required=True,
        index=True,
        ondelete="restrict",
        default=lambda s: s._default_scale(),
    )
    ts = fields.Datetime(string="Час", required=True, index=True, default=fields.Datetime.now)
    kind = fields.Selection(
        [("in", "В'їзд"), ("out", "Виїзд"), ("check", "Контрольне")], string="Вид", required=True, default="in"
    )
    weight_kg = fields.Float(string="Вага, кг", required=True, digits=(12, 1), tracking=True)
    stable = fields.Boolean(string="Стабільно", default=True)
    source = fields.Selection(
        [("auto", "Автоматично"), ("manual", "Вручну"), ("migration", "Міграція")],
        required=True,
        default="manual",
        string="Джерело",
    )
    state = fields.Selection(
        [("assigned", "Призначено"), ("unassigned", "Непризначене"), ("void", "Анульовано")],
        string="Стан",
        required=True,
        default="assigned",
        index=True,
        tracking=True,
    )
    visit_id = fields.Many2one(
        "td.yard.visit", string="Рейс", index=True, ondelete="set null", check_company=True, tracking=True
    )
    role = fields.Selection(
        [("gross", "Брутто"), ("tare", "Тара"), ("check", "Контроль")],
        string="Роль",
        compute="_compute_role",
        store=True,
    )
    picking_id = fields.Many2one("stock.picking", string="Документ", ondelete="set null")
    plate = fields.Char(string="Держномер", size=16)
    user_id = fields.Many2one("res.users", string="Хто записав", default=lambda s: s.env.user, readonly=True)
    note = fields.Char(string="Примітка", size=256)

    _f3d_yard_weighing_nonneg = models.Constraint("CHECK(weight_kg >= 0)", "Вага не може бути від'ємною.")

    @api.model
    def _default_scale(self):
        return self.env["td.yard.scale"].search([("company_id", "=", self.env.company.id)], limit=1)

    @api.depends("kind", "visit_id.visit_type")
    def _compute_role(self):
        for rec in self:
            if rec.kind == "check":
                rec.role = "check"
            elif rec.visit_id.visit_type == "outgoing":
                rec.role = "tare" if rec.kind == "in" else "gross"
            else:
                rec.role = "gross" if rec.kind == "in" else "tare"

    # ------------------------------------------------------------------ перевірки
    @api.constrains("weight_kg", "scale_id", "source", "ts")
    def _check_weight(self):
        limit = fields.Datetime.now() + timedelta(seconds=60)
        for rec in self:
            if rec.source in ("manual", "auto"):
                scale = rec.scale_id
                if not (scale.min_kg <= rec.weight_kg <= scale.max_kg):
                    raise ValidationError(
                        "Вага %s кг поза межами ваг %s: %s…%s кг."
                        % (rec.weight_kg, scale.name, scale.min_kg, scale.max_kg)
                    )
            if rec.ts > limit:
                raise ValidationError("Час зважування в майбутньому.")

    @api.constrains("visit_id", "kind", "state")
    def _check_visit_unique(self):
        for rec in self.filtered(lambda r: r.visit_id and r.state == "assigned" and r.kind != "check"):
            other = self.search(
                [
                    ("visit_id", "=", rec.visit_id.id),
                    ("kind", "=", rec.kind),
                    ("state", "=", "assigned"),
                    ("id", "!=", rec.id),
                ],
                limit=1,
            )
            if other:
                raise ValidationError(
                    "Рейс %s уже має зважування «%s» (%s кг). Анулюйте його спершу."
                    % (rec.visit_id.name, KIND_LABELS[rec.kind], other.weight_kg)
                )

    # ------------------------------------------------------------------ CRUD
    @api.model_create_multi
    def create(self, vals_list):
        Seq = self.env["ir.sequence"].sudo()
        visits = self.env["td.yard.visit"].sudo()
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == "/":
                vals["name"] = Seq.next_by_code("td.yard.weighing") or "/"
            visit = visits.browse(vals.get("visit_id"))
            if "state" not in vals:
                vals["state"] = "assigned" if visit else "unassigned"
            if visit:
                vals.setdefault("plate", visit.plate)
                if not vals.get("picking_id") and visit.batch_id.picking_ids:
                    vals["picking_id"] = visit.batch_id.picking_ids.sorted("name")[:1].id
        records = super().create(vals_list)
        records._f3d_yard_apply()
        return records

    def _f3d_yard_apply(self):
        """Наслідки призначеного зважування для рейсу, документів і ваг (M-05)."""
        for rec in self:
            visit = rec.visit_id.sudo()
            if rec.state == "assigned" and visit:
                if rec.kind == "in" and not visit.weighed_in_at:
                    visit.write({"weighed_in_at": rec.ts})
                elif rec.kind == "out" and visit.state in ("at_dock", "handling") and visit.weighing_policy == "in_out":
                    visit._set_state("weighed", ts=rec.ts)
                    if not visit.handling_end_at:
                        visit.write({"handling_end_at": rec.ts})
                visit._f3d_yard_write_pickings()
            rec.scale_id._f3d_yard_notify()

    # ------------------------------------------------------------------ дії
    def action_assign(self, visit_id, kind=None):
        _f3d_yard_require(self.env, GRP_SEC)
        visit = self.env["td.yard.visit"].browse(visit_id).exists()
        if not visit:
            raise UserError("Оберіть рейс.")
        for rec in self:
            if rec.state != "unassigned":
                raise UserError("Призначити можна лише непризначене зважування.")
            if not kind:
                kind = "out" if visit._f3d_yard_has_weighing("in") else "in"
            vals = {"visit_id": visit.id, "kind": kind, "state": "assigned", "plate": visit.plate}
            picking = visit.sudo().batch_id.picking_ids.sorted("name")[:1]
            if picking:
                vals["picking_id"] = picking.id
            rec.write(vals)
        self._f3d_yard_apply()
        return True

    def action_assign_selected(self):
        self.ensure_one()
        if not self.visit_id:
            raise UserError("Оберіть рейс.")
        return self.action_assign(self.visit_id.id, self.kind)

    def action_void(self):
        _f3d_yard_require(self.env, GRP_SEC)
        for rec in self:
            rec.write({"state": "void"})
            visit = rec.visit_id.sudo()
            if visit:
                visit.message_post(body="Анульовано зважування %s" % rec.name)
                visit._f3d_yard_write_pickings()
            rec.scale_id._f3d_yard_notify()
        return True
