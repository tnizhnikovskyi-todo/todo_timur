"""Навчальна пожежна тривога (SPEC M-11…M-11f, R-15…R-18, §10.4)."""
import logging
import time
from datetime import timedelta

from odoo import Command, api, fields, models
from odoo.modules import module as odoo_module
from odoo.exceptions import UserError, ValidationError

from ..tools import dates
from .td_fire_panel import fire_notify

_logger = logging.getLogger(__name__)

AUTO_KEYS = [
    ("none", "Вручну"), ("detector", "Тривога/тест зони на приладі"), ("sounders", "Оповіщувачі увімкнено"),
    ("brigade", "Передача на пульт"), ("ventilation", "Вентиляцію зупинено"),
    ("smoke", "Клапани димовидалення відкрито"), ("doors", "Двері розблоковано"),
    ("evacuation", "Перший вихід людей"), ("machines", "Верстати зони зупинено")]
RESULTS = [("ok", "Пройдено"), ("remarks", "Пройдено із зауваженнями"), ("failed", "Не пройдено")]
SOURCE_MAP = {"hr_attendance": "attendance", "access": "access"}
LEAD = timedelta(seconds=60)


class _SafeDict(dict):
    def __missing__(self, key):
        return "{%s}" % key


def _seconds(delta):
    return max(0, int(delta.total_seconds()))


