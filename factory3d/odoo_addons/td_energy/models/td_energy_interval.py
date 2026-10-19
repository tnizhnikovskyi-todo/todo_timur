import logging
import time
from datetime import timedelta

from odoo import _, api, fields, models, tools
from odoo.exceptions import AccessError

from odoo.addons.td_telemetry.tools.titles import fmt_num

from ..tools import backfill, bus, dates, live
from ..tools import tariff as tariff_tools
from ..tools.dates import SLOT, param_bool, param_float

_logger = logging.getLogger(__name__)

COST_ROLES = ("incomer", "feeder", "consumer")
MAX_SLOTS = 192
INSERT_SQL = """
INSERT INTO td_energy_interval (meter_id, node_id, role, ts_start, ts_end, day, hour_local, e_start, e_end, kwh,
    kwh_export, kw_avg, zone_id, price, cost, quality, built_at)
VALUES %s
ON CONFLICT (meter_id, ts_start) DO UPDATE SET e_start = EXCLUDED.e_start, e_end = EXCLUDED.e_end,
    kwh = EXCLUDED.kwh, kwh_export = EXCLUDED.kwh_export, kw_avg = EXCLUDED.kw_avg, zone_id = EXCLUDED.zone_id,
    price = EXCLUDED.price, cost = EXCLUDED.cost, quality = EXCLUDED.quality, built_at = EXCLUDED.built_at
"""


