import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..tools import hvac

SIGNAL_FIELDS = [
    ("airflow_signal_id", "витрата"),
    ("supply_signal_id", "приплив"),
    ("indoor_signal_id", "у зоні"),
    ("filter_signal_id", "фільтр припливу"),
    ("filter_extract_signal_id", "фільтр витяжки"),
    ("valve_signal_id", "клапан нагріву"),
    ("heat_signal_id", "тепло"),
    ("power_signal_id", "потужність"),
    ("mode_signal_id", "режим"),
    ("state_signal_id", "стан"),
    ("sp_day_signal_id", "уставка день"),
    ("sp_night_signal_id", "уставка ніч"),
    ("pressure_signal_id", "тиск у дільниці"),
    ("interlock_signal_id", "блокування з камерами"),
    ("check_signal_id", "перевірка"),
]
DEVIATIONS = [
    ("none", "Норма"),
    ("off_hours", "Поза робочим часом"),
    ("not_running", "Не працює в робочий час"),
    ("cold", "Холодно в зоні"),
    ("no_data", "Немає даних"),
    ("fire", "Зупинено пожежною сигналізацією"),
    ("no_mains", "Немає мережі"),
]
# тексти сигналу перевірки (SPEC §10.2) → значення `deviation`
CHECK_TEXTS = {
    "норма": "none",
    "поза робочим часом": "off_hours",
    "не працює в робочий час": "not_running",
    "холодно в зоні": "cold",
    "немає даних": "no_data",
    "зупинено пожежною сигналізацією": "fire",
    "немає мережі": "no_mains",
}
LIVE_STATUSES = ("ok", "warn", "alarm")
LIVE_FIELDS = [
    "airflow_m3h",
    "k",
    "supply_c",
    "indoor_c",
    "filter_dp_pa",
    "filter_extract_dp_pa",
    "heating_valve",
    "heat_kw",
    "p_now_kw",
    "mode_code",
    "mode_label",
    "state",
    "setpoint_day_c",
    "setpoint_night_c",
    "room_pressure_pa",
    "live_ts",
    "stale",
    "deviation",
    "deviation_text",
    "alarm_count",
    "plan_state",
]


def _is_live(sig):
    return bool(sig) and sig.status in LIVE_STATUSES and bool(sig.last_ts)


