"""M-01 `td.chp.unit` — паспорт агрегата КГУ."""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..tools import signals

SIGNAL_ACTION = "td_chp.action_td_chp_signal"
TH_FIELDS = (
    "gas_min_bar",
    "gas_warn_bar",
    "ret_set_c",
    "jacket_warn_c",
    "jacket_max_c",
    "bat_min_v",
    "oil_min_pct",
    "lel_warn_pct",
    "lel_alarm_pct",
    "nox_limit",
    "co_limit",
    "cyl_dev_warn_k",
    "cyl_dev_alarm_k",
    "knock_warn",
    "knock_alarm",
    "plug_interval_h",
    "lhv_kwh_m3",
    "co2_kg_m3",
)
PASSPORT_FIELDS = (
    "manufacturer",
    "model",
    "engine",
    "fuel",
    "p_nom_kw",
    "u_nom_v",
    "f_nom_hz",
    "rpm_nom",
    "i_nom_a",
)


class TdChpUnit(models.Model):
    _name = "td.chp.unit"
    _description = "КГУ: агрегат (паспорт)"
    _inherit = ["mail.thread"]
    _order = "sequence, id"

    _td_chp_unit_code_uniq = models.Constraint("UNIQUE(code, company_id)", "Код агрегата має бути унікальним.")

    def _default_equipment(self):
        eq = self.env.ref("td_factory3d.eq_chp", raise_if_not_found=False)
        if not eq or eq._name != "maintenance.equipment":
            eq = self.env["maintenance.equipment"].sudo().search([("td_code", "=", "CHP")], limit=1)
        return eq.id if eq else False

    def _default_source(self):
        src = self.env.ref("td_chp.source_chp_u72", raise_if_not_found=False)
        return src.id if src else False

    name = fields.Char(string="Назва", required=True, tracking=True)
    code = fields.Char(string="Код", required=True, default="CHP", copy=False, tracking=True)
    equipment_id = fields.Many2one(
        "maintenance.equipment", string="Обладнання", default=_default_equipment, ondelete="set null", tracking=True
    )
    source_id = fields.Many2one("td.source", string="Джерело даних", default=_default_source, ondelete="set null")
    manufacturer = fields.Char(string="Виробник", default="TEDOM a.s.")
    model = fields.Char(string="Модель", default="Quanto D800 NG")
    engine = fields.Char(string="Двигун", default="MWM TCG 3016 V16")
    fuel = fields.Char(string="Паливо", default="Природний газ")
    cylinders = fields.Integer(string="Циліндрів", default=16)
    p_nom_kw = fields.Float(string="P ном., кВт", default=800.0)
    u_nom_v = fields.Float(string="U ном., В", default=400.0)
    f_nom_hz = fields.Float(string="f ном., Гц", default=50.0)
    rpm_nom = fields.Float(string="Оберти ном., об/хв", default=1500.0)
    i_nom_a = fields.Float(string="I ном., А", default=1178.0)
    lhv_kwh_m3 = fields.Float(string="Теплота згоряння, кВт·год/м³", default=9.5)
    co2_kg_m3 = fields.Float(string="Викиди CO₂, кг/м³ газу", default=1.98)
    gas_min_bar = fields.Float(string="Тиск газу мін., бар", default=1.5)
    gas_warn_bar = fields.Float(string="Тиск газу: увага, бар", default=1.7)
    ret_set_c = fields.Float(string="Уставка зворотки, °C", default=70.0)
    jacket_warn_c = fields.Float(string="t ОЖ: увага, °C", default=92.0)
    jacket_max_c = fields.Float(string="t ОЖ макс., °C", default=95.0)
    bat_min_v = fields.Float(string="АКБ мін., В", default=23.5)
    oil_min_pct = fields.Float(string="Рівень масла мін., %", default=40.0)
    lel_warn_pct = fields.Float(string="Загазованість: увага, % НКПР", default=10.0)
    lel_alarm_pct = fields.Float(string="Загазованість: аварія, % НКПР", default=20.0)
    nox_limit = fields.Float(string="NOx, ліміт, мг/нм³", default=250.0)
    co_limit = fields.Float(string="CO, ліміт, мг/нм³", default=300.0)
    cyl_dev_warn_k = fields.Float(string="Розкид циліндрів: увага, К", default=25.0)
    cyl_dev_alarm_k = fields.Float(string="Розкид циліндрів: аварія, К", default=40.0)
    knock_warn = fields.Float(string="Детонація: увага, од.", default=35.0)
    knock_alarm = fields.Float(string="Детонація: аварія, од.", default=60.0)
    plug_interval_h = fields.Float(string="Інтервал заміни свічок, год", default=4000.0)
    is_assumption = fields.Boolean(string="Паспорт — допущення", default=True)
    note = fields.Text(string="Примітка")
    state_code = fields.Integer(string="Стан (код)", readonly=True, default=0)
    state_ts = fields.Datetime(string="Стан змінено", readonly=True)
    comm_lost = fields.Boolean(string="Зв'язок втрачено", readonly=True, default=False)
    rule_ids = fields.One2many("td.chp.maintenance.rule", "unit_id", string="Правила ТО")
    active = fields.Boolean(default=True)
    company_id = fields.Many2one("res.company", string="Компанія", default=lambda self: self.env.company)
    sequence = fields.Integer(default=10)

    @api.constrains("cylinders")
    def _check_cylinders(self):
        for rec in self:
            if rec.cylinders != 16:
                raise ValidationError(_("У версії 1 пульт підтримує лише V16."))

    @api.constrains("lhv_kwh_m3", "co2_kg_m3")
    def _check_kpi_constants(self):
        for rec in self:
            if rec.lhv_kwh_m3 <= 0 or rec.co2_kg_m3 <= 0:
                raise ValidationError(_("Теплота згоряння й викиди CO₂ мають бути більшими за нуль."))

    # --- службові (R-01, R-07) ------------------------------------------------------------------------------------
    def _td_signal(self, key):
        """Сигнал `chp/<key>` (запис `td.signal`, порожній, якщо немає)."""
        self.ensure_one()
        return self.env["td.signal"].sudo().search([("code", "=", signals.PREFIX + key)], limit=1)

    def _td_value(self, key):
        """R-01: свіже значення сигналу або None (немає, застаріло)."""
        self.ensure_one()
        sig = self._td_signal(key)
        if not sig or not signals.is_fresh(
            sig.last_ts, sig.period_s, signals.now(self.env), signals.cparam_int(self.env, "stale_s")
        ):
            return None
        return sig.last_value

    def _td_remote_switching(self):
        """Дозвіл дистанційного пуску (`td.chp.remote_switching_enabled`); міст підставляє налаштування td_energy."""
        self.ensure_one()
        return signals.cparam_bool(self.env, "remote_switching_enabled")

    def _td_th(self):
        self.ensure_one()
        return {f: self[f] for f in TH_FIELDS}

    def _td_passport(self):
        self.ensure_one()
        return {f: self[f] for f in PASSPORT_FIELDS}

    @api.model
    def _td_get(self, code=None):
        """Агрегат за кодом (None — перший активний) з урахуванням прав і правил користувача; невідомий → UserError."""
        domain = [("code", "=", code)] if code else []
        unit = self.search(domain, limit=1)
        if not unit:
            raise UserError(_("Невідомий агрегат: %s.", code) if code else _("Агрегат КГУ не налаштований."))
        return unit

    # --- дії --------------------------------------------------------------------------------------------------------
    def action_open_pult(self):
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "td_chp.pult",
            "name": _("Пульт КГУ"),
            "context": {"unit_code": self.code},
        }

    def action_open_map(self):
        return self.env["ir.actions.act_window"]._for_xml_id(SIGNAL_ACTION)

    def action_reset_map(self):
        """R-14: перезаписати адреси, типи, множники, одиниці, періоди й пороги сигналів із типової карти."""
        if not self.env.user.has_group("td_factory3d.group_td_manager"):
            raise AccessError(_("Відновити типову карту може лише менеджер."))
        for rec in self:
            signals.sync_map(self.env, rec, reset=True)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("Карта регістрів"), "message": _("Типову карту відновлено."), "type": "success"},
        }
