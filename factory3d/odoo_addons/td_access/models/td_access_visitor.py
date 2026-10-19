import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from ..tools import params as P
from ..tools.dates import local_day_bounds_utc
from ..tools.biostar_client import BioStarError, BioStarWriteDisabled
from .td_access_card import SYNC_STATES

_logger = logging.getLogger(__name__)

SECURITY = "td_access.group_td_access_security"
ADMIN = "td_access.group_td_access_admin"
GRACE = timedelta(hours=1)  # R-14 крок 2 (expiry користувача) і крок 3 (повторний вхід), R-20 крок 3
STATES = [
    ("draft", "Чернетка"),
    ("expected", "Очікується"),
    ("on_site", "На території"),
    ("left", "Вийшов"),
    ("closed", "Закрито"),
    ("cancelled", "Скасовано"),
]


class F3dAccessVisitor(models.Model):
    _name = "td.access.visitor"
    _description = "СКУД: відвідувач"
    _inherit = ["mail.thread"]
    _order = "date_from desc, id desc"

    def _default_server_id(self):
        Server = self.env["td.access.server"].sudo()
        return (
            Server.search([("active", "=", True), ("company_id", "=", self.env.company.id)], limit=1)
            or Server.search([("active", "=", True)], limit=1)
        ).id

    def _default_hours(self):
        return P.get_int(self.env, "visitor_default_hours", 8, 1, 72)

    name = fields.Char(string="ПІБ", size=128, required=True, tracking=True)
    visitor_company = fields.Char(string="Компанія", size=128)
    host_employee_id = fields.Many2one(
        "hr.employee", string="Хто приймає", required=True, ondelete="restrict", tracking=True
    )
    purpose = fields.Char(string="Мета візиту", size=255)
    date_from = fields.Datetime(string="З", required=True, default=fields.Datetime.now, tracking=True)
    date_to = fields.Datetime(
        string="До",
        required=True,
        tracking=True,
        default=lambda self: fields.Datetime.now() + timedelta(hours=self._default_hours()),
    )
    allowed_zone_ids = fields.Many2many(
        "td.zone",
        "td_access_visitor_zone_rel",
        "visitor_id",
        "zone_id",
        string="Дозволені зони",
        help="Порожньо — без перевірки",
    )
    card_id = fields.Many2one(
        "td.access.card",
        ondelete="set null",
        tracking=True,
        domain="[('holder_type', 'in', ('pool', 'visitor')), ('state', 'in', ('draft', 'returned')), "
        "('server_id', '=', server_id)]",
    )
    server_id = fields.Many2one("td.access.server", required=True, default=lambda self: self._default_server_id())
    company_id = fields.Many2one("res.company", required=True, index=True, default=lambda self: self.env.company)
    biostar_user_id = fields.Char(
        string="Користувач BioStar",
        size=64,
        tracking=True,
        help="Під стоп-краном запису модуль створює V-<id> сам; інакше введіть user_id, створений у BioStar",
    )
    link_id = fields.Many2one("td.access.user.link", readonly=True, ondelete="set null")
    state = fields.Selection(STATES, required=True, default="draft", tracking=True)
    arrived_at = fields.Datetime(string="Прийшов", readonly=True)
    left_at = fields.Datetime(string="Вийшов", readonly=True)
    present = fields.Boolean(readonly=True, index=True)
    zone_id = fields.Many2one("td.zone", string="Зона", readonly=True, index=True, ondelete="set null")
    zone_since = fields.Datetime(readonly=True)
    zone_door_id = fields.Many2one("td.access.door", readonly=True, ondelete="set null")
    last_event_id = fields.Many2one("td.access.event", readonly=True, ondelete="set null")
    document_checked = fields.Boolean(
        string="Документ перевірено", help="Документ не зберігається: лише відмітка, що охорона його перевірила"
    )
    overdue = fields.Boolean(string="Прострочено", readonly=True)
    origin = fields.Selection(
        [("manual", "Вручну"), ("yard", "Двір"), ("portal", "Портал")], required=True, default="manual"
    )
    origin_ref = fields.Char(string="Джерело (посилання)", size=64)
    sync_state = fields.Selection(SYNC_STATES, default="local", readonly=True)
    sync_error = fields.Char(size=255, readonly=True)
    event_ids = fields.One2many("td.access.event", "visitor_id", readonly=True)
    violation_count = fields.Integer(compute="_compute_violation_count")
    is_today = fields.Boolean(string="Сьогодні", compute="_compute_is_today", search="_search_is_today")

    def init(self):
        # presence (SQL-представлення) створюється раніше за таблицю відвідувачів: перебудувати з UNION
        self.env["td.access.presence"].init()

    @api.depends("event_ids.zone_violation")
    def _compute_violation_count(self):
        counts = {}
        if self.ids:
            groups = (
                self.env["td.access.event"]
                .sudo()
                ._read_group(
                    [("visitor_id", "in", self.ids), ("zone_violation", "=", True)], ["visitor_id"], ["__count"]
                )
            )
            counts = {visitor.id: count for visitor, count in groups}
        for rec in self:
            rec.violation_count = counts.get(rec.id, 0)

    def _compute_is_today(self):
        start, end = local_day_bounds_utc(fields.Datetime.now())
        for rec in self:
            rec.is_today = bool(rec.date_from and rec.date_to and rec.date_from < end and rec.date_to >= start)

    def _search_is_today(self, operator, value):
        """Фільтр «Сьогодні»: візит перетинає київську добу сервера (а не `context_today()` браузера з py.js без
        datetime.time.min/max)."""
        if operator not in ("=", "!=") or not isinstance(value, bool):
            raise NotImplementedError("Пошук «Сьогодні» підтримує лише = / != True/False")
        start, end = local_day_bounds_utc(fields.Datetime.now())
        if (operator == "=") == value:
            return ["&", ("date_from", "<", end), ("date_to", ">=", start)]
        return ["|", ("date_from", ">=", end), ("date_to", "<", start)]

    @api.depends("name", "visitor_company")
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = "%s (%s)" % (rec.name, rec.visitor_company) if rec.visitor_company else rec.name

    @api.constrains("date_from", "date_to", "biostar_user_id")
    def _check_visitor(self):
        for rec in self:
            if rec.date_to <= rec.date_from:
                raise ValidationError("Час «До» має бути пізніше за «З».")
            if rec.date_to - rec.date_from > timedelta(days=7):
                raise ValidationError("Візит довший за 7 діб оформіть як окремі візити.")
            if rec.biostar_user_id and not P.BSID_RE.match(rec.biostar_user_id):
                raise ValidationError("Користувач BioStar %s: 1–64 символи [0-9A-Za-z_-]." % rec.biostar_user_id)

    # ------------------------------------------------------------------ створення, зв'язок з користувачем
    @api.model_create_multi
    def create(self, vals_list):
        hours = self._default_hours()
        for vals in vals_list:
            if vals.get("date_from") and not vals.get("date_to"):
                vals["date_to"] = fields.Datetime.to_datetime(vals["date_from"]) + timedelta(hours=hours)
            self._td_check_user_owner(vals.get("biostar_user_id"), vals.get("server_id") or self._default_server_id())
        records = super().create(vals_list)
        records.filtered("biostar_user_id")._td_sync_link()
        return records

    def write(self, vals):
        if "biostar_user_id" in vals:
            for rec in self:
                self._td_check_user_owner(vals["biostar_user_id"], vals.get("server_id") or rec.server_id.id)
        res = super().write(vals)
        if "biostar_user_id" in vals:
            self._td_sync_link()
        return res

    @api.model
    def _td_check_user_owner(self, user_id, server_id):
        if not user_id or not server_id:
            return
        link = (
            self.env["td.access.user.link"]
            .sudo()
            .with_context(active_test=False)
            .search([("server_id", "=", server_id), ("biostar_user_id", "=", user_id)], limit=1)
        )
        if link.employee_id:
            raise ValidationError("Користувач BioStar %s належить працівнику %s." % (user_id, link.employee_id.name))

    def _td_sync_link(self):
        """R-14 крок 2: зв'язок (server, biostar_user_id) -> відвідувач, match='visitor'."""
        Link = self.env["td.access.user.link"].sudo().with_context(active_test=False)
        for rec in self.sudo():
            uid = rec.biostar_user_id
            stale = Link.search([("visitor_id", "=", rec.id), ("biostar_user_id", "!=", uid or "")])
            if stale:
                stale.write({"visitor_id": False, "match": "none"})
            if not uid:
                rec.link_id = False
                continue
            link = Link.search([("server_id", "=", rec.server_id.id), ("biostar_user_id", "=", uid)], limit=1)
            if link.employee_id:
                raise ValidationError("Користувач BioStar %s належить працівнику %s." % (uid, link.employee_id.name))
            vals = {"visitor_id": rec.id, "match": "visitor", "active": True}
            if link:
                link.write(vals)
            else:
                link = Link.create(dict(vals, server_id=rec.server_id.id, biostar_user_id=uid))
            rec.link_id = link

    # ------------------------------------------------------------------ права
    def _check_security(self):
        if not self.env.su and not self.env.user.has_group(SECURITY):
            raise AccessError("Цю дію з відвідувачем може виконати лише охорона.")

    @staticmethod
    def _state_label(rec):
        return dict(STATES).get(rec.state, rec.state)

    # ------------------------------------------------------------------ переходи (§10.4)
    def action_expect(self):
        self._check_security()
        for rec in self:
            if rec.state != "draft":
                raise UserError("Очікувати можна лише чернетку візиту.")
        for rec in self:
            rec.write({"state": "expected"})
            rec._td_push_user()
            rec._td_assign_card()
        return True

    def _td_assign_card(self):
        """Картка з пулу (або обрана вручну) -> видана відвідувачу."""
        self.ensure_one()
        Card = self.env["td.access.card"].sudo()
        card = self.card_id.sudo()
        if not card:
            card = Card.search(
                [
                    ("holder_type", "=", "pool"),
                    ("state", "in", ("draft", "returned")),
                    ("server_id", "=", self.server_id.id),
                ],
                order="number",
                limit=1,
            )
        if not card:
            self.message_post(body="Вільних карток у пулі немає")
            return
        if card.state != "active":
            card.write({"holder_type": "visitor", "visitor_id": self.id})
            card.action_issue()
        self.card_id = card

    def action_arrive(self):
        self._check_security()
        for rec in self:
            if rec.state != "expected":
                raise UserError("Позначити прихід можна лише для очікуваного відвідувача.")
            door = (
                self.env["td.access.door"]
                .sudo()
                .search([("is_perimeter", "=", True), ("server_id", "=", rec.server_id.id)], limit=1)
            )
            now = fields.Datetime.now()
            rec.write(
                {
                    "state": "on_site",
                    "arrived_at": now,
                    "present": True,
                    "zone_id": door.zone_to_id.id,
                    "zone_since": now,
                }
            )
        return True

    def action_leave(self):
        self._check_security()
        for rec in self:
            if rec.state != "on_site":
                raise UserError("Позначити вихід можна лише для відвідувача на території.")
            rec.write(
                {
                    "state": "left",
                    "left_at": fields.Datetime.now(),
                    "present": False,
                    "zone_id": False,
                    "zone_since": False,
                    "zone_door_id": False,
                }
            )
        return True

    def action_close(self):
        self._check_security()
        for rec in self:
            if rec.state not in ("left", "expected", "on_site"):
                raise UserError("Закрити можна лише візит, що очікується, триває або завершився.")
        for rec in self:
            rec._td_close({"state": "closed"})
        return True

    def action_cancel(self):
        self._check_security()
        for rec in self:
            if rec.state not in ("draft", "expected"):
                raise UserError("Скасувати можна лише чернетку або очікуваний візит.")
        for rec in self:
            rec._td_close({"state": "cancelled"})
        return True

    def _td_close(self, vals):
        """Спільна частина закриття/скасування: присутність знімається, картка повертається."""
        self.ensure_one()
        vals = dict(vals, present=False, zone_id=False, zone_since=False, zone_door_id=False)
        self.write(vals)
        card = self.card_id.sudo()
        if card.state in ("active", "blocked") and (card.visitor_id == self or card.holder_type == "visitor"):
            card.action_return()
        if vals["state"] == "closed" and self.link_id:
            self.link_id.sudo().write({"active": False})

    def unlink(self):
        if not self.env.context.get("f3d_housekeeping") and self.filtered(
            lambda r: r.state not in ("draft", "cancelled")
        ):
            raise UserError("Видалити можна лише чернетку або скасований візит.")
        return super().unlink()

    @api.model
    def f3d_visitor_register(self, vals):
        """CA-07: оформити візит з іншого модуля (create + «Очікується»)."""
        rec = self.create(vals)
        rec.action_expect()
        return rec

    # ------------------------------------------------------------------ користувач BioStar (R-14 крок 2)
    def _td_push_user(self):
        for rec in self.sudo():
            if not P.get_flag(self.env, "write_enabled"):
                if rec.sync_state != "synced":
                    rec.write({"sync_state": "local"})
                continue
            if rec.biostar_user_id and rec.sync_state == "local":
                continue  # користувач уже створений у BioStar вручну
            rec._td_create_user()
        return True

    def _td_create_user(self):
        self.ensure_one()
        if not self.biostar_user_id:
            self.biostar_user_id = P.get_str(self.env, "visitor_user_prefix", "V-") + str(self.id)
        server = self.server_id
        client = server._get_client()
        try:
            client.create_user(
                self.biostar_user_id,
                self.name,
                self.date_from,
                self.date_to + GRACE,
                P.get_str(self.env, "visitor_user_group_id", "1"),
            )
        except BioStarWriteDisabled:
            self.write({"sync_state": "local"})
            return False
        except BioStarError as exc:
            if "exist" in str(exc).lower():
                self.write({"sync_state": "synced", "sync_error": False})
                return True
            self.write({"sync_state": "error", "sync_error": str(exc)[:255]})
            return False
        finally:
            server._save_session(client)
        self.write({"sync_state": "synced", "sync_error": False})
        return True

    @api.model
    def _cron_user_sync(self):
        if not P.get_flag(self.env, "write_enabled"):
            return
        self.sudo().search(
            [
                ("state", "in", ("expected", "on_site")),
                "|",
                ("sync_state", "in", ("pending", "error")),
                "&",
                ("sync_state", "=", "local"),
                ("biostar_user_id", "=", False),
            ],
            limit=100,
        )._td_push_user()

    # ------------------------------------------------------------------ присутність (R-14, R-17)
    def _td_presence_set(self, vals):
        """Записати присутність/зону; True, якщо щось змінилось."""
        self.ensure_one()
        diff = {}
        for name, value in vals.items():
            current = self[name]
            current = current.id if hasattr(current, "id") else current
            if (current or False) != (value or False):
                diff[name] = value
        if diff:
            self.sudo().write(diff)
        return bool(diff)


