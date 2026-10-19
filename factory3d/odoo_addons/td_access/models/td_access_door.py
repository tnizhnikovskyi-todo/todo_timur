from odoo import api, fields, models
from odoo.exceptions import AccessError, ValidationError

from ..tools import params as P
from ..tools.dates import local_day_start_utc

STATES = [
    ("unknown", "Невідомо"),
    ("locked", "Зачинено на замок"),
    ("unlocked", "Розблоковано"),
    ("open", "Відчинено"),
    ("closed", "Зачинено"),
    ("forced", "Відчинено силоміць"),
    ("held", "Тримається відчиненим"),
]
ALARM_FIELDS = frozenset({"alarm", "alarm_reason"})


class F3dAccessDoor(models.Model):
    _name = "td.access.door"
    _description = "СКУД: двері або турнікет"
    _order = "server_id, code"
    _rec_names_search = ["code", "name", "biostar_id"]

    name = fields.Char(string="Назва", required=True, size=128)
    code = fields.Char(string="Код", required=True, index=True, size=32)
    kind = fields.Selection([("door", "Двері"), ("turnstile", "Турнікет")], required=True, default="door")
    server_id = fields.Many2one("td.access.server", required=True, index=True, ondelete="cascade")
    company_id = fields.Many2one("res.company", related="server_id.company_id", store=True, index=True)
    biostar_id = fields.Char(string="ID у BioStar", size=64, index=True)
    entry_device_id = fields.Many2one("td.access.device", string="Зчитувач входу", ondelete="set null")
    exit_device_id = fields.Many2one("td.access.device", string="Зчитувач виходу", ondelete="set null")
    zone_from_id = fields.Many2one("td.zone", string="Із зони", ondelete="set null")
    zone_to_id = fields.Many2one("td.zone", string="У зону", ondelete="set null")
    is_perimeter = fields.Boolean(
        string="Периметр (відмітки)",
        default=False,
        help="Проходи через ці двері створюють і закривають відмітки Відвідування (A-04)",
    )
    dwell_min = fields.Integer(
        string="Повернення в домашню зону, хв", default=0, help="0 — зона лишається до наступного проходу"
    )
    open_duration_s = fields.Integer(string="Час відчинення, с", readonly=True)
    state = fields.Selection(STATES, required=True, default="unknown", readonly=True)
    state_ts = fields.Datetime(readonly=True)
    alarm = fields.Boolean(string="Тривога", default=False, readonly=True)
    alarm_reason = fields.Selection(
        [("forced", "Відчинено силоміць"), ("held", "Тримається відчиненим"), ("fire", "Пожежна тривога")],
        readonly=True,
    )
    passes_today = fields.Integer(compute="_compute_passes_today")
    is_access_admin = fields.Boolean(compute="_compute_is_access_admin")  # форма: поля readonly для охорони (§4.1)
    active = fields.Boolean(default=True)

    _f3d_access_door_code_uniq = models.Constraint("UNIQUE(code)", "Код дверей має бути унікальним.")
    _f3d_access_door_bsid_uniq = models.Constraint(
        "UNIQUE(server_id, biostar_id)", "Двері з таким ID BioStar уже є на цьому сервері."
    )
    _f3d_access_door_dwell = models.Constraint(
        "CHECK(dwell_min BETWEEN 0 AND 1440)", "Повернення в домашню зону: 0–1440 хв."
    )

    @api.constrains(
        "code", "biostar_id", "zone_from_id", "zone_to_id", "is_perimeter", "entry_device_id", "exit_device_id"
    )
    def _check_door(self):
        for rec in self:
            if not rec.code or len(rec.code) > 32 or not P.CODE_RE.match(rec.code):
                raise ValidationError(
                    "Код дверей %s: лише великі латинські літери, цифри й дефіси (напр. TURN-1)." % rec.code
                )
            if rec.biostar_id and not P.BSID_RE.match(rec.biostar_id):
                raise ValidationError("ID BioStar %s: 1–64 символи [0-9A-Za-z_-]." % rec.biostar_id)
            if bool(rec.zone_from_id) != bool(rec.zone_to_id):
                raise ValidationError("Задайте обидві зони дверей («Із зони» і «У зону») або жодної.")
            if rec.is_perimeter and not rec.zone_to_id:
                raise ValidationError("Двері периметра потребують зони «У зону».")
            for device in rec.entry_device_id | rec.exit_device_id:
                if device.server_id != rec.server_id:
                    raise ValidationError("Зчитувач має належати тому самому серверу BioStar.")

    def _compute_is_access_admin(self):
        is_admin = self.env.su or self.env.user.has_group("td_access.group_td_access_admin")
        for rec in self:
            rec.is_access_admin = is_admin

    def _compute_passes_today(self):
        if "td.access.event" not in self.env:
            self.passes_today = 0
            return
        start = local_day_start_utc(fields.Datetime.now())
        for rec in self:
            rec.passes_today = self.env["td.access.event"].search_count(
                [("door_id", "=", rec.id), ("event_type", "=", "pass"), ("ts", ">=", start)]
            )

    def write(self, vals):
        # SPEC §4.1/§13.3 (A-1): охорона має RW на двері лише заради підтвердження тривоги: вона змінює тільки
        # `alarm`/`alarm_reason` і лише знімає тривогу (не виставляє). Усе інше — адміністратор СКУД або sudo()
        # (обробка подій, `action_ack_alarm`).
        if not self.env.su and not self.env.user.has_group("td_access.group_td_access_admin"):
            if set(vals) - ALARM_FIELDS:
                raise AccessError("Змінювати двері може лише адміністратор СКУД.")
            if any(vals.values()):
                raise AccessError("Охорона може лише зняти тривогу дверей.")
        return super().write(vals)

    def _td_publish_change(self):
        """Шина переглядача ('td.access.door', коди, 'state'), R-12 крок 6; у пакеті подій — через збирач."""
        codes = {c for c in self.sudo().mapped("code") if c}
        if not codes:
            return None
        collector = self.env.context.get("f3d_bus_collector")
        if collector is not None:
            collector.setdefault("td.access.door", set()).update(codes)
        else:
            self.env["td.access.event"]._td_bus("td.access.door", codes)

    def _td_set_state(self, state, ts, alarm=None, reason=None):
        """R-10: застосувати подію стану дверей; повертає двері, у яких щось змінилося."""
        changed = self.browse()
        for door in self.sudo():
            if door.state_ts and ts < door.state_ts:
                continue
            vals = {}
            if state:
                vals.update(state=state, state_ts=ts)
                if state in ("closed", "locked") and door.alarm_reason in ("forced", "held"):
                    vals.update(alarm=False, alarm_reason=False)
            if alarm:
                vals.update(alarm=True, alarm_reason=reason)
            vals = {k: v for k, v in vals.items() if k == "state_ts" or door[k] != v}
            if set(vals) - {"state_ts"}:
                changed |= door
            if vals:
                door.write(vals)
        if changed:
            changed._td_publish_change()
        return changed

    def action_f3d_show(self):
        self.ensure_one()
        return self.entry_device_id.action_f3d_show()

    def action_open_events(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Події",
            "res_model": "td.access.event",
            "view_mode": "list,form",
            "domain": [("door_id", "=", self.id)],
        }

    def action_ack_alarm(self):
        if not self.env.su and not self.env.user.has_group("td_access.group_td_access_security"):
            raise AccessError("Знімати тривогу може лише охорона.")
        self.sudo().write({"alarm": False, "alarm_reason": False})
        self._td_publish_change()
        return True
