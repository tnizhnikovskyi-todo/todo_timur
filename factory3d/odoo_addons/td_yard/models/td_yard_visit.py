from datetime import datetime, timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..tools import params as P
from ..tools import plate as plate_tools
from ..tools import tz

GRP_SEC = "factory3d_yard.group_f3d_yard_security"
GRP_DISP = "factory3d_yard.group_f3d_yard_dispatcher"
GRP_MGR = "factory3d_yard.group_f3d_yard_manager"
GRP_STOCK = "stock.group_stock_user"
FINAL_STATES = ("left", "rejected", "cancelled")


def _f3d_yard_require(env, *xmlids):
    """Пропускає суперкористувача (env.su) і членів будь-якої з груп; інакше AccessError."""
    if env.su or any(env.user.has_group(x) for x in xmlids):
        return
    names = ", ".join(env.ref(x).name for x in xmlids)
    raise AccessError("Недостатньо прав: потрібна група «%s»." % names)


class F3dYardVisit(models.Model):
    _name = "f3d.yard.visit"
    _description = "Двір: рейс фури"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "planned_start desc, arrived_at desc, id desc"
    _rec_name = "name"
    _rec_names_search = ["name", "plate", "plate_norm", "scene_code"]
    _check_company_auto = True

    STATES = [
        ("draft", "Чернетка"),
        ("planned", "Заплановано"),
        ("arrived", "Прибула"),
        ("queued", "У черзі"),
        ("at_dock", "Біля воріт"),
        ("handling", "Операція"),
        ("weighed", "Зважена"),
        ("left", "Виїхала"),
        ("rejected", "Відхилена"),
        ("cancelled", "Скасована"),
    ]
    ACTIVE_STATES = ("arrived", "queued", "at_dock", "handling", "weighed")  # фура фізично на території
    TRANSITIONS = {  # §10.1
        "draft": {"planned", "arrived", "rejected", "cancelled"},
        "planned": {"draft", "arrived", "rejected", "cancelled"},
        "arrived": {"queued", "rejected"},
        "queued": {"at_dock", "handling", "left"},
        "at_dock": {"handling", "weighed", "left"},
        "handling": {"weighed", "left"},
        "weighed": {"left"},
        "left": set(),
        "rejected": set(),
        "cancelled": {"draft"},
    }
    TS_FIELD = {
        "planned": "planned_at",
        "arrived": "arrived_at",
        "queued": "admitted_at",
        "at_dock": "at_dock_at",
        "handling": "handling_start_at",
        "weighed": "weighed_out_at",
        "left": "left_at",
        "rejected": "rejected_at",
        "cancelled": "cancelled_at",
        "draft": None,
    }

    name = fields.Char(string="Рейс", size=32, required=True, readonly=True, copy=False, index=True, default="/")
    company_id = fields.Many2one(
        "res.company", string="Компанія", required=True, index=True, default=lambda s: s.env.company
    )
    visit_type = fields.Selection(
        [("incoming", "Приймання"), ("outgoing", "Відвантаження"), ("other", "Інше")],
        string="Тип",
        required=True,
        default="incoming",
        tracking=True,
    )
    state = fields.Selection(
        STATES,
        string="Стан",
        required=True,
        default="draft",
        index=True,
        readonly=True,
        tracking=True,
        copy=False,
        group_expand="_group_expand_states",
    )
    priority = fields.Selection([("0", "Звичайний"), ("1", "Терміново")], string="Пріоритет", default="0")
    is_walk_in = fields.Boolean(
        string="Без броні",
        default=False,
        readonly=True,
        copy=False,
        help="Рейс створено на КПП для фури без бронювання (R-06)",
    )
    partner_id = fields.Many2one(
        "res.partner", string="Постачальник / клієнт", check_company=True, tracking=True, ondelete="restrict"
    )
    carrier_id = fields.Many2one(
        "res.partner",
        string="Перевізник",
        domain="[('is_company','=',True)]",
        tracking=True,
        ondelete="restrict",
        index=True,
    )
    delivery_carrier_id = fields.Many2one(
        "delivery.carrier",
        string="Спосіб доставки",
        ondelete="set null",
        help="З документа відвантаження (stock.picking.carrier_id)",
    )
    driver_id = fields.Many2one(
        "res.partner", string="Водій", domain="[('is_company','=',False)]", tracking=True, ondelete="restrict"
    )
    driver_phone = fields.Char(string="Телефон водія", size=32, groups=GRP_SEC, copy=False)
    driver_doc = fields.Char(
        string="Документ водія",
        size=32,
        groups=GRP_SEC,
        copy=False,
        help="Серія й номер посвідчення водія; без копій документа",
    )
    pii_cleared = fields.Boolean(
        string="Персональні дані очищено", readonly=True, default=False, copy=False, groups=GRP_SEC
    )
    plate = fields.Char(string="Держномер", size=16, tracking=True, copy=False)
    plate_norm = fields.Char(
        string="Номер (нормалізований)", size=16, compute="_compute_plate_norm", store=True, index=True
    )
    plate_display = fields.Char(string="Номер (для показу)", compute="_compute_plate_display")
    batch_id = fields.Many2one(
        "stock.picking.batch",
        string="Пакет (документи)",
        index=True,
        check_company=True,
        ondelete="set null",
        tracking=True,
        domain="[('picking_type_code','in',('incoming','outgoing'))]",
    )
    picking_ids = fields.Many2many("stock.picking", string="Документи", compute="_compute_picking_ids")
    picking_count = fields.Integer(string="Документів", compute="_compute_picking_ids")
    scene_code = fields.Char(string="Код фури в 3D", related="batch_id.f3d_code", store=True, index=True)
    booking_ids = fields.One2many("f3d.yard.booking", "visit_id", string="Бронювання")
    booking_id = fields.Many2one(
        "f3d.yard.booking", string="Чинне бронювання", compute="_compute_booking_id", store=True, index=True
    )
    dock_id = fields.Many2one("stock.location", string="Ворота", related="booking_id.dock_id", store=True, index=True)
    dock_code = fields.Char(string="Код воріт", related="dock_id.f3d_code")
    planned_start = fields.Datetime(string="План: початок", related="booking_id.slot_start", store=True, index=True)
    planned_end = fields.Datetime(string="План: кінець", related="booking_id.slot_end", store=True)
    side = fields.Selection(
        [("west", "Захід (приймання)"), ("east", "Схід (відвантаження)")],
        string="Сторона",
        compute="_compute_side",
        store=True,
        index=True,
    )
    weighing_policy = fields.Selection(
        [("none", "Без зважування"), ("in_out", "На в'їзді й виїзді")],
        string="Зважування",
        required=True,
        tracking=True,
    )
    planned_at = fields.Datetime(string="Заплановано о", readonly=True, copy=False)
    arrived_at = fields.Datetime(string="Прибула о", readonly=True, copy=False, index=True)
    admitted_at = fields.Datetime(string="Пропущено о", readonly=True, copy=False)
    at_dock_at = fields.Datetime(string="Біля воріт з", readonly=True, copy=False)
    handling_start_at = fields.Datetime(string="Операція з", readonly=True, copy=False)
    handling_end_at = fields.Datetime(string="Операція до", readonly=True, copy=False)
    weighed_in_at = fields.Datetime(string="Зважено на в'їзді", readonly=True, copy=False)
    weighed_out_at = fields.Datetime(string="Зважено на виїзді", readonly=True, copy=False)
    left_at = fields.Datetime(string="Виїхала о", readonly=True, copy=False, index=True)
    rejected_at = fields.Datetime(string="Відхилено о", readonly=True, copy=False)
    cancelled_at = fields.Datetime(string="Скасовано о", readonly=True, copy=False)
    reject_reason = fields.Text(string="Причина відхилення", readonly=True, copy=False)
    day = fields.Date(string="День", compute="_compute_day", store=True, index=True)
    is_today = fields.Boolean(string="Сьогодні", compute="_compute_is_today", search="_search_is_today")
    gross_kg = fields.Float(string="Брутто, кг", digits=(12, 1), compute="_compute_weights", store=True)
    tare_kg = fields.Float(string="Тара, кг", digits=(12, 1), compute="_compute_weights", store=True)
    net_kg = fields.Float(string="Нетто, кг", digits=(12, 1), compute="_compute_weights", store=True)
    expected_kg = fields.Float(string="Маса за документами, кг", digits=(12, 1), compute="_compute_weights", store=True)
    deviation_kg = fields.Float(string="Відхилення, кг", digits=(12, 1), compute="_compute_weights", store=True)
    deviation_pct = fields.Float(string="Відхилення, %", digits=(6, 2), compute="_compute_weights", store=True)
    weight_check = fields.Selection(
        [("none", "Не зважено"), ("ok", "У допуску"), ("deviation", "Відхилення"), ("no_reference", "Немає еталона")],
        string="Звірка ваги",
        compute="_compute_weights",
        store=True,
    )
    wait_min = fields.Float(
        string="Очікування, хв", digits=(8, 1), compute="_compute_durations", store=True, aggregator="avg"
    )
    dock_min = fields.Float(
        string="Біля воріт, хв", digits=(8, 1), compute="_compute_durations", store=True, aggregator="avg"
    )
    total_min = fields.Float(
        string="Загалом, хв", digits=(8, 1), compute="_compute_durations", store=True, aggregator="avg"
    )
    late_min = fields.Float(
        string="Запізнення, хв", digits=(8, 1), compute="_compute_durations", store=True, aggregator="avg"
    )
    is_no_show = fields.Boolean(string="Не приїхала", readonly=True, default=False, copy=False, index=True)
    progress = fields.Float(string="Виконано", compute="_compute_progress")
    note = fields.Text(string="Примітка")

    _f3d_yard_visit_name_uniq = models.Constraint("UNIQUE(company_id, name)", "Номер рейсу має бути унікальним.")

    # ------------------------------------------------------------------ constraints
    @api.constrains("plate")
    def _check_plate(self):
        for visit in self:
            value = (visit.plate or "").strip().upper()
            if value and not (
                plate_tools.is_valid_plate_input(value)
                and plate_tools.is_valid_norm(plate_tools.normalize_plate(value))
            ):
                raise ValidationError(
                    "Держномер «%s»: лише літери, цифри, пробіл і дефіс, 2–16 символів." % visit.plate
                )

    @api.constrains("batch_id", "state")
    def _check_batch_unique(self):
        for visit in self.filtered(lambda v: v.batch_id and v.state not in FINAL_STATES):
            other = self.sudo().search(
                [("batch_id", "=", visit.batch_id.id), ("id", "!=", visit.id), ("state", "not in", FINAL_STATES)],
                limit=1,
            )
            if other:
                raise ValidationError("Пакет %s уже має активний рейс %s." % (visit.batch_id.name, other.name))

    @api.constrains("batch_id", "visit_type")
    def _check_batch_type(self):
        labels = dict(self._fields["visit_type"].selection)
        for visit in self.filtered(lambda v: v.batch_id and v.visit_type != "other"):
            if visit.batch_id.picking_type_code != visit.visit_type:
                raise ValidationError(
                    "Тип рейсу «%s» не збігається з типом операцій пакета %s."
                    % (labels[visit.visit_type], visit.batch_id.name)
                )

    # ------------------------------------------------------------------ computes
    @api.depends("plate")
    def _compute_plate_norm(self):
        for visit in self:
            visit.plate_norm = plate_tools.normalize_plate(visit.plate)

    @api.depends("plate")
    def _compute_plate_display(self):
        for visit in self:
            visit.plate_display = plate_tools.display_plate(visit.plate)

    @api.depends("batch_id.picking_ids")
    def _compute_picking_ids(self):
        for visit in self:
            visit.picking_ids = visit.batch_id.picking_ids
            visit.picking_count = len(visit.batch_id.picking_ids)

    @api.depends("booking_ids.state", "booking_ids.slot_start")
    def _compute_booking_id(self):
        for visit in self:
            confirmed = visit.booking_ids.filtered(lambda b: b.state == "confirmed")
            visit.booking_id = confirmed.sorted("slot_start", reverse=True)[:1]

    @api.depends("dock_id.f3d_side", "visit_type")
    def _compute_side(self):
        for visit in self:
            visit.side = visit.dock_id.f3d_side or ("east" if visit.visit_type == "outgoing" else "west")

    @api.depends("planned_start", "arrived_at", "create_date")
    def _compute_day(self):
        for visit in self:
            ts = visit.planned_start or visit.arrived_at or visit.create_date or fields.Datetime.now()
            visit.day = tz.local_day(ts)

    @api.depends("day")
    def _compute_is_today(self):
        today = tz.local_today(fields.Datetime.now())
        for visit in self:
            visit.is_today = visit.day == today

    def _search_is_today(self, operator, value):
        """Фільтр «Сьогодні»: київська доба сервера, а не `context_today()` браузера (Y-2)."""
        return tz.today_domain(operator, value, fields.Datetime.now())

    def _f3d_yard_weighings(self):
        """Чинні (assigned) зважування рейсу; без моделі ваг (W3) — порожньо."""
        self.ensure_one()
        if "weighing_ids" not in self._fields:
            return self.env["f3d.yard.visit"].browse()
        return self.weighing_ids.filtered(lambda w: w.state == "assigned")

    @api.depends(
        "visit_type",
        "batch_id.picking_ids.move_ids.product_qty",
        "batch_id.picking_ids.move_ids.quantity",
        "batch_id.picking_ids.move_ids.product_id.weight",
        "batch_id.picking_ids.state",
    )
    def _compute_weights(self):
        """R-12 кроки 1–4. Модуль ваг (W3) розширює @api.depends залежностями weighing_ids.*."""
        for visit in self:
            pickings = visit.batch_id.picking_ids.filtered(lambda p: p.state != "cancel")
            expected, has_ref = 0.0, bool(pickings)
            for picking in pickings:
                exp, ref = picking._f3d_expected_kg()
                expected += exp
                has_ref = has_ref and ref
            weighings = visit._f3d_yard_weighings()
            last = {}
            for kind in ("in", "out"):
                of_kind = weighings.filtered(lambda w, k=kind: w.kind == k).sorted("ts")
                if of_kind:
                    last[kind] = of_kind[-1].weight_kg
            outgoing = visit.visit_type == "outgoing"
            gross = tare = 0.0
            if outgoing:
                tare, gross = last.get("in", 0.0), last.get("out", 0.0)
            else:
                gross, tare = last.get("in", 0.0), last.get("out", 0.0)
            both = "in" in last and "out" in last
            net = abs(gross - tare) if both else 0.0
            visit.gross_kg, visit.tare_kg, visit.net_kg = gross, tare, net
            visit.expected_kg = expected
            deviation = net - expected if both else 0.0
            visit.deviation_kg = deviation
            visit.deviation_pct = round(deviation / expected * 100, 2) if both and expected > 0 else 0.0
            if not both:
                visit.weight_check = "none"
            elif not has_ref or expected <= 0:
                visit.weight_check = "no_reference"
            else:
                tol = max(
                    expected * P.get_float(self.env, "net_tolerance_pct") / 100,
                    P.get_float(self.env, "net_tolerance_kg"),
                )
                visit.weight_check = "ok" if abs(deviation) <= tol else "deviation"

    @api.depends("arrived_at", "at_dock_at", "handling_end_at", "weighed_out_at", "left_at", "planned_start")
    def _compute_durations(self):
        def minutes(end, start):
            return round((end - start).total_seconds() / 60.0, 1) if end and start else False

        for visit in self:
            end = visit.handling_end_at or visit.weighed_out_at or visit.left_at
            visit.wait_min = minutes(visit.at_dock_at, visit.arrived_at)
            visit.dock_min = minutes(end, visit.at_dock_at)
            visit.total_min = minutes(visit.left_at, visit.arrived_at)
            visit.late_min = minutes(visit.arrived_at, visit.planned_start)

    def _compute_progress(self):
        for visit in self:
            moves = visit.batch_id.picking_ids.move_ids.filtered(lambda m: m.state != "cancel")
            demand = sum(moves.mapped("product_uom_qty"))
            visit.progress = (sum(moves.mapped("quantity")) / demand) if demand else 0.0

    @api.model
    def _group_expand_states(self, states, domain):
        return ["planned", "arrived", "queued", "at_dock", "handling", "weighed", "left"]

    # ------------------------------------------------------------------ onchange
    @api.onchange("driver_id")
    def _onchange_driver_id(self):
        driver = self.driver_id.sudo()
        if not driver:
            return
        self.driver_phone = driver.phone
        self.driver_doc = driver.f3d_driver_doc
        if not self.carrier_id:
            self.carrier_id = driver.f3d_carrier_id
        if not self.plate:
            self.plate = driver.f3d_default_plate

    # ------------------------------------------------------------------ CRUD
    @api.model_create_multi
    def create(self, vals_list):
        Seq = self.env["ir.sequence"].sudo()
        for vals in vals_list:
            if not vals.get("name") or vals["name"] == "/":
                vals["name"] = Seq.next_by_code("f3d.yard.visit") or "/"
            if vals.get("plate"):
                vals["plate"] = vals["plate"].strip().upper()
            if not vals.get("weighing_policy"):
                side = "east" if vals.get("visit_type") == "outgoing" else "west"
                vals["weighing_policy"] = P.get_str(self.env, "weighing_policy_" + side)
        visits = super().create(vals_list)
        visits._f3d_yard_notify()
        return visits

    def write(self, vals):
        if vals.get("plate"):
            vals = dict(vals, plate=vals["plate"].strip().upper())
        if {"visit_type", "batch_id"} & set(vals):
            for visit in self:
                changed = ("visit_type" in vals and vals["visit_type"] != visit.visit_type) or (
                    "batch_id" in vals and (vals["batch_id"] or False) != (visit.batch_id.id or False)
                )
                if changed and visit.state not in ("draft", "planned", "arrived"):
                    raise UserError("Тип і пакет змінюються лише до пропуску фури.")
        res = super().write(vals)
        if {"plate", "batch_id", "priority"} & set(vals):
            self._f3d_yard_notify()
        return res

    def unlink(self):
        labels = dict(self._fields["state"].selection)
        for visit in self:
            if visit.state not in ("draft", "planned", "cancelled"):
                raise UserError(
                    "Рейс у стані «%s» видаляти не можна — скасуйте або відхиліть його." % labels[visit.state]
                )
        return super().unlink()

    # ------------------------------------------------------------------ state machine
    def _set_state(self, new, ts=None, gate=None, note=None):
        """Внутрішній перехід за §10.1 (права перевіряє викликач)."""
        self.ensure_one()
        labels = dict(self._fields["state"].selection)
        self.env.cr.execute("SELECT state FROM f3d_yard_visit WHERE id = %s FOR UPDATE", [self.id])
        self.invalidate_recordset(["state"])
        old = self.state
        if new not in self.TRANSITIONS[old]:
            raise UserError("Перехід «%s» → «%s» неможливий." % (labels[old], labels[new]))
        ts = ts or fields.Datetime.now()
        vals = {"state": new}
        ts_field = self.TS_FIELD[new]
        if ts_field and not self[ts_field]:
            vals[ts_field] = ts
        if old == "queued" and new == "handling" and not self.at_dock_at:
            vals["at_dock_at"] = ts
        if new == "arrived" and gate and "gate_in_id" in self._fields:
            vals["gate_in_id"] = gate.id
        self.sudo().write(vals)
        self.sudo().message_post(
            body="Стан: %s → %s (%s)%s" % (labels[old], labels[new], tz.local_hm(ts), (" · " + note) if note else "")
        )
        self._f3d_yard_notify()
        return True

    def action_plan(self):
        self.ensure_one()
        _f3d_yard_require(self.env, GRP_DISP)
        if not self.booking_id:
            raise UserError("Спершу підтвердіть бронювання воріт.")
        return self._set_state("planned")

    def action_arrive(self, ts=None, gate=None, event=None):
        self.ensure_one()
        _f3d_yard_require(self.env, GRP_SEC)
        if gate is None and "f3d.yard.gate" in self.env:
            gate = self._f3d_yard_default_gate()
        self._set_state("arrived", ts=ts, gate=gate)
        if event:
            event.sudo().write({"visit_id": self.id, "match_state": "matched"})
        return True

    def _f3d_yard_default_gate(self):
        """КПП в'їзду для сторони рейсу (GATE-W за замовчуванням); модель воріт — W2."""
        Gate = self.env["f3d.yard.gate"].sudo()
        domain = [("direction", "in", ("in", "both"))]
        if "side" in Gate._fields:
            gates = Gate.search(domain + [("side", "=", self.side)], limit=1)
            if gates:
                return gates
        return Gate.search(domain, limit=1)

    def _f3d_yard_admit_gate(self, open_gate=True):
        """Хук W2: команда шлагбауму при пропуску. Повертає (тип, повідомлення) або None."""
        return None

    def action_admit(self, open_gate=True):
        self.ensure_one()
        _f3d_yard_require(self.env, GRP_SEC)
        self._set_state("queued")
        result = self._f3d_yard_admit_gate(open_gate) or ("success", "Фуру %s пропущено" % (self.plate or self.name))
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "type": result[0],
                "message": result[1],
                "sticky": False,
                "next": {"type": "ir.actions.act_window_close"},  # перечитати вид після кнопки
            },
        }

    def action_call_to_dock(self, dock=None):
        self.ensure_one()
        _f3d_yard_require(self.env, GRP_SEC)
        if self.state != "queued":
            raise UserError("Викликати на ворота можна лише фуру в черзі.")
        now = fields.Datetime.now()
        slot = timedelta(minutes=P.get_int(self.env, "slot_default_min"))
        if self.booking_id:
            if dock and dock != self.booking_id.dock_id:
                raise UserError("Рейс заброньовано на %s." % (self.booking_id.dock_id.f3d_code or dock.name))
            dock = self.booking_id.dock_id
        else:
            dock = dock or self._f3d_yard_pick_dock()
            if not dock:
                side_label = dict(self._fields["side"].selection)[self.side]
                raise UserError("Немає вільних воріт на стороні «%s»." % side_label)
        busy = self._f3d_yard_dock_busy(dock, now, now + slot, exclude=self)
        if busy:
            raise UserError("Ворота %s зайняті рейсом %s." % (dock.f3d_code or dock.name, busy.name))
        if not self.booking_id:
            booking = (
                self.env["f3d.yard.booking"]
                .sudo()
                .create(
                    {
                        "visit_id": self.id,
                        "dock_id": dock.id,
                        "slot_start": now,
                        "slot_end": now + slot,
                        "source": "walk_in",
                        "company_id": self.company_id.id,
                    }
                )
            )
            try:
                booking.action_confirm()
            except ValidationError as exc:
                raise UserError("Ворота %s зайняті: %s" % (dock.f3d_code or dock.name, exc.args[0])) from exc
        return self._set_state("at_dock")

    def action_start_handling(self, auto=False):
        self.ensure_one()
        if not auto:
            _f3d_yard_require(self.env, GRP_SEC, GRP_STOCK)
        note = "автоматично: почато приймання/відвантаження в документі" if auto else None
        return self._set_state("handling", note=note)

    def action_end_handling(self, auto=False):
        self.ensure_one()
        if not auto:
            _f3d_yard_require(self.env, GRP_SEC, GRP_STOCK)
        if self.state != "handling":
            raise UserError("Завершити операцію можна лише у стані «Операція».")
        if not self.handling_end_at:
            self.sudo().write({"handling_end_at": fields.Datetime.now()})
            self.sudo().message_post(body="Операцію завершено%s" % (" (автоматично)" if auto else ""))
        if P.get_bool(self.env, "auto_call_next") and self.dock_id:
            self._f3d_yard_call_next(self.dock_id)
        return True

    def _f3d_yard_do_weigh(self):
        """Хук W3: зважування (захоплення з ваг або форма ручного вводу)."""
        raise UserError("Модуль автоваг не встановлено.")

    def action_weigh(self):
        self.ensure_one()
        _f3d_yard_require(self.env, GRP_SEC, GRP_STOCK)
        if self.state not in ("queued", "at_dock", "handling"):
            raise UserError("Зважити можна фуру в черзі, біля воріт або в операції.")
        return self._f3d_yard_do_weigh()

    def _f3d_yard_has_weighing(self, kind):
        self.ensure_one()
        if "weighing_ids" not in self._fields:
            return False
        return bool(self.weighing_ids.filtered(lambda w: w.kind == kind and w.state == "assigned"))

    def action_leave(self, ts=None, note=None):
        self.ensure_one()
        _f3d_yard_require(self.env, GRP_SEC)
        ts = ts or fields.Datetime.now()
        dock = self.dock_id
        self._set_state("left", ts=ts, note=note)
        if self.weighing_policy == "in_out" and not self._f3d_yard_has_weighing("out"):
            self.sudo().message_post(body="Виїзд без зважування на виїзді")
        unfinished = self.sudo().batch_id.picking_ids.filtered(lambda p: p.state not in ("done", "cancel"))
        if unfinished:
            self.sudo().message_post(body="Документи не завершені: %s" % ", ".join(unfinished.mapped("name")))
        if P.get_bool(self.env, "auto_call_next") and dock:
            self._f3d_yard_call_next(dock)
        return True

    def action_reject_wizard(self):
        self.ensure_one()
        _f3d_yard_require(self.env, GRP_SEC)
        return {
            "type": "ir.actions.act_window",
            "name": "Відхилити рейс",
            "res_model": "f3d.yard.reject.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_visit_id": self.id},
        }

    def _do_reject(self, reason):
        """З майстра M-17: draft|planned|arrived → rejected; бронювання скасовуються."""
        self.ensure_one()
        self._set_state("rejected", note=reason)
        self.sudo().write({"reject_reason": reason})
        self.booking_ids.filtered(lambda b: b.state in ("requested", "confirmed")).sudo().action_cancel()
        if "lpr_event_ids" in self._fields:
            events = self.sudo().lpr_event_ids.filtered("kpp_alert")
            events.write({"kpp_alert": False, "match_state": "handled"})
        return True

    def action_cancel(self):
        self.ensure_one()
        _f3d_yard_require(self.env, GRP_DISP)
        if self.state not in ("draft", "planned"):
            raise UserError("Скасувати можна лише рейс у стані «Чернетка» або «Заплановано».")
        self._set_state("cancelled")
        self.booking_ids.filtered(lambda b: b.state != "cancelled").sudo().action_cancel()
        return True

    def action_draft(self):
        self.ensure_one()
        _f3d_yard_require(self.env, GRP_DISP)
        return self._set_state("draft")

    def action_show_3d(self):
        self.ensure_one()
        if self.scene_code:
            return self.batch_id.action_f3d_show()
        if self.dock_id.f3d_code:
            return self.dock_id.action_f3d_show()
        if "gate_in_id" in self._fields and self.gate_in_id:
            return self.gate_in_id.action_f3d_show()
        raise UserError("Рейс не має об'єкта в 3D.")

    def action_open_batch(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Пакет",
            "res_model": "stock.picking.batch",
            "res_id": self.batch_id.id,
            "view_mode": "form",
        }

    def action_open_pickings(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Документи",
            "res_model": "stock.picking",
            "view_mode": "list,form",
            "domain": [("id", "in", self.picking_ids.ids)],
        }

    # ------------------------------------------------------------------ черга й ворота (R-05)
    @api.model
    def _f3d_yard_queue(self, side, dock=None):
        now = fields.Datetime.now()
        window = now + timedelta(minutes=P.get_int(self.env, "queue_slot_window_min"))
        visits = self.search([("state", "=", "queued"), ("side", "=", side)])
        if dock:
            visits = visits.filtered(lambda v: not v.booking_id or v.booking_id.dock_id == dock)

        def key(visit):
            arrived = visit.arrived_at or datetime.max
            if visit.priority == "1":
                return (0, datetime.min, arrived, visit.id)
            if visit.booking_id and visit.booking_id.slot_start <= window:
                return (1, visit.booking_id.slot_start, arrived, visit.id)
            return (2, arrived, arrived, visit.id)

        return visits.sorted(key=key)

    @api.model
    def _f3d_yard_dock_busy(self, dock, start, end, exclude=None):
        """Рейс (або бронювання без рейсу), що займає ворота на [start, end); порожньо — вільні."""
        exclude_id = exclude.id if exclude else False
        domain = [("state", "in", ("at_dock", "handling")), ("dock_id", "=", dock.id)]
        if exclude_id:
            domain.append(("id", "!=", exclude_id))
        busy = self.sudo().search(domain, limit=1)
        if busy:
            return busy
        bookings = (
            self.env["f3d.yard.booking"]
            .sudo()
            .search(
                [
                    ("dock_id", "=", dock.id),
                    ("state", "=", "confirmed"),
                    ("slot_start", "<", end),
                    ("slot_end", ">", start),
                ]
            )
        )
        for booking in bookings:
            visit = booking.visit_id
            if not visit:
                return booking
            if visit.id != exclude_id and visit.state not in FINAL_STATES:
                return visit
        return self.browse()

    def _f3d_yard_category_warning(self, dock):
        """R-04: попередження, якщо категорії товарів рейсу не підходять воротам."""
        self.ensure_one()
        allowed = dock.f3d_accepts
        if not allowed:
            return False
        moves = self.batch_id.picking_ids.move_ids.filtered(lambda m: m.state != "cancel")
        bad = moves.product_id.categ_id.filtered(
            lambda c: not any((c.parent_path or "").startswith(a.parent_path or "\0") for a in allowed)
        )
        if not bad:
            return False
        return "Ворота %s приймають: %s. У рейсі є: %s." % (
            dock.f3d_code or dock.name,
            ", ".join(allowed.mapped("name")),
            ", ".join(bad.mapped("name")),
        )

    def _f3d_yard_pick_dock(self):
        self.ensure_one()
        now = fields.Datetime.now()
        end = now + timedelta(minutes=P.get_int(self.env, "slot_default_min"))
        docks = self.env["stock.location"].search(
            [
                ("f3d_kind", "=", "dock"),
                ("f3d_side", "=", self.side),
                ("company_id", "in", (self.company_id.id, False)),
            ]
        )
        type_docks = self.batch_id.picking_type_id.dock_ids
        if type_docks:
            docks &= type_docks
        docks = docks.sorted(key=lambda d: (bool(self._f3d_yard_category_warning(d)), d.f3d_dock_no, d.id))
        for dock in docks:
            if not self._f3d_yard_dock_busy(dock, now, end, exclude=self):
                return dock
        return self.env["stock.location"]

    @api.model
    def _f3d_yard_call_next(self, dock):
        now = fields.Datetime.now()
        end = now + timedelta(minutes=P.get_int(self.env, "slot_default_min"))
        for visit in self._f3d_yard_queue(dock.f3d_side, dock):
            if not self._f3d_yard_dock_busy(dock, now, end, exclude=visit):
                visit.sudo().action_call_to_dock(dock)
                return visit
        return False

    # ------------------------------------------------------------------ вага документів (R-12 п. 5)
    def _f3d_yard_write_pickings(self, net=None):
        """Розподіляє нетто рейсу по документах пакета й виставляє звірку (sudo)."""
        self.ensure_one()
        net = self.net_kg if net is None else net
        pickings = self.batch_id.picking_ids.filtered(lambda p: p.state != "cancel").sorted("name")
        if not pickings:
            return
        expected = {p.id: p._f3d_expected_kg() for p in pickings}
        total = sum(e for e, _r in expected.values())
        pct = P.get_float(self.env, "net_tolerance_pct")
        min_kg = P.get_float(self.env, "net_tolerance_kg")
        kgm = self.env.ref("uom.product_uom_kgm")
        weight_uom = self.env["product.template"]._get_weight_uom_id_from_ir_config_parameter()
        for picking in pickings.sudo():
            exp, ref = expected[picking.id]
            if len(pickings) == 1:
                share = net
            else:
                share = net * (exp / total) if total else net / len(pickings)
            dev = share - exp
            tol = max(exp * pct / 100, min_kg)
            if not ref or exp <= 0:
                check = "no_reference"
            else:
                check = "ok" if abs(dev) <= tol else "deviation"
            vals = {
                "f3d_net_weight_kg": share,
                "f3d_weight_check": check,
                "f3d_weight_deviation_pct": round(dev / exp * 100, 2) if exp > 0 else 0.0,
            }
            if self.visit_type == "outgoing" and "shipping_weight" in picking._fields:
                vals["shipping_weight"] = kgm._compute_quantity(share, weight_uom)
            picking.write(vals)
            if check == "deviation":
                self._f3d_yard_deviation_activity(picking, share, exp, dev, tol)

    def _f3d_yard_deviation_activity(self, picking, net, expected, dev, tol):
        summary = "Відхилення нетто"
        user = picking.user_id or picking.batch_id.user_id
        if not user:
            return
        if picking.activity_ids.filtered(lambda a: a.summary == summary):
            return
        picking.activity_schedule(
            "mail.mail_activity_data_warning",
            summary=summary,
            note="Нетто %s кг, за документом %s кг, відхилення %+.0f кг (%+.2f %%) при допуску %s кг."
            % (net, expected, dev, dev / expected * 100 if expected else 0.0, tol),
            user_id=user.id,
        )

    # ------------------------------------------------------------------ хуки W4
    def _f3d_yard_notify(self):
        """R-21: сповіщення шини (реалізує W4); у W1 — нічого."""
        return True

    @api.model
    def _f3d_yard_viewer_event(self):
        return self.env["f3d.viewer.event"].sudo() if "f3d.viewer.event" in self.env else None
