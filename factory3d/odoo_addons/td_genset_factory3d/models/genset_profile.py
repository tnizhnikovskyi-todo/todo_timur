import json

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError

from ..adapters import td_genset as td

# Макет: картка GENSET; пороги — ПРИПУЩЕННЯ Q-06/Q-13 (SPEC §8.2)
RELAY_DEFAULTS = {
    "sensors": {
        "coolant_idle_c": 22,
        "coolant_run_c": 85,
        "coolant_tau_s": 600,
        "oil_run_bar": 4.5,
        "oil_idle_bar": 0.0,
        "batt_v": 25.2,
        "charger_v": 27.6,
        "rpm_run": 1500,
        "u_v": 400,
        "f_hz": 50.0,
        "pf": 0.8,
    },
    "alarms": {
        "low_fuel_warn_pct": 25,
        "low_fuel_sd_pct": 10,
        "coolant_high_c": 98,
        "oil_low_bar": 1.0,
        "batt_low_v": 23.0,
        "batt_high_v": 33.0,
    },
    "start": {
        "hours": 1213.0,
        "starts": 184,
        "fuel_pct": 82,
        "kwh": 61250,
        "mode": "auto",
        "mains_ok": True,
        "load_kw": 348,
        "last_test": "2026-10-12T07:30:00+03:00",
    },
}
TIMER_PRESETS = {
    "default": {
        "mains_abnormal_s": 5,
        "start_delay_s": 1,
        "crank_s": 8,
        "crank_rest_s": 10,
        "start_times": 3,
        "safety_on_s": 10,
        "warming_s": 10,
        "transfer_s": 1.0,
        "mains_normal_s": 10,
        "stop_delay_s": 1,
        "cooling_s": 10,
        "ets_hold_s": 20,
        "crank_fire_s": 3,
        "over_current_delay_s": 30,
    },
    "plant": {
        "mains_abnormal_s": 2,
        "start_delay_s": 0,
        "crank_s": 8,
        "crank_rest_s": 10,
        "start_times": 3,
        "safety_on_s": 5,
        "warming_s": 3,
        "transfer_s": 1.0,
        "mains_normal_s": 10,
        "stop_delay_s": 1,
        "cooling_s": 10,
        "ets_hold_s": 20,
        "crank_fire_s": 3,
        "over_current_delay_s": 30,
    },
}
PLANT_KEYS = ("mains_abnormal_s", "start_delay_s", "safety_on_s", "warming_s")


