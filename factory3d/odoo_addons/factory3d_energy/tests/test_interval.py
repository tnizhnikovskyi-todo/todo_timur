"""AC-11, AC-20…AC-25, AC-83, AC-84, AC-86: 15-хвилинний профіль, kwh_shift, профіль доби, ротація."""

from datetime import datetime, time, timedelta

from odoo import Command, fields
from odoo.tests import tagged

from ..tools import dates
from .common import TAGS, F3DEnergyCase
from .test_counter import EnergyMixin

M15 = timedelta(minutes=15)


QUERY_LIMIT = 40


@tagged(*TAGS)
class TestInterval(EnergyMixin, F3DEnergyCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Interval = cls.env["f3d.energy.interval"]
        cls.Event = cls.env["f3d.energy.event"]
        cls.day = (fields.Datetime.now() - timedelta(days=3)).replace(hour=0, minute=0, second=0, microsecond=0)

    def at(self, h, m=0):
        return self.day + timedelta(hours=h, minutes=m)

    def build(self, now):
        return self.Interval.with_context(f3d_now=now)._cron_build()

    def rows(self, meter):
        return self.Interval.search([("meter_id", "=", meter.id)], order="ts_start")

    def test_build_slot(self):  # AC-21
        meter = self.mk_meter("PM-SAW-T")
        self.feed(
            meter.e_import_signal_id, [(self.at(1, 30), 998.808), (self.at(1, 45), 1001.98), (self.at(2), 1005.0)]
        )
        self.build(self.at(2, 30))
        row = self.rows(meter)[0]
        local = dates.to_local(self.at(1, 30))
        self.assertEqual(row.ts_start, self.at(1, 30))
        self.assertAlmostEqual(row.kwh, 3.172, places=3)
        self.assertAlmostEqual(row.kw_avg, 12.69, places=2)
        self.assertEqual((row.price, row.zone_id.code), (8.4, "flat"))
        self.assertAlmostEqual(row.cost, 26.64, places=2)
        self.assertEqual((row.quality, row.day, row.hour_local), ("measured", local.date(), local.hour))
        count = len(self.rows(meter))
        self.build(self.at(2, 30))
        self.assertEqual(len(self.rows(meter)), count)
        self.assertEqual(meter.last_interval_start, self.rows(meter)[-1].ts_start)

    def test_no_tariff_event(self):  # AC-11
        self.env.ref("factory3d_energy.tariff_demo").active = False
        meter = self.mk_meter("PM-SAW-T")
        self.feed(meter.e_import_signal_id, [(self.at(1, 30), 10.0), (self.at(1, 45), 12.0), (self.at(2), 14.0)])
        self.build(self.at(2, 30))
        rows = self.rows(meter)
        self.assertEqual(len(rows), 2)
        self.assertEqual((rows[0].price, rows[0].cost, bool(rows[0].zone_id)), (0.0, 0.0, False))
        events = self.Event.search([("text", "=like", "Немає чинного тарифу на%")])
        self.assertEqual(len(events), 1)
        self.assertEqual(events.level, "warn")
        self.assertEqual(
            events.text, "Немає чинного тарифу на %s" % dates.to_local(self.at(1, 30)).strftime("%d.%m.%Y")
        )

    def test_reset_offset_and_event(self):  # AC-20
        meter = self.mk_meter("PM-SAW-T")
        self.feed(meter.e_import_signal_id, [(self.at(1, 30), 12345.678), (self.at(1, 45), 0.512), (self.at(2), 1.0)])
        self.build(self.at(2, 30))
        self.assertAlmostEqual(meter.counter_offset, 12345.678, places=3)
        events = self.Event.search([("kind", "=", "meter"), ("code", "=", "PM-SAW-T")])
        self.assertEqual(len(events), 1)
        self.assertEqual(events.level, "warn")
        self.assertEqual(events.text, "Лічильник PM-SAW-T: скидання показника 12 345,678 → 0,512 кВт·год")
        self.assertEqual(self.rows(meter)[0].quality, "reset")
        self.build(self.at(2, 30))
        self.assertEqual(self.Event.search_count([("kind", "=", "meter"), ("code", "=", "PM-SAW-T")]), 1)

    def test_wait_missing_and_gapfill(self):  # AC-22
        meter = self.mk_meter("PM-SAW-T")
        sig = meter.e_import_signal_id
        self.feed(sig, [(self.at(10), 100.0)])
        self.build(self.at(10, 30))
        self.assertFalse(self.rows(meter))
        self.build(self.at(16, 30))
        rows = self.rows(meter)
        self.assertEqual(len(rows), 25)
        self.assertEqual(set(rows.mapped("quality")), {"missing"})
        self.assertEqual(sum(rows.mapped("kwh")), 0.0)
        self.assertEqual(rows[-1].ts_start, self.at(16))
        self.feed(sig, [(self.at(16, 45), 127.0)])
        self.build(self.at(16, 50))
        rows = self.rows(meter).filtered(lambda r: r.ts_start <= self.at(16, 30))
        self.assertEqual(set(rows.mapped("quality")), {"interpolated"})
        self.assertAlmostEqual(sum(rows.mapped("kwh")), 27.0, places=3)
        self.assertEqual(rows[0].ts_start, self.at(10))

    def test_export_and_roles(self):  # AC-23
        incomer = self.mk_meter("PM-Q-T", role="incomer", export=True)
        pv = self.mk_meter("PM-PV-T", role="generation")
        self.feed(incomer.e_import_signal_id, [(self.at(1, 30), 100.0), (self.at(1, 45), 110.0), (self.at(2), 111.0)])
        self.feed(incomer.e_export_signal_id, [(self.at(1, 30), 5.0), (self.at(1, 45), 8.0), (self.at(2), 8.5)])
        self.feed(pv.e_import_signal_id, [(self.at(1, 30), 50.0), (self.at(1, 45), 60.0), (self.at(2), 61.0)])
        self.build(self.at(2, 30))
        row = self.rows(incomer)[0]
        self.assertAlmostEqual(row.kwh_export, 3.0, places=3)
        self.assertAlmostEqual(row.cost, 84.0, places=2)
        pv_row = self.rows(pv)[0]
        self.assertEqual((pv_row.kwh, pv_row.cost), (10.0, 0.0))

    def test_read_disabled(self):  # AC-24
        meter = self.mk_meter("PM-SAW-T")
        self.feed(meter.e_import_signal_id, [(self.at(1, 30), 1.0), (self.at(1, 45), 2.0), (self.at(2), 3.0)])
        self.env["ir.config_parameter"].sudo().set_param("factory3d.energy.read_enabled", "False")
        self.build(self.at(2, 30))
        self.assertFalse(self.rows(meter))

    def test_slot_limit(self):  # AC-25
        meter = self.mk_meter("PM-SAW-T")
        start = self.at(0)
        self.feed(meter.e_import_signal_id, [(start + M15 * k, 100.0 + k) for k in range(0, 300)])
        meter.last_interval_start = start - M15
        now = start + timedelta(days=3, hours=6)
        self.build(now)
        rows = self.rows(meter)
        self.assertEqual(len(rows), 192)
        self.assertEqual(meter.last_interval_start, start + M15 * 191)
        self.assertEqual(rows[-1].ts_start, start + M15 * 191)
        self.build(now)
        self.assertGreater(len(self.rows(meter)), 192)

    def test_build_query_count(self):  # D-1: N+1 за слотами відсутній
        meter = self.mk_meter("PM-SAW-T")
        start = self.at(0)
        self.feed(meter.e_import_signal_id, [(start + M15 * k, 100.0 + k) for k in range(0, 100)])
        meter.last_interval_start = start - M15
        self.Interval.invalidate_model()
        with self.assertQueryCount(QUERY_LIMIT):
            self.Interval.with_context(f3d_now=start + timedelta(hours=30))._f3d_build_meter(
                meter, start + timedelta(hours=30)
            )
        self.assertEqual(len(self.rows(meter)), 99)

    def test_kwh_shift(self):  # AC-83
        cal = self.env["resource.calendar"].create(
            {
                "name": "Зміна 07:00",
                "attendance_ids": [
                    Command.create({"name": "d%d" % d, "dayofweek": str(d), "hour_from": 7, "hour_to": 15})
                    for d in range(7)
                ],
            }
        )
        self.env["ir.config_parameter"].sudo().set_param("factory3d.energy.shift_calendar_id", str(cal.id))
        meter = self.mk_meter("PM-SAW-T")
        total = meter.e_import_signal_id
        shift = self.mk_signal(
            "energy/consumers/SAW-T/kwh_shift", "counter", "кВт·год", derived_from_id=total.id, decimals=2
        )
        day = dates.local_day(self.at(12))
        start = dates.to_utc(datetime.combine(day, time(7, 0)))  # зміна 07:00 Київ
        now = start + timedelta(hours=3, minutes=30)  # 10:30 Київ
        self.feed(total, [(start, 1003.3), (now, 1053.8)])
        self.Interval._f3d_shift_kwh(now)
        self.assertAlmostEqual(shift.last_value, 50.5, places=2)
        # о 06:30 за Києвом — від учорашніх 07:00
        early = dates.to_utc(datetime.combine(day, time(6, 30)))
        prev = dates.to_utc(datetime.combine(day - timedelta(days=1), time(7, 0)))
        self.assertEqual(dates.shift_start(early, {d: 7 for d in range(7)}), prev)

    def test_day_profile(self):  # AC-86
        m1, m2 = self.mk_meter("PM-F1-T", role="feeder"), self.mk_meter("PM-F2-T", role="feeder")
        d0, _d1 = dates.local_day_bounds(dates.local_day(self.at(12)))
        now = d0 + timedelta(hours=10, minutes=30)
        peak_slot = d0 + timedelta(hours=9, minutes=15)
        slot = d0
        while slot < now:
            kwh = 3.0 if slot == peak_slot else 1.0
            for meter in (m1, m2):
                self.mk_interval(meter, slot, kwh)
            slot += M15
        data = self.Interval._f3d_day_profile(now)
        profile = data["profile"]
        self.assertEqual(len(profile), 24)
        self.assertTrue(all(v is not None for v in profile[:11]))
        self.assertTrue(all(v is None for v in profile[11:]))
        self.assertEqual(profile[9], 2 * (1 + 3 + 1 + 1))
        self.assertEqual(profile[10], 2 * 2)
        self.assertEqual((data["peak_kw"], data["peak_time"]), (24, "09:15"))
        self.assertEqual(data["kwh_today"], sum(profile[:11]))
        self.assertEqual(data["cost_today"], round(sum(profile[:11]) * 8.4))
        self.assertIsNone(data["typical"])

    def test_rotate(self):  # AC-84
        meter = self.mk_meter("PM-SAW-T")
        now = dates.now_utc(self.env)
        old = self.mk_interval(meter, dates.floor15(now) - timedelta(days=401), 1.0)
        fresh = self.mk_interval(meter, dates.floor15(now) - timedelta(days=1), 1.0)
        old_event = self.Event._f3d_log("info", "manual", "X", "старе", ts=now - timedelta(days=91))
        fresh_event = self.Event._f3d_log("info", "manual", "X", "свіже", ts=now - timedelta(days=5))
        self.Interval._cron_rotate()
        self.assertFalse(old.exists())
        self.assertTrue(fresh.exists())
        self.assertFalse(old_event.exists())
        self.assertTrue(fresh_event.exists())
