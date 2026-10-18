"""M-01 `td.energy.resource` — довідник ресурсів (FR-01): одиниці, прапорці екрана, ціноутворення, ліміти."""

import re

from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError, ValidationError

CODE_RE = re.compile(r"^[a-z0-9_]{1,8}$")


class TdEnergyResource(models.Model):
    _name = "td.energy.resource"
    _description = "Енергетика: ресурс"
    _inherit = ["mail.thread"]
    _order = "sequence, id"
    _rec_name = "name"

    code = fields.Char(string="Код", size=8, required=True, index=True, copy=False)
    name = fields.Char(string="Назва", size=64, required=True, translate=False)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    uom_label = fields.Char(string="Одиниця кількості", size=16, required=True)
    rate_label = fields.Char(string="Одиниця швидкості", size=16, required=True)
    rate_hour_factor = fields.Float(
        string="Швидкість → кількість за годину",
        digits=(8, 3),
        required=True,
        default=1.0,
        help="qty_per_hour = rate × factor (повітря: м³/хв → ×60).",
    )
    kwh_per_unit = fields.Float(string="кВт·год на одиницю", digits=(8, 3), default=0.0)
    co2_kg_per_unit = fields.Float(string="кг CO₂ на одиницю", digits=(8, 4), default=0.0)
    is_derived = fields.Boolean(string="Похідний (не додається до загальної вартості)", default=False)
    in_energy_cost = fields.Boolean(string="Входить у вартість енергії (W4)", default=False)
    show_tab_cost = fields.Boolean(string="Вартість у підписі вкладки", default=True)
    source_note = fields.Char(string="Підпис замість вартості", size=32)
    price_source = fields.Selection(
        [
            ("tariff", "Тариф електрики"),
            ("price", "Таблиця цін"),
            ("derived_gas", "Похідна від газу"),
            ("derived_el", "Похідна від електрики"),
            ("none", "Без вартості"),
        ],
        string="Джерело ціни",
        required=True,
        default="none",
    )
    limit_kind = fields.Selection(
        [("none", "Без ліміту"), ("fixed", "Фіксований"), ("tariff_contract", "Договірна потужність")],
        string="Ліміт швидкості",
        required=True,
        default="none",
    )
    rate_limit = fields.Float(string="Ліміт швидкості", digits=(10, 2))
    daily_limit = fields.Float(string="Ліміт доби за договором", digits=(12, 2))
    list_basis = fields.Selection(
        [("rate", "Швидкість"), ("qty_day", "Кількість за добу")], string="Список споживачів", default="rate"
    )
    color = fields.Char(string="Колір", size=7)
    chart_title = fields.Char(string="Заголовок графіка", size=64)
    chart_note = fields.Char(string="Примітка над графіком", size=128)
    list_title = fields.Char(string="Заголовок списку", size=64)
    foot_template = fields.Text(string="Підпис під графіком")
    meter_ids = fields.One2many("td.energy.meter", "resource_id", string="Лічильники", readonly=True)
    meter_count = fields.Integer(string="Лічильників", compute="_compute_counts")
    point_count = fields.Integer(string="Точок обліку", compute="_compute_counts")

    _td_energy_resource_code_uniq = models.Constraint("UNIQUE(code)", "Код ресурсу має бути унікальним.")

    # --- перевірки ------------------------------------------------------------------------------------
    @api.constrains("code")
    def _check_codes(self):
        for rec in self:
            if not rec.code or not CODE_RE.match(rec.code):
                raise ValidationError(_("Код ресурсу %s: до 8 символів a–z, 0–9, підкреслення.", rec.code))

    @api.constrains("code", "active")
    def _check_el(self):
        count = self.with_context(active_test=False).search_count([("code", "=", "el"), ("active", "=", True)])
        if count != 1:
            raise ValidationError(_("Ресурс «Електрика» має бути єдиним."))

    @api.constrains("rate_hour_factor")
    def _check_factor(self):
        for rec in self:
            if rec.rate_hour_factor <= 0:
                raise ValidationError(_("Коефіцієнт швидкості ресурсу %s має бути більшим за нуль.", rec.code))

    @api.constrains("limit_kind", "rate_limit")
    def _check_limit(self):
        for rec in self:
            if rec.limit_kind == "fixed" and rec.rate_limit <= 0:
                raise ValidationError(_("Ресурс %s: для фіксованого ліміту вкажіть значення більше нуля.", rec.code))

    @api.depends("meter_ids")
    def _compute_counts(self):
        meters = dict(
            self.env["td.energy.meter"]._read_group([("resource_id", "in", self.ids)], ["resource_id"], ["__count"])
        )
        points = dict(
            self.env["td.energy.point"]._read_group([("resource_id", "in", self.ids)], ["resource_id"], ["__count"])
        )
        for rec in self:
            rec.meter_count = meters.get(rec, 0)
            rec.point_count = points.get(rec, 0)

    # --- життєвий цикл -------------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        taken = set(self.with_context(active_test=False).search([]).mapped("code"))
        for vals in vals_list:
            code = vals.get("code")
            if code and code in taken:
                raise ValidationError(
                    _("Ресурс «Електрика» має бути єдиним.") if code == "el" else _("Код ресурсу має бути унікальним.")
                )
            taken.add(code)
        records = super().create(vals_list)
        self.env.registry.clear_cache()
        return records

    def write(self, vals):
        result = super().write(vals)
        self.env.registry.clear_cache()
        return result

    @api.ondelete(at_uninstall=False)
    def _unlink_except_el(self):
        if any(rec.code == "el" for rec in self):
            raise UserError(_("Ресурс «Електрика» видаляти не можна."))

    def unlink(self):
        result = super().unlink()
        self.env.registry.clear_cache()
        return result

    # --- API ------------------------------------------------------------------------------------------
    @api.model
    @tools.ormcache("code")
    def _get_id_by_code(self, code):
        rec = self.search([("code", "=", code)], limit=1)
        return rec.id

    @api.model
    def get_by_code(self, code):
        """Активний ресурс за кодом або `False`."""
        rid = self._get_id_by_code(code) if code else False
        return self.browse(rid) if rid else self.browse()

    def _td_active_with_meters(self):
        """R-12, D-48: активні ресурси, у яких є хоча б один активний лічильник (`self` — звузити, інакше всі)."""
        records = self or self.search([])
        groups = self.env["td.energy.meter"]._read_group(
            [("resource_id", "in", records.ids), ("active", "=", True)], ["resource_id"], ["__count"]
        )
        with_meters = {res.id for res, _count in groups}
        return records.filtered(lambda r: r.active and r.id in with_meters)

    def _td_rate_to_qty(self, rate, hours):
        """`rate × rate_hour_factor × hours` (R-01)."""
        self.ensure_one()
        return rate * self.rate_hour_factor * hours

    def _td_kwh_eq(self, qty):
        """R-01 п. 2: `kwh_eq` кількості (газ — × `kwh_per_unit`; електрика й тепло — `qty`; повітря й вода — 0)."""
        self.ensure_one()
        if self.kwh_per_unit:
            return qty * self.kwh_per_unit
        return qty if self.code in ("el", "heat") else 0.0

    @api.model
    def td_no_price_count(self):
        """Скільки активних ресурсів із `price_source='price'` не мають чинної ціни на сьогодні (екран налаштувань)."""
        from odoo.addons.td_energy.tools import dates

        today = dates.local_day(dates.now_utc(self.env))
        missing = 0
        for res in self.search([("price_source", "=", "price")]):
            if not self.env["td.energy.price"]._td_base_price(res, today):
                missing += 1
        return missing
