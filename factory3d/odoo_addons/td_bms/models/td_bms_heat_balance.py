from odoo import Command, _, api, fields, models
from odoo.exceptions import ValidationError

from ..tools import heat, hvac
from .td_bms_hvac_unit import _is_live

DESIGN_FIELDS = [
    "t_out_design",
    "t_in_set",
    "length_m",
    "width_m",
    "height_m",
    "u_wall",
    "u_roof",
    "u_floor",
    "infiltration_ach",
    "winter_oa_share",
    "heat_recovery",
    "air_wh_m3k",
    "ahu_design_share",
    "ahu_supply_c",
    "internal_gains_kw",
    "boilers",
    "boiler_kw",
    "chp_heat_kw",
    "boiler_stage_share",
]
PARAM_FIELDS = DESIGN_FIELDS + ["chp_el_kw", "chp_heat_75_kw", "chp_heat_50_kw", "chp_min_load"]
LIVE_FIELDS = [
    "outdoor_c",
    "heat_need_kw",
    "chp_heat_now_kw",
    "chp_source",
    "boilers_on_calc",
    "boilers_on",
    "boiler_state",
    "boiler_load",
    "boiler_heat_kw",
    "supply_c",
    "return_c",
    "silo_fill",
    "deficit_kw",
    "deviation",
    "deviation_text",
]
MACRO_DEFAULTS = {
    "t_out_design": -15.0,
    "t_in_set": 18.0,
    "u_wall": 0.35,
    "u_roof": 0.25,
    "u_floor": 0.15,
    "infiltration_ach": 0.1,
    "winter_oa_share": 0.5,
    "heat_recovery": 0.78,
    "air_wh_m3k": 0.34,
    "ahu_design_share": 0.85,
    "ahu_supply_c": 21.0,
    "internal_gains_kw": 0.0,
    "boilers": 2,
    "boiler_kw": 495.0,
    "boiler_stage_share": 0.85,
    "chp_min_load": 0.5,
}


