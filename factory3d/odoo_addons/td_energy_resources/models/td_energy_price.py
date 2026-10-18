"""M-02 `td.energy.price` — ціна неелектричного ресурсу (FR-02); `_td_price_at` — контракт C-01 (API-09)."""

from datetime import date, datetime

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.td_energy.tools import dates

from ..tools.build import rparam_float

COST_GROUP = "td_energy.group_td_energy_cost"


class TdEnergyPrice(models.Model):
    _name = "td.energy.price"
    _description = "Енергетика: ціна ресурсу"
    _inherit = ["mail.thread"]
    _order = "resource_id, date_from desc"

    resource_id = fields.Many2one(
        "td.energy.resource",
        string="Ресурс",
        required=True,
        ondelete="restrict",
        index=True,
        tracking=True,
        domain="[('price_source', '=', 'price')]",
    )
    date_from = fields.Date(string="Діє з", required=True, tracking=True)
    date_to = fields.Date(string="Діє по", tracking=True, help="Порожньо — безстроково")
    price = fields.Float(string="Ціна за одиницю (₴)", digits=(12, 4), required=True, groups=COST_GROUP, tracking=True)
    currency_id = fields.Many2one(
        "res.currency", string="Валюта", required=True, default=lambda self: self.env.company.currency_id
    )
    company_id = fields.Many2one("res.company", string="Компанія", required=True, default=lambda self: self.env.company)
    note = fields.Char(string="Примітка", size=128)
    active = fields.Boolean(default=True)

    # --- перевірки ------------------------------------------------------------------------------------
    @api.constrains("resource_id")
    def _check_resource(self):
        for rec in self:
            if rec.resource_id.code == "el":
                raise ValidationError(_("Ціни електрики задаються в тарифі."))

    @api.constrains("date_from", "date_to", "resource_id", "company_id", "active")
    def _check_period(self):
        for rec in self:
            if rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_("Дата «По» раніше за дату «З»."))
            if not rec.active:
                continue
            domain = [
                ("id", "!=", rec.id),
                ("resource_id", "=", rec.resource_id.id),
                ("company_id", "=", rec.company_id.id),
                ("date_from", "<=", rec.date_to or date.max),
                "|",
                ("date_to", "=", False),
                ("date_to", ">=", rec.date_from),
            ]
            if self.search_count(domain):
                raise ValidationError(_("Період ціни перетинається з іншою."))

    @api.constrains("price")
    def _check_price(self):
        for rec in self.sudo():
            if rec.price < 0:
                raise ValidationError(_("Ціна не може бути від'ємною."))

    # --- API-09 ---------------------------------------------------------------------------------------
    @api.model
    def _td_resource(self, resource):
        Resource = self.env["td.energy.resource"]
        if isinstance(resource, str):
            return Resource.get_by_code(resource)
        if isinstance(resource, int):
            return Resource.browse(resource)
        return resource

    @api.model
    def _td_base_price(self, resource, day, company=None):
        company = company or self.env.company
        rec = self.sudo().search(
            [
                ("resource_id", "=", resource.id),
                ("company_id", "in", (company.id, False)),
                ("date_from", "<=", day),
                "|",
                ("date_to", "=", False),
                ("date_to", ">=", day),
            ],
            order="date_from desc",
            limit=1,
        )
        return rec.price if rec else 0.0

    @api.model
    def _td_price_at(self, resource, dt_local=None, company=None):
        """API-09 (C-01): ціна одиниці ресурсу на місцеву дату (`date`/`datetime`, за умовчанням — сьогодні).

        `resource` — запис, код або id. `price` — таблиця цін; `derived_gas` (тепло) — `ціна газу / (кВт·год на м³ ×
        ККД котельні)` (R-02 п. 3); `tariff`/`derived_el`/`none` — 0.0 (вартість береться з тарифу або з електро-
        інтервалів). Дата поза періодами — 0.0 (вартість 0, а не помилка)."""
        res = self._td_resource(resource)
        if not res:
            return 0.0
        if dt_local is None:
            day = dates.local_day(dates.now_utc(self.env))
        else:
            day = dt_local.date() if isinstance(dt_local, datetime) else dt_local
        if res.price_source == "price":
            return self._td_base_price(res, day, company)
        if res.price_source == "derived_gas":
            gas = self.env["td.energy.resource"].get_by_code("gas")
            eff = rparam_float(self.env, "boiler_eff")
            if not gas or not gas.kwh_per_unit or eff <= 0:
                return 0.0
            return self._td_base_price(gas, day, company) / (gas.kwh_per_unit * eff)
        return 0.0
