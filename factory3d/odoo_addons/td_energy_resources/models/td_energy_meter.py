"""M-04 `td.energy.meter` — розширення: лічильники будь-якого ресурсу (FR-04, FR-07; A-02).

`node_id` перестає бути обов'язковим; у неелектричних лічильників немає `e_import_signal_id`, тому електричні розрахунки
`td_energy` (`_cron_build`, `backfill.Plan`, баланс) їх не бачать. Перевизначено `role`, `model`, `company_id`,
`_f3d_update_state` — їх перебирає `cron_td_energy_live` для всіх лічильників (R8, AC-05).
"""

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.td_energy.tools import dates

NO_RESOURCE_MODEL = "other"
STATE_STALE_MIN = 30


class TdEnergyMeter(models.Model):
    _inherit = "td.energy.meter"

    node_id = fields.Many2one(required=False)
    role = fields.Selection(selection_add=[("resource", "Ресурс")], ondelete={"resource": "cascade"})
    # не `required` на рівні БД: колонка додається до наявних лічильників до завантаження ресурсу `el` (дані — хук
    # `_set_el_on_meters`); обов'язковість — `_check_resource_binding` і форма
    resource_id = fields.Many2one(
        "td.energy.resource",
        string="Ресурс",
        index=True,
        ondelete="restrict",
        default=lambda self: self.env.ref("td_energy_resources.resource_el", raise_if_not_found=False),
    )
    point_id = fields.Many2one("td.energy.point", string="Точка обліку", index=True, ondelete="restrict")
    mode = fields.Selection(
        [("counter", "Лічильник"), ("flow_integrate", "Інтеграл витрати"), ("estimate", "Оцінка")],
        string="Режим",
        required=True,
        default="counter",
    )
    qty_signal_id = fields.Many2one(
        "td.signal", string="Сигнал лічильника об'єму / енергії", domain="[('kind', '=', 'counter')]",
        ondelete="set null",
    )  # fmt: skip
    flow_signal_ids = fields.Many2many(
        "td.signal", "td_energy_meter_flow_signal_rel", "meter_id", "signal_id", string="Сигнали швидкості"
    )
    max_rate = fields.Float(
        string="Макс. швидкість (од. ресурсу/год)", digits=(12, 3), default=0.0,
        help="Правдоподібність показань після скидання лічильника; 0 — паспортна швидкість точки або 1000.",
    )  # fmt: skip
    e_react_signal_id = fields.Many2one(
        "td.signal", string="Реактивна енергія, квар·год", domain="[('kind', '=', 'counter')]", ondelete="set null"
    )
    res_last_interval_start = fields.Datetime(string="Останній інтервал ресурсу", readonly=True)
    company_id = fields.Many2one(
        "res.company", related=False, compute="_compute_company_id", store=True, readonly=True, index=True
    )

    @api.depends("node_id.company_id", "point_id.company_id")
    def _compute_company_id(self):
        for rec in self:
            rec.company_id = rec.node_id.company_id or rec.point_id.company_id or self.env.company

    # --- створення: роль і модель неелектричних -------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        el = self.env.ref("td_energy_resources.resource_el", raise_if_not_found=False)
        for vals in vals_list:
            if vals.get("resource_id") and el and vals["resource_id"] != el.id:
                vals.setdefault("role", "resource")
                vals.setdefault("model", NO_RESOURCE_MODEL)
        return super().create(vals_list)

    # --- перевірки (A-02) -----------------------------------------------------------------------------
    @api.constrains(
        "resource_id", "node_id", "point_id", "mode", "role", "model", "qty_signal_id", "flow_signal_ids",
        "e_import_signal_id", "e_export_signal_id", "e_react_signal_id",
    )  # fmt: skip
    def _check_resource_binding(self):
        for rec in self:
            if not rec.resource_id:  # NOT NULL на колонці не ставимо: наявні рядки заповнює хук, а не default
                raise ValidationError(_("Для лічильника потрібен ресурс."))
            if rec.resource_id.code == "el":
                if not rec.node_id:
                    raise ValidationError(_("Для електричного лічильника потрібен вузол."))
                if rec.point_id:
                    raise ValidationError(_("Для електричного лічильника точка обліку не задається."))
                if rec.mode != "counter":
                    raise ValidationError(_("Електричний лічильник працює лише в режимі «Лічильник»."))
                if rec.role == "resource":
                    raise ValidationError(_("Роль «Ресурс» — лише для неелектричних лічильників."))
                if rec.e_react_signal_id and rec.role != "incomer":
                    raise ValidationError(_("Реактивна енергія — лише для лічильників ролі «Ввід»."))
                continue
            if not rec.point_id:
                raise ValidationError(_("Для лічильника ресурсу потрібна точка обліку."))
            if rec.e_import_signal_id or rec.e_export_signal_id:
                raise ValidationError(_("Електричні сигнали лише для ресурсу «Електрика»."))
            if rec.e_react_signal_id:
                raise ValidationError(_("Реактивна енергія — лише для лічильників ролі «Ввід» ресурсу «Електрика»."))
            if rec.role != "resource" or rec.model != NO_RESOURCE_MODEL:
                raise ValidationError(_("Лічильник ресурсу має роль «Ресурс» і модель «Інший»."))
            if rec.point_id.resource_id != rec.resource_id:
                raise ValidationError(_("Точка обліку має бути з того самого ресурсу, що й лічильник."))
            if rec.mode == "counter" and not rec.qty_signal_id:
                raise ValidationError(_("Для режиму «Лічильник» потрібен сигнал лічильника."))
            if rec.mode == "flow_integrate" and not rec.flow_signal_ids:
                raise ValidationError(_("Для режиму «Інтеграл витрати» потрібен хоча б один сигнал швидкості."))
            if rec.mode == "estimate" and rec.point_id.estimate_method == "none":
                raise ValidationError(_("Для режиму «Оцінка» у точки має бути метод оцінки."))

    def write(self, vals):
        if "mode" in vals:  # R-10: зміна режиму — перебудова останніх 24 год
            vals = dict(vals, res_last_interval_start=False)
        return super().write(vals)

    # --- стан даних (R8): cron_td_energy_live викликає для всіх лічильників -----------------------------
    def _f3d_update_state(self):
        electric = self.filtered(lambda m: not m.resource_id or m.resource_id.code == "el")
        if electric:
            super(TdEnergyMeter, electric)._f3d_update_state()
        resource = self - electric
        if resource:
            resource._td_update_resource_state()

    def _td_update_resource_state(self):
        """`data_state` неелектричних: `counter` — за `qty_signal_id`, `flow_integrate` — за `flow_signal_ids`,
        `estimate` — за останнім слотом; подій `meter` немає (A-14)."""
        now = dates.now_utc(self.env)
        Interval = self.env["td.energy.res.interval"].sudo()
        for rec in self.sudo():
            if rec.mode == "estimate":
                last = Interval.search([("meter_id", "=", rec.id)], order="ts_start desc", limit=1)
                if not last:
                    state = "no_data"
                elif now - last.ts_end > timedelta(minutes=STATE_STALE_MIN):
                    state = "stale"
                elif Interval.search_count(
                    [("meter_id", "=", rec.id), ("quality", "in", ("missing", "interpolated")),
                     ("ts_start", ">=", now - timedelta(hours=2))]
                ):  # fmt: skip
                    state = "gap"
                else:
                    state = "ok"
            else:
                signals = rec.flow_signal_ids if rec.mode == "flow_integrate" else rec.qty_signal_id
                if not signals or not any(s.last_ts for s in signals):
                    state = "no_data"
                elif any(
                    not s.last_ts or s.status == "stale" or now - s.last_ts > timedelta(seconds=3 * (s.period_s or 60))
                    for s in signals
                ):
                    state = "stale"
                else:
                    state = "ok"
            if state != rec.data_state:
                rec.write({"data_state": state, "data_state_since": now})