class F3dBmsHeatBalance(models.Model):
    _name = "td.bms.heat.balance"
    _description = "Будівля: тепловий баланс"
    _inherit = ["mail.thread"]
    _order = "company_id"

    def _default_plant(self, key, default):
        return float(self.env["ir.config_parameter"].sudo().get_param("td.base.plant_%s_m" % key, default))

    def _default_chp(self, key, default):
        passport = self.env["td.equipment.passport"].sudo().search([("role", "=", "chp")], limit=1)
        if not passport:
            return default
        if key == "power_kw":
            return passport.power_kw or default
        return passport.get_num(key) or default

    name = fields.Char(size=128, required=True, default="Тепловий баланс цеху")
    company_id = fields.Many2one("res.company", required=True, default=lambda s: s.env.company, index=True)
    t_out_design = fields.Float(string="Розрахункова зовнішня, °C", digits=(4, 1), default=-15.0, tracking=True)
    t_in_set = fields.Float(string="Уставка в цеху, °C", digits=(4, 1), default=18.0)
    length_m = fields.Float(string="Довжина, м", digits=(6, 2), default=lambda s: s._default_plant("length", 150))
    width_m = fields.Float(string="Ширина, м", digits=(6, 2), default=lambda s: s._default_plant("width", 72))
    height_m = fields.Float(string="Висота, м", digits=(6, 2), default=lambda s: s._default_plant("height", 9))
    u_wall = fields.Float(string="U стін, Вт/(м²·К)", digits=(5, 3), default=0.35, tracking=True)
    u_roof = fields.Float(string="U покрівлі, Вт/(м²·К)", digits=(5, 3), default=0.25, tracking=True)
    u_floor = fields.Float(string="U підлоги, Вт/(м²·К)", digits=(5, 3), default=0.15, tracking=True)
    infiltration_ach = fields.Float(string="Інфільтрація, обмінів/год", digits=(5, 3), default=0.1)
    winter_oa_share = fields.Float(string="Частка зовнішнього повітря в установках узимку", digits=(4, 2), default=0.5)
    heat_recovery = fields.Float(string="Ефективність рекуперації", digits=(4, 2), default=0.78)
    air_wh_m3k = fields.Float(string="Теплоємність повітря, Вт·год/(м³·К)", digits=(5, 3), default=0.34)
    ahu_design_share = fields.Float(string="Частка номінальної витрати AHU-1 у розрахунку", digits=(4, 2), default=0.85)
    ahu_supply_c = fields.Float(string="Приплив AHU-1, °C", digits=(4, 1), default=21.0)
    internal_gains_kw = fields.Float(
        string="Внутрішні теплонадходження, кВт",
        digits=(8, 1),
        default=0.0,
        help="0 — як у макеті: не враховуються, це запас (Q-11)",
    )
    boilers = fields.Integer(string="Котлів", default=2)
    boiler_kw = fields.Float(string="Потужність котла, кВт", digits=(8, 1), default=495.0)
    boiler_stage_share = fields.Float(string="Поріг вмикання другого котла (частка К1)", digits=(4, 2), default=0.85)
    chp_el_kw = fields.Float(string="КГУ: електрична, кВт", default=lambda s: s._default_chp("power_kw", 800.0))
    chp_heat_kw = fields.Float(string="КГУ: теплова, кВт", default=lambda s: s._default_chp("heat_kw", 856.0))
    chp_heat_75_kw = fields.Float(
        string="КГУ: теплова при 75 %, кВт", default=lambda s: s._default_chp("heat_kw_75", 676.0)
    )
    chp_heat_50_kw = fields.Float(
        string="КГУ: теплова при 50 %, кВт", default=lambda s: s._default_chp("heat_kw_50", 497.0)
    )
    chp_min_load = fields.Float(string="КГУ: мінімальне навантаження", digits=(4, 2), default=0.5)
    line_ids = fields.One2many("td.bms.heat.balance.line", "balance_id", string="Складові")
    total_raw = fields.Float(digits=(10, 2), readonly=True)
    total_kw = fields.Integer(string="Навантаження при розрахунковій, кВт", readonly=True)
    capacity_kw = fields.Integer(string="Котли, кВт", readonly=True)
    reserve = fields.Float(string="Запас із КГУ", digits=(6, 2), readonly=True)
    reserve_boilers = fields.Float(string="Запас котлів", digits=(6, 2), readonly=True)
    note = fields.Char(size=512, readonly=True)
    computed_at = fields.Datetime(readonly=True)
    boiler_equipment_id = fields.Many2one("maintenance.equipment", string="Котельня", ondelete="set null")
    chp_equipment_id = fields.Many2one("maintenance.equipment", string="КГУ", ondelete="set null")
    outdoor_signal_id = fields.Many2one("td.signal", string="Сигнал: зовнішня температура", ondelete="set null")
    boiler_state_signal_id = fields.Many2one("td.signal", string="Сигнал: стан котельні", ondelete="set null")
    boiler_supply_signal_id = fields.Many2one("td.signal", string="Сигнал: подача", ondelete="set null")
    boiler_return_signal_id = fields.Many2one("td.signal", string="Сигнал: зворот", ondelete="set null")
    boiler_heat_signal_id = fields.Many2one("td.signal", string="Сигнал: тепло котлів", ondelete="set null")
    silo_signal_id = fields.Many2one("td.signal", string="Сигнал: заповнення бункера", ondelete="set null")
    chp_heat_signal_id = fields.Many2one("td.signal", string="Сигнал: тепло КГУ", ondelete="set null")
    chp_el_signal_id = fields.Many2one("td.signal", string="Сигнал: електрична потужність КГУ", ondelete="set null")
    mains_signal_id = fields.Many2one("td.signal", string="Сигнал: мережа", ondelete="set null")
    fire_signal_id = fields.Many2one("td.signal", string="Сигнал: пожежна сигналізація", ondelete="set null")
    check_signal_id = fields.Many2one("td.signal", string="Сигнал: перевірка", ondelete="set null")
    # --- живі значення (R-15, R-16) ---
    outdoor_c = fields.Float(string="Зовнішня, °C", digits=(4, 1), compute="_compute_live")
    heat_need_kw = fields.Float(string="Потреба зараз, кВт", digits=(8, 1), compute="_compute_live")
    chp_heat_now_kw = fields.Float(string="Тепло КГУ зараз, кВт", digits=(8, 1), compute="_compute_live")
    chp_source = fields.Selection(
        [("signal", "Сигнал КГУ"), ("calc", "За електричною потужністю"), ("design", "Проєктне (50 %)")],
        string="Джерело тепла КГУ",
        compute="_compute_live",
    )
    boilers_on_calc = fields.Integer(string="Котлів потрібно", compute="_compute_live")
    boilers_on = fields.Integer(string="Котлів працює", compute="_compute_live")
    boiler_state = fields.Char(string="Стан котельні", compute="_compute_live")
    boiler_load = fields.Float(string="Навантаження котлів", digits=(4, 2), compute="_compute_live")
    boiler_heat_kw = fields.Float(string="Тепло котлів, кВт", compute="_compute_live")
    supply_c = fields.Float(string="Подача, °C", compute="_compute_live")
    return_c = fields.Float(string="Зворот, °C", compute="_compute_live")
    silo_fill = fields.Float(string="Бункер", compute="_compute_live")
    deficit_kw = fields.Float(string="Дефіцит тепла, кВт", digits=(8, 1), compute="_compute_live")
    deviation = fields.Selection(
        [("none", "Норма"), ("deficit", "Дефіцит тепла"), ("no_data", "Немає даних")],
        string="Відхилення",
        compute="_compute_live",
    )
    deviation_text = fields.Char(string="Відхилення (текст)", compute="_compute_live")
    deficit_since = fields.Datetime(readonly=True)

    _f3d_bms_balance_company_uniq = models.Constraint("UNIQUE(company_id)", "Тепловий баланс для компанії вже є.")

    @api.constrains(*PARAM_FIELDS)
    def _check_params(self):
        def bad(label):
            raise ValidationError(_("Тепловий баланс: %s поза межами.", label))

        for r in self:
            if min(r.u_wall, r.u_roof, r.u_floor) <= 0:
                bad("U")
            if not 0 <= r.infiltration_ach <= 5:
                bad("інфільтрація")
            if not 0 <= r.winter_oa_share <= 1:
                bad("частка зовнішнього повітря")
            if not 0 <= r.heat_recovery < 1:
                bad("рекуперація")
            if r.t_in_set <= r.t_out_design:
                bad("температури")
            if r.boilers < 0:
                bad("кількість котлів")
            if r.boiler_kw <= 0:
                bad("потужність котла")
            if not 0 < r.boiler_stage_share <= 1:
                bad("поріг другого котла")
            if not r.chp_heat_50_kw <= r.chp_heat_75_kw <= r.chp_heat_kw:
                bad("теплова потужність КГУ")

    def _params(self):
        self.ensure_one()
        return {name: self[name] for name in PARAM_FIELDS}

    # --- проєктний розрахунок ---
    def action_recompute(self):
        units = [
            {"kind": u.kind, "airflow_nom": u.airflow_nom} for u in self.env["td.bms.hvac.unit"].sudo().search([])
        ]
        for rec in self:
            res = heat.design_balance(rec._params(), units)
            lines = [Command.clear()] + [Command.create(line) for line in res["lines"]]
            rec.write(
                {
                    "line_ids": lines,
                    "total_raw": res["total_raw"],
                    "total_kw": res["total_kw"],
                    "capacity_kw": res["capacity_kw"],
                    "reserve": res["reserve"],
                    "reserve_boilers": res["reserve_boilers"],
                    "note": res["note"],
                    "computed_at": fields.Datetime.now(),
                }
            )
            rec.message_post(
                body=_(
                    "Перераховано: %(kw)s кВт, запас %(res)s %%", kw=res["total_kw"], res=round(res["reserve"] * 100)
                )
            )
        return True

    @api.model_create_multi
    def create(self, vals_list):
        recs = super().create(vals_list)
        recs.action_recompute()
        return recs

    def write(self, vals):
        res = super().write(vals)
        if set(vals) & set(PARAM_FIELDS):
            self.action_recompute()
        return res

    def action_reset_macro(self):
        self.write(dict(MACRO_DEFAULTS))
        self.action_recompute()
        return True

    @api.model
    def _f3d_bms_get(self):
        rec = self.search([("company_id", "=", self.env.company.id)], limit=1)
        if not rec:
            rec = self.sudo().create({"company_id": self.env.company.id}).with_env(self.env)
        return rec

    # --- живий баланс ---
    def _f3d_bms_live(self):
        """R-15, R-16: словник живих значень (поля `LIVE_FIELDS` + `need`, `boil`) для огляду, провайдера й крона."""
        self.ensure_one()
        p = self._params()

        def val(sig):
            return sig.last_value if _is_live(sig) else None

        outdoor = val(self.outdoor_signal_id)
        need = sum(self.env["td.bms.hvac.unit"]._f3d_bms_heat_now().values())
        chp, source = heat.chp_heat(val(self.chp_el_signal_id), p, val(self.chp_heat_signal_id))
        state_sig = self.boiler_state_signal_id
        state_text = state_sig.last_text if _is_live(state_sig) else None
        res = heat.live_balance(need, chp, p, state_text)
        check = self.check_signal_id
        text = check.last_text if _is_live(check) else False
        dev = {"немає даних": "no_data", "дефіцит тепла": "deficit"}.get(text, "none") if text else "none"
        silo = val(self.silo_signal_id)
        return {
            "outdoor_c": hvac.OUTDOOR_C if outdoor is None else outdoor,
            "heat_need_kw": round(need, 1),
            "chp_heat_now_kw": round(chp, 1),
            "chp_source": source,
            "boilers_on_calc": res["calc"],
            "boilers_on": res["boilers_on"],
            "boiler_state": res["boiler_state"],
            "boiler_load": res["load"],
            "boiler_heat_kw": val(self.boiler_heat_signal_id) or 0.0,
            "supply_c": val(self.boiler_supply_signal_id) or 0.0,
            "return_c": val(self.boiler_return_signal_id) or 0.0,
            "silo_fill": (silo / 100.0 if silo is not None and silo > 1 else silo) or 0.0,
            "deficit_kw": res["deficit"],
            "deviation": dev,
            "deviation_text": text or False,
            "need": need,
            "boil": res["boil"],
        }

    def _compute_live(self):
        for rec in self:
            live = rec.sudo()._f3d_bms_live()
            for name in LIVE_FIELDS:
                rec[name] = live[name]


class F3dBmsHeatBalanceLine(models.Model):
    _name = "td.bms.heat.balance.line"
    _description = "Будівля: складова теплового балансу"
    _order = "balance_id, sequence"

    balance_id = fields.Many2one("td.bms.heat.balance", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    key = fields.Selection(
        [
            ("trans", "Огородження"),
            ("infil", "Інфільтрація"),
            ("vent_rv", "Дахові установки"),
            ("vent_ahu", "Приплив фасадів"),
            ("internal", "Внутрішні надходження"),
        ],
        required=True,
    )
    name = fields.Char(size=256, required=True)
    kw = fields.Float(digits=(10, 2))
    kw_round = fields.Integer(string="кВт")
    formula = fields.Char(size=512)