class F3dFireDrill(models.Model):
    _name = "td.fire.drill"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Пожежна безпека: навчальна тривога"
    _order = "planned_ts desc, id desc"
    _rec_name = "name"

    name = fields.Char(size=32, required=True, readonly=True, copy=False, default="/", index=True)
    title = fields.Char(string="Назва", size=128, required=True, default="Навчальна пожежна тривога")
    company_id = fields.Many2one("res.company", required=True, default=lambda self: self.env.company, index=True)
    state = fields.Selection(
        [("draft", "Чернетка"), ("planned", "Заплановано"), ("running", "Триває"),
         ("evaluating", "Оцінювання"), ("done", "Завершено"), ("cancelled", "Скасовано")],
        string="Стан", default="draft", required=True, index=True, tracking=True)
    origin = fields.Selection(
        [("manual", "Вручну"), ("panel", "З приладу (тест)"), ("demo", "Демо")],
        string="Походження", default="manual", required=True, readonly=True)
    mode = fields.Selection(
        [("sim", "Емулятор"), ("panel_test", "Тест приладу"), ("tabletop", "Настільне")],
        string="Режим", required=True, default="panel_test", tracking=True)
    planned_ts = fields.Datetime(string="Заплановано на", tracking=True)
    zone_id = fields.Many2one("td.fire.zone", string="Зона пожежі", required=True, ondelete="restrict",
                              tracking=True)
    device_id = fields.Many2one(
        "td.fire.device", string="Сповіщувач", ondelete="set null",
        domain="[('zone_id', '=', zone_id), ('is_detector', '=', True)]")
    template_id = fields.Many2one("td.fire.drill.template", string="Шаблон", ondelete="set null",
                                  default=lambda self: self._default_template())
    responsible_id = fields.Many2one("res.users", string="Відповідальний", default=lambda self: self.env.user)
    start_ts = fields.Datetime(string="Початок", readonly=True)
    end_ts = fields.Datetime(string="Завершення", readonly=True)
    duration_s = fields.Integer(string="Тривалість, с", compute="_compute_duration", store=True)
    elapsed_s = fields.Integer(string="Минуло, с", compute="_compute_elapsed")
    sim_run_ref = fields.Char(string="Запуск емулятора", size=32, readonly=True)
    sim_available = fields.Boolean(compute="_compute_sim_available")
    real_alarm = fields.Boolean(string="Справжня тривога під час навчання", readonly=True)
    step_ids = fields.One2many("td.fire.drill.step", "drill_id", string="Кроки", copy=True)
    person_ids = fields.One2many(
        "td.fire.drill.person", "drill_id", string="Люди", copy=False,
        groups="td_fire_safety.group_td_fire_drill,hr.group_hr_user")
    event_ids = fields.One2many("td.fire.event", "drill_id", string="Події", readonly=True)
    steps_done = fields.Integer(compute="_compute_steps", store=True)
    steps_total = fields.Integer(compute="_compute_steps", store=True)
    on_site_count = fields.Integer(string="На об'єкті", compute="_compute_people", store=True, compute_sudo=True)
    evacuated_count = fields.Integer(string="Вийшли", compute="_compute_people", store=True, compute_sudo=True)
    present_count = fields.Integer(string="Є на перекличці", compute="_compute_people", store=True,
                                   compute_sudo=True)
    missing_count = fields.Integer(string="Не знайдено", compute="_compute_people", store=True, compute_sudo=True)
    evac_time_s = fields.Integer(string="Час евакуації, с", readonly=True)
    evac_pct = fields.Float(string="Евакуовано, %", compute="_compute_people", store=True, compute_sudo=True,
                            digits=(5, 1))
    time_limit_s = fields.Integer(string="Норматив часу, с", default=lambda self: self._default_time_limit())
    data_quality = fields.Selection(
        [("full", "Повні"), ("partial", "Неповні")], string="Якість даних", compute="_compute_people",
        store=True, compute_sudo=True)
    passage_source = fields.Char(string="Джерело проходів", size=32, readonly=True)
    result_suggested = fields.Selection(RESULTS, string="Запропонований результат",
                                        compute="_compute_result_suggested", store=True)
    result = fields.Selection(RESULTS, string="Результат", tracking=True)
    conclusions = fields.Text(string="Висновки")
    remarks = fields.Text(string="Зауваження й заходи")
    print_names = fields.Boolean(string="Друкувати прізвища у протоколі", default=False)
    last_tick_ts = fields.Datetime(string="Останній такт")
    color = fields.Integer(compute="_compute_color")

    # --- значення за замовчуванням -----------------------------------------------------------------------
    @api.model
    def _default_template(self):
        return self.env["td.fire.drill.template"].sudo().search([("is_default", "=", True)], limit=1).id

    @api.model
    def _default_time_limit(self):
        return self.env["td.fire.panel"]._get_param("drill_time_limit_s", 300)

    @api.model
    def _param(self, key, default):
        return self.env["td.fire.panel"]._get_param(key, default)

    # --- обчислювані поля --------------------------------------------------------------------------------
    @api.depends("start_ts", "end_ts")
    def _compute_duration(self):
        for rec in self:
            rec.duration_s = _seconds(rec.end_ts - rec.start_ts) if rec.start_ts and rec.end_ts else 0

    @api.depends("state", "start_ts", "end_ts")
    def _compute_elapsed(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.state == "running" and rec.start_ts:
                rec.elapsed_s = _seconds(now - rec.start_ts)
            else:
                rec.elapsed_s = _seconds(rec.end_ts - rec.start_ts) if rec.start_ts and rec.end_ts else 0

    def _compute_sim_available(self):
        available = "td.sim.run" in self.env
        for rec in self:
            rec.sim_available = available

    @api.depends("step_ids.done")
    def _compute_steps(self):
        for rec in self:
            rec.steps_total = len(rec.step_ids)
            rec.steps_done = len(rec.step_ids.filtered("done"))

    @api.depends("person_ids.status")
    def _compute_people(self):
        for rec in self:
            persons = rec.person_ids
            on_site = len(persons)
            evacuated = len(persons.filtered(lambda p: p.status == "evacuated"))
            present = len(persons.filtered(lambda p: p.status == "present"))
            missing = len(persons.filtered(lambda p: p.status == "missing"))
            rec.on_site_count, rec.evacuated_count = on_site, evacuated
            rec.present_count, rec.missing_count = present, missing
            rec.evac_pct = round((evacuated + present) / on_site * 100.0, 1) if on_site else 100.0
            rec.data_quality = "partial" if (present + missing > 0 or on_site == 0) else "full"

    @api.depends("state", "missing_count", "evac_time_s", "time_limit_s", "data_quality", "real_alarm",
                 "steps_done", "steps_total")
    def _compute_result_suggested(self):
        for rec in self:
            if rec.state not in ("evaluating", "done"):
                rec.result_suggested = False
            elif rec.missing_count > 0:
                rec.result_suggested = "failed"
            elif (rec.evac_time_s > rec.time_limit_s or rec.data_quality == "partial" or rec.real_alarm
                  or rec.steps_done < rec.steps_total):
                rec.result_suggested = "remarks"
            else:
                rec.result_suggested = "ok"

    @api.depends("state", "result")
    def _compute_color(self):
        for rec in self:
            if rec.state == "running":
                rec.color = 1
            elif rec.state == "evaluating":
                rec.color = 3
            elif rec.state == "done":
                rec.color = {"ok": 10, "remarks": 2, "failed": 1}.get(rec.result, 0)
            else:
                rec.color = 0

    # --- обмеження ---------------------------------------------------------------------------------------
    @api.constrains("state", "planned_ts")
    def _check_planned_ts(self):
        for rec in self:
            if rec.state == "planned" and not rec.planned_ts:
                raise ValidationError("Вкажіть дату й час навчання.")

    @api.constrains("device_id", "zone_id")
    def _check_device_zone(self):
        for rec in self:
            if rec.device_id and rec.device_id.zone_id != rec.zone_id:
                raise ValidationError("Сповіщувач %s не належить зоні %s." % (
                    rec.device_id.address, rec.zone_id.code))

    @api.constrains("state")
    def _check_single_running(self):
        for rec in self.filtered(lambda r: r.state == "running"):
            if self.sudo().search_count([("state", "=", "running"), ("company_id", "=", rec.company_id.id)]) > 1:
                raise ValidationError("Одночасно може тривати лише одне навчання.")

    # --- створення / видалення ---------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        seq = self.env["ir.sequence"].sudo()
        no_steps = []
        for i, vals in enumerate(vals_list):
            if vals.get("name", "/") == "/":
                vals["name"] = seq.next_by_code("td.fire.drill") or "/"
            if not vals.get("step_ids"):
                no_steps.append(i)
        records = super().create(vals_list)
        for i in no_steps:
            rec = records[i]
            if rec.template_id:
                rec._fill_steps()
        return records

    def unlink(self):
        if any(rec.state not in ("draft", "cancelled") for rec in self):
            raise UserError("Видалити можна лише чернетку або скасоване навчання.")
        return super().unlink()

    def _fill_steps(self):
        """Кроки з шаблона (A-29): плейсхолдери {detector}, {zone}, {sounders}; невідомі лишаються як є."""
        for rec in self:
            sounders = self.env["td.fire.device"].sudo().search_count(
                [("type", "=", "sounder"), ("active", "=", True)])
            ctx = _SafeDict(detector=rec.device_id.address or "—", zone=rec.zone_id.name, sounders=sounders)
            commands = [Command.clear()]
            for step in rec.template_id.sudo().step_ids:
                try:
                    text = step.text.format_map(ctx)
                except (ValueError, IndexError, KeyError, AttributeError):
                    text = step.text
                commands.append(Command.create({
                    "sequence": step.sequence, "t_plan_s": step.t_plan_s, "who": step.who, "text": text,
                    "auto_key": step.auto_key}))
            rec.write({"step_ids": commands})

    # --- переходи ----------------------------------------------------------------------------------------
    def _notify_state(self):
        for rec in self:
            fire_notify(self.env, "td.fire.drill", [rec.name], "state")

    def _log_event(self, etype, text, ts, key=None, **extra):
        self.ensure_one()
        return self.env["td.fire.event"]._log(
            etype, self.zone_id.code, ts, text, source="drill", key=key or "%s:%s" % (etype, self.name),
            zone_id=self.zone_id.id, device_id=self.device_id.id or False, drill_id=self.id, **extra)

    def action_plan(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError("Запланувати можна лише чернетку.")
            if not rec.planned_ts:
                raise ValidationError("Вкажіть дату й час навчання.")
            rec.state = "planned"
            rec.message_post(body="Навчання заплановано.")
        return True

    def action_start(self, ts=None, source="manual"):
        base = self.env["td.fire.passage.source"]
        for rec in self:
            if rec.state not in ("draft", "planned"):
                raise UserError("Почати можна лише чернетку або заплановане навчання.")
            if not rec.zone_id:
                raise UserError("Вкажіть зону пожежі.")
            other = self.sudo().search([("state", "=", "running"), ("company_id", "=", rec.company_id.id),
                                        ("id", "!=", rec.id)], limit=1)
            if other:
                raise UserError("Уже триває навчання %s." % other.name)
            start = fields.Datetime.to_datetime(ts) or fields.Datetime.now()
            src = base._f3d_get_source()
            key = base._f3d_source_key(src)
            try:
                people = base._f3d_people_at(src, start)
            except Exception as exc:
                _logger.exception("Джерело проходів %s недоступне", key)
                raise UserError("Джерело проходів %s недоступне: %s" % (key, exc))
            people = sorted(people, key=lambda p: (p["since"], p["employee_id"]))
            employees = set(self.env["hr.employee"].sudo().browse([p["employee_id"] for p in people]).exists().ids)
            person_source = SOURCE_MAP.get(key, "manual")
            lines, seen = [], set()
            for person in people:
                emp = person["employee_id"]
                if emp in seen or emp not in employees:
                    continue
                seen.add(emp)
                lines.append(Command.create({
                    "seq": len(lines) + 1, "employee_id": emp, "since": person["since"], "source": person_source}))
            rec.sudo().write({"state": "running", "start_ts": start, "end_ts": False, "evac_time_s": 0,
                              "passage_source": key, "person_ids": [Command.clear()] + lines})
            if not rec.step_ids:
                rec._fill_steps()
            rec.step_ids.sudo().write({"done": False, "done_ts": False, "t_fact_s": 0, "done_by": False})
            rec._log_event("drill_start", "Навчання %s розпочато (%s), зона %s, на об'єкті %d" % (
                rec.name, source, rec.zone_id.code, len(lines)), start)
            rec.message_post(body="Почато о %s, на об'єкті %d" % (dates.local(start, "%H:%M:%S"), len(lines)))
            rec._notify_state()
        return True

    def action_start_sim(self):
        for rec in self:
            if rec.mode != "sim" or not rec.sim_available:
                raise UserError("Модуль емулятора не встановлено.")
            run = rec._f3d_sim_start()
            rec.sim_run_ref = run.name
            if run.state == "failed":
                raise UserError("Емулятор не запустив сценарій: %s" % run.message)
            rec.action_start(source="sim")
        return True

    def action_stop(self, ts=None):
        for rec in self:
            if rec.state != "running":
                raise UserError("Завершити можна лише навчання, що триває.")
            end = fields.Datetime.to_datetime(ts) or fields.Datetime.now()
            rec.sudo().end_ts = end
            rec._process_passages()
            rec._auto_steps()
            exits = rec.sudo().person_ids.filtered("exit_ts").mapped("exit_s")
            rec.sudo().write({"evac_time_s": max(exits) if exits else 0, "state": "evaluating"})
            rec._log_event("drill_end", "Навчання %s завершено, вийшли %d з %d" % (
                rec.name, rec.evacuated_count, rec.on_site_count), end)
            rec._sim_stop_if_any()
            rec.message_post(body="Завершено о %s, вийшли %d з %d, час евакуації %d с" % (
                dates.local(end, "%H:%M:%S"), rec.evacuated_count, rec.on_site_count, rec.evac_time_s))
            rec._notify_state()
        return True

    def _sim_stop_if_any(self):
        self.ensure_one()
        if self.sim_run_ref and self.sim_available:
            self._f3d_sim_stop()

    def action_rollcall(self):
        self.ensure_one()
        if self.state != "evaluating":
            raise UserError("Перекличка — після завершення навчання.")
        action = self.env["ir.actions.act_window"]._for_xml_id(
            "td_fire_safety.action_td_fire_drill_rollcall")
        action["context"] = {"default_drill_id": self.id}
        return action

    def action_close(self):
        for rec in self:
            if rec.state != "evaluating":
                raise UserError("Закрити можна лише навчання на стадії оцінювання.")
            if not rec.result:
                raise UserError("Оберіть результат навчання.")
            if not rec.conclusions:
                raise UserError("Заповніть висновки.")
            rec.state = "done"
            rec.message_post(body="Навчання закрито, результат: %s" % dict(RESULTS)[rec.result])
        return True

    def action_cancel(self):
        for rec in self:
            if rec.state not in ("draft", "planned", "running"):
                raise UserError("Скасувати можна лише чернетку, заплановане або навчання, що триває.")
            vals = {"state": "cancelled"}
            if rec.state == "running":
                vals["end_ts"] = fields.Datetime.now()
                rec._sim_stop_if_any()
            rec.sudo().write(vals)
            rec.message_post(body="Навчання скасовано.")
            rec._notify_state()
        return True

    def action_reset_draft(self):
        for rec in self:
            if rec.state != "cancelled":
                raise UserError("У чернетку можна повернути лише скасоване навчання.")
            rec.sudo().person_ids.unlink()
            rec.step_ids.sudo().write({"done": False, "done_ts": False, "t_fact_s": 0, "done_by": False})
            rec.sudo().write({"state": "draft", "start_ts": False, "end_ts": False, "evac_time_s": 0,
                              "real_alarm": False, "passage_source": False})
        return True

    def action_print(self):
        return self.env.ref("td_fire_safety.report_td_fire_drill").report_action(self)

    def action_f3d_show(self):
        self.ensure_one()
        return self.zone_id.action_f3d_show()

    # --- хід навчання ------------------------------------------------------------------------------------
    def _passage_model(self):
        self.ensure_one()
        base = self.env["td.fire.passage.source"]
        name = base.PREFIX + (self.passage_source or "")
        if self.passage_source and name in self.env.registry:
            return self.env[name].sudo()
        return base._f3d_get_source()

    def _process_passages(self):
        """R-16 п. 2: виходи людей за проходами джерела."""
        self.ensure_one()
        if not self.start_ts:
            return False
        now = fields.Datetime.now()
        end = min(now, self.end_ts) if self.end_ts else now
        passages = self._passage_model()._f3d_passages(self.start_ts, end)
        persons = {p.employee_id.id: p for p in self.sudo().person_ids if p.employee_id}
        changed = False
        for passage in sorted((p for p in passages if p.get("direction") == "out"), key=lambda p: p["ts"]):
            person = persons.get(passage["employee_id"])
            if person and not person.exit_ts:
                person.write({"exit_ts": passage["ts"], "exit_point": (passage.get("point") or "")[:64]})
                changed = True
        return changed

    def _events_since_start(self, etypes, zone=None):
        self.ensure_one()
        domain = [("etype", "in", list(etypes)), ("ts", ">=", self.start_ts - LEAD)]
        if self.end_ts:
            domain.append(("ts", "<=", self.end_ts))
        if zone:
            domain.append(("zone_id", "=", zone.id))
        return self.env["td.fire.event"].sudo().search(domain, order="ts, id")

    def _auto_done_ts(self, key, now):
        """R-17: час виконання кроку з auto_key або False."""
        self.ensure_one()
        env = self.env
        if key == "detector":
            return self._events_since_start(("test", "alarm", "prealarm"), self.zone_id)[:1].ts
        if key in ("sounders", "brigade", "smoke"):
            etype = {"sounders": "sounders_on", "brigade": "brigade_on", "smoke": "smoke_open"}[key]
            return self._events_since_start((etype,))[:1].ts
        if key == "evacuation":
            exits = self.sudo().person_ids.filtered("exit_ts").mapped("exit_ts")
            return min(exits) if exits else False
        if key == "ventilation":
            signals = env["td.signal"].sudo().search(
                [("code", "=like", "ventilation/units/%/mode"), ("source_id", "!=", False)])
            if signals and all(s.last_text in ("ST", "Off") and s.last_ts and s.last_ts >= self.start_ts
                               for s in signals):
                return max(signals.mapped("last_ts"))
            return False
        if key == "doors":
            if "td.access.door" not in env:
                return False
            Door = env["td.access.door"].sudo()
            doors = Door.search([("is_perimeter", "=", True)] if "is_perimeter" in Door._fields else [])
            if doors and all(d.state in ("unlocked", "open") for d in doors):
                return now
            return False
        if key == "machines":
            workcenters = self.zone_id.sudo().zone_id.workcenter_ids
            if not workcenters:
                return False
            codes = ["workcenters/%s/machine_state" % wc.td_code for wc in workcenters if wc.td_code]
            if not codes:
                return False
            signals = env["td.signal"].sudo().search([("code", "in", codes)])
            if len(signals) < len(codes) or any(s.last_text not in ("fault", "off", "idle") for s in signals):
                return False
            return max([self.start_ts] + [s.last_ts for s in signals if s.last_ts])
        return False

    def _auto_steps(self):
        """R-17: автовідмітка кроків."""
        self.ensure_one()
        if not self.start_ts:
            return False
        now = fields.Datetime.now()
        changed = False
        for step in self.step_ids.sudo().filtered(lambda s: not s.done and s.auto_key != "none"):
            done_ts = self._auto_done_ts(step.auto_key, now)
            if done_ts:
                step.write({"done": True, "done_ts": done_ts, "t_fact_s": _seconds(done_ts - self.start_ts),
                            "done_by": "auto"})
                changed = True
        return changed

    def _auto_stop_ts(self, now):
        """R-16 п. 7: момент, за яким навчання можна завершити автоматично, або False."""
        self.ensure_one()
        zone = self.zone_id
        if not self._events_since_start(("test", "alarm", "prealarm"), zone):
            return False
        panel = zone.panel_id
        if panel.state not in ("normal", "unknown") or any(
                z.state not in ("normal", "unknown") for z in panel.zone_ids):
            return False
        ends = self.env["td.fire.event"].sudo().search(
            [("etype", "in", ("test_end", "reset")), ("zone_id", "=", zone.id),
             ("ts", ">=", self.start_ts - LEAD)], order="ts desc, id desc", limit=1)
        if not ends or (now - ends.ts).total_seconds() < self._param("drill_auto_stop_s", 120):
            return False
        return ends.ts

    def _tick(self):
        for rec in self:
            if rec.state != "running":
                continue
            changed = False
            try:
                with self.env.cr.savepoint():
                    changed |= rec._process_passages()
            except Exception:
                _logger.exception("Навчання %s: джерело проходів недоступне, ітерацію пропущено", rec.name)
            changed |= rec._auto_steps()
            now = fields.Datetime.now()
            if rec.mode != "tabletop":
                stop_ts = rec._auto_stop_ts(now)
                if stop_ts:
                    rec.action_stop(ts=stop_ts)
                    changed = True
            rec.sudo().last_tick_ts = now
            if changed:
                rec._notify_state()
        return True

    @api.model
    def _cron_tick(self):
        drills = self.sudo().search([("state", "=", "running")])
        if not drills:
            return
        test_mode = bool(odoo_module.current_test)
        for _ in range(1 if test_mode else 5):
            drills._tick()
            if test_mode:
                break
            self.env.cr.commit()
            time.sleep(10)
            drills = drills.exists().filtered(lambda d: d.state == "running")
            if not drills:
                break

    @api.model
    def _f3d_is_active_at(self, ts):
        """CF-06 (для td_access): чи йшло навчання в момент ts (UTC naive)."""
        return self.sudo().search_count([
            ("start_ts", "!=", False), ("start_ts", "<=", ts), "|", ("end_ts", "=", False), ("end_ts", ">=", ts),
            ("state", "in", ("running", "evaluating", "done", "cancelled"))]) > 0

    @api.model
    def _match_test_alarm(self, zone, device, ts, real=False):
        """R-18: зіставлення тесту/тривоги приладу з навчанням."""
        Drill = self.sudo()
        ts = fields.Datetime.to_datetime(ts)
        company = zone.panel_id.company_id or self.env.company
        running = Drill.search([("state", "=", "running"), ("company_id", "=", company.id)], limit=1)
        if real:
            if running:
                running.real_alarm = True
                running._log_event(
                    "drill_real_alarm", "Під час навчання %s прилад показав справжню тривогу (зона %s)" % (
                        running.name, zone.code), ts, key="drill_real_alarm:%s" % running.name)
                running.message_post(body="Під час навчання прилад показав справжню тривогу: зона %s." % zone.code)
            return running
        if running:
            if not running.device_id and device and device.zone_id == running.zone_id:
                running.device_id = device
            return running
        window = timedelta(minutes=self._param("drill_match_window_min", 30))
        planned = Drill.search([("state", "=", "planned"), ("company_id", "=", company.id),
                                ("planned_ts", ">=", ts - window), ("planned_ts", "<=", ts + window)])
        if planned:
            drill = planned.sorted(lambda d: (d.zone_id != zone, abs((d.planned_ts - ts).total_seconds())))[0]
            if drill.zone_id != zone:
                drill.message_post(body="Тест прийшов із зони %s, заплановано %s" % (zone.code, drill.zone_id.code))
                drill.zone_id = zone
            drill.device_id = device if device and device.zone_id == zone else False
            drill.action_start(ts, source="panel")
            return drill
        if not self._param("drill_auto_create", True):
            return Drill.browse()
        drill = Drill.create({
            "title": "Тест приладу: %s" % zone.name, "origin": "panel", "mode": "panel_test", "zone_id": zone.id,
            "device_id": device.id if device and device.zone_id == zone else False, "planned_ts": ts,
            "company_id": company.id})
        drill.action_start(ts, source="panel")
        drill._log_event("drill_auto", "Навчання %s створено автоматично за тестом приладу" % drill.name, ts,
                         key="drill_auto:%s" % drill.name)
        return drill


class F3dFireDrillStep(models.Model):
    _name = "td.fire.drill.step"
    _description = "Навчальна тривога: крок"
    _order = "drill_id, sequence, id"

    drill_id = fields.Many2one("td.fire.drill", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    t_plan_s = fields.Integer(string="План, с", required=True, default=0)
    who = fields.Char(string="Хто", size=64, required=True)
    text = fields.Char(string="Дія", size=256, required=True)
    auto_key = fields.Selection(AUTO_KEYS, string="Автовідмітка", required=True, default="none")
    done = fields.Boolean(string="Виконано", default=False)
    done_ts = fields.Datetime(string="Час виконання")
    t_fact_s = fields.Integer(string="Факт, с")
    delay_s = fields.Integer(string="Затримка, с", compute="_compute_delay", store=True)
    done_by = fields.Selection([("auto", "Автоматично"), ("manual", "Вручну")], string="Хто відмітив")
    note = fields.Char(size=256)

    @api.depends("done", "t_fact_s", "t_plan_s")
    def _compute_delay(self):
        for rec in self:
            rec.delay_s = rec.t_fact_s - rec.t_plan_s if rec.done else 0

    @api.constrains("t_plan_s")
    def _check_t_plan(self):
        if any(rec.t_plan_s < 0 for rec in self):
            raise ValidationError("Планований час кроку не може бути від'ємним.")

    def action_done_now(self):
        now = fields.Datetime.now()
        for rec in self:
            if rec.drill_id.state not in ("running", "evaluating"):
                raise UserError("Відмітити крок можна лише під час навчання або оцінювання.")
            start = rec.drill_id.start_ts
            rec.write({"done": True, "done_ts": now, "t_fact_s": _seconds(now - start) if start else 0,
                       "done_by": "manual"})
        return True

    def action_undo(self):
        for rec in self:
            if rec.done_by != "manual" or rec.drill_id.state not in ("running", "evaluating"):
                raise UserError("Скасувати можна лише ручну відмітку під час навчання або оцінювання.")
            rec.write({"done": False, "done_ts": False, "t_fact_s": 0, "done_by": False})
        return True


class F3dFireDrillPerson(models.Model):
    _name = "td.fire.drill.person"
    _description = "Навчальна тривога: людина на об'єкті"
    _order = "drill_id, seq"

    drill_id = fields.Many2one("td.fire.drill", required=True, ondelete="cascade", index=True)
    seq = fields.Integer(string="№")
    employee_id = fields.Many2one("hr.employee", ondelete="set null", index=True)
    since = fields.Datetime(string="На об'єкті з")
    source = fields.Selection(
        [("attendance", "Відмітки"), ("access", "СКУД"), ("manual", "Вручну"), ("demo", "Демо")], required=True)
    exit_ts = fields.Datetime(string="Вийшов о")
    exit_point = fields.Char(string="Де вийшов", size=64)
    exit_s = fields.Integer(string="Вийшов через, с", compute="_compute_exit_s", store=True)
    rollcall = fields.Selection(
        [("na", "—"), ("present", "Присутній на місці збору"), ("absent", "Відсутній")], default="na")
    status = fields.Selection(
        [("on_site", "На об'єкті"), ("evacuated", "Вийшов"), ("present", "Є на перекличці"),
         ("missing", "Не знайдено")], compute="_compute_status", store=True)

    _f3d_fire_person_uniq = models.Constraint(
        "UNIQUE(drill_id, employee_id)", "Працівник уже є в списку навчання.")

    @api.depends("exit_ts", "drill_id.start_ts")
    def _compute_exit_s(self):
        for rec in self:
            rec.exit_s = _seconds(rec.exit_ts - rec.drill_id.start_ts) if rec.exit_ts and rec.drill_id.start_ts \
                else 0

    @api.depends("exit_ts", "rollcall", "drill_id.state")
    def _compute_status(self):
        for rec in self:
            if rec.exit_ts:
                rec.status = "evacuated"
            elif rec.rollcall == "present":
                rec.status = "present"
            elif rec.drill_id.state in ("draft", "planned", "running"):
                rec.status = "on_site"
            else:
                rec.status = "missing"


class F3dFireDrillTemplate(models.Model):
    _name = "td.fire.drill.template"
    _description = "Навчальна тривога: шаблон"
    _order = "sequence, id"

    name = fields.Char(string="Назва", required=True)
    sequence = fields.Integer(default=10)
    is_default = fields.Boolean(string="За замовчуванням")
    duration_s = fields.Integer(string="Тривалість, с", default=300)
    default_zone_id = fields.Many2one("td.fire.zone", string="Зона за замовчуванням")
    default_device_id = fields.Many2one("td.fire.device", string="Сповіщувач за замовчуванням")
    step_ids = fields.One2many("td.fire.drill.template.step", "template_id", string="Кроки", copy=True)
    note = fields.Text(string="Примітка")
    active = fields.Boolean(default=True)

    @api.constrains("is_default", "active")
    def _check_default(self):
        if self.sudo().search_count([("is_default", "=", True), ("active", "=", True)]) > 1:
            raise ValidationError("Шаблон за замовчуванням може бути лише один.")


class F3dFireDrillTemplateStep(models.Model):
    _name = "td.fire.drill.template.step"
    _description = "Навчальна тривога: крок шаблона"
    _order = "template_id, sequence, id"

    template_id = fields.Many2one("td.fire.drill.template", required=True, ondelete="cascade", index=True)
    sequence = fields.Integer(default=10)
    t_plan_s = fields.Integer(string="План, с", default=0)
    who = fields.Char(string="Хто", size=64, required=True)
    text = fields.Char(string="Дія", size=256, required=True)
    auto_key = fields.Selection(AUTO_KEYS, string="Автовідмітка", required=True, default="none")

    @api.constrains("t_plan_s")
    def _check_t_plan(self):
        if any(rec.t_plan_s < 0 for rec in self):
            raise ValidationError("Планований час кроку не може бути від'ємним.")