class F3dBmsHvacUnit(models.Model):
    _name = "td.bms.hvac.unit"
    _description = "Будівля: установка вентиляції"
    _inherit = ["mail.thread"]
    _order = "sequence, code"
    _rec_name = "name"
    _rec_names_search = ["name", "code"]
    CODE_RE = re.compile(r"^(RV-\d{2}|AHU-\d{1,2}|EF-[A-Z]{2,8})$")

    code = fields.Char(string="Код", size=16, required=True, index=True, tracking=True)
    name = fields.Char(string="Назва", size=128, required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    kind = fields.Selection(
        [
            ("roofvent", "Дахова установка"),
            ("ahu", "Припливна установка"),
            ("fan", "Витяжний вентилятор"),
            ("exfan", "Витяжний вентилятор (Ex)"),
        ],
        string="Вид",
        required=True,
    )
    zone_id = fields.Many2one("td.zone", string="Зона", required=True, ondelete="restrict", index=True)
    zone_name = fields.Char(related="zone_id.name")
    x = fields.Float(string="X, м", digits=(8, 2))
    y = fields.Float(string="Y, м", digits=(8, 2))
    equipment_id = fields.Many2one("maintenance.equipment", string="Обладнання", ondelete="set null")
    passport_id = fields.Many2one("td.equipment.passport", string="Паспорт", ondelete="set null")
    source_id = fields.Many2one(
        "td.source", string="Джерело BACnet", domain="[('type','=','bacnet_ip')]", ondelete="set null"
    )
    bacnet_device = fields.Integer(string="BACnet device")
    fan_count = fields.Integer(string="Вентиляторів", default=1)
    airflow_nom = fields.Float(
        string="Номінальна витрата, м³/год", digits=(10, 0), compute="_compute_nominals", store=True, readonly=False
    )
    heat_nom_kw = fields.Float(
        string="Теплова потужність нагрівача, кВт",
        digits=(8, 1),
        compute="_compute_nominals",
        store=True,
        readonly=False,
    )
    p_inst_kw = fields.Float(
        string="Потужність вентиляторів, кВт", digits=(8, 3), compute="_compute_nominals", store=True, readonly=False
    )
    required_m3h = fields.Float(string="Потрібна витрата, м³/год", digits=(8, 1))
    mode_design = fields.Selection(
        [
            ("VE", "VE — приплив і витяжка"),
            ("VEL", "VEL — знижена вентиляція"),
            ("AQ", "AQ — рекуперація за якістю повітря"),
            ("REC", "REC — рециркуляція"),
            ("EA", "EA — витяжка"),
            ("SA", "SA — приплив"),
            ("ST", "ST — очікування"),
            ("Off", "Вимкнено"),
            ("thermostat", "За термостатом"),
            ("charging", "Під час заряджання"),
        ],
        string="Режим за проєктом",
        required=True,
    )
    required_in_work = fields.Boolean(string="Має працювати в робочий час", default=True)
    t_supply_design = fields.Float(string="Приплив за проєктом, °C", digits=(4, 1))
    calendar_id = fields.Many2one("resource.calendar", string="Робочий календар")
    note = fields.Text(string="Примітка")

    airflow_signal_id = fields.Many2one("td.signal", string="Сигнал: витрата", ondelete="set null")
    supply_signal_id = fields.Many2one("td.signal", string="Сигнал: приплив", ondelete="set null")
    indoor_signal_id = fields.Many2one("td.signal", string="Сигнал: у зоні", ondelete="set null")
    filter_signal_id = fields.Many2one("td.signal", string="Сигнал: фільтр припливу", ondelete="set null")
    filter_extract_signal_id = fields.Many2one("td.signal", string="Сигнал: фільтр витяжки", ondelete="set null")
    valve_signal_id = fields.Many2one("td.signal", string="Сигнал: клапан нагріву", ondelete="set null")
    heat_signal_id = fields.Many2one("td.signal", string="Сигнал: тепло", ondelete="set null")
    power_signal_id = fields.Many2one("td.signal", string="Сигнал: потужність", ondelete="set null")
    mode_signal_id = fields.Many2one("td.signal", string="Сигнал: режим", ondelete="set null")
    state_signal_id = fields.Many2one("td.signal", string="Сигнал: стан", ondelete="set null")
    sp_day_signal_id = fields.Many2one("td.signal", string="Сигнал: уставка день", ondelete="set null")
    sp_night_signal_id = fields.Many2one("td.signal", string="Сигнал: уставка ніч", ondelete="set null")
    pressure_signal_id = fields.Many2one("td.signal", string="Сигнал: тиск у дільниці", ondelete="set null")
    interlock_signal_id = fields.Many2one("td.signal", string="Сигнал: блокування з камерами", ondelete="set null")
    check_signal_id = fields.Many2one("td.signal", string="Сигнал: перевірка", ondelete="set null")

    # --- живі значення (R-12, не зберігаються) ---
    airflow_m3h = fields.Float(string="Витрата, м³/год", digits=(10, 1), compute="_compute_live")
    k = fields.Float(string="Частка номінальної витрати", digits=(4, 3), compute="_compute_live")
    supply_c = fields.Float(string="Приплив, °C", digits=(5, 1), compute="_compute_live")
    indoor_c = fields.Float(string="У зоні, °C", digits=(5, 1), compute="_compute_live")
    filter_dp_pa = fields.Float(string="Фільтр припливу, Па", digits=(6, 1), compute="_compute_live")
    filter_extract_dp_pa = fields.Float(string="Фільтр витяжки, Па", digits=(6, 1), compute="_compute_live")
    heating_valve = fields.Float(string="Клапан нагріву", digits=(4, 2), compute="_compute_live")
    heat_kw = fields.Float(string="Тепло, кВт", digits=(8, 1), compute="_compute_live")
    p_now_kw = fields.Float(string="Потужність зараз, кВт", digits=(8, 3), compute="_compute_live")
    mode_code = fields.Char(string="Режим (код)", compute="_compute_live")
    mode_label = fields.Char(string="Режим", compute="_compute_live")
    state = fields.Selection(
        [("on", "Працює"), ("standby", "Очікування"), ("off", "Вимкнено"), ("fault", "Аварія")],
        string="Стан",
        compute="_compute_live",
    )
    setpoint_day_c = fields.Float(string="Уставка день, °C", digits=(5, 1), compute="_compute_live")
    setpoint_night_c = fields.Float(string="Уставка ніч, °C", digits=(5, 1), compute="_compute_live")
    room_pressure_pa = fields.Float(string="Тиск у дільниці, Па", digits=(5, 1), compute="_compute_live")
    live_ts = fields.Datetime(string="Час показань", compute="_compute_live")
    stale = fields.Boolean(string="Немає живих даних", compute="_compute_live")
    deviation = fields.Selection(DEVIATIONS, string="Відхилення", compute="_compute_live", search="_search_deviation")
    deviation_text = fields.Char(string="Відхилення (текст)", compute="_compute_live")
    alarm_count = fields.Integer(string="Тривог", compute="_compute_live")
    plan_state = fields.Selection(
        [("on", "Працює"), ("standby", "Очікування"), ("alarm", "Відхилення"), ("nodata", "Немає даних")],
        string="Стан на плані",
        compute="_compute_live",
    )
    off_since = fields.Datetime(string="Не працює з", readonly=True, copy=False)
    cold_since = fields.Datetime(string="Холодно з", readonly=True, copy=False)
    cold_off_since = fields.Datetime(string="Холодно поза робочим часом з", readonly=True, copy=False)
    request_ids = fields.Many2many("maintenance.request", compute="_compute_requests")
    request_count = fields.Integer(compute="_compute_requests")
    deviation_count = fields.Integer(compute="_compute_requests")
    td_bms_write_enabled = fields.Boolean(compute="_compute_write_enabled")

    _f3d_bms_unit_code_uniq = models.Constraint("UNIQUE(code)", "Код установки має бути унікальним.")
    _f3d_bms_unit_checks = models.Constraint(
        "CHECK(fan_count >= 1 AND (airflow_nom IS NULL OR airflow_nom >= 0) AND (p_inst_kw IS NULL OR p_inst_kw >= 0))",
        "Установка: вентиляторів ≥ 1, номінали ≥ 0.",
    )

    # --- номінали ---
    @api.depends(
        "kind",
        "fan_count",
        "passport_id",
        "passport_id.spec_ids",
        "passport_id.spec_ids.value_num",
        "passport_id.power_kw",
    )
    def _compute_nominals(self):
        for rec in self:
            get_num = rec.passport_id.get_num if rec.passport_id else (lambda key: None)
            nom = hvac.nominals(rec.kind or "roofvent", rec.fan_count, get_num)
            rec.airflow_nom = nom["airflow_nom"]
            rec.heat_nom_kw = nom["heat_nom_kw"]
            rec.p_inst_kw = nom["p_inst_kw"]

    @api.onchange("kind", "passport_id")
    def _onchange_required_m3h(self):
        for rec in self:
            if rec.kind == "exfan" and not rec.required_m3h:
                rec.required_m3h = hvac.nominals(
                    "exfan", 1, rec.passport_id.get_num if rec.passport_id else (lambda key: None)
                )["required_m3h"]

    @api.constrains("code")
    def _check_code(self):
        for rec in self:
            if not rec.code or not self.CODE_RE.match(rec.code):
                raise ValidationError(_("Код установки: RV-NN, AHU-N або EF-<назва>."))

    @api.constrains("source_id", "bacnet_device")
    def _check_bacnet_device(self):
        for rec in self:
            if rec.source_id and rec.bacnet_device:
                device = (rec.source_id.params or {}).get("device")
                if device != rec.bacnet_device:
                    raise ValidationError(
                        _(
                            "BACnet device %(dev)s не збігається з джерелом %(src)s (device %(sd)s).",
                            dev=rec.bacnet_device,
                            src=rec.source_id.code,
                            sd=device,
                        )
                    )

    @api.constrains("kind", "mode_design")
    def _check_mode_design(self):
        for rec in self:
            if rec.kind in ("roofvent", "ahu") and rec.mode_design in ("thermostat", "charging"):
                raise ValidationError(_("Режим «%s» — лише для вентиляторів.", rec.mode_design))

    # --- живі значення ---
    @api.model
    def _f3d_bms_static_units(self):
        """Статика макета `ventilation.units[code]` (R-12); ключі — як у payload R-27. Підміняється розділом
        провайдера/тестом через контекст `f3d_bms_static_units`."""
        return self.env.context.get("f3d_bms_static_units") or {}

    @api.model
    def _f3d_bms_env_params(self):
        """(t_set, t_out) для формул R-13: уставка балансу й живий зовнішній (інакше 9,0)."""
        bal = self.env["td.bms.heat.balance"].sudo().search([("company_id", "=", self.env.company.id)], limit=1)
        t_set = bal.t_in_set if bal else 18.0
        t_out = bal.outdoor_signal_id.last_value if bal and _is_live(bal.outdoor_signal_id) else hvac.OUTDOOR_C
        return t_set, t_out

    def _signals(self):
        self.ensure_one()
        return self.env["td.signal"].browse([self[f].id for f, _l in SIGNAL_FIELDS if self[f]])

    def _compute_live(self):
        static_all = self._f3d_bms_static_units()
        t_set, t_out = self._f3d_bms_env_params()
        for rec in self:
            vals = rec.sudo()._live_values(static_all.get(rec.code) or {}, t_set, t_out)
            for name in LIVE_FIELDS:
                rec[name] = vals.get(name, False)

    def _live_values(self, st, t_set, t_out):
        """R-10…R-13: словник живих значень однієї установки."""
        self.ensure_one()
        kind = self.kind

        def live_val(sig):
            return sig.last_value if _is_live(sig) else None

        air = live_val(self.airflow_signal_id)
        state_live = self.state_signal_id.last_text if _is_live(self.state_signal_id) else None
        mode_code = (
            self.mode_signal_id.last_text if _is_live(self.mode_signal_id) and self.mode_signal_id.last_text else False
        )
        air_live = air is not None
        if air is None:
            air = st.get("airflow_m3h") or 0.0
        k = hvac.share(air, self.airflow_nom)
        state = hvac.unit_state(kind, state_live, mode_code)
        stale = (state_live is None) if kind in ("fan", "exfan") else (not air_live)
        if state is None:
            state = st.get("state") or "standby"
            if kind in ("fan", "exfan") and not state_live and not st.get("state"):
                state = "on" if self.required_in_work and air else "standby"
        running = state == "on"
        mode = mode_code or self.mode_design
        fb = hvac.fallback_heat(
            kind, k, mode, t_out, t_set, self.heat_nom_kw, self.p_inst_kw, air, self.t_supply_design or 21.0
        )
        if kind in ("fan", "exfan"):
            fb["p_now"] = hvac.fallback_power(kind, k, self.p_inst_kw, running)

        def pick(live, static_key, fallback, prefer_formula=False):
            """R-12: живий сигнал → (жива витрата → формула R-13) → статика → формула R-13."""
            if live is not None:
                return live
            if prefer_formula and air_live and fallback is not None:
                return fallback
            if st.get(static_key) is not None:
                return st[static_key]
            return fallback

        heat = pick(live_val(self.heat_signal_id), "heat_kw", fb["heat"], True) if kind in ("roofvent", "ahu") else 0.0
        valve_live = live_val(self.valve_signal_id)
        valve_fb = fb["valve"] if kind == "roofvent" else (0.0 if kind == "ahu" else None)
        valve = pick(
            valve_live / 100.0 if valve_live is not None else None, "heating_valve", valve_fb, kind == "roofvent"
        )
        p_now = pick(live_val(self.power_signal_id), "p_now", fb["p_now"], True)
        sig_alarm = len(self._signals().filtered(lambda s: s.status == "alarm"))
        check = self.check_signal_id
        text = check.last_text if _is_live(check) else False
        if check and not text:
            dev = "no_data"
        else:
            dev = CHECK_TEXTS.get(text, "none") if text else "none"
        ts = [s.last_ts for s in (self.airflow_signal_id, self.state_signal_id) if _is_live(s)]
        if dev in ("none", "off_hours") and not sig_alarm:
            plan = "nodata" if stale else ("on" if state == "on" else "standby")
        elif dev == "no_data":
            plan = "nodata"
        else:
            plan = "alarm"
        return {
            "airflow_m3h": air,
            "k": k,
            "state": state,
            "stale": stale,
            "mode_code": mode_code,
            "mode_label": hvac.mode_label(
                kind, mode_code, self.mode_design, running, self.fan_count, self.required_m3h
            ),
            "supply_c": pick(live_val(self.supply_signal_id), "supply_c", 0.0),
            "indoor_c": pick(live_val(self.indoor_signal_id), "indoor_c", 0.0),
            "filter_dp_pa": pick(live_val(self.filter_signal_id), "filter_dp_pa", 0.0),
            "filter_extract_dp_pa": pick(live_val(self.filter_extract_signal_id), "filter_extract_dp_pa", 0.0),
            "heat_kw": heat,
            "heating_valve": valve or 0.0,
            "p_now_kw": p_now,
            "setpoint_day_c": pick(live_val(self.sp_day_signal_id), "setpoint_day_c", 0.0),
            "setpoint_night_c": pick(live_val(self.sp_night_signal_id), "setpoint_night_c", 0.0),
            "room_pressure_pa": pick(live_val(self.pressure_signal_id), "room_pressure_pa", 0.0),
            "live_ts": max(ts) if ts else False,
            "deviation": dev,
            "deviation_text": text or False,
            "alarm_count": sig_alarm,
            "plan_state": plan,
        }

    @api.model
    def _search_deviation(self, operator, value):
        if operator not in ("=", "!=", "in", "not in"):
            raise UserError(_("Непідтримуваний оператор пошуку за відхиленням."))
        values = value if isinstance(value, (list, tuple)) else [value]
        texts = [t for t, d in CHECK_TEXTS.items() if d in values]
        positive = operator in ("=", "in")
        if not texts:
            return [("id", "!=", 0)] if not positive else [("id", "=", 0)]
        ids = self.env["td.signal"].sudo().search([("last_text", "in", texts)]).ids
        domain = [("check_signal_id", "in", ids)]
        return domain if positive else [("check_signal_id", "not in", ids)]

    def _compute_requests(self):
        has_dev = "td.bms.deviation" in self.env
        for rec in self:
            sigs = rec.sudo()._signals()
            reqs = (
                self.env["maintenance.request"].search(
                    [("td_signal_id", "in", sigs.ids), ("stage_id.done", "=", False)]
                )
                if sigs
                else self.env["maintenance.request"]
            )
            rec.request_ids = reqs
            rec.request_count = len(reqs)
            rec.deviation_count = (
                self.env["td.bms.deviation"]
                .sudo()
                .search_count([("object_code", "=", rec.code), ("state", "=", "open")])
                if has_dev
                else 0
            )

    def _compute_write_enabled(self):
        enabled = self.env["ir.config_parameter"].sudo().get_param("td.bms.write_enabled") == "True"
        for rec in self:
            rec.td_bms_write_enabled = enabled

    # --- дії ---
    def action_f3d_show(self):
        self.ensure_one()
        target = self.equipment_id if self.equipment_id.td_code else self.zone_id
        return target.action_f3d_show()

    def action_open_command(self):
        self.ensure_one()
        if self.kind not in ("roofvent", "ahu"):
            raise UserError(_("Керування вентиляторами EF не передбачено (ARCH §1.4)."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Керування вентиляцією"),
            "res_model": "td.bms.hvac.command.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_unit_ids": [self.id]},
        }

    def action_view_readings(self):
        self.ensure_one()
        sigs = self.airflow_signal_id | self.filter_signal_id | self.supply_signal_id | self.heat_signal_id
        return {
            "type": "ir.actions.act_window",
            "name": _("Графіки: %s", self.code),
            "res_model": "td.reading",
            "view_mode": "graph,list",
            "domain": [("signal_id", "in", sigs.ids)],
            "context": {"search_default_last_48h": 1},
        }

    def action_view_deviations(self):
        self.ensure_one()
        if "td.bms.deviation" not in self.env:
            raise UserError(_("Журнал відхилень недоступний."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Відхилення: %s", self.code),
            "res_model": "td.bms.deviation",
            "view_mode": "list,form",
            "domain": [("object_code", "=", self.code)],
        }

    def action_view_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Заявки: %s", self.code),
            "res_model": "maintenance.request",
            "view_mode": "list,form",
            "domain": [("id", "in", self.request_ids.ids)],
        }

    @api.model
    def _f3d_bms_heat_now(self):
        """CH-03: {code: heat_kw} для дахових установок і AHU."""
        units = self.sudo().search([("kind", "in", ("roofvent", "ahu"))])
        return {u.code: u.heat_kw for u in units}
