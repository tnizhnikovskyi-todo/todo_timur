import logging
import re
from datetime import timedelta

from psycopg2 import OperationalError

from odoo import _, api, fields, models, tools
from odoo.exceptions import AccessError, UserError, ValidationError

from odoo.addons.td_telemetry.tools import thresholds
from odoo.addons.td_telemetry.tools.titles import fmt_num, render_title

from ..tools import bus, dates

_logger = logging.getLogger(__name__)

STATUS_LEVEL = {"warn": "warn", "alarm": "bad"}
OPEN_STATES = ("active", "acked")
PFC_FAULT_RE = re.compile(r"^energy/cells/PFC-(\d)/fault_step$")
SECTION_COS_RE = re.compile(r"^energy/sections/S(\d)/cos_phi$")
TITLE_MAX = 128
TITLE_SPLIT_AT = 100


def split_text(text):
    """R-24 п. 1: `text` → `(title, detail)`: розділювач «. » або «: » на позиції ≤ 100, інакше весь текст."""
    text = (text or "").strip()
    positions = [p for p in (text.find(". "), text.find(": ")) if 0 <= p <= TITLE_SPLIT_AT]
    if positions:
        pos = min(positions)
        title, detail = text[:pos].rstrip(), text[pos + 2 :].strip()
    else:
        title, detail = text, ""
    if len(title) > TITLE_MAX:
        title = title[: TITLE_MAX - 3] + "…"
    return title, detail


