from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..tools import tariff as tariff_tools

COST_GROUP = "td_energy.group_td_energy_cost"
CONTRACT_FIELDS = {"contract_kw", "peak_warn_pct", "date_from", "date_to", "active", "company_id"}
GRID15_CODE = "energy/totals/grid15_kw"
GRID15_TITLE = "Перевищення договірної потужності: {value} кВт при ліміті {threshold} кВт"


class F3dEnergyTariff(models.Model):
    _name = "td.energy.tariff"
    _description = "Енергетика: тариф"
    _inherit = ["mail.thread"]
    _order = "date_from desc"

    name = fields.Char(string="Назва", required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company", string="Компанія", required=True, default=lambda self: self.env.company, index=True
    )
    currency_id = fields.Many2one(
        "res.currency", string="Валюта", required=True, default=lambda self: self.env.company.currency_id
    )
    date_from = fields.Date(string="Діє з", required=True, tracking=True)
    date_to = fields.Date(string="Діє по", tracking=True, help="Порожньо — безстроково")
    zone_ids = fields.One2many("td.energy.tariff.zone", "tariff_id", string="Зони", copy=True)
    export_price = fields.Float(
        string="Ціна віддачі в мережу, грн/кВт·год", digits=(10, 4), default=0, groups=COST_GROUP
    )
    contract_kw = fields.Float(
        string="Договірна потужність, кВт", digits=(10, 1), required=True, default=800, tracking=True
    )
    peak_warn_pct = fields.Float(string="Попередження від, % договірної", digits=(5, 1), default=90)
    note = fields.Text(string="Примітка")

    # --- перевірки ---------------------------------------------------------------------------------
    @api.constrains("date_from", "date_to", "active", "company_id")
    def _check_period(self):
        for rec in self:
            if rec.date_to and rec.date_to < rec.date_from:
                raise ValidationError(_("Дата «по» раніше дати «з»."))
            if not rec.active:
                continue
            domain = [("id", "!=", rec.id), ("company_id", "=", rec.company_id.id), ("active", "=", True)]
            if rec.date_to:
                domain.append(("date_from", "<=", rec.date_to))
            domain += ["|", ("date_to", "=", False), ("date_to", ">=", rec.date_from)]
            other = self.search(domain, limit=1)
            if other:
                raise ValidationError(_("Період тарифу перетинається з «%s».", other.name))

    @api.constrains("zone_ids")
    def _check_coverage(self):
        """R-05 п. 3. Тариф без зон дозволений (зони додають окремими записами); ціна такого тарифу — 0."""
        for rec in self:
            if not rec.zone_ids:
                continue
            err = tariff_tools.check_coverage(rec.zone_ids.sorted("sequence"))
            if err and err[0] == "missing":
                raise ValidationError(_("Зони тарифу «%s»: %s о %s не покрито", rec.name, err[1], err[2]))
            if err:
                raise ValidationError(
                    _("Зони тарифу «%s»: %s о %s покрито двічі (%s, %s)", rec.name, err[1], err[2], err[3], err[4])
                )

    # --- запис -------------------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        records._f3d_refresh_thresholds()
        return records

    def write(self, vals):
        res = super().write(vals)
        if CONTRACT_FIELDS & set(vals):
            self._f3d_refresh_thresholds()
        return res

    def _f3d_refresh_thresholds(self):
        """Після зміни договору: пороги беруться з тарифу, чинного сьогодні, для кожної компанії."""
        now = fields.Datetime.now()
        for company in self.company_id:
            self._f3d_tariff_at(now, company)._f3d_apply_contract_thresholds()

    # --- API ---------------------------------------------------------------------------------------
    @api.model
    def _f3d_tariff_at(self, dt_utc, company=None):
        """Активний тариф компанії, чинний на місцеву дату `dt_utc`; немає — порожній набір."""
        company = company or self.env.company
        local_date = tariff_tools.to_local(dt_utc).date()
        return self.search(
            [
                ("company_id", "=", company.id),
                ("active", "=", True),
                ("date_from", "<=", local_date),
                "|",
                ("date_to", "=", False),
                ("date_to", ">=", local_date),
            ],
            order="date_from desc",
            limit=1,
        )

    @api.model
    def _f3d_price_at(self, dt_utc, company=None):
        """R-05: (зона, ціна) за початком слота; немає тарифу чи зони — (порожня зона, 0.0)."""
        zone_model = self.env["td.energy.tariff.zone"]
        tariff = self._f3d_tariff_at(dt_utc, company)
        if not tariff:
            return zone_model, 0.0
        zone = tariff_tools.zone_for(tariff_tools.to_local(dt_utc), tariff.zone_ids.sorted("sequence"))
        if zone is None:
            return zone_model, 0.0
        return zone, zone.price

    def _f3d_apply_contract_thresholds(self):
        """R-12 п. 1: пороги сигналу `grid15_kw` з договірної потужності тарифу."""
        signal = (
            self.env["td.signal"].sudo().with_context(active_test=False).search([("code", "=", GRID15_CODE)], limit=1)
        )
        for rec in self[:1]:
            if not signal:
                break
            vals = {
                "warn_high": rec.contract_kw * rec.peak_warn_pct / 100,
                "alarm_high": rec.contract_kw,
                "warn_high_on": True,
                "alarm_high_on": True,
                "min_duration_s": 0,
                "alarm_title": GRID15_TITLE,
            }
            switchboard = self.env["maintenance.equipment"].sudo().search_f3d("SWB-1")
            if switchboard:
                vals["equipment_id"] = switchboard.id
            signal.write(vals)


class F3dEnergyTariffZone(models.Model):
    _name = "td.energy.tariff.zone"
    _description = "Енергетика: зона тарифу"
    _order = "tariff_id, sequence, id"

    tariff_id = fields.Many2one("td.energy.tariff", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    name = fields.Char(string="Зона", required=True)
    code = fields.Selection(
        [
            ("flat", "Цілодобова"),
            ("day", "День"),
            ("night", "Ніч"),
            ("peak", "Пік"),
            ("half_peak", "Напівпік"),
        ],
        required=True,
        default="flat",
    )
    price = fields.Float(string="Ціна, грн/кВт·год", digits=(10, 4), required=True, groups=COST_GROUP)
    weekdays = fields.Char(string="Дні тижня", size=7, required=True, default="0123456", help="0 — понеділок")
    hour_from = fields.Float(string="З (год)", required=True, default=0)
    hour_to = fields.Float(string="До (год)", required=True, default=24)
    color = fields.Integer()

    @api.constrains("weekdays")
    def _check_weekdays(self):
        for rec in self:
            if not tariff_tools.weekdays_valid(rec.weekdays):
                raise ValidationError(_("Дні тижня: цифри 0…6 без повторів (0 — понеділок)."))

    @api.constrains("hour_from", "hour_to")
    def _check_hours(self):
        for rec in self:
            if not tariff_tools.hours_valid(rec.hour_from, rec.hour_to):
                raise ValidationError(_("Години зони — від 0 до 24 з кроком 15 хв."))
            if rec.hour_from == rec.hour_to:
                raise ValidationError(_("Зона «%s» має нульову тривалість.", rec.name))

    @api.constrains("price")
    def _check_price(self):
        for rec in self:
            if rec.price < 0:
                raise ValidationError(_("Ціна не може бути від'ємною."))