class F3dAccessUserLink(models.Model):
    _inherit = "td.access.user.link"

    visitor_id = fields.Many2one("td.access.visitor", string="Відвідувач", index=True, ondelete="set null")

    _f3d_access_link_one_holder = models.Constraint(
        "CHECK(employee_id IS NULL OR visitor_id IS NULL)",
        "Користувач BioStar належить або працівнику, або відвідувачу.",
    )


class F3dAccessEvent(models.Model):
    _inherit = "td.access.event"

    visitor_id = fields.Many2one("td.access.visitor", string="Відвідувач", index=True, ondelete="set null")

    _f3d_access_event_visitor_ts_idx = models.Index("(visitor_id, ts)")

    def _td_visitor_pass(self, visitor):
        """R-14 кроки 3–4: стан і зона відвідувача за проходом; відміток hr.attendance немає."""
        self.ensure_one()
        res = {"attendance_action": "not_employee"}
        visitor = visitor.sudo()
        last = visitor.last_event_id
        if last and last != self and last.ts > self.ts:
            return {"attendance_action": "late"}
        ts, door, direction = self.ts, self.door_id, self.direction
        upd = {}
        note = False
        if direction not in ("in", "out"):
            return res
        if self.is_perimeter:
            if direction == "in":
                if visitor.state == "left" and ts > visitor.date_to + GRACE:
                    note = True
                elif visitor.state in ("expected", "on_site", "left"):
                    upd = {
                        "state": "on_site",
                        "present": True,
                        "zone_id": door.zone_to_id.id,
                        "zone_since": ts,
                        "zone_door_id": False,
                        "left_at": False,
                    }
                    if visitor.state == "expected":
                        upd["arrived_at"] = ts
                else:
                    note = True
            elif visitor.state == "on_site":
                upd = {
                    "state": "left",
                    "left_at": ts,
                    "present": False,
                    "zone_id": False,
                    "zone_since": False,
                    "zone_door_id": False,
                }
            else:
                note = True
        elif visitor.state != "on_site":
            note = True
        elif direction == "in" and door.zone_to_id:
            upd = {
                "present": True,
                "zone_id": door.zone_to_id.id,
                "zone_door_id": door.id if door.dwell_min > 0 else False,
            }
            if visitor.zone_id != door.zone_to_id:
                upd["zone_since"] = ts
            if visitor.allowed_zone_ids and door.zone_to_id not in visitor.allowed_zone_ids:
                res["zone_violation"] = True
        elif direction == "out" and door.zone_from_id:
            upd = {"present": True, "zone_id": door.zone_from_id.id, "zone_since": ts, "zone_door_id": False}
        if note:
            res["error_message"] = "Відвідувач у стані «%s»: прохід лише зафіксовано" % self.env[
                "td.access.visitor"
            ]._state_label(visitor)
        else:
            res["presence_changed"] = visitor._td_presence_set(upd)
            visitor.sudo().write({"last_event_id": self.id})
        return res

    @api.model
    def _td_on_site_visitors(self, ts, cids, hours):
        self.flush_model()
        self.env["td.access.visitor"].flush_model()
        cr = self.env.cr
        cr.execute(
            """
            SELECT visitor_id FROM (
              SELECT DISTINCT ON (visitor_id) visitor_id, direction
                FROM td_access_event
               WHERE visitor_id IS NOT NULL AND is_perimeter AND event_type = 'pass'
                 AND direction IN ('in', 'out') AND ts <= %(ts)s
                 AND ts >= %(ts)s - make_interval(hours => %(h)s) AND company_id = ANY(%(cids)s)
               ORDER BY visitor_id, ts DESC, id DESC) last
             WHERE direction = 'in'""",
            {"ts": ts, "h": hours, "cids": cids},
        )
        ids = {r[0] for r in cr.fetchall()}
        cr.execute(
            """
            SELECT v.id FROM td_access_visitor v
             WHERE v.present AND v.state = 'on_site' AND v.arrived_at <= %(ts)s AND v.company_id = ANY(%(cids)s)
               AND NOT EXISTS (SELECT 1 FROM td_access_event ev WHERE ev.visitor_id = v.id
                                  AND ev.is_perimeter AND ev.event_type = 'pass')""",
            {"ts": ts, "cids": cids},
        )
        ids |= {r[0] for r in cr.fetchall()}
        return self.env["td.access.visitor"].sudo().browse(sorted(ids))

    @api.model
    def _td_dwell_visitors(self, now, collector):
        """R-17 для відвідувачів: повернення з технічного приміщення в зону `zone_from_id` дверей."""
        visitors = self.env["td.access.visitor"].sudo().search([("present", "=", True), ("zone_door_id", "!=", False)])
        for visitor in visitors:
            door = visitor.zone_door_id
            if (
                door.dwell_min > 0
                and visitor.zone_since
                and visitor.zone_since + timedelta(minutes=door.dwell_min) <= now
            ):
                visitor._td_presence_set({"zone_id": door.zone_from_id.id, "zone_since": now, "zone_door_id": False})

    @api.model
    def _td_housekeeping_visitors(self, now, keep_days):
        """R-20 кроки 3, 5, 6: закриття прострочених візитів, відв'язка карток, видалення старих візитів."""
        Visitor = self.env["td.access.visitor"].sudo()
        expired = Visitor.search([("state", "in", ("expected", "on_site", "left")), ("date_to", "<", now - GRACE)])
        for visitor in expired:
            vals = {"state": "closed"}
            if visitor.state in ("expected", "on_site"):
                vals["overdue"] = True
            visitor._td_close(vals)
            visitor.message_post(body="Закрито автоматично: строк візиту минув")
        cutoff = now - timedelta(days=keep_days)
        cards = (
            self.env["td.access.card"]
            .sudo()
            .search([("state", "in", ("returned", "lost")), ("returned_at", "<", cutoff), ("visitor_id", "!=", False)])
        )
        for card in cards:
            card.write(
                {"visitor_id": False, "holder_type": "pool"} if card.holder_type == "visitor" else {"visitor_id": False}
            )
        Visitor.with_context(f3d_housekeeping=True).search(
            [("state", "in", ("closed", "cancelled")), ("date_to", "<", cutoff)]
        ).unlink()


class F3dZone(models.Model):
    _inherit = "td.zone"

    td_people_visitor_ids = fields.Many2many("td.access.visitor", compute="_compute_f3d_people")

    def _td_people_visitors(self):
        by_zone = {}
        for visitor in (
            self.env["td.access.visitor"]
            .sudo()
            .search([("present", "=", True), ("state", "=", "on_site"), ("zone_id", "in", self.ids)])
        ):
            by_zone.setdefault(visitor.zone_id.id, []).append(visitor.id)
        return by_zone

    def _compute_f3d_people(self):
        super()._compute_f3d_people()
        visitors = self._td_people_visitors()
        for zone in self:
            zone.td_people_visitor_ids = self.env["td.access.visitor"].sudo().browse(visitors.get(zone.id, []))


class F3dAccessPresence(models.Model):
    _inherit = "td.access.presence"

    visitor_id = fields.Many2one("td.access.visitor", readonly=True)

    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        # представлення читає таблиці працівників і відвідувачів: ORM не знає про них, тому скидаємо кеш запису
        self.env["hr.employee"].flush_model()
        self.env["td.access.visitor"].flush_model()
        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)
