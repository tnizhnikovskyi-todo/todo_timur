import logging
import re
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from odoo import _, api, fields, models
from odoo.exceptions import UserError

from .td_machine import CONTENTION_ERRORS, local, param, param_bool

_logger = logging.getLogger(__name__)

UTC = ZoneInfo("UTC")
WO_RE = re.compile(r"^(?:WO0*(\d{1,9})|(\d{1,9}))$")
CJ_RE = re.compile(r"^cj-\d+$")
FIT_STATES = ("ready", "progress", "blocked")
PRODUCTIVE = ("productive", "performance")
BLOCKING = ("availability", "quality")
NO_JOB_MARK = "працює без завдання"


class F3dMachineWo(models.Model):
    """M-01 (`_inherit = "td.machine"`): автостарт, пауза, лічильник, завершення (R-09…R-12). Власник — W3.

    Перевизначення гачків `_td_on_count`, `_td_on_job`, `_td_after_commit`, `_td_tick_extra`,
    `_td_apply_event` — через `super()` першим. Діяльності на верстаті потребують `mail.activity.mixin`.

    DEC-1: у CE немає `employee_ids`/`start_employee`/`stop_employee` (це Enterprise `mrp_workorder`); код користується
    ними лише за наявності (duck typing), інакше `button_start()` + `mrp.workorder.td_employee_id`.
    """

    _name = "td.machine"
    _inherit = ["td.machine", "mail.activity.mixin"]

    # --- службове -----------------------------------------------------------------------------------
    def _td_autostart_on(self):
        self.ensure_one()
        return param_bool(self.env, "auto_start_enabled") and self.auto_start_mode != "off"

    def _td_lock_wo(self, wo):
        """DEC-20: `FOR UPDATE SKIP LOCKED` на рядок завдання; `False` — зайнято (диспетчер живого виробництва,
        інший крон) або змінено паралельно після знімка (REPEATABLE READ): крок такту пропускається до наступного."""
        cr = self.env.cr
        try:
            with cr.savepoint(flush=False):
                cr.execute(
                    "SELECT id FROM mrp_workorder WHERE id = %s FOR UPDATE SKIP LOCKED", (wo.id,), log_exceptions=False
                )
                return bool(cr.fetchone())
        except CONTENTION_ERRORS:
            return False

    def _td_activity(self, rec, text, user=None):
        """Діяльність `mail.mail_activity_data_todo` (SPEC §13.0 п. 7); дубль за `summary` не створюється."""
        summary = text[:64]
        if (
            self.env["mail.activity"]
            .sudo()
            .search_count([("res_model", "=", rec._name), ("res_id", "=", rec.id), ("summary", "=", summary)])
        ):
            return False
        user = user or self.equipment_id.sudo().technician_user_id or self.env.ref("base.user_admin")
        rec.sudo().activity_schedule("mail.mail_activity_data_todo", summary=summary, note=text, user_id=user.id)
        return True

    def _td_post_mo(self, wo, body):
        wo.production_id.sudo().message_post(body=body, subtype_xmlid="mail.mt_note")

    def _td_wc_employees(self, wc):
        """Дозволені працівники РЦ: `wc.employee_ids` (Enterprise), інакше порожньо (дозволено все)."""
        if "employee_ids" in wc._fields:
            return wc.sudo().employee_ids
        return self.env["hr.employee"]

    def _td_open_timers(self, wo):
        return (
            self.env["mrp.workcenter.productivity"]
            .sudo()
            .search([("workorder_id", "=", wo.id), ("date_end", "=", False)])
        )

    def _td_operator_working(self, wo):
        """R-09 п. 4 (а): оператор уже працює над завданням."""
        wo = wo.sudo()
        if "employee_ids" in wo._fields and wo.employee_ids:
            return True
        return bool(wo.td_employee_id and self._td_open_timers(wo))

    def _td_timer_employee(self, rec):
        """Працівник запису журналу часу: `wo.td_employee_id`, інакше працівник користувача запису."""
        bot = self.env.ref("td_machine_connect.user_td_machine")
        emp = rec.workorder_id.sudo().td_employee_id
        if not emp and rec.user_id and rec.user_id != bot:
            emp = rec.user_id.sudo().employee_id
        return emp or self.env["hr.employee"]

    def _td_day_start(self, wc, now):
        tz = self._td_tz(wc)
        midnight = datetime.combine(now.replace(tzinfo=UTC).astimezone(tz).date(), time.min, tz)
        return midnight.astimezone(UTC).replace(tzinfo=None)

    def _td_last_employee(self, domain):
        recs = (
            self.env["mrp.workcenter.productivity"]
            .sudo()
            .search(domain + [("loss_id.loss_type", "in", PRODUCTIVE)], order="date_start desc, id desc")
        )
        for rec in recs:
            emp = self._td_timer_employee(rec)
            if emp:
                return emp
        return self.env["hr.employee"]

    # --- збіг завдання (R-09 п. 1–2) ------------------------------------------------------------------
    def _td_job_wo(self, text):
        """Завдання за текстом `JobOrderID` без перевірки придатності."""
        wo = self.env["mrp.workorder"]
        text = (text or "").strip()
        match = WO_RE.match(text)
        if match:
            return wo.sudo().browse(int(match.group(1) or match.group(2))).exists()
        if CJ_RE.match(text):
            cut_map = self.env["td.cut.map"].sudo().search([("ext_job_id", "=", text)], limit=1)
            return cut_map.workorder_id
        return wo

    def _td_match_job(self, text):
        self.ensure_one()
        wo = self._td_job_wo(text)
        if wo and wo.workcenter_id == self.workcenter_id and wo.state in FIT_STATES:
            return wo
        return self.env["mrp.workorder"]

    def _td_candidate(self, ts):
        """Одне в черзі (лише `job_or_single`): `progress` рівно 1, або `progress` 0 і `ready` рівно 1."""
        self.ensure_one()
        WO = self.env["mrp.workorder"].sudo()
        base = [("workcenter_id", "=", self.workcenter_id.id), ("td_partial_hold", "=", False)]
        progress = WO.search(base + [("state", "=", "progress")])
        if len(progress) == 1:
            return progress
        if not progress:
            ready = WO.search(base + [("state", "=", "ready")])
            if len(ready) == 1:
                return ready
        return WO

    def _td_pick_employee(self, wo):
        """R-09 п. 4 (б…д): працівник для старту; (а) обробляє `_td_autostart`."""
        self.ensure_one()
        wc = wo.workcenter_id
        allowed = self._td_wc_employees(wc)

        def ok(emp):
            return emp and (not allowed or emp in allowed)

        since = self._td_day_start(wc, fields.Datetime.now())
        emp = self._td_last_employee([("workcenter_id", "=", wc.id), ("date_start", ">=", since)])
        if ok(emp):
            return emp
        emp = self.env["hr.employee"].sudo().search_f3d("OP-%s" % self.code)
        if ok(emp):
            return emp
        if ok(self.employee_id):
            return self.employee_id
        if allowed:
            return allowed[:1]
        return self.env["hr.employee"]

    def _td_start_wo(self, wo, emp):
        """Старт таймера в технічному середовищі: `start_employee` (Enterprise), інакше `button_start` + працівник."""
        tech_wo = wo.with_env(self._td_tech_env())
        if emp and hasattr(tech_wo, "start_employee"):
            tech_wo.start_employee(emp.id)
            return
        tech_wo.button_start()
        if emp:
            wo.sudo().write({"td_employee_id": emp.id})

    def _td_unblock_wc(self, ts):
        """R-09 п. 5: верстат працює — закрити відкриті записи втрат РЦ (A-03)."""
        recs = (
            self.env["mrp.workcenter.productivity"]
            .sudo()
            .search(
                [
                    ("workcenter_id", "=", self.workcenter_id.id),
                    ("date_end", "=", False),
                    ("loss_id.loss_type", "in", BLOCKING),
                ]
            )
        )
        tech = self._td_tech_env()
        for rec in recs:
            rec.with_env(tech).write({"date_end": max(ts, rec.date_start)})
        if recs:
            self.env["mrp.workcenter"].invalidate_model(["working_state"])

    def _td_start_at(self, wo, emp, ts):
        """Старт/відновлення з `date_start` нового таймера = `ts` (R-09 п. 6)."""
        before = self._td_open_timers(wo)
        self._td_start_wo(wo, emp)
        wo.invalidate_recordset()
        tech = self._td_tech_env()
        for timer in self._td_open_timers(wo) - before:
            if ts < timer.date_start:
                timer.with_env(tech).write({"date_start": ts})

    # --- R-09: автостарт -------------------------------------------------------------------------------
    def _td_autostart(self, ts, text=None):
        self.ensure_one()
        if self.env.context.get("f3d_mc_internal") or not self._td_autostart_on() or self.state != "working":
            return False
        if text is None:
            text = self.env.context.get("f3d_mc_jobs", {}).get(ts, self.raw_job)
        text = (text or "").strip()
        empty = text in ("", "-")
        wo = self.env["mrp.workorder"]
        if not empty:
            wo = self._td_match_job(text)
            if not wo:
                if not self._td_job_wo(text) or not self._td_job_wo(text).td_partial_hold:
                    self._td_activity(self, _("Завдання верстата «%s» не знайдено в Odoo", text))
        elif self.auto_start_mode == "job_or_single":
            wo = self._td_candidate(ts)
        if wo and wo.td_partial_hold:
            wo = self.env["mrp.workorder"]
        started = False
        if wo:
            started = self._td_start_job(wo, ts, replace=not empty)
        if not self.active_workorder_id and not self.no_job_since:
            self.with_context(tracking_disable=True).write({"no_job_since": ts})
        return started

    def _td_start_job(self, wo, ts, replace=False):
        """R-09 п. 3, 5–7: старт завдання (або лише активне завдання), ключ ідемпотентності, помилки стандарту."""
        self.ensure_one()
        active = self.active_workorder_id
        if replace and active and active != wo and active.state == "progress":
            self._td_try_finish(ts, "job_changed")
        key = "wo:%s@%s" % (wo.id, ts.isoformat())
        if self.last_autostart_key == key and self.active_workorder_id == wo:
            return False
        if self._td_open_timers(wo):  # п. 3, п. 4 (а): таймер уже відкрито (будь-хто)
            self._td_set_active(wo)
            return False
        emp = self._td_pick_employee(wo)
        try:
            with self.env.cr.savepoint():
                self._td_unblock_wc(ts)
                self._td_start_at(wo, emp, ts)
        except UserError as e:
            text = _("Автостарт %(code)s не вдався: %(err)s", code=self.code, err=e.args[0] if e.args else e)
            self._td_activity(wo.production_id, text)
            self.message_post(body=text, subtype_xmlid="mail.mt_note")
            return False
        wo.sudo().write({"td_auto_started": True})
        self._td_set_active(wo, emp=emp)
        self.with_context(tracking_disable=True).write({"last_autostart_key": key})
        self._td_stat("autostarts")
        self._td_post_mo(
            wo,
            _(
                "Завдання %(wo)s стартував верстат %(code)s о %(t)s (працівник %(emp)s)",
                wo=wo.display_name,
                code=self.code,
                t=local(ts, "%H:%M"),
                emp=emp.name or "—",
            ),
        )
        return True

    def _td_set_active(self, wo, emp=None):
        self.ensure_one()
        self.with_context(tracking_disable=True).write(
            {"active_workorder_id": wo.id, "wo_paused": False, "no_job_since": False, "no_job_notified": False}
        )
        log = self.current_log_id.sudo()
        if log and not log.date_end:
            vals = {"workorder_id": wo.id}
            emp = emp or wo.sudo().td_employee_id
            if emp:
                vals["employee_id"] = emp.id
            log.write(vals)
        acts = (
            self.env["mail.activity"]
            .sudo()
            .search(
                [
                    ("res_model", "=", self._name),
                    ("res_id", "=", self.id),
                    ("summary", "like", NO_JOB_MARK),
                ]
            )
        )
        if acts:
            acts.action_feedback(feedback=_("Завдання %s", wo.display_name))

    # --- R-10: пауза й відновлення -----------------------------------------------------------------------
    def _td_close_timers(self, ts):
        """R-10 п. 1: закрити відкриті продуктивні таймери завдань РЦ о `ts` (стандартний `_close()` + підрізання)."""
        self.ensure_one()
        timers = (
            self.env["mrp.workcenter.productivity"]
            .sudo()
            .search(
                [
                    ("workcenter_id", "=", self.workcenter_id.id),
                    ("date_end", "=", False),
                    ("workorder_id", "!=", False),
                    ("loss_id.loss_type", "in", PRODUCTIVE),
                ]
            )
        )
        if not timers:
            return False
        tech = self._td_tech_env()
        for wo in timers.workorder_id:
            wo_timers = timers.filtered(lambda t, wo=wo: t.workorder_id == wo)
            before = set(wo.time_ids.ids)
            wo_timers.with_env(tech)._close()
            wo.invalidate_recordset(["time_ids"])
            touched = wo.time_ids.filtered(
                lambda t, ids=wo_timers.ids, before=before: t.id in ids or t.id not in before
            )
            for timer in touched.sudo():
                if timer.date_end and timer.date_end > ts:
                    timer.with_env(tech).write({"date_end": max(ts, timer.date_start)})
        if self.active_workorder_id in timers.workorder_id:
            self.with_context(tracking_disable=True).write({"wo_paused": True})
        self.env["mrp.workcenter"].invalidate_model(["working_state"])
        return True

    def _td_autopause(self, ts, reason):
        self.ensure_one()
        wo = self.active_workorder_id
        if not (self._td_autostart_on() and self.auto_pause and wo and wo.state == "progress"):
            return False
        self._td_close_timers(ts)
        if not self.wo_paused:
            self.with_context(tracking_disable=True).write({"wo_paused": True})
        _logger.info("td.machine %s: автопауза %s (%s) о %s", self.code, wo.display_name, reason, ts)
        return True

    def _td_resume(self, ts):
        """R-10 п. 3: `working` і `wo_paused` і завдання ще `progress` → новий таймер (працівник останнього запису)."""
        self.ensure_one()
        wo = self.active_workorder_id
        if not (self._td_autostart_on() and self.wo_paused and wo):
            return False
        if wo.state != "progress":
            self.with_context(tracking_disable=True).write({"wo_paused": False, "active_workorder_id": False})
            return self._td_autostart(ts)
        if wo.td_partial_hold or self._td_open_timers(wo):
            self.with_context(tracking_disable=True).write({"wo_paused": False})
            return False
        allowed = self._td_wc_employees(wo.workcenter_id)
        emp = self._td_last_employee([("workorder_id", "=", wo.id)])
        if allowed and emp not in allowed:
            emp = self.env["hr.employee"]
        try:
            with self.env.cr.savepoint():
                self._td_unblock_wc(ts)
                self._td_start_at(wo, emp, ts)
        except UserError as e:
            text = _("Відновлення %(code)s не вдалось: %(err)s", code=self.code, err=e.args[0] if e.args else e)
            self._td_activity(wo.production_id, text)
            self.message_post(body=text, subtype_xmlid="mail.mt_note")
            return False
        self.with_context(tracking_disable=True).write({"wo_paused": False})
        return True

    # --- R-12: завершення й неповна партія ----------------------------------------------------------------
    def _td_plan_qty(self, wo):
        return max(wo.qty_production - wo.qty_reported_from_previous_wo, 0.0)

    def _td_idle_since(self):
        """Від якого моменту верстат не `working` (з урахуванням відкладеного переходу, R-02)."""
        if self.state != "working":
            return self.state_since
        if self.pending_state and self.pending_since:
            return self.pending_since
        return False

    def _td_try_finish(self, ts, trigger):
        """R-12: `trigger` ∈ {`job_changed`, `event`, `idle`}."""
        self.ensure_one()
        wo = self.active_workorder_id
        if not (self._td_autostart_on() and self.auto_finish and wo and wo.state == "progress"):
            return False
        if wo.td_partial_hold:
            return False
        plan = self._td_plan_qty(wo)
        counted = wo.td_qty_counted
        if trigger == "idle":
            if self.sig_job_id:
                return False
            since = self._td_idle_since()
            if counted < plan or not since or ts < since + timedelta(seconds=self.finish_idle_s):
                return False
            if not self._td_lock_wo(wo):
                _logger.info("td.machine %s: завдання %s зайняте, завершення пізніше", self.code, wo.id)
                return False
            return self._td_finish(wo, ts, counted, plan)
        return self._td_finish(wo, ts, counted, plan) if counted >= plan else self._td_partial(wo, ts, counted, plan)

    def _td_finish(self, wo, ts, counted, plan):
        """R-12 п. 4."""
        tech_wo = wo.with_env(self._td_tech_env())
        try:
            with self.env.cr.savepoint():
                self._td_close_timers(ts)
                tech_wo.write({"qty_produced": plan})
                if hasattr(tech_wo, "stop_employee") and wo.employee_ids:
                    tech_wo.stop_employee(wo.employee_ids.ids)
                tech_wo.button_finish()
        except UserError as e:
            text = _("Завершення %(code)s не вдалось: %(err)s", code=self.code, err=e.args[0] if e.args else e)
            self._td_activity(wo.production_id, text)
            self.message_post(body=text, subtype_xmlid="mail.mt_note")
            return False
        self.with_context(tracking_disable=True).write({"active_workorder_id": False, "wo_paused": False})
        if counted > wo.qty_production:
            self._td_post_mo(wo, _("Верстат порахував %(c)s, план %(q)s", c=counted, q=wo.qty_production))
        self._td_post_mo(
            wo,
            _(
                "Завдання %(wo)s завершив верстат %(code)s: %(c)s шт",
                wo=wo.display_name,
                code=self.code,
                c=counted,
            ),
        )
        self._td_stat("finished")
        return True

    def _td_partial(self, wo, ts, counted, plan):
        """R-12 п. 5: неповна партія — позначка, таймери закрито, діяльність майстру."""
        wo.sudo().write({"td_partial_hold": True})
        self._td_close_timers(ts)
        self.with_context(tracking_disable=True).write({"active_workorder_id": False, "wo_paused": False})
        text = _(
            "Неповна партія на %(code)s: %(c)s з %(q)s. Завершіть як є або дозапустіть",
            code=self.code,
            c=counted,
            q=plan,
        )
        user = wo.production_id.user_id or self.env.ref("base.user_admin")
        self._td_activity(wo.production_id, text, user=user)
        return True

    # --- гачки (super() першим) -------------------------------------------------------------------------
    @api.model
    def _td_apply_event(self, payload):
        """R-12 п. 1: подія EV-01 `I0002` з `{job}` цього завдання → завершення/неповна партія."""
        machine = super()._td_apply_event(payload)
        if payload.get("message_id") == "I0002":
            args = payload.get("args") or {}
            job = args.get("job") or args.get("JobOrderID")
            machine = machine.sudo()
            wo = machine.active_workorder_id
            if job and wo and machine._td_job_wo(job) == wo:
                ts = fields.Datetime.now()
                machine._td_try_finish(ts, "event")
        return machine

    def _td_apply(self, items):
        """Зберігає тексти завдань показань за `ts`: автостарт у момент переходу бачить `job` того самого `ts`."""
        jobs = {
            it["ts"]: it["text"] for it in items if it["role"] == "job" and it["q"] != "bad" and it["text"] is not None
        }
        return super(F3dMachineWo, self.with_context(f3d_mc_jobs=jobs))._td_apply(items)

    def _td_after_commit(self, old, new, ts):
        super()._td_after_commit(old, new, ts)
        for rec in self:
            if not rec._td_autostart_on():
                continue
            if new == "fault":
                rec._td_autopause(ts, "fault")
            elif new == "working":
                rec._td_on_working(ts)
            else:
                if rec.no_job_since or rec.no_job_notified:
                    rec.with_context(tracking_disable=True).write({"no_job_since": False, "no_job_notified": False})
                if new != "nodata":
                    rec._td_try_finish(ts, "idle")

    def _td_on_working(self, ts):
        self.ensure_one()
        wo = self.active_workorder_id
        if self.wo_paused and wo:
            text = (self.env.context.get("f3d_mc_jobs", {}).get(ts, self.raw_job) or "").strip()
            target = self._td_match_job(text) if text not in ("", "-") else wo
            if not target or target == wo:
                self._td_resume(ts)
                return
        self._td_autostart(ts)

    def _td_on_count(self, delta, ts):
        """R-11 п. 4–5: приріст `td_qty_counted` активного завдання; режим `live` — синхронізація `qty_produced`."""
        super()._td_on_count(delta, ts)
        for rec in self:
            wo = rec.active_workorder_id.sudo()
            if not delta or rec.state not in ("working", "setup") or not wo or wo.state != "progress":
                continue
            counted = wo.td_qty_counted + delta
            wo.write({"td_qty_counted": counted})
            now = fields.Datetime.now()
            if param(rec.env, "qty_sync_mode", "finish") == "live":
                sync_s = int(param(rec.env, "qty_sync_s", "300"))
                if not wo.td_qty_synced_at or now - wo.td_qty_synced_at >= timedelta(seconds=sync_s):
                    wo.with_env(rec._td_tech_env()).write({"qty_produced": min(counted, wo.qty_production)})
                    wo.write({"td_qty_synced_at": now})

    def _td_on_job(self, text, ts):
        """R-09 п. 8, R-12 п. 1: зміна завдання на верстаті."""
        olds = {rec.id: rec.raw_job for rec in self}
        super()._td_on_job(text, ts)
        for rec in self:
            if not rec._td_autostart_on():
                continue
            wo = rec.active_workorder_id
            if wo and wo.state == "progress" and rec._td_job_wo(olds.get(rec.id)) == wo:
                rec._td_try_finish(ts, "job_changed")
            if rec.state == "working":
                rec._td_autostart(ts, text=text)

    def _td_tick_extra(self, now):
        """R-10 п. 2, R-12 п. 3, R-09 п. 9."""
        super()._td_tick_extra(now)
        for rec in self:
            if not rec._td_autostart_on():
                continue
            wo = rec.active_workorder_id
            if wo and wo.state == "progress" and not rec.wo_paused:
                if rec.state in ("idle", "off") and rec.state_since:
                    if now - rec.state_since >= timedelta(minutes=rec.pause_after_min):
                        rec._td_autopause(rec.state_since, "idle")
            rec._td_try_finish(now, "idle")
            rec._td_tick_no_job(now)

    def _td_tick_no_job(self, now):
        """R-09 п. 9: верстат працює без завдання довше `no_job_activity_min` → діяльність (раз)."""
        self.ensure_one()
        if self.state != "working" or self.active_workorder_id or not self.no_job_since or self.no_job_notified:
            return
        minutes = int(param(self.env, "no_job_activity_min", "15"))
        if now - self.no_job_since < timedelta(minutes=minutes):
            return
        text = _(
            "%(code)s %(mark)s з %(t)s — оберіть завдання в «Цеху»",
            code=self.code,
            mark=NO_JOB_MARK,
            t=local(self.no_job_since, "%H:%M"),
        )
        self._td_activity(self, text)
        self.with_context(tracking_disable=True).write({"no_job_notified": True})
