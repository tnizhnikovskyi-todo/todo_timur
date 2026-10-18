"""M-04 `td.energy.baseline` — модель бази ISO 50001 (регресія), M-05 `.line` (W4-A): R-04."""

from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.td_energy.tools import dates

from ..tools import enpi as enpi_tools
from ..tools import ols, periods
from ..tools.fmt import fmt_dec

MANAGER = "td_energy.group_td_energy_manager"
CHIEF = "td_energy.group_td_energy_chief"
MAX_LINES = 3
SCOPES = {"plant": "Завод", "area": "Ділянка"}


class TdEnergyBaseline(models.Model):
    _name = "td.energy.baseline"
    _description = "Енергетика: модель бази (EnPB)"
    _inherit = ["mail.thread"]
    _order = "state, period_to desc, id desc"

    name = fields.Char(string="Назва", compute="_compute_name", store=True, required=True, readonly=True)
    resource_id = fields.Many2one(
        "td.energy.resource", string="Ресурс", required=True, default=lambda self: self._default_resource()
    )
    scope = fields.Selection([("plant", "Завод"), ("area", "Ділянка")], string="Рівень", default="plant")
    area_id = fields.Many2one("td.energy.area", string="Ділянка")
    period_from = fields.Date(string="Період з", required=True)
    period_to = fields.Date(string="Період по", required=True)
    const_per_day = fields.Float(string="Постійна складова, од./добу", digits=(14, 3))
    line_ids = fields.One2many("td.energy.baseline.line", "baseline_id", string="Драйвери")
    n_days = fields.Integer(string="Діб у підгонці", readonly=True)
    r2 = fields.Float(string="R²", readonly=True)
    rmse = fields.Float(string="RMSE", readonly=True)
    method = fields.Selection([("ols", "Регресія"), ("manual", "Вручну")], string="Метод", default="ols")
    state = fields.Selection(
        [("draft", "Чернетка"), ("approved", "Затверджено"), ("archived", "В архіві")],
        string="Стан",
        default="draft",
        tracking=True,
    )
    fitted_at = fields.Datetime(string="Розраховано", readonly=True)
    approved_at = fields.Datetime(string="Затверджено", readonly=True)
    approved_by = fields.Many2one("res.users", string="Затвердив", readonly=True)
    warning = fields.Char(string="Попередження", readonly=True)
    company_id = fields.Many2one("res.company", string="Компанія", required=True, default=lambda self: self.env.company)
    note = fields.Text(string="Примітка")

    @api.model
    def _default_resource(self):
        return self.env["td.energy.resource"].sudo().search([("code", "=", "el")], limit=1)

    # --- обчислення -----------------------------------------------------------------------------------
    @api.depends("resource_id", "scope", "area_id", "period_from", "period_to")
    def _compute_name(self):
        for rec in self:
            scope = rec.area_id.name if rec.scope == "area" and rec.area_id else SCOPES.get(rec.scope, "")
            span = ""
            if rec.period_from and rec.period_to:
                span = "%s…%s" % (rec.period_from.strftime("%Y-%m"), rec.period_to.strftime("%Y-%m"))
            rec.name = "%s · %s · %s" % (rec.resource_id.name or "", scope, span)

    # --- обмеження ------------------------------------------------------------------------------------
    @api.constrains("line_ids")
    def _check_lines(self):
        for rec in self:
            if len(rec.line_ids) > MAX_LINES:
                raise ValidationError(_("Не більше 3 драйверів."))

    @api.constrains("scope", "area_id", "resource_id")
    def _check_scope(self):
        for rec in self:
            if rec.scope == "area" and not rec.area_id:
                raise ValidationError(_("Для рівня «Ділянка» потрібно вказати ділянку."))
            if rec.scope == "area" and rec.resource_id.code != "el":
                raise ValidationError(_("Для газу доступний лише рівень «Завод»."))

    @api.constrains("resource_id")
    def _check_resource(self):
        for rec in self:
            if rec.resource_id.code not in ("el", "gas"):
                raise ValidationError(_("Модель бази підтримується для електрики та газу."))

    @api.constrains("period_from", "period_to")
    def _check_period(self):
        min_days = periods.param_int(self.env, "baseline_min_days", 30)
        for rec in self:
            if rec.period_to < rec.period_from:
                raise ValidationError(_("Кінець періоду бази раніше початку."))
            if (rec.period_to - rec.period_from).days + 1 < min_days:
                raise ValidationError(_("Період бази має бути не коротшим за %s діб.", min_days))

    @api.constrains("state", "resource_id", "scope", "area_id", "company_id")
    def _check_unique_approved(self):
        for rec in self.filtered(lambda r: r.state == "approved"):
            domain = [
                ("id", "!=", rec.id), ("state", "=", "approved"), ("resource_id", "=", rec.resource_id.id),
                ("scope", "=", rec.scope), ("area_id", "=", rec.area_id.id or False),
                ("company_id", "=", rec.company_id.id),
            ]  # fmt: skip
            if self.sudo().search_count(domain):
                raise ValidationError(_("Для цієї пари ресурс/рівень уже є затверджена модель бази."))

    # --- розрахунки -----------------------------------------------------------------------------------
    def _td_context(self):
        """`(resource_code, scope, area_id, driver_ids, codes)` — вхід для вибірок."""
        self.ensure_one()
        lines = self.line_ids.sorted("sequence")
        driver_ids = [line.driver_id.id for line in lines]
        codes = [line.driver_id.code for line in lines]
        return self.resource_id.code, self.scope, self.area_id.id or None, driver_ids, codes

    def expected(self, day_values):
        """R-04 п. 6: `const + Σ coef·x`; `day_values` — `{код драйвера: значення}`; немає значення — `None`."""
        self.ensure_one()
        lines = self.line_ids.sorted("sequence")
        values = [day_values.get(line.driver_id.code) for line in lines]
        return enpi_tools.expected(self.const_per_day, [line.coef for line in lines], values)

    def _td_expected_series(self, day_from, day_to):
        """`{day: очікування або None}` за значеннями драйверів `td.energy.driver.value`."""
        self.ensure_one()
        _code, _scope, _area, driver_ids, codes = self._td_context()
        series = enpi_tools.driver_series(self.env.cr, driver_ids, day_from, day_to)
        lines = self.line_ids.sorted("sequence")
        out, day = {}, day_from
        while day <= day_to:
            values = [series.get(line.driver_id.id, {}).get(day) for line in lines]
            out[day] = enpi_tools.expected(self.const_per_day, [line.coef for line in lines], values)
            day += timedelta(days=1)
        return out

    # --- захист стану ---------------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        if any(vals.get("state") == "approved" for vals in vals_list):
            self._td_check(CHIEF, _("Затверджувати модель бази може лише головний енергетик."))
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("state") == "approved":
            self._td_check(CHIEF, _("Затверджувати модель бази може лише головний енергетик."))
        return super().write(vals)

    # --- кнопки ---------------------------------------------------------------------------------------
    def _td_check(self, group, message):
        if not (self.env.is_superuser() or self.env.user.has_group(group)):
            raise AccessError(message)

    def action_fit(self):
        """R-04: підгонка моделі за період (стан `draft`, право «Енергетик»)."""
        self._td_check(MANAGER, _("Підганяти модель бази може лише енергетик."))
        self.env.flush_all()
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Підганяти можна лише чернетку."))
            if rec.method != "ols":
                raise UserError(_("Для методу «Вручну» підгонка не потрібна."))
            rec._td_fit()
        return True

    def _td_fit(self):
        self.ensure_one()
        cr = self.env.cr
        resource, scope, area_id, driver_ids, codes = self._td_context()
        actual = enpi_tools.actual_series(cr, resource, scope, area_id, self.period_from, self.period_to)
        series = enpi_tools.driver_series(cr, driver_ids, self.period_from, self.period_to)
        rows = enpi_tools.fit_rows(actual, series, driver_ids)
        k = len(driver_ids)
        n_min = max(periods.param_int(self.env, "baseline_min_days", 30), 10 * (k + 1))
        if len(rows) < n_min:
            raise UserError(_("Замало даних для моделі бази: потрібно ≥ %(need)s діб, є %(have)s.", need=n_min, have=len(rows)))
        try:
            const, coefs, r2, rmse = ols.fit([r[1] for r in rows], [r[2] for r in rows])
        except ols.SingularError as exc:
            raise UserError(_("Драйвери лінійно залежні або сталі.")) from exc
        warnings = []
        lines = self.line_ids.sorted("sequence")
        for line, coef in zip(lines, coefs, strict=True):
            if coef < 0:
                warnings.append(_("Від'ємний коефіцієнт %s.", line.driver_id.code))
        if const < 0:
            warnings.append(_("Від'ємна постійна складова."))
        r2_min = periods.param_float(self.env, "r2_min", 0.6)
        if r2 < r2_min:
            warnings.append(_("R² %(r2)s нижче порогу %(min)s.", r2=fmt_dec(r2, 2), min=fmt_dec(r2_min, 2)))
        for line, coef in zip(lines, coefs, strict=True):
            line.coef = coef
        self.write(
            {
                "const_per_day": const, "r2": r2, "rmse": rmse, "n_days": len(rows),
                "fitted_at": fields.Datetime.now(), "warning": " ".join(warnings) or False,
            }
        )  # fmt: skip

    def action_approve(self):
        """R-04 п. 7: затвердження (право «Головний енергетик»); попередню модель пари — в архів; EnPI — перерахунок."""
        self._td_check(CHIEF, _("Затверджувати модель бази може лише головний енергетик."))
        r2_min = periods.param_float(self.env, "r2_min", 0.6)
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Затверджувати можна лише чернетку."))
            if rec.method == "ols":
                problems = []
                if rec.r2 < r2_min:
                    problems.append(_("R² %(r2)s нижче порогу %(min)s", r2=fmt_dec(rec.r2, 2), min=fmt_dec(r2_min, 2)))
                bad = rec.line_ids.filtered(lambda line: line.coef < 0).driver_id.mapped("code")
                if bad:
                    problems.append(_("від'ємні коефіцієнти: %s", ", ".join(bad)))
                if problems:
                    raise UserError(_("Модель не може бути затверджена: %s.", "; ".join(problems)))
            previous = self.sudo().search(
                [
                    ("id", "!=", rec.id), ("state", "=", "approved"), ("resource_id", "=", rec.resource_id.id),
                    ("scope", "=", rec.scope), ("area_id", "=", rec.area_id.id or False),
                    ("company_id", "=", rec.company_id.id),
                ]
            )  # fmt: skip
            previous.write({"state": "archived"})
            rec.write({"state": "approved", "approved_by": self.env.user.id, "approved_at": fields.Datetime.now()})
            yesterday = dates.local_day(dates.now_utc(self.env)) - timedelta(days=1)
            if yesterday >= rec.period_from:
                self.env["td.energy.enpi"].sudo().recompute(rec.period_from, yesterday, baseline=rec)
        return True

    def action_archive(self):
        self._td_check(CHIEF, _("Архівувати модель бази може лише головний енергетик."))
        self.write({"state": "archived"})
        return True

    def action_to_draft(self):
        """Повернення в чернетку (головний енергетик): EnPI моделі скидається."""
        self._td_check(CHIEF, _("Повертати модель бази в чернетку може лише головний енергетик."))
        self.env["td.energy.enpi"].sudo().search([("baseline_id", "in", self.ids)]).unlink()
        self.write({"state": "draft", "approved_by": False, "approved_at": False})
        return True


class TdEnergyBaselineLine(models.Model):
    _name = "td.energy.baseline.line"
    _description = "Енергетика: рядок моделі бази"
    _order = "sequence, id"

    baseline_id = fields.Many2one("td.energy.baseline", string="Модель", required=True, ondelete="cascade")
    driver_id = fields.Many2one("td.energy.driver", string="Драйвер", required=True, ondelete="restrict")
    coef = fields.Float(string="Коефіцієнт, од. на одиницю драйвера", digits=(14, 6))
    sequence = fields.Integer(default=10)

    _baseline_driver_uniq = models.Constraint("UNIQUE(baseline_id, driver_id)", "Драйвер у моделі вже використано.")
