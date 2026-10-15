import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from odoo import _, api, fields, models
from odoo.exceptions import AccessError

from ..tools import oee, ppt
from .f3d_machine import param

_logger = logging.getLogger(__name__)

D12 = (12, 1)
KYIV = ZoneInfo("Europe/Kyiv")
AGG_FIELDS = ("ppt_min", "run_min", "run_wo_min", "ideal_min", "qty_total", "qty_bad")


def _local_date(dt):
    """Дата за Києвом для naive UTC `dt`."""
    return dt.replace(tzinfo=timezone.utc).astimezone(KYIV).date()


def _day_bounds(day: date):
    """Межі київської доби `day` у naive UTC."""

    def utc(d):
        return datetime(d.year, d.month, d.day, tzinfo=KYIV).astimezone(timezone.utc).replace(tzinfo=None)

    return utc(day), utc(day + timedelta(days=1))


class F3dOeeShift(models.Model):
    _name = "f3d.oee.shift"
    _description = "Верстати: OEE за зміну"
    _order = "date desc, code"

    machine_id = fields.Many2one("f3d.machine", required=True, index=True, ondelete="cascade")
    workcenter_id = fields.Many2one("mrp.workcenter", related="machine_id.workcenter_id", store=True, index=True)
    code = fields.Char(related="machine_id.code", store=True)
    zone_id = fields.Many2one("f3d.zone", related="machine_id.zone_id", store=True)
    company_id = fields.Many2one("res.company", related="machine_id.company_id", store=True)
    date = fields.Date(string="Дата зміни", required=True, index=True)
    date_start = fields.Datetime(string="Початок зміни")
    date_end = fields.Datetime(string="Кінець зміни")
    state = fields.Selection([("open", "Поточна"), ("closed", "Закрита")], required=True, default="open")
    source = fields.Selection([("machine", "Журнал станів"), ("timelog", "Журнал часу Odoo")], required=True)
    ppt_min = fields.Float(digits=D12, string="Плановий час, хв")
    planned_stop_min = fields.Float(digits=D12)
    nodata_min = fields.Float(digits=D12)
    run_min = fields.Float(digits=D12)
    run_wo_min = fields.Float(digits=D12)
    setup_min = fields.Float(digits=D12)
    fault_min = fields.Float(digits=D12)
    idle_min = fields.Float(digits=D12)
    off_min = fields.Float(digits=D12)
    unexplained_min = fields.Float(digits=D12)
    down_min = fields.Float(digits=D12)
    ideal_min = fields.Float(digits=D12, string="Ідеальний час, хв")
    qty_total = fields.Float(digits=D12)
    qty_bad = fields.Float(digits=D12)
    qty_good = fields.Float(digits=D12)
    availability = fields.Float(digits=(6, 4))
    performance = fields.Float(digits=(6, 4))
    performance_raw = fields.Float(digits=(6, 4))
    quality = fields.Float(digits=(6, 4))
    oee = fields.Float(digits=(6, 4))
    has_data = fields.Boolean(string="Є дані")
    coverage = fields.Float(digits=(6, 4), string="Повнота даних")
    incomplete = fields.Boolean(string="Неповні дані")
    losses = fields.Json(string="Втрати")
    computed_at = fields.Datetime(readonly=True)
    oee_color = fields.Selection(
        [("good", "Добре"), ("warn", "Увага"), ("bad", "Погано")], compute="_compute_oee_color"
    )

    _f3d_oee_uniq = models.Constraint("UNIQUE(machine_id, date)", "OEE за цю зміну вже є.")

    @api.depends("oee")
    def _compute_oee_color(self):
        good = float(param(self.env, "oee_good", "0.75"))
        warn = float(param(self.env, "oee_warn", "0.5"))
        for rec in self:
            rec.oee_color = "good" if rec.oee >= good else "warn" if rec.oee >= warn else "bad"

    @api.model
    def _f3d_compute(self, machine, day, close=False):
        """R-14: upsert запису `(machine, day)`; порожній набір — вихідний або зміна ще не почалась."""
        machine = machine.sudo()
        a, b = _day_bounds(day)
        windows = ppt.ppt_intervals(self.env, machine.workcenter_id, a, b)
        if not windows:
            return self.browse()
        t0, t_end = windows[0][0], windows[-1][1]
        now = fields.Datetime.now()
        if now <= t0 and not close:
            return self.browse()
        finished = close or now >= t_end
        res = machine._f3d_oee(t0, t_end if finished else now)
        vals = {k: v for k, v in res.items() if k in self._fields}
        vals.update(
            date_start=t0,
            date_end=t_end,
            state="closed" if finished else "open",
            source=res["source"],
            computed_at=now,
        )
        rec = self.sudo().search([("machine_id", "=", machine.id), ("date", "=", day)], limit=1)
        if rec:
            rec.write(vals)
        else:
            rec = self.sudo().create(dict(vals, machine_id=machine.id, date=day))
        return rec

    @api.model
    def _cron_oee(self):
        """R-14 п. 2: поточна зміна кожного підключеного верстата; вчорашня відкрита — закривається."""
        today = _local_date(fields.Datetime.now())
        machines = self.env["f3d.machine"].sudo().search([("active", "=", True), ("read_enabled", "=", True)])
        for machine in machines:
            try:
                with self.env.cr.savepoint():
                    self._f3d_cron_machine(machine, today)
            except Exception:
                _logger.exception("OEE: помилка розрахунку верстата %s", machine.code)
        return True

    @api.model
    def _f3d_cron_machine(self, machine, today):
        yesterday = self.sudo().search(
            [("machine_id", "=", machine.id), ("date", "=", today - timedelta(days=1)), ("state", "=", "open")], limit=1
        )
        if yesterday:
            self._f3d_compute(machine, yesterday.date, close=True)
        rec = self.sudo().search([("machine_id", "=", machine.id), ("date", "=", today)], limit=1)
        if not rec or rec.state != "closed":
            rec = self._f3d_compute(machine, today)
        if rec:
            machine.write({"oee_shift_id": rec.id})

    def action_recompute(self):
        if not (self.env.is_superuser() or self.env.user.has_group("factory3d_base.group_f3d_manager")):
            raise AccessError(_("Перерахувати OEE може лише менеджер."))
        for rec in self.sudo():
            self._f3d_compute(rec.machine_id, rec.date, close=rec.state == "closed")
        return True

    def action_oee_period(self):
        """V-14: агрегат R-13 п. 8 за виділеними записами (суми хвилин, не середнє відношень)."""
        rows = self.sudo().filtered(lambda r: r.ppt_min > 0)
        res = oee.aggregate([{k: r[k] for k in AGG_FIELDS} for r in rows])
        dates = rows.mapped("date")
        codes = ", ".join(sorted(set(rows.mapped("code")))) or "-"
        period = "%s–%s" % (min(dates).strftime("%d.%m"), max(dates).strftime("%d.%m")) if dates else "-"

        def f(x):
            return ("%.2f" % x).replace(".", ",")

        message = "%s, %s: A %s · P %s · Q %s · OEE %s" % (
            codes,
            period,
            f(res["availability"]),
            f(res["performance"]),
            f(res["quality"]),
            f(res["oee"]),
        )
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {"title": _("OEE за період"), "message": message, "type": "info", "sticky": True},
        }