class F3dEnergyInterval(models.Model):
    """M-03. 15-хвилинний профіль лічильника; запис — лише кроном і майстром (R-04)."""

    _name = "td.energy.interval"
    _inherit = ["td.energy.day.mixin"]
    _description = "Енергетика: 15-хвилинний інтервал"
    _order = "ts_start desc, meter_id"
    _log_access = False
    _rec_name = "ts_start"

    meter_id = fields.Many2one("td.energy.meter", string="Лічильник", required=True, ondelete="cascade", index=True)
    node_id = fields.Many2one(related="meter_id.node_id", store=True, index=True)
    role = fields.Selection(related="meter_id.role", store=True)
    ts_start = fields.Datetime(string="Початок (UTC)", required=True, index=True)
    ts_end = fields.Datetime(string="Кінець (UTC)", required=True)
    day = fields.Date(string="Дата (Київ)", required=True, index=True)
    hour_local = fields.Integer(string="Година (Київ)", required=True)
    e_start = fields.Float(digits=(16, 3), string="Показник на початку")
    e_end = fields.Float(digits=(16, 3), string="Показник у кінці")
    kwh = fields.Float(string="кВт·год", digits=(12, 3))
    kwh_export = fields.Float(string="Віддано, кВт·год", digits=(12, 3), default=0)
    kw_avg = fields.Float(string="Середня, кВт", digits=(10, 2))
    zone_id = fields.Many2one("td.energy.tariff.zone", string="Зона тарифу", ondelete="set null")
    price = fields.Float(string="Ціна, грн/кВт·год", digits=(10, 4), groups="td_energy.group_td_energy_cost")
    cost = fields.Float(string="Вартість, грн", digits=(12, 2), groups="td_energy.group_td_energy_cost")
    quality = fields.Selection(
        [
            ("measured", "Виміряно"),
            ("interpolated", "Інтерпольовано"),
            ("reset", "Скидання лічильника"),
            ("missing", "Немає даних"),
        ],
        string="Якість",
        required=True,
        default="measured",
        index=True,
    )
    built_at = fields.Datetime(string="Побудовано", required=True)
    is_backfill = fields.Boolean(string="Синтетичні дані", default=False, index=True, readonly=True)  # W1 (M-24)

    _f3d_energy_interval_uniq = models.Constraint("UNIQUE(meter_id, ts_start)", "Інтервал для лічильника вже є.")

    def init(self):
        tools.sql.create_index(self.env.cr, "td_energy_interval_day_idx", self._table, ["day", "role"])

    # --- R-04: крон -----------------------------------------------------------------------------------
    @api.model
    def _cron_build(self):
        if not param_bool(self.env, "read_enabled"):
            return 0
        now = dates.now_utc(self.env)
        meters = self.env["td.energy.meter"].sudo().search([("active", "=", True), ("e_import_signal_id", "!=", False)])
        total = 0
        for meter in meters:
            try:
                with self.env.cr.savepoint():
                    total += self._td_build_meter(meter, now)
            except Exception:
                _logger.exception("f3d_energy: профіль лічильника %s", meter.code)
        try:
            with self.env.cr.savepoint():
                self._td_after_build(now)
        except Exception:
            _logger.exception("f3d_energy: kwh_shift / профіль доби / пік")
        bus.tick(self.env, "profile")  # W1 R-33: один раз за прогін
        return total

    @api.model
    def _td_rebuild(self, meters, date_from, date_to):
        """R-04 для вікна (майстер M-19, повтор `missing`): upsert слотів `[date_from, date_to)`."""
        now = dates.now_utc(self.env)
        total = 0
        for meter in meters.sudo().filtered("e_import_signal_id"):
            total += self._td_build_meter(meter, now, force_from=date_from, force_to=date_to)
        return total

    @api.model
    def _td_build_meter(self, meter, now, force_from=None, force_to=None):
        """R-04 п. 1–7 для одного лічильника; повертає кількість записаних слотів."""
        env = self.env
        meter = meter.sudo()
        signal = meter.e_import_signal_id
        settle = timedelta(seconds=param_float(env, "settle_s", 120))
        max_wait = timedelta(hours=param_float(env, "max_wait_h", 6))
        end_limit = dates.floor15(now - settle)
        last = meter.last_interval_start
        done_until = last + SLOT if last else None
        limit = None if force_from else MAX_SLOTS
        if force_from:
            s0 = dates.floor15(force_from)
            if force_to:
                end_limit = min(end_limit, dates.ceil15(force_to))
        else:
            if last:
                s0 = last + SLOT
            else:
                first = (
                    env["td.reading"]
                    .sudo()
                    .search([("signal_id", "=", signal.id), ("quality", "!=", "bad")], order="ts", limit=1)
                )
                if not first:
                    return 0
                s0 = max(dates.ceil15(first.ts), dates.floor15(now - timedelta(days=2)))
            missing = self.search(
                [
                    ("meter_id", "=", meter.id),
                    ("quality", "=", "missing"),
                    ("ts_start", ">=", now - timedelta(hours=48)),
                ],
                order="ts_start",
                limit=1,
            )
            if missing and signal.last_ts and signal.last_ts >= missing.ts_end and missing.ts_start < s0:
                s0 = missing.ts_start
        if s0 + SLOT > end_limit:
            return 0
        count = (end_limit - s0) // SLOT
        if limit:
            count = min(count, limit)
        s_end = s0 + count * SLOT
        series = meter._td_counter_series(s0, s_end, base=meter.counter_offset)
        series_x = (
            meter._td_counter_series(s0, s_end, base=meter.counter_offset_export, export=True)
            if meter.e_export_signal_id
            else None
        )
        prev = self.search([("meter_id", "=", meter.id), ("ts_start", "=", s0 - SLOT)], limit=1)
        c_prev = prev.e_end if prev else None
        t_last = series.ts[-1] if series else None
        Tariff = env["td.energy.tariff"].sudo()
        company = meter.company_id
        built_at = fields.Datetime.now()
        rows, built_to, tariffs = [], None, {}
        for k in range(count):
            a = s0 + k * SLOT
            b = a + SLOT
            e_a, e_b = series.value_at(a), series.value_at(b)
            if e_a is None:
                e_a = c_prev
            if e_b is None:
                silent = now - b >= max_wait or (t_last is not None and now - t_last >= max_wait)
                if not silent:
                    break
                c_known = e_a if e_a is not None else series.last_c
                if c_known is None:
                    break
                e_a = e_b = c_known
                kwh, quality = 0.0, "missing"
            elif e_a is None:
                continue
            elif series.value_at(a) is None:
                kwh, quality = max(e_b - e_a, 0.0), "interpolated"
            else:
                kwh, quality = series.delta(a, b)
            kwh_export = 0.0
            if series_x is not None:
                dx, _qx = series_x.delta(a, b)
                kwh_export = dx or 0.0
            local = dates.to_local(a)
            ld = local.date()
            if ld not in tariffs:  # D-1: тариф і зони — один пошук на місцеву добу, а не на слот
                tariff = Tariff._td_tariff_at(a, company)
                tariffs[ld] = (tariff, tariff.zone_ids.sorted("sequence") if tariff else None)
                if not tariff:
                    env["td.energy.event"]._td_log(
                        "warn",
                        "meter",
                        meter.code,
                        "Немає чинного тарифу на %s" % local.strftime("%d.%m.%Y"),
                        ts=now,
                        dedup_min=1440,
                    )
            tariff, zones = tariffs[ld]
            zone, price = env["td.energy.tariff.zone"], 0.0
            if tariff:
                zone = tariff_tools.zone_for(local, zones) or zone
                price = zone.price if zone else 0.0
            kwh_r = round(kwh, 3)
            cost = round(kwh_r * price, 2) if meter.role in COST_ROLES else 0.0
            rows.append(
                (
                    meter.id, meter.node_id.id, meter.role, a, b, local.date(), local.hour, round(e_a, 3),
                    round(e_b, 3), kwh_r, round(kwh_export, 3), round(kwh * 4, 2), zone.id or None, price, cost,
                    quality, built_at,
                )
            )  # fmt: skip
            c_prev, built_to = e_b, a
        if not rows:
            return 0
        env.cr.execute_values(INSERT_SQL, rows)
        self.invalidate_model()
        self._td_apply_resets(meter, series, series_x, done_until or s0, built_to + SLOT)
        meter.with_context(mail_notrack=True).write({"last_interval_start": max(built_to, last) if last else built_to})
        return len(rows)

    @api.model
    def _td_apply_resets(self, meter, series, series_x, after, until):
        """R-03 п. 2: нова поправка `counter_offset` і подія — для скидань, що потрапили в збудований інтервал."""
        vals = {}
        for t, v_prev, v, c in series.resets:
            if after < t <= until:
                vals["counter_offset"] = c - v
                self.env["td.energy.event"]._td_log(
                    "warn",
                    "meter",
                    meter.code,
                    "Лічильник %s: скидання показника %s → %s кВт·год"
                    % (meter.code, fmt_num(v_prev, 3), fmt_num(v, 3)),
                    ts=t,
                    node=meter.node_id,
                )
        if series_x is not None:
            for t, _v_prev, v, c in series_x.resets:
                if after < t <= until:
                    vals["counter_offset_export"] = c - v
        if vals:
            meter.with_context(mail_notrack=True).write(vals)

    # --- R-11, R-15: після побудови --------------------------------------------------------------------
    @api.model
    def _td_after_build(self, now):
        self._td_shift_kwh(now)
        self._td_load_signals(now)
        self._td_peak_event(now)
        if "td.viewer.event" in self.env:
            self.env["td.viewer.event"]._notify("td.energy", ["energy"], "signal")

    @api.model
    def _td_shift_hours(self):
        """Мінімальний `hour_from` атендансів календаря зміни за днями тижня."""
        raw = self.env["ir.config_parameter"].sudo().get_param("td.energy.shift_calendar_id")
        if not (raw and str(raw).isdigit()):
            return {}
        cal = self.env["resource.calendar"].sudo().browse(int(raw)).exists()
        hours = {}
        for att in cal.attendance_ids:
            if att.display_type:
                continue
            dow = int(att.dayofweek)
            hours[dow] = min(att.hour_from, hours.get(dow, 24))
        return hours

    @api.model
    def _td_shift_kwh(self, now):
        """R-11: `energy/consumers/<код>/kwh_shift` = `delta(shift_start, last_ts)` лічильника вузла.

        Лічильник без показання на `shift_start` (звітує менше зміни): енергія від першого показання,
        якість `uncertain` (E-4).
        """
        if not param_bool(self.env, "read_enabled"):
            return
        Signal = self.env["td.signal"].sudo()
        start = dates.shift_start(now, self._td_shift_hours())
        readings = []
        for sig in Signal.search([("code", "=like", "energy/consumers/%/kwh_shift"), ("derived_from_id", "!=", False)]):
            src = sig.derived_from_id
            meter = self.env["td.energy.meter"].sudo().search([("e_import_signal_id", "=", src.id)], limit=1)
            if not meter or not src.last_ts or src.last_ts <= start:
                continue
            series = meter._td_counter_series(start, src.last_ts)
            delta, _q = series.delta(start, src.last_ts)
            quality = "good"
            if delta is None and series and start < series.ts[0] < src.last_ts:
                # E-4: лічильник почав звітувати посеред зміни (новий вузол, свіжа установка, стенд) — немає
                # `Ec(shift_start)`, `delta` дає `missing`, і `kwh_shift` лишався порожнім до наступної зміни.
                # Енергія від першого показання, `uncertain`.
                delta, _q = series.delta(series.ts[0], src.last_ts)
                quality = "uncertain"
            if delta is not None:
                readings.append({"code": sig.code, "ts": src.last_ts, "value": round(delta, 2), "q": quality})
        Signal._td_energy_put(readings)

    @api.model
    def _td_load_signals(self, now):
        """R-15 п. 3–4: `load15_kw` (фідери) і `grid15_kw` (вводи) за збудованими слотами останніх 2 год."""
        lo = dates.floor15(now) - timedelta(hours=2)
        readings = []
        rows = self.sudo().search_read(
            [("role", "in", ("feeder", "incomer")), ("ts_start", ">=", lo)],
            ["role", "ts_start", "kwh", "kwh_export"],
            order="ts_start",
        )
        feeders, grid = {}, {}
        for r in rows:
            if r["role"] == "feeder":
                feeders[r["ts_start"]] = feeders.get(r["ts_start"], 0.0) + r["kwh"]
            else:
                grid[r["ts_start"]] = grid.get(r["ts_start"], 0.0) + r["kwh"] - r["kwh_export"]
        for ts_start, kwh in sorted(feeders.items()):
            readings.append(
                {"code": "energy/totals/load15_kw", "ts": ts_start + SLOT, "value": round(kwh * 4, 2), "q": "good"}
            )
        for ts_start, net in sorted(grid.items()):
            readings.append(
                {
                    "code": "energy/totals/grid15_kw",
                    "ts": ts_start + SLOT,
                    "value": round(max(0.0, net) * 4, 2),
                    "q": "good",
                }
            )
        self.env["td.signal"].sudo()._td_energy_put(readings)

    @api.model
    def _td_peak_event(self, now):
        """R-13 п. 3: перший прогін після місцевої півночі — подія про пік 15-хв потужності за вчора."""
        Event = self.env["td.energy.event"].sudo()
        today = dates.local_day(now)
        today_start = dates.local_day_bounds(today)[0]
        if Event.search_count([("kind", "=", "peak"), ("ts", ">=", today_start)]):
            return False
        y0, y1 = dates.local_day_bounds(today - timedelta(days=1))
        rows = self.sudo().search_read(
            [("role", "=", "feeder"), ("ts_start", ">=", y0), ("ts_start", "<", y1)], ["ts_start", "kwh"]
        )
        per_slot = {}
        for r in rows:
            per_slot[r["ts_start"]] = per_slot.get(r["ts_start"], 0.0) + r["kwh"] * 4
        peak_kw, start = live.peak(sorted(per_slot.items()))
        if start is None:
            return False
        local = dates.to_local(start)
        text = "Пік 15-хвилинної потужності за %s: %s кВт о %s" % (
            (today - timedelta(days=1)).strftime("%d.%m"),
            fmt_num(peak_kw, 0),
            local.strftime("%H:%M"),
        )
        level = "info"
        tariff = self.env["td.energy.tariff"].sudo()._td_tariff_at(now)
        if tariff and tariff.contract_kw:
            contract = tariff.contract_kw
            warn = contract * tariff.peak_warn_pct / 100
            level = "info" if peak_kw <= warn else "warn"
            if peak_kw > contract:
                text += "; ліміт договірної потужності (%s кВт) перевищено на %s кВт." % (
                    fmt_num(contract, 0),
                    fmt_num(peak_kw - contract, 0),
                )
            else:
                text += "; ліміт договірної потужності (%s кВт) не перевищено." % fmt_num(contract, 0)
        else:
            text += "."
        node = self.env["td.energy.node"].sudo().search([("code", "=", "SWB-1")], limit=1)
        Event._td_log(level, "peak", "SWB-1", text, ts=now, node=node or None)
        return True

    @api.model
    def _td_day_profile(self, now=None):
        """R-15: `profile`, `kwh_today`, `cost_today`, `peak_kw`, `peak_time`, `typical` (None — статика без змін)."""
        now = now or dates.now_utc(self.env)
        today = dates.local_day(now)
        d0, d1 = dates.local_day_bounds(today)
        cur = dates.floor15(now)
        base = [("role", "=", "feeder")]
        Interval = self.sudo()
        rows = Interval.search_read(
            base + [("ts_start", ">=", d0), ("ts_start", "<", min(d1, cur))], ["ts_start", "hour_local", "kwh", "cost"]
        )
        partial = 0.0
        if now > cur:
            for meter in self.env["td.energy.meter"].sudo().search([("role", "=", "feeder"), ("active", "=", True)]):
                delta, _q = meter._td_counter_series(cur, now).delta(cur, now)
                partial += delta or 0.0
        _zone, price = self.env["td.energy.tariff"].sudo()._td_price_at(cur)
        profile = live.day_profile([(r["hour_local"], r["kwh"]) for r in rows], dates.to_local(now).hour, partial)
        per_slot = {}
        for r in rows:
            per_slot[r["ts_start"]] = per_slot.get(r["ts_start"], 0.0) + r["kwh"] * 4
        peak_kw, start = live.peak(sorted(per_slot.items()))
        keep = int(param_float(self.env, "typical_days", 20))
        return {
            "profile": profile,
            "kwh_today": int(round(sum(r["kwh"] for r in rows) + partial)),
            "cost_today": int(round(sum(r["cost"] for r in rows) + partial * price)),
            "peak_kw": peak_kw,
            "peak_time": dates.to_local(start).strftime("%H:%M") if start else None,
            "typical": live.typical(self._td_typical_profiles(today, keep)),
        }

    @api.model
    def _td_typical_profiles(self, today, keep):
        """Профілі останніх `keep` робочих днів (пн–пт), де ≥ 90 % слотів фідерів не `missing`."""
        first = today - timedelta(days=max(keep * 2, 14))
        d0, d1 = dates.local_day_bounds(first)[0], dates.local_day_bounds(today)[0]
        self.env.cr.execute(
            """SELECT day, hour_local, sum(kwh), count(*), count(*) FILTER (WHERE quality = 'missing')
                 FROM td_energy_interval WHERE role = 'feeder' AND ts_start >= %s AND ts_start < %s
                GROUP BY day, hour_local""",
            (d0, d1),
        )
        cells, total, bad = {}, {}, {}
        for day, hour, kwh, cnt, miss in self.env.cr.fetchall():
            cells.setdefault(day, [0.0] * 24)[hour] += kwh or 0.0
            total[day] = total.get(day, 0) + cnt
            bad[day] = bad.get(day, 0) + miss
        days = [
            d for d in sorted(cells, reverse=True)
            if d.weekday() < 5 and total.get(d) and bad.get(d, 0) <= 0.1 * total[d]
        ]  # fmt: skip
        return [[int(round(v)) for v in cells[d]] for d in days[:keep]]

    # --- W1 (M-24, R-36): генератор історії для демо-стенда -----------------------------------------------
    @api.model
    def _td_backfill(
        self, days=90, until=None, seed=20261018, purge=False, with_balance=True, with_events=True, with_advice=False,
        meters=None,
    ):  # fmt: skip
        """API-15: заповнити БД синтетичними 15-хв інтервалами (R-36); дозволено адміністратору й суперкористувачу."""
        if not (self.env.is_superuser() or self.env.user.has_group("td_factory3d.group_td_admin")):
            raise AccessError(_("Генерувати історію може лише адміністратор."))
        return backfill.run(
            self.env(su=True, context=dict(self.env.context, tracking_disable=True)), days=days, until=until,
            seed=seed, purge=purge, with_balance=with_balance, with_events=with_events, with_advice=with_advice,
            meters=meters,
        )  # fmt: skip

    # --- R-19: ротація --------------------------------------------------------------------------------
    @api.model
    def _td_delete_old(self, table, column, cutoff, deadline):
        cr = self.env.cr
        while time.monotonic() < deadline:
            cr.execute(
                "DELETE FROM %s WHERE id IN (SELECT id FROM %s WHERE %s < %%s LIMIT 50000)" % (table, table, column),
                (cutoff,),
            )
            if cr.rowcount < 50000:
                break

    @api.model
    def _cron_rotate(self):
        now = dates.now_utc(self.env)
        deadline = time.monotonic() + 60
        cutoff = now - timedelta(days=int(param_float(self.env, "keep_interval_days", 400)))
        self._td_delete_old("td_energy_interval", "ts_start", cutoff, deadline)
        self._td_delete_old("td_energy_balance", "hour", cutoff, deadline)
        event_cutoff = now - timedelta(days=int(param_float(self.env, "keep_event_days", 90)))
        self._td_delete_old("td_energy_event", "ts", event_cutoff, deadline)
        self.env.invalidate_all()
