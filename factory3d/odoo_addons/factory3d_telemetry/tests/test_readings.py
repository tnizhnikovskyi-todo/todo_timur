from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun import freeze_time
from psycopg2 import IntegrityError

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import F3DTelemetryCase

TAGS = ("post_install", "-at_install", "f3d", "f3d_telemetry")
FREEZE = "2026-10-14 08:00:00"


class ReadingCase(F3DTelemetryCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_telemetry_fixtures()

    def setUp(self):
        super().setUp()
        frozen = freeze_time(FREEZE)
        frozen.start()
        self.addCleanup(frozen.stop)

    def rows(self, sig):
        return self.env["f3d.reading"].search([("signal_id", "=", sig.id)], order="ts")

    def at(self, seconds):
        return self.T0 + timedelta(seconds=seconds)

    def messages(self, sig):
        return self.env["mail.message"].search_count([("model", "=", "f3d.signal"), ("res_id", "=", sig.id)])

    def raw(self, code, ts, value=None, text=None, q=None):
        res = {"code": code, "ts": ts, "value": value, "text": text, "q": q}
        return {k: v for k, v in res.items() if v is not None}


@tagged(*TAGS)
class TestStorePolicy(ReadingCase):
    def setUp(self):
        super().setUp()
        self.sig_press.min_duration_s = 0

    def _first_hour(self):
        return self.push([self.rd(self.sig_press, 6.80, at=10 * k) for k in range(360)])

    def test_store_every_300s(self):
        res = self._first_hour()
        sig = self.sig_press
        self.assertEqual(res["accepted"], 360)
        self.assertEqual(sig.last_value, 6.80)
        self.assertEqual(sig.last_ts, self.at(3590))
        self.assertEqual(self.rows(sig).mapped("ts"), [self.at(300 * k) for k in range(12)])
        self.assertEqual(sig.last_stored_ts, self.at(3300))

    def test_status_change_stored(self):
        self._first_hour()
        self.push([self.rd(self.sig_press, 5.9, at=3600)])
        self.assertIn(self.at(3600), self.rows(self.sig_press).mapped("ts"))
        self.assertEqual(self.sig_press.status, "alarm")
        self.push([self.rd(self.sig_press, 5.85, at=3610)])
        self.assertNotIn(self.at(3610), self.rows(self.sig_press).mapped("ts"))
        self.assertEqual(self.sig_press.last_value, 5.85)

    def test_bad_quality(self):
        self._first_hour()
        self.push([self.rd(self.sig_press, 5.85, at=3610)])
        self.push([self.rd(self.sig_press, 7.5, at=3620, q="bad")])
        sig = self.sig_press
        self.assertEqual(sig.last_value, 5.85)
        bad = self.rows(sig).filtered(lambda r: r.quality == "bad")
        self.assertEqual(bad.mapped("ts"), [self.at(3620)])
        self.push([self.rd(sig, 7.5, at=3630, q="bad")])
        self.assertEqual(self.rows(sig).filtered(lambda r: r.quality == "bad").mapped("ts"), [self.at(3620)])

    def test_store_period_zero(self):
        self.sig_press.store_period_s = 0
        self.push([self.rd(self.sig_press, 6.5, at=k) for k in range(10)])
        self.assertEqual(len(self.rows(self.sig_press)), 10)


@tagged(*TAGS)
class TestIdempotency(ReadingCase):
    def _batch(self):
        return [
            self.rd(self.sig_press, 6.772),
            self.rd(self.sig_bat, 23.6),
            self.rd(self.sig_flstate, text="busy"),
            self.rd(self.sig_water, 18642.37),
        ]

    def test_repeat_batch(self):
        sigs = self.sig_press | self.sig_bat | self.sig_flstate | self.sig_water
        res = self.push(self._batch())
        self.assertEqual((res["accepted"], res["stored"], res["duplicates"], res["rejected"]), (4, 4, 0, []))
        self.assertEqual(set(res["changed_codes"]), set(sigs.mapped("code")))
        msgs = [self.messages(s) for s in sigs]
        res = self.push(self._batch())
        self.assertEqual((res["accepted"], res["stored"], res["duplicates"]), (4, 0, 4))
        self.assertEqual(res["changed_codes"], [])
        self.assertEqual(self.env["f3d.reading"].search_count([("signal_id", "in", sigs.ids)]), 4)
        self.assertEqual([self.messages(s) for s in sigs], msgs)
        self.assertEqual(self.sig_press.last_value, 6.772)

    def test_older_reading_stored_not_last(self):
        self.push(self._batch())
        self.push([self.rd(self.sig_press, 6.5, at=-600)])
        self.assertIn(self.at(-600), self.rows(self.sig_press).mapped("ts"))
        self.assertEqual(self.sig_press.last_value, 6.772)
        self.assertEqual(self.sig_press.last_ts, self.T0)


@tagged(*TAGS)
class TestRace(ReadingCase):
    def test_older_does_not_override(self):
        self.set_sql(self.sig_press, last_ts=self.at(100), last_value=6.9, status="ok")
        self.push([self.rd(self.sig_press, 5.0, at=50)])
        sig = self.sig_press
        self.assertEqual((sig.last_value, sig.last_ts, sig.status), (6.9, self.at(100), "ok"))
        self.assertEqual(self.env["maintenance.request"].search_count([("equipment_id", "=", self.eq_comp.id)]), 0)
        self.assertIn(self.at(50), self.rows(sig).mapped("ts"))


@tagged(*TAGS)
class TestReadingModel(ReadingCase):
    def _reading(self):
        return self.env["f3d.reading"].create({"signal_id": self.sig_press.id, "ts": self.T0, "value": 1.0})

    def test_no_edit(self):
        with self.assertRaises(UserError) as ctx:
            self._reading().with_user(self.user_manager).write({"value": 2.0})
        self.assertEqual(ctx.exception.args[0], "Показання не редагуються.")

    def test_admin_quality(self):
        rec = self._reading()
        rec.with_user(self.user_admin).write({"quality": "bad"})
        self.assertEqual(rec.quality, "bad")

    def test_unique(self):
        self._reading()
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.cr.savepoint():
            self._reading()


@tagged(*TAGS)
class TestHourly(ReadingCase):
    def _create(self, sig, ts, value, quality="good"):
        return self.env["f3d.reading"].create({"signal_id": sig.id, "ts": ts, "value": value, "quality": quality})

    def _fill(self):
        d = datetime(2026, 10, 14, 10)
        values = [280, 282, 284, 286, 288, 290, 290, 288, 286, 284, 282, 280]
        for k, v in enumerate(values):
            self._create(self.sig_rv, d + timedelta(minutes=5 * k), v)
        self._create(self.sig_rv, d + timedelta(minutes=57), 999, quality="bad")
        self._create(self.sig_hours, d + timedelta(minutes=5), 17846.6)
        self._create(self.sig_hours, d + timedelta(minutes=55), 17847.6)

    def _hours(self, sig):
        return self.env["f3d.reading.hour"].search([("signal_id", "=", sig.id)], order="hour")

    def test_aggregate_values(self):
        self._fill()
        with freeze_time("2026-10-14 11:20"):
            self.env["f3d.reading.hour"]._cron_aggregate()
        rv = self._hours(self.sig_rv)
        self.assertEqual(len(rv), 1)
        self.assertEqual(rv.hour, datetime(2026, 10, 14, 10))
        self.assertEqual((rv.v_min, rv.v_max, rv.v_count, rv.v_first, rv.v_last, rv.delta), (280, 290, 12, 280, 280, 0))
        self.assertAlmostEqual(rv.v_avg, 285, places=6)
        h = self._hours(self.sig_hours)
        self.assertAlmostEqual(h.v_first, 17846.6, places=6)
        self.assertAlmostEqual(h.v_last, 17847.6, places=6)
        self.assertAlmostEqual(h.delta, 1.0, places=6)

    def test_rerun_upsert(self):
        self._fill()
        with freeze_time("2026-10-14 11:20"):
            self.env["f3d.reading.hour"]._cron_aggregate()
            self.env["f3d.reading.hour"]._cron_aggregate()
        self.assertEqual(len(self._hours(self.sig_rv)), 1)
        self.assertEqual(self._hours(self.sig_rv).v_count, 12)

    def test_late_reading(self):
        self._fill()
        with freeze_time("2026-10-14 11:20"):
            self.env["f3d.reading.hour"]._cron_aggregate()
        self._create(self.sig_rv, datetime(2026, 10, 14, 10, 58), 295)
        with freeze_time("2026-10-14 11:30"):
            self.env["f3d.reading.hour"]._cron_aggregate()
        rv = self._hours(self.sig_rv)
        self.assertEqual((len(rv), rv.v_max, rv.v_count), (1, 295, 13))

    def test_open_hour_skipped(self):
        self._fill()
        self._create(self.sig_rv, datetime(2026, 10, 14, 11, 5), 281)
        with freeze_time("2026-10-14 11:20"):
            self.env["f3d.reading.hour"]._cron_aggregate()
        self.assertEqual(self._hours(self.sig_rv).mapped("hour"), [datetime(2026, 10, 14, 10)])

    def test_counter_delta_from_prev_hour(self):
        self._fill()
        with freeze_time("2026-10-14 11:20"):
            self.env["f3d.reading.hour"]._cron_aggregate()
        self.assertAlmostEqual(self._hours(self.sig_hours).delta, 1.0, places=6)

    def test_counter_delta_gap(self):
        self._fill()
        with freeze_time("2026-10-14 11:20"):
            self.env["f3d.reading.hour"]._cron_aggregate()
        self._create(self.sig_hours, datetime(2026, 10, 14, 11, 5), 17847.9)
        self._create(self.sig_hours, datetime(2026, 10, 14, 11, 50), 17848.4)
        self._create(self.sig_hours, datetime(2026, 10, 14, 13, 30), 17849.0)
        with freeze_time("2026-10-14 14:20"):
            self.env["f3d.reading.hour"]._cron_aggregate()
        rows = {r.hour.hour: r for r in self._hours(self.sig_hours)}
        self.assertEqual(sorted(rows), [10, 11, 13])
        self.assertAlmostEqual(rows[11].v_first, 17847.9, places=6)
        self.assertAlmostEqual(rows[11].v_last, 17848.4, places=6)
        self.assertAlmostEqual(rows[11].delta, 0.8, places=6)
        self.assertAlmostEqual(rows[13].delta, 0.6, places=6)
        self.assertAlmostEqual(sum(r.delta for r in rows.values()), 2.4, places=6)

    def test_counter_delta_daily_reset(self):
        sig = self.env["f3d.signal"].create(
            {
                "code": "equipment/GANTRY-T/cycles_today",
                "name": "Цикли",
                "kind": "counter",
                "source_id": self.src_mb.id,
                "address": {"fc": 3, "addr": 2},
                "sim_params": {"reset": "daily"},
            }
        )
        self._create(sig, datetime(2026, 10, 13, 23, 50), 370)
        self._create(sig, datetime(2026, 10, 14, 0, 10), 2)
        self._create(sig, datetime(2026, 10, 14, 0, 40), 5)
        with freeze_time("2026-10-14 11:20"):
            self.env["f3d.reading.hour"]._cron_aggregate()
        rows = {r.hour: r for r in self._hours(sig)}
        self.assertEqual(rows[datetime(2026, 10, 13, 23)].delta, 0)
        self.assertEqual(rows[datetime(2026, 10, 14, 0)].delta, 3)


@tagged(*TAGS)
class TestRotate(ReadingCase):
    def _fill(self, now):
        Reading, Hour = self.env["f3d.reading"], self.env["f3d.reading.hour"]
        old = Reading.create({"signal_id": self.sig_press.id, "ts": datetime(2026, 10, 14, 1)})
        young = Reading.create({"signal_id": self.sig_press.id, "ts": datetime(2026, 10, 16, 1)})
        h_old = Hour.create({"signal_id": self.sig_press.id, "hour": now - timedelta(days=401)})
        h_young = Hour.create({"signal_id": self.sig_press.id, "hour": now - timedelta(days=399)})
        return old, young, h_old, h_young

    def test_rotate_keep_days(self):
        with freeze_time("2026-11-14 02:40"):
            old, young, h_old, h_young = self._fill(datetime(2026, 11, 14, 2))
            self.env["f3d.reading"]._cron_rotate()
            self.assertFalse(old.exists() or h_old.exists())
            self.assertTrue(young.exists() and h_young.exists())

    def test_rotate_batches(self):
        from odoo.addons.factory3d_telemetry.models import f3d_reading

        with freeze_time("2026-11-14 02:40"):
            olds = self.env["f3d.reading"]
            for k in range(5):
                olds |= self.env["f3d.reading"].create(
                    {"signal_id": self.sig_press.id, "ts": datetime(2026, 10, 1, 1, k)}
                )
            with patch.object(f3d_reading, "ROTATE_BATCH", 2):
                self.env["f3d.reading"]._cron_rotate()
            self.assertFalse(olds.exists())


@tagged(*TAGS)
class TestCounters(ReadingCase):
    def test_decrease_uncertain(self):
        self.set_sql(self.sig_hours, last_value=17846.6, last_ts=self.at(-60))
        self.push([self.rd(self.sig_hours, 17846.8)])
        self.assertEqual(self.sig_hours.last_quality, "good")
        self.push([self.rd(self.sig_hours, 17000.0, at=60)])
        sig = self.sig_hours
        self.assertEqual((sig.last_value, sig.last_quality), (17000.0, "uncertain"))
        decreased = self.env["mail.message"].search(
            [("model", "=", "f3d.signal"), ("res_id", "=", sig.id), ("body", "ilike", "Лічильник зменшився")]
        )
        self.assertEqual(len(decreased), 1)
        self.push([self.rd(sig, 16000.0, at=120)])
        decreased = self.env["mail.message"].search(
            [("model", "=", "f3d.signal"), ("res_id", "=", sig.id), ("body", "ilike", "Лічильник зменшився")]
        )
        self.assertEqual(len(decreased), 1)

    def test_daily_reset_good(self):
        sig = self.env["f3d.signal"].create(
            {
                "code": "equipment/GANTRY-T/cycles_today",
                "name": "Цикли",
                "kind": "counter",
                "source_id": self.src_mb.id,
                "address": {"fc": 3, "addr": 2},
                "sim_params": {"reset": "daily"},
            }
        )
        self.set_sql(sig, last_value=373, last_ts=self.at(-60))
        self.push([self.rd(sig, 2)])
        self.assertEqual((sig.last_value, sig.last_quality), (2, "good"))

    def test_rate_h_derived(self):
        self.push([self.rd(self.sig_water, 18642.00)])
        self.assertEqual(self.env["f3d.reading"].search_count([("signal_id", "=", self.sig_flow.id)]), 0)
        self.push([self.rd(self.sig_water, 18642.35, at=600)])
        flow = self.rows(self.sig_flow)
        self.assertEqual(len(flow), 1)
        self.assertEqual(flow.ts, self.at(600))
        self.assertAlmostEqual(flow.value, 2.1, places=6)
        self.assertEqual(flow.src, "collector")
        self.assertAlmostEqual(self.sig_flow.last_value, 2.1, places=6)

    def test_first_no_derived(self):
        self.push([self.rd(self.sig_water, 18642.00)])
        self.assertFalse(self.rows(self.sig_flow))


@tagged(*TAGS)
class TestTimezones(ReadingCase):
    def setUp(self):
        super().setUp()
        self.frozen_inner = freeze_time("2026-10-14 06:10:10")
        self.frozen_inner.start()
        self.addCleanup(self.frozen_inner.stop)

    def test_ts_variants(self):
        code = self.sig_rv.code
        stamps = [
            "2026-10-14T06:10:03.250+03:00",
            "2026-10-14T06:10:03",
            "2026-10-14T06:11:30Z",
            "2026-10-14T06:11:00Z",
            "2026-09-13T06:00:00Z",
            "2026-13-01T00:00:00Z",
        ]
        res = self.push([{"code": code, "ts": ts, "value": 100.0} for ts in stamps])
        self.assertEqual(
            [(r["i"], r["reason"]) for r in res["rejected"]],
            [(1, "ts_no_tz"), (2, "ts_future"), (4, "ts_too_old"), (5, "ts_invalid")],
        )
        self.assertEqual(res["accepted"], 2)
        self.cr.execute("SELECT ts FROM f3d_reading WHERE signal_id = %s ORDER BY ts", [self.sig_rv.id])
        self.assertEqual(
            [r[0] for r in self.cr.fetchall()],
            [datetime(2026, 10, 14, 3, 10, 3, 250000), datetime(2026, 10, 14, 6, 11)],
        )

    def test_request_time_kyiv(self):
        self.push([{"code": self.sig_rv.code, "ts": "2026-10-14T06:10:00Z", "value": 285.0}])
        req = self.sig_rv.maintenance_request_id
        self.assertTrue(req)
        self.assertIn("14.10.2026 09:10", req.description)


@tagged(*TAGS)
class TestModuleIngest(ReadingCase):
    def test_ct10_no_rate_limit_and_rules(self):
        Sig = self.env["f3d.signal"]
        for i in range(100):
            res = Sig._f3d_ingest([self.rd(self.sig_free, float(i), at=i)], src="module")
            self.assertEqual(res["accepted"], 1)
            self.assertEqual(res["rejected"], [])
        self.assertEqual(set(self.rows(self.sig_free).mapped("src")), {"module"})
        res = Sig._f3d_ingest([{"code": "equipment/NOPE/x", "ts": self.T0, "value": 1}], src="module")
        self.assertEqual(res["rejected"][0]["reason"], "unknown_code")
        self.sig_press.min_duration_s = 0
        res = Sig._f3d_ingest([self.rd(self.sig_press, 5.9)], src="module")
        self.assertEqual(res["alarms_opened"], 1)
        self.assertTrue(self.sig_press.maintenance_request_id)
