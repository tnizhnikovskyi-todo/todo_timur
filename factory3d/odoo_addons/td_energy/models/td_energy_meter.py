import logging
import re
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from ..tools import dates
from ..tools.counter import Series
from ..tools.dates import param_float

_logger = logging.getLogger(__name__)

ENERGY_UNIT = "кВт·год"
POWER_UNIT = "кВт"


class F3dEnergyMeter(models.Model):
    """M-02. Методи `_f3d_counter_series`, `_f3d_kwh`, `_f3d_update_state` — R-03, R-21."""

    _name = "td.energy.meter"
    _description = "Енергетика: лічильник"
    _inherit = ["mail.thread"]
    _order = "node_id, code"
    _rec_name = "code"
    _rec_names_search = ["code", "name"]
    CODE_RE = re.compile(r"^[A-Z0-9][A-Z0-9\-]{0,31}$")

    code = fields.Char(string="Код", size=32, required=True, index=True, copy=False)
    name = fields.Char(string="Назва", size=128)
    active = fields.Boolean(default=True)
    node_id = fields.Many2one("td.energy.node", string="Вузол", required=True, ondelete="restrict", index=True)
    model = fields.Selection(
        [
            ("pm5560", "Schneider PowerLogic PM5560"),
            ("sun2000", "Huawei SUN2000"),
            ("luna2000", "Huawei LUNA2000"),
            ("tedom", "TEDOM ProCon"),
            ("other", "Інший"),
        ],
        required=True,
        default="pm5560",
    )
    role = fields.Selection(
        [
            ("incomer", "Ввід"),
            ("feeder", "Фідер"),
            ("consumer", "Споживач"),
            ("generation", "Генерація"),
            ("storage", "Накопичувач"),
        ],
        string="Роль",
        required=True,
    )
    source_id = fields.Many2one("td.source", string="Джерело", ondelete="set null")
    p_signal_id = fields.Many2one("td.signal", string="Сигнал потужності, кВт", ondelete="set null")
    e_import_signal_id = fields.Many2one(
        "td.signal",
        string="Лічильник енергії (споживання / вироблення), кВт·год",
        domain="[('kind', '=', 'counter')]",
        ondelete="set null",
    )
    e_export_signal_id = fields.Many2one(
        "td.signal",
        string="Лічильник енергії (віддача), кВт·год",
        domain="[('kind', '=', 'counter')]",
        ondelete="set null",
    )
    counter_offset = fields.Float(string="Поправка після скидань (імпорт)", digits=(16, 3), default=0, readonly=True)
    counter_offset_export = fields.Float(
        string="Поправка після скидань (експорт)", digits=(16, 3), default=0, readonly=True
    )
    data_state = fields.Selection(
        [
            ("no_data", "Ще не було даних"),
            ("ok", "Норма"),
            ("stale", "Немає даних"),
            ("gap", "Пропуск"),
            ("reset", "Скидання лічильника"),
        ],
        string="Стан даних",
        default="no_data",
        readonly=True,
        index=True,
        tracking=True,
    )
    data_state_since = fields.Datetime(string="Стан з", readonly=True)
    last_interval_start = fields.Datetime(string="Останній побудований інтервал", readonly=True)
    last_value = fields.Float(related="e_import_signal_id.last_value", string="Показник, кВт·год")
    last_ts = fields.Datetime(related="e_import_signal_id.last_ts", string="Час показника")
    p_now = fields.Float(related="p_signal_id.last_value", string="Потужність, кВт")
    max_kw = fields.Float(
        string="Максимальна потужність, кВт",
        digits=(10, 1),
        required=True,
        default=10,
        help="Правдоподібність показань після скидання лічильника (R-03 п. 2).",
    )
    ct_ratio = fields.Char(string="Трансформатори струму", size=16)
    unit_id = fields.Integer(related="node_id.unit_id", string="Modbus unit")
    company_id = fields.Many2one(related="node_id.company_id", store=True)
    note = fields.Text(string="Примітка")

    _f3d_energy_meter_code_uniq = models.Constraint("UNIQUE(code)", "Код лічильника має бути унікальним.")

    @api.constrains("code")
    def _check_code(self):
        for rec in self:
            if not rec.code or not self.CODE_RE.match(rec.code):
                raise ValidationError(
                    _("Код лічильника %s: великі латинські літери, цифри, дефіс (напр. PM-SAW-1).", rec.code)
                )

    @api.constrains("e_import_signal_id", "e_export_signal_id", "p_signal_id")
    def _check_signals(self):
        for rec in self:
            for signal in (rec.e_import_signal_id, rec.e_export_signal_id):
                if not signal:
                    continue
                if signal.kind != "counter":
                    raise ValidationError(
                        _("Лічильник %s: сигнал енергії має бути накопичувальним (counter).", rec.code)
                    )
                if signal.unit != ENERGY_UNIT:
                    raise ValidationError(_("Лічильник %s: сигнал енергії має бути в кВт·год.", rec.code))
            if rec.p_signal_id and rec.p_signal_id.unit != POWER_UNIT:
                raise ValidationError(_("Лічильник %s: потужність має бути в кВт.", rec.code))

    def action_view_intervals(self):
        """Графік 15-хв профілю за останні 2 доби (M-03)."""
        self.ensure_one()
        since = fields.Datetime.subtract(fields.Datetime.now(), hours=48)
        return {
            "type": "ir.actions.act_window",
            "name": _("Профіль"),
            "res_model": "td.energy.interval",
            "view_mode": "graph,pivot,list",
            "domain": [("meter_id", "=", self.id), ("ts_start", ">=", since)],
        }

    # --- безперервний лічильник (R-03) ---------------------------------------------------------------
    def _f3d_counter_series(self, a, b, base=0.0, export=False):
        """R-03 п. 5: ряд `Ec` на вікно `[a, b]` (UTC naive). Показання `td.reading` у `[a − 2 год, b + 2 год]`,
        остання точка до вікна (якорь) і `last_value` сигналу; немає показань (вікно старше `keep_days`) —
        ряд з інтервалів лічильника (лише імпорт)."""
        self.ensure_one()
        signal = (self.e_export_signal_id if export else self.e_import_signal_id).sudo()
        if not signal:
            return Series([], [], [])
        lo, hi = a - timedelta(hours=2), b + timedelta(hours=2)
        Reading = self.env["td.reading"].sudo()
        base_dom = [("signal_id", "=", signal.id), ("quality", "!=", "bad")]
        points = {
            r["ts"]: r["value"]
            for r in Reading.search_read(base_dom + [("ts", ">=", lo), ("ts", "<=", hi)], ["ts", "value"], order="ts")
            if r["value"] is not None
        }
        if signal.last_ts and lo <= signal.last_ts <= hi and signal.last_quality != "bad":
            points.setdefault(signal.last_ts, signal.last_value)
        if not any(t <= a for t in points):
            lead = Reading.search(base_dom + [("ts", "<", lo)], order="ts desc", limit=1)
            if lead and lead.value is not None:
                points[lead.ts] = lead.value
        if not export:
            keep_days = int(self.env["ir.config_parameter"].sudo().get_param("td.telemetry.keep_days", "30"))
            old = a < dates.now_utc(self.env) - timedelta(days=keep_days)
            if not points or (old and min(points) > a):
                series = self._f3d_series_from_intervals(a, b)
                if series:
                    return series
        anchor = max((t for t in points if t <= a), default=None)
        pts = sorted((t, v) for t, v in points.items() if anchor is None or t >= anchor)
        return Series.build(
            pts,
            base=base,
            reset_tol=param_float(self.env, "reset_tol_kwh", 1.0),
            max_kw=self.max_kw,
            gap_max_s=param_float(self.env, "gap_max_s", 900),
        )

    def _f3d_series_from_intervals(self, a, b):
        ivs = (
            self.env["td.energy.interval"]
            .sudo()
            .search_read(
                [("meter_id", "=", self.id), ("ts_end", ">=", a), ("ts_start", "<=", b)],
                ["ts_start", "ts_end", "e_start", "e_end", "quality"],
                order="ts_start",
            )
        )
        ts, cs, seg = [], [], []
        for iv in ivs:
            if ts and iv["ts_start"] < ts[-1]:
                continue
            if ts and iv["ts_start"] > ts[-1]:
                seg.append("interpolated")
                ts.append(iv["ts_start"])
                cs.append(iv["e_start"])
            elif not ts:
                ts.append(iv["ts_start"])
                cs.append(iv["e_start"])
            seg.append(iv["quality"])
            ts.append(iv["ts_end"])
            cs.append(iv["e_end"])
        return Series.from_segments(ts, cs, seg)

    def _f3d_kwh(self, date_from, date_to):
        """CE-06 / API: `(кВт·год, якість)` лічильника за вікно; немає даних — `(0.0, 'missing')`."""
        self.ensure_one()
        if date_from >= date_to:
            raise ValueError("date_from має бути раніше за date_to")
        delta, quality = self._f3d_counter_series(date_from, date_to).delta(date_from, date_to)
        if delta is None:
            return 0.0, "missing"
        return round(delta, 3), quality

    # --- стан даних (R-21) ---------------------------------------------------------------------------
    def _f3d_update_state(self):
        """R-21 п. 1–2: `data_state`, `data_state_since`; подія про відсутність даних довше `gap_alarm_min`."""
        now = dates.now_utc(self.env)
        Interval = self.env["td.energy.interval"].sudo()
        Event = self.env["td.energy.event"].sudo()
        gap_alarm = timedelta(minutes=param_float(self.env, "gap_alarm_min", 60))
        for rec in self.sudo():
            sig = rec.e_import_signal_id
            if not sig or not sig.last_ts:
                state = "no_data"
            else:
                stale_after = timedelta(seconds=3 * (sig.period_s or 60))
                if sig.status == "stale" or now - sig.last_ts > stale_after:
                    state = "stale"
                elif Interval.search_count(
                    [
                        ("meter_id", "=", rec.id),
                        ("quality", "=", "reset"),
                        ("ts_start", ">=", now - timedelta(hours=24)),
                    ]
                ):
                    state = "reset"
                elif Interval.search_count(
                    [
                        ("meter_id", "=", rec.id),
                        ("quality", "in", ("missing", "interpolated")),
                        ("ts_start", ">=", now - timedelta(hours=2)),
                    ]
                ):
                    state = "gap"
                else:
                    state = "ok"
            if state != rec.data_state:
                rec.write({"data_state": state, "data_state_since": now})
            if state == "stale" and sig.last_ts and now - sig.last_ts > gap_alarm:
                minutes = int((now - sig.last_ts).total_seconds() // 60)
                last_local = dates.to_local(sig.last_ts).strftime("%H:%M")
                if not Event.search_count([("kind", "=", "meter"), ("code", "=", rec.code), ("ts", ">", sig.last_ts)]):
                    Event._f3d_log(
                        "warn",
                        "meter",
                        rec.code,
                        "Лічильник %s: немає даних %d хв (останнє показання %s)." % (rec.code, minutes, last_local),
                        ts=now,
                        node=rec.node_id,
                    )
