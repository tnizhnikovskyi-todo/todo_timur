import re

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from ..tools import lighting

SIGNAL_FIELDS = (
    "level_signal_id",
    "power_signal_id",
    "scene_signal_id",
    "faults_signal_id",
    "faulty_signal_id",
    "check_signal_id",
)


def _param(env, key, default):
    return env["ir.config_parameter"].sudo().get_param("td.bms." + key, default)


class F3dBmsLightGroup(models.Model):
    _name = "td.bms.light.group"
    _description = "Будівля: група освітлення"
    _inherit = ["mail.thread"]
    _order = "sequence, code"
    _rec_name = "name"
    _rec_names_search = ["name", "code"]
    CODE_RE = re.compile(r"^LT-[A-Z0-9]+(-[A-Z0-9]+)*$")

    code = fields.Char(string="Код", size=32, required=True, index=True, tracking=True)
    name = fields.Char(string="Назва", size=128, required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    zone_id = fields.Many2one("td.zone", string="Зона", required=True, ondelete="restrict", index=True)
    zone_code = fields.Char(related="zone_id.td_code")
    zone_name = fields.Char(related="zone_id.name")
    area_m2 = fields.Float(string="Площа, м²", related="zone_id.area_m2")
    norm_id = fields.Many2one(
        "td.bms.light.norm", string="Вид робіт", required=True, ondelete="restrict", tracking=True
    )
    e_norm = fields.Integer(string="Норма, лк", related="norm_id.lux")
    panel_id = fields.Many2one("td.bms.light.panel", string="Щит", required=True, ondelete="restrict", index=True)
    equipment_id = fields.Many2one("maintenance.equipment", string="Обладнання", ondelete="set null")
    passport_id = fields.Many2one("td.equipment.passport", string="Паспорт світильника", ondelete="set null")
    fixture_kind = fields.Selection(
        [("highbay", "Широка оптика (WB)"), ("highbay_rack", "Вузька оптика над проходами (NB)")],
        string="Тип світильника",
        required=True,
    )
    lumen = fields.Integer(string="Світловий потік, лм", compute="_compute_fixture", store=True, readonly=False)
    watt = fields.Integer(string="Потужність світильника, Вт", compute="_compute_fixture", store=True, readonly=False)
    n_fixtures = fields.Integer(string="Світильників встановлено", required=True, tracking=True)
    uf = fields.Float(
        string="Коефіцієнт використання UF",
        required=True,
        digits=(3, 2),
        default=lambda s: float(_param(s.env, "light_uf", "0.7")),
    )
    mf = fields.Float(
        string="Коефіцієнт експлуатації MF",
        required=True,
        digits=(3, 2),
        default=lambda s: float(_param(s.env, "light_mf", "0.8")),
    )
    n_required = fields.Integer(string="Світильників потрібно", compute="_compute_design", store=True)
    e_calc_raw = fields.Float(compute="_compute_design", store=True, digits=(10, 3))
    e_calc = fields.Integer(string="Розрахункова освітленість, лк", compute="_compute_design", store=True)
    design_ok = fields.Boolean(string="Норму виконано", compute="_compute_design", store=True)
    p_inst_kw = fields.Float(string="Встановлена потужність, кВт", compute="_compute_design", store=True, digits=(8, 2))
    level_design = fields.Float(string="Рівень за проєктом", required=True, digits=(3, 2))
    control_mode = fields.Selection(
        [("shift", "DALI: зміна, 100 %"), ("presence", "DALI: присутність і денне світло")],
        string="Керування",
        required=True,
    )
    check_off = fields.Boolean(string="Перевіряти «вимкнено в робочий час»", default=True)
    check_norm = fields.Boolean(string="Перевіряти норму", compute="_compute_check_norm", store=True, readonly=False)
    calendar_id = fields.Many2one(
        "resource.calendar",
        string="Робочий час",
        help="Порожньо — параметр td.bms.calendar_id або календар компанії",
    )
    dali_group = fields.Integer(string="DALI-група (G)", required=True)
    dali_devices = fields.Char(string="Пристрої DALI", size=256, help="@c.r.s.d1-d2[;@c.r.s.d1-d2…]")
    level_signal_id = fields.Many2one("td.signal", string="Сигнал: рівень", ondelete="set null")
    power_signal_id = fields.Many2one("td.signal", string="Сигнал: потужність", ondelete="set null")
    scene_signal_id = fields.Many2one("td.signal", string="Сигнал: сцена", ondelete="set null")
    faults_signal_id = fields.Many2one("td.signal", string="Сигнал: несправних", ondelete="set null")
    faulty_signal_id = fields.Many2one("td.signal", string="Сигнал: адреси несправних", ondelete="set null")
    check_signal_id = fields.Many2one("td.signal", string="Сигнал: перевірка", ondelete="set null")
    # живі значення (R-05), без store
    level_pct = fields.Float(string="Рівень зараз, %", digits=(5, 1), compute="_compute_live")
    level_source = fields.Selection([("live", "З DALI"), ("design", "Проєктний")], compute="_compute_live")
    e_now = fields.Integer(string="Освітленість зараз, лк", compute="_compute_live")
    p_now_kw = fields.Float(string="Потужність зараз, кВт", digits=(8, 2), compute="_compute_live")
    scene = fields.Integer(string="Остання сцена", compute="_compute_live", help="0 — невідомо")
    faults = fields.Integer(string="Несправних світильників", compute="_compute_live")
    faulty = fields.Char(string="Адреси несправних", compute="_compute_live")
    live_ts = fields.Datetime(compute="_compute_live")
    stale = fields.Boolean(compute="_compute_live")
    deviation = fields.Selection(
        [
            ("none", "Норма"),
            ("off_hours", "Поза робочим часом"),
            ("off_in_work", "Вимкнено в робочий час"),
            ("below_norm", "Нижче норми"),
            ("no_data", "Немає даних"),
            ("no_mains", "Немає мережі"),
        ],
        compute="_compute_live",
        search="_search_deviation",
    )
    deviation_text = fields.Char(compute="_compute_live")
    plan_state = fields.Selection(
        [
            ("ok", "Норма"),
            ("low", "Нижче норми"),
            ("off", "Вимкнено"),
            ("fault", "Є несправні"),
            ("alarm", "Відхилення"),
            ("nodata", "Немає даних"),
        ],
        compute="_compute_live",
    )
    off_since = fields.Datetime(readonly=True, copy=False)
    low_since = fields.Datetime(readonly=True, copy=False)
    request_ids = fields.Many2many("maintenance.request", compute="_compute_requests")
    request_count = fields.Integer(compute="_compute_requests")
    deviation_count = fields.Integer(compute="_compute_deviation_count")
    td_is_manager = fields.Boolean(compute="_compute_is_f3d_manager")
    td_bms_write_enabled = fields.Boolean(compute="_compute_write_enabled")
    note = fields.Text()

    _f3d_bms_group_code_uniq = models.Constraint("UNIQUE(code)", "Код групи освітлення має бути унікальним.")
    _f3d_bms_group_dali_uniq = models.Constraint("UNIQUE(dali_group)", "DALI-група вже використана іншою групою.")
    _f3d_bms_group_checks = models.Constraint(
        "CHECK(n_fixtures >= 1 AND level_design >= 0 AND level_design <= 1 AND uf > 0 AND uf <= 1 "
        "AND mf > 0 AND mf <= 1 AND dali_group BETWEEN 1 AND 16383)",
        "Група освітлення: світильників ≥ 1, рівень 0…1, UF і MF у (0; 1], DALI-група 1…16383.",
    )

    # --- обмеження ------------------------------------------------------------------------------------
    @api.constrains("code")
    def _check_code(self):
        for rec in self:
            if not rec.code or not self.CODE_RE.match(rec.code):
                raise ValidationError("Код групи: LT-<зона>, великі латинські літери, цифри, дефіси.")

    @api.constrains("dali_devices", "n_fixtures", "panel_id")
    def _check_dali_devices(self):
        for rec in self:
            if not rec.dali_devices:
                continue
            try:
                items = lighting.parse_devices(rec.dali_devices)
            except ValueError as e:
                raise ValidationError("Пристрої DALI: %s" % e) from e
            count = lighting.count_devices(items)
            if count != rec.n_fixtures:
                raise ValidationError("Пристроїв DALI %s, а світильників %s." % (count, rec.n_fixtures))
            for c, r, s, d1, _d2 in items:
                if (c, r) != (rec.panel_id.cluster, rec.panel_id.router):
                    raise ValidationError("Адреса @%d.%d.%d.%d не належить щиту %s." % (c, r, s, d1, rec.panel_id.code))

    @api.constrains("zone_id")
    def _check_zone_area(self):
        for rec in self:
            if rec.zone_id.area_m2 <= 0:
                raise ValidationError("Зона %s без контуру: площа 0 м², розрахунок неможливий." % rec.zone_id.td_code)

    # --- обчислення -----------------------------------------------------------------------------------
    @api.depends("passport_id", "fixture_kind")
    def _compute_fixture(self):
        for rec in self:
            lm = rec.passport_id.get_num("lumen") if rec.passport_id else None
            w = rec.passport_id.get_num("watt") if rec.passport_id else None
            d_lm, d_w = lighting.DEFAULT_FIX.get(rec.fixture_kind, (0, 0))
            rec.lumen = int(round(lm if lm is not None else d_lm))
            rec.watt = int(round(w if w is not None else d_w))

    @api.depends("control_mode")
    def _compute_check_norm(self):
        for rec in self:
            rec.check_norm = rec.control_mode == "shift"

    @api.depends("zone_id.area_m2", "norm_id.lux", "lumen", "watt", "n_fixtures", "uf", "mf")
    def _compute_design(self):
        for rec in self:
            n_req, raw, e_calc, ok, p_inst = lighting.design(
                rec.norm_id.lux, rec.zone_id.area_m2, rec.lumen, rec.watt, rec.n_fixtures, rec.uf, rec.mf
            )
            rec.n_required, rec.e_calc_raw, rec.e_calc, rec.design_ok, rec.p_inst_kw = n_req, raw, e_calc, ok, p_inst

    def _compute_is_f3d_manager(self):
        manager = self.env.user.has_group("td_factory3d.group_td_manager")
        for rec in self:
            rec.td_is_manager = manager

    def _td_design_p_now(self):
        """Проєктна потужність зараз: n · W · level_design (R-05 п. 6)."""
        self.ensure_one()
        return round(self.n_fixtures * self.watt * self.level_design / 1000.0, 2)

    def _td_live_values(self):
        """R-05: живі значення групи (словник; використовується й щитом)."""
        self.ensure_one()
        sig = {name: self[name].sudo() for name in SIGNAL_FIELDS}
        level_live = bool(sig["level_signal_id"]) and lighting.is_live(sig["level_signal_id"].status)
        if level_live:
            level, source = min(100.0, max(0.0, sig["level_signal_id"].last_value)), "live"
        else:
            level, source = self.level_design * 100.0, "design"
        power_live = bool(sig["power_signal_id"]) and lighting.is_live(sig["power_signal_id"].status)
        if power_live:
            p_now = sig["power_signal_id"].last_value
        else:
            p_now = round(self.n_fixtures * self.watt * level / 100.0 / 1000.0, 2)
        e_now_raw = self.e_calc_raw * level / 100.0
        scene_live = bool(sig["scene_signal_id"]) and lighting.is_live(sig["scene_signal_id"].status)
        faults_live = bool(sig["faults_signal_id"]) and lighting.is_live(sig["faults_signal_id"].status)
        faulty_sig = sig["faulty_signal_id"]
        faulty_live = bool(faulty_sig) and lighting.is_live(faulty_sig.status)
        check = sig["check_signal_id"]
        deviation_text = (check.last_text or "") if check else ""
        deviation = lighting.DEVIATION_BY_TEXT.get(deviation_text, "none") if check else "none"
        faults = int(sig["faults_signal_id"].last_value) if faults_live else 0
        stale = not level_live
        ts = [s.last_ts for s in (sig["level_signal_id"], sig["power_signal_id"]) if s and s.last_ts]
        tol = float(_param(self.env, "light_norm_tolerance_pct", "5")) / 100.0
        return {
            "level_pct": level,
            "level_source": source,
            "e_now": lighting.round_half_up(e_now_raw),
            "p_now_kw": p_now,
            "power_live": power_live,
            "scene": int(sig["scene_signal_id"].last_value) if scene_live else 0,
            "faults": faults,
            "faulty": (faulty_sig.last_text or "") if faulty_live else "",
            "live_ts": max(ts) if ts else False,
            "stale": stale,
            "deviation": deviation,
            "deviation_text": deviation_text,
            "plan_state": lighting.plan_state(
                faults, deviation, stale, level, self.check_norm, e_now_raw, self.e_norm, tol
            ),
        }

    @api.depends_context("uid")
    @api.depends(
        "level_design",
        "e_calc_raw",
        "n_fixtures",
        "watt",
        "check_norm",
        "e_norm",
        *[f"{n}.{f}" for n in SIGNAL_FIELDS for f in ("last_value", "last_text", "last_ts", "status")],
    )
    def _compute_live(self):
        for rec in self:
            v = rec._td_live_values()
            rec.level_pct = v["level_pct"]
            rec.level_source = v["level_source"]
            rec.e_now = v["e_now"]
            rec.p_now_kw = v["p_now_kw"]
            rec.scene = v["scene"]
            rec.faults = v["faults"]
            rec.faulty = v["faulty"]
            rec.live_ts = v["live_ts"]
            rec.stale = v["stale"]
            rec.deviation = v["deviation"]
            rec.deviation_text = v["deviation_text"]
            rec.plan_state = v["plan_state"]

    def _search_deviation(self, operator, value):
        if operator not in ("=", "!=", "in", "not in"):
            raise UserError("Непідтримуваний оператор пошуку за відхиленням.")
        values = [value] if isinstance(value, str) or not hasattr(value, "__iter__") else list(value)
        positive = operator in ("=", "in")
        recs = self.sudo().with_context(active_test=False).search([])
        ids = [r.id for r in recs if (r._td_live_values()["deviation"] in values) == positive]
        return [("id", "in", ids)]

    def _compute_requests(self):
        Request = self.env["maintenance.request"]
        for rec in self:
            sigs = [rec[n].id for n in SIGNAL_FIELDS if rec[n]]
            reqs = Request.search([("td_signal_id", "in", sigs), ("stage_id.done", "=", False)]) if sigs else Request
            rec.request_ids = reqs
            rec.request_count = len(reqs)

    def _compute_deviation_count(self):
        Dev = self.env.get("td.bms.deviation")
        for rec in self:
            rec.deviation_count = (
                Dev.search_count([("object_code", "=", rec.code), ("state", "=", "open")]) if Dev is not None else 0
            )

    def _compute_write_enabled(self):
        enabled = self.env["ir.config_parameter"].sudo().get_param("td.bms.write_enabled") == "True"
        for rec in self:
            rec.td_bms_write_enabled = enabled

    # --- дії ------------------------------------------------------------------------------------------
    def action_open_command(self):
        self.ensure_one()
        self.env["td.bms.light.command.wizard"]._td_bms_check_operator()
        return {
            "type": "ir.actions.act_window",
            "name": "Керування освітленням",
            "res_model": "td.bms.light.command.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_group_ids": [self.id]},
        }

    def action_f3d_show(self):
        self.ensure_one()
        if self.equipment_id.td_code:
            return self.equipment_id.action_f3d_show()
        return self.zone_id.action_f3d_show()

    def action_view_readings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Графік рівня",
            "res_model": "td.reading",
            "view_mode": "graph,list",
            "domain": [("signal_id", "in", (self.level_signal_id | self.power_signal_id).ids)],
            "context": {"search_default_last_48h": 1},
        }

    def action_view_deviations(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Відхилення",
            "res_model": "td.bms.deviation",
            "view_mode": "list,form",
            "domain": [("object_code", "=", self.code)],
        }

    def action_view_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Заявки",
            "res_model": "maintenance.request",
            "view_mode": "list,form",
            "domain": [("id", "in", self.request_ids.ids)],
        }

    # --- контракти ------------------------------------------------------------------------------------
    @api.model
    def _td_bms_light_power(self):
        """CH-03: {code: {zone, panel, p_now_kw, p_inst_kw, level_pct}} для активних груп."""
        res = {}
        for g in self.search([]):
            v = g._td_live_values()
            res[g.code] = {
                "zone": g.zone_code,
                "panel": g.panel_id.code,
                "p_now_kw": v["p_now_kw"],
                "p_inst_kw": g.p_inst_kw,
                "level_pct": v["level_pct"],
            }
        return res

    @api.model
    def _td_bms_kwh(self, date_from, date_to):
        """CH-03: кВт·год за [date_from, date_to) з годинних агрегатів сигналу потужності."""
        groups = self.search([])
        sig_ids = groups.power_signal_id.ids
        sums = {}
        if sig_ids:
            rows = (
                self.env["td.reading.hour"]
                .sudo()
                ._read_group(
                    [("signal_id", "in", sig_ids), ("hour", ">=", date_from), ("hour", "<", date_to)],
                    ["signal_id"],
                    ["v_avg:sum"],
                )
            )
            sums = {sig.id: total for sig, total in rows}
        return {g.code: round(sums.get(g.power_signal_id.id, 0.0), 2) for g in groups}
