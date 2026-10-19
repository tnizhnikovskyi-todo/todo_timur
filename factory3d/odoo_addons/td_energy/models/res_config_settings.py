import json

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

P = "td.energy."


class ResConfigSettings(models.TransientModel):
    """M-18: налаштування енергетики; стоп-кран `read_enabled` вимикає читання джерел `module='energy'`."""

    _inherit = "res.config.settings"

    td_energy_read_enabled = fields.Boolean(string="Читати лічильники", config_parameter=P + "read_enabled")
    td_energy_write_enabled = fields.Boolean(
        string="Писати уставки в пристрої", config_parameter=P + "write_enabled", readonly=True
    )
    td_energy_costing_enabled = fields.Boolean(
        string="Енергія в собівартості МО", config_parameter=P + "costing_enabled"
    )
    td_energy_analytic_enabled = fields.Boolean(
        string="Аналітичні рядки енергії", config_parameter=P + "analytic_enabled"
    )
    td_energy_balance_tol_pct = fields.Float(string="Допуск небалансу, %", config_parameter=P + "balance_tol_pct")
    td_energy_balance_tol_kwh = fields.Float(string="Допуск небалансу, кВт·год", config_parameter=P + "balance_tol_kwh")
    td_energy_gap_alarm_min = fields.Integer(
        string="Пропуск даних до тривоги, хв", config_parameter=P + "gap_alarm_min"
    )
    td_energy_max_wait_h = fields.Integer(string="Макс. очікування даних, год", config_parameter=P + "max_wait_h")
    td_energy_keep_interval_days = fields.Integer(
        string="Зберігати інтервали, діб", config_parameter=P + "keep_interval_days"
    )
    td_energy_keep_event_days = fields.Integer(string="Зберігати події, діб", config_parameter=P + "keep_event_days")
    td_energy_shift_calendar_id = fields.Many2one("resource.calendar", string="Календар змін")
    td_energy_typical_days = fields.Integer(string="Робочих діб для типового дня", config_parameter=P + "typical_days")
    td_energy_ats_fail_start_s = fields.Integer(
        string="Очікування пуску генератора, с", config_parameter=P + "ats_fail_start_s"
    )
    td_energy_peak_shave_kw = fields.Float(string="Зрізання піків понад, кВт", config_parameter=P + "peak_shave_kw")
    # --- W1 (SPEC 5.1): cos φ (E-10), Пульт, прогноз, накопичувач, повірка ---------------------------------
    td_energy_cos_phi_target = fields.Float(string="cos φ: ціль", digits=(4, 2), config_parameter=P + "cos_phi_target")
    td_energy_cos_phi_warn = fields.Float(
        string="cos φ: попередження", digits=(4, 2), config_parameter=P + "cos_phi_warn"
    )
    td_energy_cos_phi_alarm = fields.Float(string="cos φ: тривога", digits=(4, 2), config_parameter=P + "cos_phi_alarm")
    td_energy_pult_refresh_s = fields.Integer(
        string="Резервне опитування Пульту, с", config_parameter=P + "pult_refresh_s"
    )
    td_energy_alarm_list_limit = fields.Integer(
        string="Рядків у списку тривог", config_parameter=P + "alarm_list_limit"
    )
    td_energy_load_warn_pct = fields.Integer(string="Завантаження: увага, %", config_parameter=P + "load_warn_pct")
    td_energy_load_alarm_pct = fields.Integer(string="Завантаження: тривога, %", config_parameter=P + "load_alarm_pct")
    td_energy_forecast_weeks = fields.Integer(string="Прогноз: глибина, тижнів", config_parameter=P + "forecast_weeks")
    td_energy_forecast_min_days = fields.Integer(
        string="Прогноз: мінімум днів", config_parameter=P + "forecast_min_days"
    )
    td_energy_bess_reserve_pct = fields.Integer(string="Резерв BESS, %", config_parameter=P + "bess_reserve_pct")
    td_energy_verify_warn_days = fields.Integer(
        string="Нагадати про повірку за, діб", config_parameter=P + "verify_warn_days"
    )
    td_energy_pv_kwp = fields.Float(string="Потужність СЕС, кВт", config_parameter=P + "pv_kwp")
    td_energy_install_state = fields.Char(string="Стан встановлення", compute="_compute_f3d_energy_install_state")

    @api.depends_context("uid")
    def _compute_f3d_energy_install_state(self):
        raw = self.env["ir.config_parameter"].sudo().get_param(P + "install_report", "{}") or "{}"
        try:
            report = json.loads(raw)
            state = report.get("state", "—") if isinstance(report, dict) else "—"
        except ValueError:
            state = "—"
        for rec in self:
            rec.td_energy_install_state = state

    @api.model
    def get_values(self):
        res = super().get_values()
        raw = self.env["ir.config_parameter"].sudo().get_param(P + "shift_calendar_id") or ""
        res["td_energy_shift_calendar_id"] = int(raw) if raw.isdigit() else False
        return res

    @api.constrains("td_energy_cos_phi_target", "td_energy_cos_phi_warn", "td_energy_cos_phi_alarm")
    def _check_td_energy_cos_phi(self):
        for rec in self:
            if not (rec.td_energy_cos_phi_alarm < rec.td_energy_cos_phi_warn <= rec.td_energy_cos_phi_target <= 1):
                raise ValidationError(_("Пороги cos φ: тривога < попередження ≤ ціль ≤ 1."))

    @api.model
    def _td_apply_cos_thresholds(self):
        """W1 5.1: пороги cos φ з параметрів → `warn_low`/`alarm_low` сигналів заводу й секцій
        (патерн `_td_apply_contract_thresholds`)."""
        icp = self.env["ir.config_parameter"].sudo()
        warn = float(icp.get_param(P + "cos_phi_warn", "0.92") or 0.92)
        alarm = float(icp.get_param(P + "cos_phi_alarm", "0.90") or 0.90)
        codes = ["energy/totals/cos_phi"] + ["energy/sections/S%d/cos_phi" % s for s in (1, 2)]
        signals = self.env["td.signal"].sudo().with_context(active_test=False).search([("code", "in", codes)])
        signals.write({"warn_low": warn, "alarm_low": alarm, "warn_low_on": True, "alarm_low_on": True})
        return signals

    def set_values(self):
        icp = self.env["ir.config_parameter"].sudo()
        # стоп-кран запису (A-15) у формі лише для читання: значення з форми не застосовується
        old_write = icp.get_param(P + "write_enabled", "False")
        super().set_values()
        icp.set_param(P + "write_enabled", old_write)
        for rec in self:
            icp.set_param(P + "shift_calendar_id", str(rec.td_energy_shift_calendar_id.id or ""))
        self._td_apply_cos_thresholds()  # W1: пороги cos φ → сигнали
        # AC-80: стоп-кран читання → джерела енергетики
        read_enabled = icp.get_param(P + "read_enabled", "False") in ("True", "true", "1")
        sources = self.env["td.source"].sudo().search([("module", "=", "energy")])
        if sources.filtered(lambda s: s.read_enabled != read_enabled):
            sources.write({"read_enabled": read_enabled})
