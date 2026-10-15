import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..tools import ats, dates
from ..tools.dates import param_float

_logger = logging.getLogger(__name__)

ATS = "infra/ats/"
INCOMER_CODES = ("energy/cells/Q1/p_now", "energy/cells/Q1/i_now", "energy/cells/Q2/p_now", "energy/cells/Q2/i_now")
TRIGGER_CODES = (
    ATS + "src1_state",
    ATS + "src2_state",
    ATS + "position",
    ATS + "gen_start",
    ATS + "mode",
) + INCOMER_CODES


class F3dEnergyOutage(models.Model):
    """M-10. Відключення мережі (R-14)."""

    _name = "f3d.energy.outage"
    _description = "Енергетика: відключення мережі"
    _inherit = ["mail.thread"]
    _order = "ts_start desc"

    name = fields.Char(string="Назва", compute="_compute_name", store=True)
    ts_start = fields.Datetime(string="Початок", required=True, index=True)
    ts_end = fields.Datetime(string="Кінець")
    duration_min = fields.Float(string="Тривалість, хв", compute="_compute_duration", store=True, digits=(10, 1))
    state = fields.Selection(
        [("open", "Триває"), ("closed", "Завершено")], string="Стан", required=True, default="open", index=True
    )
    source = fields.Selection([("ats", "За АВР"), ("incomers", "За вводами")], string="Джерело", required=True)
    amf_master = fields.Selection(
        [("hgm", "HGM6120N (Remote control АВР)"), ("ats", "ATyS p (Auto)"), ("unknown", "Невідомо")],
        string="Ведучий АВР",
        default="unknown",
    )
    transfer_s = fields.Float(string="Переключення на генератор, с", digits=(8, 1))
    return_s = fields.Float(string="Повернення на мережу, с")
    gen_started = fields.Boolean(string="Генератор запустився")
    gen_start_at = fields.Datetime(string="Пуск генератора", readonly=True)
    grid_back_at = fields.Datetime(string="Мережа повернулась", readonly=True)
    fail_start = fields.Boolean(string="FAIL START")
    load_before_kw = fields.Float(string="Навантаження до, кВт", digits=(10, 1))
    critical_kw = fields.Float(string="Критичне навантаження, кВт", digits=(10, 1))
    load_island_kw = fields.Float(string="Навантаження в острові, кВт", digits=(10, 1))
    shed_kw = fields.Float(string="Відключено, кВт", digits=(10, 1))
    event_ids = fields.One2many("f3d.energy.event", "outage_id", string="Події")
    note = fields.Text(string="Примітка")

    @api.depends("ts_start")
    def _compute_name(self):
        for rec in self:
            rec.name = (
                _("Відключення %s") % dates.to_local(rec.ts_start).strftime("%d.%m.%Y %H:%M") if rec.ts_start else ""
            )

    @api.depends("ts_start", "ts_end")
    def _compute_duration(self):
        for rec in self:
            if rec.ts_start and rec.ts_end:
                rec.duration_min = (rec.ts_end - rec.ts_start).total_seconds() / 60.0
            else:
                rec.duration_min = 0.0

    @api.constrains("state")
    def _check_single_open(self):
        for rec in self.filtered(lambda r: r.state == "open"):
            other = self.sudo().search([("state", "=", "open"), ("id", "!=", rec.id)], limit=1)
            if other:
                raise ValidationError(_("Уже триває відключення %s.") % other.name)

    # --- R-14: читання сигналів -------------------------------------------------------------------------
    @api.model
    def _f3d_ats_read(self, now):
        """{код: (рядок сигналу, свіжий?)} для сигналів АВР і вводів."""
        factor = param_float(self.env, "ats_fresh_factor", 3.0)
        rows = (
            self.env["f3d.signal"]
            .sudo()
            .search_read(
                [("code", "in", list(TRIGGER_CODES))],
                ["code", "status", "last_text", "last_value", "last_ts", "period_s"],
            )
        )
        out = {}
        for r in rows:
            age = (now - r["last_ts"]).total_seconds() if r["last_ts"] else None
            out[r["code"]] = (r, ats.is_fresh(r["status"], age, r["period_s"], factor))
        return out

    @api.model
    def _f3d_ats_totals(self):
        """Значення `energy/totals/p_now` (None — немає)."""
        sig = self.env["f3d.signal"].sudo().search([("code", "=", "energy/totals/p_now")], limit=1)
        return sig.last_value if sig and sig.last_ts else None

    # --- R-14 п. 2–10: крок автомата ---------------------------------------------------------------------
    @api.model
    def _f3d_ats_step(self, now=None):
        """Ідемпотентний крок: стан мережі за свіжими сигналами → відкрити/оновити/закрити відключення."""
        now = now or dates.now_utc(self.env)
        sig = self._f3d_ats_read(now)

        def text(code, fresh_only=True):
            row, fresh = sig.get(ATS + code, (None, False))
            if row is None or not row["last_ts"] or (fresh_only and not fresh):
                return None
            return row["last_text"]

        def ts_of(code):
            row = sig.get(ATS + code, (None, False))[0]
            return row["last_ts"] if row else None

        position = sig.get(ATS + "position", (None, False))
        position_v = position[0]["last_value"] if position[1] and position[0]["last_value"] is not None else None
        incomers = []
        for p_code, i_code in (
            ("energy/cells/Q1/p_now", "energy/cells/Q1/i_now"),
            ("energy/cells/Q2/p_now", "energy/cells/Q2/i_now"),
        ):
            p_row, i_row = sig.get(p_code, (None, False)), sig.get(i_code, (None, False))
            incomers.append(
                (
                    p_row[0]["last_value"] if p_row[1] else None,
                    i_row[0]["last_value"] if i_row[1] else None,
                )
            )
        grid_ok, source = ats.grid_state(text("src1_state"), position_v, incomers)
        ats_fresh = text("src1_state") is not None or position_v is not None
        mode = text("mode", fresh_only=False)
        self._f3d_ats_bridge_check(mode, now)

        outage = self.sudo().search([("state", "=", "open")], limit=1)
        if not outage:
            if grid_ok:
                return self.browse()
            outage = self._f3d_ats_open(source, mode, text("src1_state") and ts_of("src1_state"), position, now)
        outage = outage.sudo()
        Event = self.env["f3d.energy.event"]
        # п. 5: gen_start і FAIL START
        gen_on = text("gen_start", fresh_only=False) == "on"
        if gen_on and not outage.gen_start_at:
            outage.gen_start_at = ts_of("gen_start") or now
        self._f3d_ats_fail_start(outage, mode, gen_on, text("src2_state", fresh_only=False), now)
        # п. 6: переключення на генератор
        if position_v == ats.POS_GEN and not outage.gen_started:
            ts = ts_of("position") or now
            outage.write({"transfer_s": max(0.0, (ts - outage.ts_start).total_seconds()), "gen_started": True})
            Event._f3d_log(
                "info",
                "ats",
                "ATS-1",
                "АВР: переключено на генератор за %d с." % round(outage.transfer_s),
                ts=ts,
                outage=outage,
            )
        # п. 7: повернення мережі й закриття
        if grid_ok:
            if not outage.grid_back_at:
                back = ts_of("src1_state") if text("src1_state") is not None else now
                outage.grid_back_at = max(back, outage.ts_start)
            if position_v == ats.POS_GRID or not ats_fresh:
                ts = ts_of("position") if position_v == ats.POS_GRID else now
                ts = max(ts or now, outage.grid_back_at)
                return_s = (ts - outage.grid_back_at).total_seconds()
                outage.write({"ts_end": ts, "return_s": return_s, "state": "closed"})
                Event._f3d_log(
                    "info",
                    "outage",
                    "ATS-1",
                    "Мережу відновлено, АВР повернув живлення від мережі через %d с; відключення тривало %d хв."
                    % (round(return_s), round(outage.duration_min)),
                    ts=ts,
                    outage=outage,
                )
        return outage

    @api.model
    def _f3d_ats_open(self, source, mode, ts_src, position, now):
        """П. 4: нове відключення."""
        ts = ts_src or (position[0]["last_ts"] if position[1] and source == "ats" else None) or now
        critical = 0.0
        try:
            critical = self.env["f3d.energy.node"]._f3d_live_snapshot()["critical_kw"]
        except Exception:
            _logger.exception("f3d_energy: critical_kw при відкритті відключення")
        outage = self.sudo().create(
            {
                "ts_start": ts,
                "source": source,
                "amf_master": ats.amf_master(mode),
                "load_before_kw": self._f3d_ats_totals() or 0.0,
                "critical_kw": critical,
            }
        )
        self.env["f3d.energy.event"]._f3d_log(
            "bad",
            "outage",
            "ATS-1",
            "Зникла напруга мережі (ввід 10 кВ). Режим АВР: %s." % ats.mode_label(mode),
            ts=ts,
            outage=outage,
        )
        return outage

    @api.model
    def _f3d_ats_fail_start(self, outage, mode, gen_on, src2, now):
        """П. 5: реле `infra/ats/fail_start` і прапорець відключення."""
        limit = param_float(self.env, "ats_fail_start_s", 35.0)
        Signal = self.env["f3d.signal"].sudo()
        cur = Signal.search([("code", "=", ATS + "fail_start")], limit=1)
        age = (now - outage.gen_start_at).total_seconds() if gen_on and outage.gen_start_at else None
        if ats.fail_start_due(mode, age, src2, limit):
            if not outage.fail_start:
                outage.fail_start = True
                self.env["f3d.energy.event"]._f3d_log(
                    "bad",
                    "ats",
                    "ATS-1",
                    "АВР: генератор не запустився за %d с (FAIL START)." % round(limit),
                    ts=now,
                    outage=outage,
                )
            if not cur.last_value:
                Signal._f3d_energy_put([{"code": ATS + "fail_start", "ts": now, "value": 1, "q": "good"}])
        elif cur.last_value and (src2 == "available" or not gen_on):
            Signal._f3d_energy_put([{"code": ATS + "fail_start", "ts": now, "value": 0, "q": "good"}])

    @api.model
    def _f3d_ats_bridge_check(self, mode, now):
        """П. 10: узгодженість режиму АВР з налаштуванням моста генератора (раз на добу)."""
        bridge = self.env["ir.config_parameter"].sudo().get_param("factory3d.genset.amf_master")
        if bridge in ("hgm", "ats") and ats.amf_master(mode) in ("hgm", "ats") and ats.amf_master(mode) != bridge:
            self.env["f3d.energy.event"]._f3d_log(
                "warn",
                "ats",
                "ATS-1",
                "Режим АВР «%s» не відповідає налаштуванню моста генератора «%s»." % (ats.mode_label(mode), bridge),
                ts=now,
                dedup_min=1440,
            )

    # --- R-14 п. 8: крон живих показників ----------------------------------------------------------------
    @api.model
    def _f3d_ats_tick(self, now=None):
        """Під час відкритого відключення: `load_island_kw`, `shed_kw`; повторний крок автомата (таймаут FAIL START)."""
        now = now or dates.now_utc(self.env)
        self._f3d_ats_step(now)
        outage = self.sudo().search([("state", "=", "open")], limit=1)
        if outage:
            load = self._f3d_ats_totals()
            if load is not None:
                outage.write({"load_island_kw": load, "shed_kw": ats.shed(outage.load_before_kw, load, outage.shed_kw)})
        return outage