class F3dMachineOee(models.Model):
    _inherit = "f3d.machine"

    # --- R-28: інтервали для енергії -----------------------------------------------------------------
    @api.model
    def _f3d_log_domain(self, date_from, date_to):
        domain = []
        if date_to:
            domain.append(("date_start", "<", date_to))
        if date_from:
            domain += ["|", ("date_end", "=", False), ("date_end", ">", date_from)]
        return domain

    @api.model
    def _f3d_clipped(self, log, date_from, date_to, now):
        start, end = log.date_start, log.date_end or now
        if date_from:
            start = max(start, date_from)
        if date_to:
            end = min(end, date_to)
        return start, end

    @api.model
    def _f3d_wo_intervals(self, workorders, date_from=None, date_to=None):
        """R-28 п. 1: `{wo_id: [(start, end, state), …]}` для `working`/`setup`, UTC naive."""
        now = fields.Datetime.now()
        domain = [("state", "in", ("working", "setup")), ("workorder_id", "in", workorders.ids)]
        logs = self.env["f3d.machine.state.log"].sudo().search(domain + self._f3d_log_domain(date_from, date_to))
        res = {}
        for log in logs.sorted("date_start"):
            start, end = self._f3d_clipped(log, date_from, date_to, now)
            if end > start:
                res.setdefault(log.workorder_id.id, []).append((start, end, log.state))
        return res

    @api.model
    def _f3d_wc_intervals(self, workcenter, date_from, date_to):
        """R-28 п. 2: `[(start, end, state, wo_id | False), …]` усіх станів РЦ."""
        now = fields.Datetime.now()
        domain = [("workcenter_id", "=", workcenter.id)] + self._f3d_log_domain(date_from, date_to)
        res = []
        for log in self.env["f3d.machine.state.log"].sudo().search(domain).sorted("date_start"):
            start, end = self._f3d_clipped(log, date_from, date_to, now)
            if end > start:
                res.append((start, end, log.state, log.workorder_id.id or False))
        return res

    # --- R-13: OEE за фактом -------------------------------------------------------------------------
    @api.model
    def _f3d_cycle(self, wo):
        """Ідеальний цикл завдання, хв/шт (R-13 п. 5)."""
        wc, op = wo.workcenter_id, wo.operation_id
        if op:
            cap = wc._get_capacity(wo.product_id, wo.product_uom_id)
            cap = (cap[0] if isinstance(cap, (tuple, list)) else cap) or 1
            return op.time_cycle_manual / cap * 100.0 / (wc.time_efficiency or 100.0)
        return wo.duration_expected / wo.qty_production if wo.qty_production else 0.0

    def _f3d_oee(self, t0, t1):
        """R-13: показники OEE верстата за `[t0, t1)` (naive UTC) — словник полів `f3d.oee.shift` + `source`."""
        self.ensure_one()
        wc = self.workcenter_id.sudo()
        env = self.env
        inp = {"ppt": ppt.ppt_intervals(env, wc, t0, t1), "planned": [], "nodata": [], "pieces": {}, "cycles": {}}
        # прості (R-13 п. 1, 10)
        losses = {}
        for dt in (
            env["f3d.downtime"]
            .sudo()
            .search(
                [
                    ("machine_id", "=", self.id),
                    ("date_start", "<", t1),
                    "|",
                    ("date_end", "=", False),
                    ("date_end", ">", t0),
                ]
            )
        ):
            iv = ppt.clip([(dt.date_start, dt.date_end or t1)], t0, t1)
            if dt.loss_id.f3d_planned:
                inp["planned"] += iv
            else:
                losses.setdefault(dt.loss_id, []).extend(iv)
        inp["losses"] = [(loss.id, loss.name, ivs) for loss, ivs in losses.items()]
        logs = env["f3d.machine.state.log"].sudo().search([("machine_id", "=", self.id)] + self._f3d_log_domain(t0, t1))
        wos = env["mrp.workorder"]
        if logs:
            source = "machine"
            buckets = {k: [] for k in ("run", "run_wo", "setup", "fault", "idle", "off", "nodata")}
            for log in logs:
                start, end = max(log.date_start, t0), min(log.date_end or t1, t1)
                if end <= start:
                    continue
                key = {"working": "run"}.get(log.state, log.state)
                buckets[key].append((start, end))
                if log.state == "working" and log.workorder_id:
                    buckets["run_wo"].append((start, end))
                if log.workorder_id and log.pieces:
                    full = ((log.date_end or t1) - log.date_start).total_seconds()
                    share = (end - start).total_seconds() / full if full > 0 else 1.0
                    inp["pieces"][log.workorder_id.id] = (
                        inp["pieces"].get(log.workorder_id.id, 0.0) + log.pieces * share
                    )
                    wos |= log.workorder_id
            inp.update(buckets)
        else:
            source = "timelog"
            wos = self._f3d_timelog_inputs(inp, wc, t0, t1)
        for wo in wos.sudo():
            inp["cycles"][wo.id] = self._f3d_cycle(wo)
        inp["bad"] = self._f3d_bad(wc, t0, t1)
        res = oee.compute_oee(inp, float(param(env, "coverage_min", "0.95")))
        res["source"] = source
        return res

    def _f3d_timelog_inputs(self, inp, wc, t0, t1):
        """R-13 п. 9: джерело — журнал часу Odoo; повертає завдання, завершені у вікні."""
        env = self.env
        setup_ids = {
            r.id
            for r in (
                env.ref("mrp.block_reason2", raise_if_not_found=False),
                env.ref("factory3d.loss_tool", raise_if_not_found=False),
            )
            if r
        }
        fault = env.ref("mrp.block_reason1", raise_if_not_found=False)
        for key in ("run", "run_wo", "setup", "fault", "idle", "off"):
            inp[key] = []
        recs = (
            env["mrp.workcenter.productivity"]
            .sudo()
            .search(
                [
                    ("workcenter_id", "=", wc.id),
                    ("date_start", "<", t1),
                    "|",
                    ("date_end", "=", False),
                    ("date_end", ">", t0),
                ]
            )
        )
        for rec in recs:
            iv = ppt.clip([(rec.date_start, rec.date_end or t1)], t0, t1)
            loss_type = rec.loss_id.loss_type
            if loss_type in ("productive", "performance"):
                inp["run"] += iv
                inp["run_wo"] += iv
            elif loss_type in ("availability", "quality"):
                key = "setup" if rec.loss_id.id in setup_ids else "fault" if rec.loss_id == fault else "idle"
                inp[key] += iv
        wos = (
            env["mrp.workorder"]
            .sudo()
            .search(
                [
                    ("workcenter_id", "=", wc.id),
                    ("state", "=", "done"),
                    ("date_finished", ">=", t0),
                    ("date_finished", "<", t1),
                ]
            )
        )
        for wo in wos:
            inp["pieces"][wo.id] = wo.qty_produced
        return wos

    def _f3d_bad(self, wc, t0, t1):
        """Брак за вікно: `stock.scrap` у стані `done` завдань РЦ (товар — виріб МО)."""
        scraps = (
            self.env["stock.scrap"]
            .sudo()
            .search(
                [
                    ("state", "=", "done"),
                    ("workorder_id.workcenter_id", "=", wc.id),
                    ("date_done", ">=", t0),
                    ("date_done", "<", t1),
                ]
            )
        )
        return sum(s.scrap_qty for s in scraps if s.product_id == s.workorder_id.production_id.product_id)