class F3dGensetProfile(models.Model):
    _name = "td.genset3d.profile"
    _description = "Генератор: профіль (паливо, потужність, таймери)"
    _order = "code"
    _rec_name = "name"

    code = fields.Char(string="Код", size=32, required=True, index=True)
    name = fields.Char(string="Назва", required=True)
    passport_id = fields.Many2one(
        "td.equipment.passport", string="Паспорт", domain="[('role', '=', 'genset')]", ondelete="set null"
    )
    kva_prp = fields.Float(string="PRP, кВА", digits=(8, 1), required=True, default=634)
    kw_prp = fields.Float(string="PRP, кВт", digits=(8, 1), required=True, default=507)
    kva_esp = fields.Float(string="ESP, кВА", default=697)
    kw_esp = fields.Float(string="ESP, кВт", default=558)
    tank_l = fields.Float(string="Бак, л", digits=(8, 1), required=True, default=610)
    fuel_lph_25 = fields.Float(string="Витрата при 25 %, л/год", digits=(8, 1), default=38.6)
    fuel_lph_50 = fields.Float(string="Витрата при 50 %, л/год", digits=(8, 1), default=71.2)
    fuel_lph_75 = fields.Float(string="Витрата при 75 %, л/год", digits=(8, 1), default=103.8)
    fuel_lph_100 = fields.Float(string="Витрата при 100 % PRP, л/год", digits=(8, 1), default=136.4)
    fuel_lph_esp = fields.Float(string="Витрата при 100 % ESP, л/год", digits=(8, 1), default=149.5)
    oil_l = fields.Float(string="Олива, л", default=34)
    oil_pressure_min_bar = fields.Float(string="Мін. тиск оливи, бар", default=0.5)
    start_to_load_s = fields.Integer(
        string="Пуск до навантаження, с", default=15, help="Ціль заводу; умовчання HGM ≈ 30 с"
    )
    autonomy_warn_h = fields.Float(string="Попередження про автономність, год", default=2.0)
    timer_preset = fields.Selection(
        [("default", "Умовчання HGM6120N (Table 7)"), ("plant", "Заводський пресет (Q-06)")],
        string="Пресет таймерів",
        default="default",
    )
    timers_json = fields.Json(string="Таймери", compute="_compute_timers")
    timers_text = fields.Char(string="Таймери (JSON)", compute="_compute_timers_text")
    note = fields.Text(string="Примітка")
    active = fields.Boolean(default=True)

    _code_uniq = models.Constraint("UNIQUE(code)", "Код профілю має бути унікальним.")

    @api.depends("timer_preset")
    def _compute_timers(self):
        for rec in self:
            rec.timers_json = dict(TIMER_PRESETS.get(rec.timer_preset or "default"))

    @api.depends("timers_json")
    def _compute_timers_text(self):
        for rec in self:
            rec.timers_text = json.dumps(rec.timers_json or {}, ensure_ascii=False)

    @api.constrains(
        "tank_l", "kw_prp", "kva_prp", "fuel_lph_25", "fuel_lph_50", "fuel_lph_75", "fuel_lph_100", "fuel_lph_esp"
    )
    def _check_values(self):
        for rec in self:
            if rec.tank_l <= 0 or rec.kw_prp <= 0:
                raise ValidationError(_("Бак і потужність PRP мають бути більшими за нуль."))
            if rec.kva_prp < rec.kw_prp:
                raise ValidationError(_("Потужність PRP в кВА не може бути меншою за кВт."))
            curve = [rec.fuel_lph_25, rec.fuel_lph_50, rec.fuel_lph_75, rec.fuel_lph_100, rec.fuel_lph_esp]
            if any(v <= 0 for v in curve):
                raise ValidationError(_("Витрата палива має бути більшою за нуль."))
            if curve != sorted(curve):
                raise ValidationError(_("Крива витрати має бути неспадною."))

    # --- R-01, R-02 -----------------------------------------------------------------------------------
    def fuel_lph(self, load_pct):
        """R-01: витрата за навантаженням, лінійна інтерполяція між вузлами 25/50/75/100/110 %."""
        self.ensure_one()
        p = min(max(load_pct or 0.0, 0.0), 110.0)
        nodes = [
            (25.0, self.fuel_lph_25),
            (50.0, self.fuel_lph_50),
            (75.0, self.fuel_lph_75),
            (100.0, self.fuel_lph_100),
            (110.0, self.fuel_lph_esp),
        ]
        if p <= 25.0:
            return round(nodes[0][1], 1)
        for (x0, y0), (x1, y1) in zip(nodes, nodes[1:], strict=False):
            if p <= x1:
                return round(y0 + (p - x0) / (x1 - x0) * (y1 - y0) + 1e-9, 1)
        return round(nodes[-1][1], 1)

    def autonomy_h(self, fuel_l, load_pct):
        """R-02: автономність у годинах; витрата ≤ 0 -> None."""
        self.ensure_one()
        lph = self.fuel_lph(load_pct)
        if not lph or lph <= 0:
            return None
        return round((fuel_l or 0.0) / lph, 1)

    # --- експорт / застосування ------------------------------------------------------------------------
    def to_relay_profile(self):
        """§8.2: JSON профілю для fake_relay."""
        self.ensure_one()
        timers = dict(TIMER_PRESETS.get(self.timer_preset or "default"))
        return {
            "profile": self.code,
            "rated": {"kva_prp": self.kva_prp, "kw_prp": self.kw_prp, "kva_esp": self.kva_esp, "kw_esp": self.kw_esp},
            "tank_l": self.tank_l,
            "fuel_lph": {
                "25": self.fuel_lph_25,
                "50": self.fuel_lph_50,
                "75": self.fuel_lph_75,
                "100": self.fuel_lph_100,
                "esp": self.fuel_lph_esp,
            },
            "timers": timers,
            "timers_plant": {k: TIMER_PRESETS["plant"][k] for k in PLANT_KEYS},
            "sensors": dict(RELAY_DEFAULTS["sensors"]),
            "alarms": dict(RELAY_DEFAULTS["alarms"]),
            "start": dict(RELAY_DEFAULTS["start"]),
        }

    def action_export_relay_profile(self):
        self.ensure_one()
        content = json.dumps(self.to_relay_profile(), ensure_ascii=False, indent=1).encode()
        att = self.env["ir.attachment"].create(
            {
                "name": "%s.json" % self.code.lower(),
                "res_model": self._name,
                "res_id": self.id,
                "mimetype": "application/json",
                "raw": content,
            }
        )
        return {"type": "ir.actions.act_url", "url": "/web/content/%d?download=true" % att.id, "target": "self"}

    def action_apply_to_td(self):
        self.ensure_one()
        if not self.env.user.has_group("td_factory3d.group_td_manager"):
            raise AccessError(_("Записувати в td_genset може лише менеджер «Завод 3D»."))
        done = skipped = 0
        for link in self.env["td.genset3d.link"].search([("profile_id", "=", self.id)]):
            if td.set_fuel_rate(link.td_genset_ref, self.fuel_lph_75):
                done += 1
            else:
                skipped += 1
        message = _(
            "Записано в td_genset: %(done)s генераторів; пропущено (крива/поля немає): %(skipped)s",
            done=done,
            skipped=skipped,
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"message": message, "type": "info", "sticky": False},
        }
