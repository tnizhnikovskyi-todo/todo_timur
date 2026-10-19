import re
from datetime import timedelta, timezone

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..tools import sld
from ..tools.tariff import to_local


def _today_start_utc():
    """Початок поточної доби за Києвом у UTC (naive, як у Odoo). R-20: повна версія — `tools/dates.py` (W2)."""
    start = to_local(fields.Datetime.now()).replace(hour=0, minute=0, second=0, microsecond=0)
    return start.astimezone(timezone.utc).replace(tzinfo=None)


class F3dEnergyNode(models.Model):
    _name = "td.energy.node"
    _description = "Енергетика: вузол мережі"
    _inherit = ["mail.thread"]
    _parent_name = "parent_id"
    _parent_store = True
    _order = "sequence, code"
    _rec_name = "name"
    _rec_names_search = ["name", "code"]
    CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{0,31}$")
    KINDS = [
        ("input", "Ввід мережі"),
        ("substation", "РУ 10 кВ"),
        ("transformer", "Трансформатор"),
        ("switchboard", "ГРЩ"),
        ("section", "Секція шин"),
        ("cell", "Шафа ГРЩ"),
        ("line", "Лінія"),
        ("tapoff", "Відгалуження"),
        ("consumer", "Споживач"),
        ("generator", "Генерація"),
        ("storage", "Накопичувач"),
        ("ats", "АВР"),
    ]
    NEEDS_PARENT = ("consumer", "cell", "line", "tapoff", "section", "transformer", "substation")

    code = fields.Char(string="Код", size=32, required=True, index=True, copy=False, tracking=True)
    name = fields.Char(string="Назва", size=128, required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    kind = fields.Selection(KINDS, string="Вид", required=True, index=True, tracking=True)
    cell_type = fields.Selection(
        [
            ("incomer", "Ввідна"),
            ("feeder", "Фідер шинопроводу"),
            ("cable", "Кабельні фідери"),
            ("coupler", "Секційний вимикач"),
            ("pfc", "Компенсація"),
        ],
        string="Тип шафи",
    )
    line_kind = fields.Selection([("busway", "Шинопровід"), ("cable", "Кабелі")], string="Тип лінії")
    gen_kind = fields.Selection(
        [
            ("pv_inverters", "СЕС: група інверторів"),
            ("pv_inverter", "Інвертор СЕС"),
            ("pv_field", "Поле модулів СЕС"),
            ("chp", "Когенерація"),
            ("genset", "Дизель-генератор"),
        ],
        string="Тип генерації",
    )
    parent_id = fields.Many2one("td.energy.node", string="Живиться від", ondelete="restrict", index=True)
    parent_path = fields.Char(index=True)
    child_ids = fields.One2many("td.energy.node", "parent_id", string="Живить")
    cabinet_id = fields.Many2one(
        "td.energy.node", string="Шафа (збірка)", domain="[('kind', '=', 'switchboard')]", ondelete="set null"
    )
    peer_id = fields.Many2one("td.energy.node", string="З'єднує з", ondelete="set null")
    section = fields.Integer(string="Секція шин", default=0)
    equipment_id = fields.Many2one("maintenance.equipment", string="Обладнання", ondelete="set null", index=True)
    equipment_code = fields.Char(related="equipment_id.td_code")
    workcenter_id = fields.Many2one("mrp.workcenter", string="Робочий центр", ondelete="set null", index=True)
    zone_id = fields.Many2one("td.zone", related="equipment_id.td_zone_id", string="Зона")
    rating_a = fields.Integer(string="Номінал, А")
    rating_kva = fields.Integer(string="Номінал, кВА")
    rating_kvar = fields.Integer(string="Номінал, квар")
    voltage_kv = fields.Float(string="Напруга, кВ", digits=(5, 2), default=0.4)
    p_inst_kw = fields.Float(string="Встановлена, кВт", digits=(10, 2))
    p_inst_source = fields.Selection(
        [("passport", "Паспорт"), ("estimate", "Оцінка"), ("mixed", "Паспорт + оцінка")],
        string="Джерело потужності",
    )
    load_factor = fields.Float(string="Коефіцієнт завантаження в роботі", digits=(6, 3))
    idle_factor = fields.Float(string="Коефіцієнт простою", digits=(6, 3))
    cos_phi_nominal = fields.Float(string="cos φ (номінал)", digits=(4, 2), default=0.9)
    is_critical = fields.Boolean(string="Критичний (живлення від ДГУ)", tracking=True)
    alloc_role = fields.Selection(
        [
            ("direct", "Прямий (верстат)"),
            ("shared", "Спільний (пул)"),
            ("overhead", "Накладні"),
            ("none", "Не розподіляється"),
        ],
        string="Роль у розподілі",
        default="none",
        required=True,
    )
    pool_id = fields.Many2one("td.energy.pool", string="Пул", ondelete="set null")
    meter_ids = fields.One2many("td.energy.meter", "node_id", string="Лічильники")
    meter_count = fields.Integer(string="Лічильників", compute="_compute_meter_count")
    meter_id = fields.Many2one("td.energy.meter", compute="_compute_meter_id", string="Лічильник")
    unit_id = fields.Integer(string="Modbus unit (стенд)")
    note = fields.Text(string="Примітка")
    group = fields.Selection([("light", "Освітлення"), ("vent", "Вентиляція")], string="Група")
    company_id = fields.Many2one(
        "res.company", string="Компанія", required=True, default=lambda self: self.env.company, index=True
    )
    p_now = fields.Float(string="Зараз, кВт", compute="_compute_live")
    kwh_today = fields.Float(string="Сьогодні, кВт·год", compute="_compute_live")
    pfc_q_now = fields.Integer(string="Компенсація зараз, квар", readonly=True)
    live_status = fields.Selection(
        [
            ("ok", "Норма"),
            ("stale", "Немає даних"),
            ("gap", "Пропуск"),
            ("reset", "Скидання"),
            ("no_data", "Ще не було даних"),
            ("none", "Без лічильника"),
        ],
        string="Стан даних",
        compute="_compute_live",
    )

    # --- W1 (M-22): схема Пульту, захист, ступені PFC --------------------------------------------------
    sld_show = fields.Boolean(string="На схемі Пульту", default=False)
    sld_shape = fields.Selection(
        [("box", "Блок"), ("bar", "Шина"), ("switch", "Вимикач"), ("label", "Підпис")],
        string="Форма на схемі",
        default="box",
    )
    sld_x = fields.Integer(string="X на схемі", default=0)
    sld_y = fields.Integer(string="Y на схемі", default=0)
    sld_w = fields.Integer(string="Ширина на схемі", default=0)
    sld_h = fields.Integer(string="Висота на схемі", default=0)
    sld_label = fields.Char(string="Підпис на схемі", size=32)
    sld_anchor_id = fields.Many2one(
        "td.energy.node", string="Вузол-батько на схемі", ondelete="set null", domain="[('id', '!=', id)]"
    )
    sld_state = fields.Selection(
        [("ok", "Норма"), ("warn", "Увага"), ("alarm", "Тривога"), ("off", "Резерв / вимкнено"), ("gen", "Генерація")],
        string="Стан на схемі",
        compute="_compute_sld_state",
    )
    protection_trip_unit = fields.Char(string="Розчіплювач", size=64)
    protection_ir_ratio = fields.Float(string="Уставка Ir, × In", digits=(4, 2))
    trip_count_year = fields.Integer(string="Спрацювань за рік", compute="_compute_trip_count_year")
    pfc_step_kvar = fields.Integer(string="Крок ступеня, квар", default=35)
    pfc_steps_total = fields.Integer(string="Ступенів", default=10)

    _f3d_energy_node_code_uniq = models.Constraint("UNIQUE(code)", "Код вузла мережі має бути унікальним.")
    _f3d_energy_node_wc_uniq = models.Constraint(
        "UNIQUE(workcenter_id)", "Робочий центр уже прив'язаний до іншого вузла."
    )

    # --- перевірки ---------------------------------------------------------------------------------
    @api.constrains(
        "code", "kind", "cell_type", "line_kind", "parent_id", "alloc_role", "workcenter_id", "pool_id", "section"
    )
    def _check_node(self):
        for rec in self:
            if not rec.code or not self.CODE_RE.match(rec.code):
                raise ValidationError(
                    _("Код вузла %s: великі латинські літери, цифри, дефіс (напр. QF-3, TAP-SAW-1).", rec.code)
                )
            if rec._has_cycle():
                raise ValidationError(_("Вузол %s не може живитися сам від себе (цикл у схемі).", rec.code))
            if rec.kind == "cell" and not rec.cell_type:
                raise ValidationError(_("Для шафи ГРЩ задайте тип шафи."))
            if rec.kind == "line" and not rec.line_kind:
                raise ValidationError(_("Для лінії задайте тип."))
            if rec.kind in self.NEEDS_PARENT and not rec.parent_id:
                raise ValidationError(_("Вузол %s має живитися від іншого вузла.", rec.code))
            if rec.alloc_role == "direct" and (not rec.workcenter_id or rec.kind != "consumer"):
                raise ValidationError(_("Прямий споживач має бути вузлом-споживачем з робочим центром."))
            if rec.alloc_role == "shared" and not rec.pool_id:
                raise ValidationError(_("Спільний споживач має належати пулу."))
            if rec.pool_id and rec.alloc_role != "shared":
                raise ValidationError(_("Пул задається лише спільним споживачам."))
            if rec.workcenter_id and rec.kind != "consumer":
                raise ValidationError(_("Робочий центр прив'язується лише до споживача."))
            if rec.section not in (0, 1, 2):
                raise ValidationError(_("Секція шин: 0, 1 або 2."))

    @api.constrains("sld_show", "sld_shape", "sld_x", "sld_y", "sld_w", "sld_h", "sld_anchor_id")
    def _check_sld(self):
        for rec in self:
            if min(rec.sld_x, rec.sld_y, rec.sld_w, rec.sld_h) < 0:
                raise ValidationError(_("Координати й розміри на схемі мають бути невід'ємними (%s).", rec.code))
            if rec.sld_show and rec.sld_shape in ("box", "bar", "switch") and not (rec.sld_w > 0 and rec.sld_h > 0):
                raise ValidationError(_("Задайте розміри блоку на схемі для %s.", rec.code))
            if rec.sld_anchor_id == rec:
                raise ValidationError(_("Вузол %s не може бути батьком на схемі сам для себе.", rec.code))

    @api.constrains("cell_type", "rating_kvar", "pfc_step_kvar", "pfc_steps_total")
    def _check_pfc(self):
        for rec in self:
            if rec.cell_type != "pfc" or rec.rating_kvar <= 0:
                continue
            if rec.pfc_step_kvar * rec.pfc_steps_total != rec.rating_kvar:
                raise ValidationError(_("Ступені PFC %s не відповідають номіналу %s квар.", rec.code, rec.rating_kvar))

    def write(self, vals):
        # цикл ловимо до `_parent_store_update` ORM («Recursion Detected»), щоб віддати повідомлення SPEC
        if vals.get("parent_id"):
            for rec in self:
                if rec.id == vals["parent_id"] or rec.search_count(
                    [("id", "=", vals["parent_id"]), ("id", "child_of", rec.id)]
                ):
                    raise ValidationError(_("Вузол %s не може живитися сам від себе (цикл у схемі).", rec.code))
        return super().write(vals)

    # --- обчислювані -------------------------------------------------------------------------------
    @api.depends("meter_ids")
    def _compute_meter_count(self):
        for rec in self:
            rec.meter_count = len(rec.meter_ids)

    @api.depends("meter_ids.active", "meter_ids.code")
    def _compute_meter_id(self):
        for rec in self:
            rec.meter_id = rec.meter_ids.filtered("active").sorted("code")[:1]

    @api.depends("meter_ids.active", "meter_ids.code", "meter_ids.p_signal_id.last_value", "meter_ids.data_state")
    def _compute_live(self):
        meters = self.meter_id.sudo()
        kwh = {}
        if meters and "td.energy.interval" in self.env:
            groups = (
                self.env["td.energy.interval"]
                .sudo()
                ._read_group(
                    [("meter_id", "in", meters.ids), ("ts_start", ">=", _today_start_utc())],
                    ["meter_id"],
                    ["kwh:sum"],
                )
            )
            kwh = {meter.id: total for meter, total in groups}
        for rec in self:
            meter = rec.meter_id.sudo()
            rec.p_now = meter.p_signal_id.last_value if meter.p_signal_id else 0.0
            rec.kwh_today = kwh.get(meter.id, 0.0)
            rec.live_status = meter.data_state if meter else "none"

    def _compute_sld_state(self):
        states = sld.states(self.env, self)
        for rec in self:
            rec.sld_state = states.get(rec.id, "ok")

    def _compute_trip_count_year(self):
        counts = {}
        if self.ids:
            since = fields.Datetime.now() - timedelta(days=365)
            groups = (
                self.env["td.energy.event"]
                .sudo()
                ._read_group(
                    [("kind", "=", "trip"), ("node_id", "in", self.ids), ("ts", ">=", since)], ["node_id"], ["__count"]
                )
            )
            counts = {node.id: n for node, n in groups}
        for rec in self:
            rec.trip_count_year = counts.get(rec.id, 0)

    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s · %s" % (rec.code, rec.name) if rec.code else (rec.name or "")

    # --- API ---------------------------------------------------------------------------------------
    @api.model
    def _td_kwh_by_code(self, code, date_from, date_to):
        """CE-06: кВт·год вузла за вікно; немає вузла чи лічильника — (0.0, 'missing')."""
        node = self.search([("code", "=", code)], limit=1)
        if not node or not node.meter_id:
            return 0.0, "missing"
        return node.meter_id._td_kwh(date_from, date_to)

    def _td_descendant_meters(self):
        """Активні лічильники вузлів-нащадків (без самого `self`)."""
        nodes = self.search([("id", "child_of", self.ids)]) - self
        return nodes.meter_ids.filtered("active")

    def action_view_meters(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Лічильники"),
            "res_model": "td.energy.meter",
            "view_mode": "list,form",
            "domain": [("node_id", "child_of", self.id)],
        }

    def action_view_intervals(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Профіль"),
            "res_model": "td.energy.interval",
            "view_mode": "graph,pivot,list",
            "domain": [("node_id", "child_of", self.id), ("ts_start", ">=", _today_start_utc())],
        }

    def action_view_balance(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Баланс"),
            "res_model": "td.energy.balance",
            "view_mode": "list",
            "domain": [("node_id", "=", self.id)],
        }

    def action_f3d_show(self):
        self.ensure_one()
        if not self.equipment_id:
            raise UserError(_("Вузол %s не має об'єкта в 3D.", self.code))
        return self.equipment_id.action_f3d_show()

    action_td_show = action_f3d_show  # ім'я з W1_SPEC (A-23, AC-147); існуючий метод — `action_f3d_show`

    def action_open_card(self):
        """V-23: відкрити клієнтську картку вузла (`td_energy.node_card`) для `self.code`."""
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "td_energy.node_card",
            "name": self.name,
            "params": {"code": self.code},
            "context": {"active_code": self.code},
        }

    @api.model
    def action_td_energy_rebind(self):
        """§5.2: повтор прив'язки даних (лише адміністратор)."""
        if not self.env.user.has_group("td_factory3d.group_td_admin"):
            raise AccessError(_("Повтор прив'язки даних енергетики — лише адміністратор."))
        from .. import hooks  # відкладено: hooks імпортується пакетом після models

        report = hooks.run_bind(self.env)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": "success",
                "sticky": True,
                "message": _("Прив'язку виконано: %s", hooks.dump(report)),
            },
        }