class F3dEnergyEvent(models.Model):
    """M-09. Журнал подій енергетики (R-13). `outage_id` — W4 (R-14). W1 (M-21): життєвий цикл тривог (R-24, R-25)."""

    _name = "td.energy.event"
    _description = "Енергетика: подія"
    _order = "ts desc, id desc"
    _log_access = False

    ts = fields.Datetime(string="Час", required=True, index=True, default=fields.Datetime.now)
    level = fields.Selection(
        [("info", "Інформація"), ("warn", "Увага"), ("bad", "Аварія")], string="Рівень", required=True, index=True
    )
    kind = fields.Selection(
        [
            ("threshold", "Поріг сигналу"),
            ("peak", "Пік потужності"),
            ("balance", "Баланс"),
            ("meter", "Лічильник"),
            ("ats", "АВР"),
            ("outage", "Відключення"),
            ("pfc", "Компенсація"),
            ("trip", "Спрацювання захисту"),  # W1 (ND-14): подію створює R-30 п. 9
            ("manual", "Вручну"),
        ],
        string="Вид",
        required=True,
    )
    code = fields.Char(string="Код", size=32)
    node_id = fields.Many2one("td.energy.node", string="Вузол", ondelete="set null")
    signal_id = fields.Many2one("td.signal", string="Сигнал", ondelete="set null")
    text = fields.Char(string="Текст", size=256, required=True)
    outage_id = fields.Many2one("td.energy.outage", string="Відключення", ondelete="set null", index=True)  # W4
    # --- W1 (M-21): тривога з життєвим циклом -----------------------------------------------------------
    title = fields.Char(string="Заголовок", size=128)
    detail = fields.Char(string="Деталі", size=256)
    state = fields.Selection(
        [("na", "Інформація"), ("active", "Активна"), ("acked", "Підтверджена"), ("resolved", "Вирішена")],
        string="Стан",
        required=True,
        default="na",
        index=True,
    )
    acked_by = fields.Many2one("res.users", string="Підтвердив", ondelete="set null", readonly=True)
    acked_at = fields.Datetime(string="Підтверджено", readonly=True)
    assigned_user_id = fields.Many2one(
        "res.users", string="Виконавець", ondelete="set null", index=True, readonly=True
    )
    taken_at = fields.Datetime(string="Взято в роботу", readonly=True)
    resolved_at = fields.Datetime(string="Вирішено", readonly=True)
    request_id = fields.Many2one("maintenance.request", string="Заявка ТО", compute="_compute_request_id")
    action_code = fields.Char(string="Дія", compute="_compute_action_code")
    is_backfill = fields.Boolean(string="Синтетична (backfill)", default=False, index=True, readonly=True)

    def init(self):
        tools.sql.create_index(self.env.cr, "td_energy_event_state_ts_idx", self._table, ["state", "ts"])

    @api.constrains("level", "state")
    def _check_state(self):
        for rec in self:
            ok = rec.state == "na" if rec.level == "info" else rec.state in OPEN_STATES + ("resolved",)
            if not ok:
                raise ValidationError(_("Некоректний стан події: %s.", rec.state))

    def _compute_request_id(self):
        Request = self.env["maintenance.request"].sudo()
        for rec in self:
            request = Request
            if rec.signal_id:
                request = Request.search(
                    [("td_signal_id", "=", rec.signal_id.id), ("stage_id.done", "=", False)], order="id desc", limit=1
                )
            rec.request_id = request

    @api.depends("kind", "state", "signal_id")
    def _compute_action_code(self):
        for rec in self:
            if rec.kind == "meter" and rec.state != "resolved":
                rec.action_code = "diag"
            elif rec.request_id:
                rec.action_code = "request"
            else:
                rec.action_code = False

    @api.model_create_multi
    def create(self, vals_list):
        """R-24: `title`/`detail` із `text`; початковий `state` за рівнем; після створення — тік шини `alarm`."""
        for vals in vals_list:
            if not vals.get("title"):
                vals["title"], detail = split_text(vals.get("text"))
                vals.setdefault("detail", detail)
            else:
                vals.setdefault("detail", "")
            if "state" not in vals:
                vals["state"] = "na" if vals.get("level") == "info" else "active"
        records = super().create(vals_list)
        if not all(v.get("is_backfill") for v in vals_list):
            bus.tick(self.env, "alarm")
        return records

    @api.model
    def _f3d_log(
        self, level, kind, code, text, ts=None, node=None, signal=None, outage=None, dedup_min=0, title=None,
        detail=None,
    ):  # fmt: skip
        """M-09: подія; `dedup_min > 0` і є така сама (kind, code, text) за останні хвилини — не створювати.
        W1 (API-03): `title`/`detail` — явні (інакше R-24); тік шини `alarm` — у `create`. SPEC-ім'я — `_td_log`."""
        ts = ts or dates.now_utc(self.env)
        text = (text or "")[:256]
        if dedup_min > 0 and self.sudo().search_count(
            [
                ("kind", "=", kind),
                ("code", "=", code or False),
                ("text", "=", text),
                ("ts", ">=", ts - timedelta(minutes=dedup_min)),
            ]
        ):
            return self.browse()
        vals = {"ts": ts, "level": level, "kind": kind, "code": code or False, "text": text}
        if title:
            vals.update(title=title[:TITLE_MAX], detail=(detail or "")[:256])
        if node:
            vals["node_id"] = node.id
        if signal:
            vals["signal_id"] = signal.id
        if outage:
            vals["outage_id"] = outage.id
        rec = self.sudo().create(vals)
        if "td.viewer.event" in self.env:
            self.env["td.viewer.event"]._notify("td.energy", [code] if code else [], "signal")
        return rec

    _td_log = _f3d_log  # ім'я з W1_SPEC (A-23); існуючі виклики — `_f3d_log`

    # --- R-13 п. 1–2: події за зміною показань ---------------------------------------------------------
    @api.model
    def _f3d_on_ingest(self, before, readings):
        """`before` — {код: (status, last_text, last_value)} до прийому пакета; пакет уже в базі."""
        try:
            with self.env.cr.savepoint():
                self._f3d_on_ingest_inner(before)
        except OperationalError:
            raise  # O-2: serialization/deadlock — ретрай запиту (Odoo http/telemetry) має спрацювати
        except Exception:
            _logger.exception("f3d_energy: помилка журналу подій після прийому показань")

    @api.model
    def _f3d_on_ingest_inner(self, before):
        Signal = self.env["td.signal"].sudo()
        self._f3d_ats_hook(before)  # W4: R-14
        signals = Signal.search([("code", "in", list(before))])
        for sig in signals.sorted("code"):
            old_status, old_text, _old_value = before[sig.code]
            if sig.code.startswith("workcenters/"):
                if sig.last_text == "fault" and old_text != "fault":
                    self._f3d_machine_fault(sig)
            elif sig.module == "energy":
                if PFC_FAULT_RE.match(sig.code):
                    self._td_pfc_fault_event(sig, _old_value)  # W1 R-35 п. 3а
                if sig.status != old_status:
                    self._f3d_status_event(sig, old_status)
                if sig.kind == "state" and sig.last_text == "tripped" and old_text != "tripped":
                    self._td_trip_event(sig)  # W1 R-30 п. 9

    @api.model
    def _f3d_ats_hook(self, before):
        """W4, R-14 п. 1: похідні `src{1,2}_ok`; п. 2–10: автомат відключення (крок після кожного пакета АВР/вводів)."""
        if self.env.context.get("f3d_ats_busy"):
            return
        from ..models.td_energy_outage import TRIGGER_CODES

        if not any(c in TRIGGER_CODES for c in before):
            return
        self = self.with_context(f3d_ats_busy=True)
        Signal = self.env["td.signal"].sudo()
        derived = []
        for n in (1, 2):
            sig = Signal.search([("code", "=", "infra/ats/src%d_state" % n)], limit=1)
            if sig and "infra/ats/src%d_state" % n in before and sig.last_ts:
                derived.append(
                    {
                        "code": "infra/ats/src%d_ok" % n,
                        "ts": sig.last_ts,
                        "value": 1 if sig.last_text == "available" else 0,
                        "q": "good",
                    }
                )
        if derived:
            Signal._f3d_energy_put(derived)
        self.env["td.energy.outage"]._f3d_ats_step()

    @api.model
    def _f3d_status_event(self, sig, old_status):
        new = sig.status
        if new in ("stale", "unknown"):
            return
        match = SECTION_COS_RE.match(sig.code)
        if match:  # W1 R-35 п. 3б: низький cos φ секції — подія `pfc`, а не загальний поріг
            return self._td_section_cos_event(sig, int(match.group(1)), old_status)
        if PFC_FAULT_RE.match(sig.code):  # подію `pfc` створює `_td_pfc_fault_event` (за значенням, не за статусом)
            return
        ts = sig.last_ts or dates.now_utc(self.env)
        unit = (" " + sig.unit) if sig.unit else ""
        if new in STATUS_LEVEL:
            threshold, rel = thresholds.breach_info(sig._f3d_cfg(), sig.last_value)
            text = render_title(sig, sig.last_value, rel, threshold, sig.last_text)
            level = STATUS_LEVEL[new]
        elif old_status in ("warn", "alarm"):
            if sig.kind == "state":
                value = sig.last_text or ""
            else:
                value = ("%s%s" % (fmt_num(sig.last_value, sig.decimals), unit)).strip()
            text = "%s: повернувся в норму (%s)" % (sig.name, value)
            level = "info"
        else:
            return
        self._f3d_log(level, "threshold", sig.equipment_code or False, text, ts=ts, signal=sig)
        if new == "ok":  # W1 R-25: поріг повернувся в норму — відкриті події сигналу вирішено
            self._td_auto_resolve("threshold", signal=sig)

    @api.model
    def _f3d_machine_fault(self, sig):
        """R-13 п. 2: верстат став `fault` — аварійна зупинка зі споживанням вузла."""
        wc_code = sig.code.split("/")[1]
        Node = self.env["td.energy.node"].sudo()
        node = Node.search([("code", "=", wc_code)], limit=1) or Node.search(
            [("workcenter_id.name", "=", wc_code)], limit=1
        )
        p_now = node.p_now if node else 0.0
        text = "%s: аварійна зупинка, споживання впало до %s кВт." % (wc_code, fmt_num(p_now, 1))
        self._f3d_log("bad", "threshold", wc_code, text, ts=sig.last_ts, node=node or None, signal=sig)

    @api.model
    def _f3d_pfc_event(self, node, old_q, new_q, cos_after, ts=None):
        """R-13 п. 4: зміна кількості увімкнених ступенів компенсації секції."""
        diff = int(new_q) - int(old_q)
        if not diff:
            return self.browse()
        step = node.pfc_step_kvar or 50  # W1 D-09: крок ступеня — параметр вузла (за замовчуванням 35 квар)
        n = abs(diff) // step
        if n == 1:
            action = (
                "увімкнено ще один ступінь %d квар" % step if diff > 0 else "вимкнено ступінь %d квар" % step
            )
        else:
            word = "ступені" if n in (2, 3, 4) else "ступенів"
            action = "%s %d %s (%d квар)" % ("увімкнено" if diff > 0 else "вимкнено", n, word, abs(diff))
        text = "Компенсація секції %d: %s, cos φ %s." % (node.section, action, fmt_num(cos_after, 2))
        return self._f3d_log("info", "pfc", node.code, text, ts=ts, node=node, dedup_min=10)

    # --- W1 (M-21, R-35): події PFC, захисту ------------------------------------------------------------
    @api.model
    def _td_pfc_fault_event(self, sig, old_value):
        """R-35 п. 3а: `fault_step` 0→k>0 — подія `pfc` `warn` (dedup 60 хв); k→0 — спроба вирішити (R-25)."""
        section = int(PFC_FAULT_RE.match(sig.code).group(1))
        code = "PFC-%d" % section
        new, old = int(sig.last_value or 0), int(old_value or 0)
        if new > 0 and not old:
            node = self.env["td.energy.node"].sudo().search([("code", "=", code)], limit=1)
            title = "%s: ступінь %d не вмикається" % (code, new)
            self._f3d_log(
                "warn", "pfc", code, title, ts=sig.last_ts, node=node or None, signal=sig, dedup_min=60, title=title
            )
        elif not new and old:
            self._td_pfc_resolve(section)

    @api.model
    def _td_section_cos_event(self, sig, section, old_status):
        """R-35 п. 3б: cos φ секції нижче порогу довше `min_duration_s` — подія `pfc` (`bad` при `< alarm`)."""
        code = "PFC-%d" % section
        if sig.status in ("warn", "alarm"):
            node = self.env["td.energy.node"].sudo().search([("code", "=", code)], limit=1)
            title = "cos φ секції %d — %s" % (section, fmt_num(sig.last_value, 2))
            level = "bad" if sig.status == "alarm" else "warn"
            return self._f3d_log(
                level, "pfc", code, title, ts=sig.last_ts, node=node or None, signal=sig, dedup_min=5, title=title
            )
        if old_status in ("warn", "alarm"):
            self._td_pfc_resolve(section)
        return self.browse()

    @api.model
    def _td_pfc_resolve(self, section):
        """R-25: `pfc` вирішується, коли `fault_step = 0` і cos φ секції ≥ `cos_phi_warn` (немає даних — не заважає)."""
        Signal = self.env["td.signal"].sudo()
        fault = Signal.search([("code", "=", "energy/cells/PFC-%d/fault_step" % section)], limit=1)
        if fault and fault.last_ts and (fault.last_value or 0) > 0:
            return self.browse()
        cos = Signal.search([("code", "=", "energy/sections/S%d/cos_phi" % section)], limit=1)
        warn = dates.param_float(self.env, "cos_phi_warn", 0.92)
        if cos and cos.last_ts and cos.last_value is not None and cos.last_value < warn:
            return self.browse()
        return self._td_auto_resolve("pfc", code="PFC-%d" % section)

    @api.model
    def _td_trip_event(self, sig):
        """R-30 п. 9: стан автомата → `tripped`: подія `trip` `warn` «Спрацював захист {QF}» (ND-14)."""
        code = sig.equipment_code or False
        node = self.env["td.energy.node"].sudo().search([("code", "=", code)], limit=1) if code else None
        title = "Спрацював захист %s" % (code or sig.name)
        return self._f3d_log(
            "warn", "trip", code, title, ts=sig.last_ts, node=node or None, signal=sig, dedup_min=1, title=title
        )

    # --- W1 (M-21, R-25): життєвий цикл -----------------------------------------------------------------
    def _td_check_energetic(self):
        if not self.env.user.has_group("td_energy.group_td_energy_manager"):
            raise AccessError(_("Підтверджувати тривоги може лише енергетик."))

    def _td_lock(self):
        """Гонка двох користувачів (R-25, розд. 11): блокування рядків і свіжий стан."""
        if self.ids:
            self.env.cr.execute("SELECT id FROM td_energy_event WHERE id IN %s FOR UPDATE", (tuple(self.ids),))
            self.invalidate_recordset()

    def action_ack(self):
        """M-21: `active → acked` (`acked_by`, `acked_at`); інші стани — пропустити без помилки."""
        self._td_check_energetic()
        now = dates.now_utc(self.env)
        self._td_lock()
        todo = self.sudo().filtered(lambda r: r.state == "active")
        todo.write({"acked_by": self.env.uid, "acked_at": now, "state": "acked"})
        bus.tick(self.env, "alarm")
        return True

    def action_take(self):
        """M-21: `active|acked` + виконавець = поточний користувач (одночасно `ack` для `active`)."""
        self._td_check_energetic()
        now = dates.now_utc(self.env)
        self._td_lock()
        for rec in self.sudo():
            if rec.state not in OPEN_STATES:
                raise UserError(_("Подію вже закрито."))
            if rec.assigned_user_id and rec.assigned_user_id.id != self.env.uid:
                raise UserError(_("Уже в роботі: %s.", rec.assigned_user_id.name))
            vals = {"assigned_user_id": self.env.uid, "taken_at": now}
            if rec.state == "active":
                vals.update(acked_by=self.env.uid, acked_at=now, state="acked")
            rec.write(vals)
        bus.tick(self.env, "alarm")
        return True

    def _td_check_owner(self):
        chief = self.env.user.has_group("td_energy.group_td_energy_chief")
        for rec in self.sudo():
            if not chief and rec.assigned_user_id.id != self.env.uid:
                raise AccessError(_("Змінювати чужу тривогу може лише виконавець або головний енергетик."))

    def action_release(self):
        self._td_check_energetic()
        self._td_check_owner()
        self.sudo().write({"assigned_user_id": False, "taken_at": False})
        bus.tick(self.env, "alarm")
        return True

    def action_resolve(self):
        self._td_check_energetic()
        if any(rec.level == "info" for rec in self):
            raise UserError(_("Інформаційну подію закривати не потрібно."))
        self._td_check_owner()
        now = dates.now_utc(self.env)
        self._td_lock()
        self.sudo().filtered(lambda r: r.state in OPEN_STATES).write({"state": "resolved", "resolved_at": now})
        bus.tick(self.env, "alarm")
        return True

    @api.model
    def _td_auto_resolve(self, kind, code=None, node=None, signal=None):
        """R-25: відкриті (`active|acked`) події виду `kind` за `code`, `node` або `signal` → `resolved`."""
        match = []
        if code:
            match.append(("code", "=", code))
        if node:
            match.append(("node_id", "=", node.id))
        if signal:
            match.append(("signal_id", "=", signal.id))
        if not match:
            return self.browse()
        domain = [("kind", "=", kind), ("state", "in", OPEN_STATES)] + ["|"] * (len(match) - 1) + match
        events = self.sudo().search(domain)
        if events:
            events.write({"state": "resolved", "resolved_at": dates.now_utc(self.env)})
            bus.tick(self.env, "alarm")
        return events
