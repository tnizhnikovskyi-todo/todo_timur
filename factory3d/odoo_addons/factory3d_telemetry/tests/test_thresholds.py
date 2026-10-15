from datetime import datetime, timedelta

from freezegun import freeze_time

from odoo import fields
from odoo.tests import tagged
from odoo.tests.common import BaseCase

from ..tools.thresholds import cov_check_s, eval_status
from .common import F3DTelemetryCase

TAGS = ("post_install", "-at_install", "f3d", "f3d_telemetry")
NOW = "2026-10-14 08:00:00"
T = datetime(2026, 10, 14, 10, 0, 0)


def cfg(**kw):
    base = {"kind": "gauge", "hysteresis": 0.0, "min_duration_s": 0, "alarm_states": []}
    return {**base, **kw}


@tagged(*TAGS)
class TestEvalStatusPure(BaseCase):
    def run_seq(self, config, values, start="unknown"):
        state, out = {"status": start, "breach_since": None}, []
        for i, (v, text) in enumerate(values):
            status, since = eval_status(state, v, text, T + timedelta(seconds=i), config)
            state = {"status": status, "breach_since": since}
            out.append(status)
        return out

    def test_high_hysteresis(self):
        c = cfg(alarm_high_on=True, alarm_high=250, hysteresis=10)
        self.assertEqual(
            self.run_seq(c, [(v, None) for v in (250, 285, 248, 240.5, 239)]), ["ok", "alarm", "alarm", "alarm", "ok"]
        )

    def test_low_warn_alarm(self):
        c = cfg(warn_low_on=True, warn_low=25, alarm_low_on=True, alarm_low=15)
        self.assertEqual(
            self.run_seq(c, [(v, None) for v in (26, 23.6, 14.2, 16, 26)]), ["ok", "warn", "alarm", "warn", "ok"]
        )

    def test_min_duration(self):
        c = cfg(alarm_low_on=True, alarm_low=6.0, hysteresis=0.1, min_duration_s=30)
        status, since = eval_status({"status": "ok", "breach_since": None}, 5.9, None, T, c)
        self.assertEqual((status, since), ("ok", T))
        status, since = eval_status({"status": status, "breach_since": since}, 5.95, None, T + timedelta(seconds=30), c)
        self.assertEqual(status, "alarm")
        status, since = eval_status({"status": status, "breach_since": since}, 6.05, None, T + timedelta(seconds=40), c)
        self.assertEqual(status, "alarm")
        status, since = eval_status({"status": status, "breach_since": since}, 6.11, None, T + timedelta(seconds=50), c)
        self.assertEqual((status, since), ("ok", None))

    def test_state(self):
        c = cfg(kind="state", alarm_states=["fault"])
        self.assertEqual(self.run_seq(c, [(None, "fault"), (None, "loaded")]), ["alarm", "ok"])

    def test_event(self):
        self.assertEqual(self.run_seq(cfg(kind="event"), [(1, "x")]), ["ok"])

    def test_bad_quality(self):
        c = cfg(alarm_high_on=True, alarm_high=10)
        self.assertEqual(
            eval_status({"status": "ok", "breach_since": None}, 99, None, T, c, quality="bad"), ("ok", None)
        )

    def test_cov_check(self):
        self.assertEqual((cov_check_s(10), cov_check_s(60), cov_check_s(30)), (300, 600, 300))


class ThresholdCase(F3DTelemetryCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_telemetry_fixtures()

    def at(self, seconds):
        return self.T0 + timedelta(seconds=seconds)

    def setUp(self):
        super().setUp()
        frozen = freeze_time(NOW)
        frozen.start()
        self.addCleanup(frozen.stop)

    def statuses(self, sig, values, step=600):
        out = []
        for i, v in enumerate(values):
            self.push([self.rd(sig, v, at=i * step)])
            out.append(sig.status)
        return out


@tagged(*TAGS)
class TestHighHysteresis(ThresholdCase):
    def test_statuses(self):
        self.assertEqual(
            self.statuses(self.sig_rv, [250, 285, 248, 240.5, 239]), ["ok", "alarm", "alarm", "alarm", "ok"]
        )


@tagged(*TAGS)
class TestLowWarnAlarm(ThresholdCase):
    def test_statuses(self):
        self.assertEqual(self.statuses(self.sig_bat, [26, 23.6, 14.2, 16, 26]), ["ok", "warn", "alarm", "warn", "ok"])


@tagged(*TAGS)
class TestMinDuration(ThresholdCase):
    def test_statuses(self):
        sig = self.sig_press
        base = 4 * 3600
        with freeze_time("2026-10-14 10:02"):
            self.push([self.rd(sig, 5.9, at=base)])
            self.assertEqual(sig.status, "ok")
            self.assertEqual(sig.breach_since, self.at(base))
            self.assertFalse(sig.maintenance_request_id)
            self.push([self.rd(sig, 5.95, at=base + 30)])
            self.assertEqual(sig.status, "alarm")
            self.assertTrue(sig.maintenance_request_id)
            self.push([self.rd(sig, 6.05, at=base + 40)])
            self.assertEqual(sig.status, "alarm")
            self.push([self.rd(sig, 6.11, at=base + 50)])
            self.assertEqual(sig.status, "ok")
            self.assertFalse(sig.breach_since)
            for dt, v in ((60, 5.9), (70, 6.2), (80, 5.9), (105, 5.9)):
                self.push([self.rd(sig, v, at=base + dt)])
                self.assertEqual(sig.status, "ok", dt)
            self.assertEqual(sig.breach_since, self.at(base + 80))


@tagged(*TAGS)
class TestStateEvent(ThresholdCase):
    def test_state_alarm_and_ok(self):
        self.push([self.rd(self.sig_cstate, text="fault")])
        self.assertEqual(self.sig_cstate.status, "alarm")
        req = self.sig_cstate.maintenance_request_id
        self.assertEqual(req.name, "Компресор: стан «fault»")
        self.push([self.rd(self.sig_cstate, text="loaded", at=60)])
        self.assertEqual(self.sig_cstate.status, "ok")

    def test_event_always_ok(self):
        self.push([self.rd(self.sig_plate, text="AA4512KT")])
        self.assertEqual(self.sig_plate.status, "ok")
        self.assertEqual(self.sig_plate.last_text, "AA4512KT")

    def test_bad_quality_keeps_status(self):
        self.push([self.rd(self.sig_press, 6.8)])
        self.assertEqual(self.sig_press.status, "ok")
        self.push([self.rd(self.sig_press, 2.0, at=10, q="bad")])
        self.assertEqual(self.sig_press.status, "ok")
        self.assertEqual(self.sig_press.last_value, 6.8)

    def test_unknown_state(self):
        res = self.push([self.rd(self.sig_cstate, text="boost")])
        self.assertEqual(res["accepted"], 1)
        self.assertEqual(res["rejected"], [{"i": 0, "code": self.sig_cstate.code, "reason": "unknown_state"}])
        self.assertEqual(self.sig_cstate.last_quality, "bad")
        row = self.env["f3d.reading"].search([("signal_id", "=", self.sig_cstate.id)])
        self.assertEqual((row.value, row.quality, row.text), (-1.0, "bad", "boost"))


@tagged(*TAGS)
class TestStale(ThresholdCase):
    def _prepare(self):
        now = fields.Datetime.now()
        for sig, age in ((self.sig_press, 61), (self.sig_bat, 59), (self.sig_water, 179), (self.sig_rv, 61)):
            self.set_sql(sig, status="ok", last_ts=now - timedelta(seconds=age))
        req = self.env["maintenance.request"].create({"name": "Заявка", "equipment_id": self.eq_rv.id})
        self.set_sql(self.sig_rv, status="alarm", maintenance_request_id=req.id)
        self.set_sql(self.sig_free, status="ok", last_ts=now - timedelta(days=1))
        return req

    def test_cron_stale_windows(self):
        req = self._prepare()
        requests = self.env["maintenance.request"].search_count([])
        self.env["f3d.signal"]._cron_stale()
        for sig in (self.sig_press, self.sig_rv):
            self.assertEqual(sig.status, "stale")
        for sig in (self.sig_bat, self.sig_water, self.sig_free):
            self.assertEqual(sig.status, "ok")
        self.assertIn("Немає даних: timeout", self.sig_press.message_ids[0].body)
        self.assertEqual(self.sig_rv.maintenance_request_id, req)
        self.assertEqual(self.env["maintenance.request"].search_count([]), requests)

    def test_no_source_never_stale(self):
        self.set_sql(self.sig_free, status="ok", last_ts=fields.Datetime.now() - timedelta(days=3))
        self.env["f3d.signal"]._cron_stale()
        self.assertEqual(self.sig_free.status, "ok")

    def test_request_kept(self):
        req = self._prepare()
        self.env["f3d.signal"]._cron_stale()
        self.assertEqual(self.sig_rv.maintenance_request_id, req)

    def test_recover(self):
        self._prepare()
        self.env["f3d.signal"]._cron_stale()
        self.push([self.rd(self.sig_press, 6.8, at=7200)])
        self.assertEqual(self.sig_press.status, "ok")

    def test_params(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("factory3d.telemetry.stale_min_s", "30")
        icp.set_param("factory3d.telemetry.stale_periods", "5")
        now = fields.Datetime.now()
        self.set_sql(self.sig_press, status="ok", last_ts=now - timedelta(seconds=51))
        self.set_sql(self.sig_rv, status="ok", last_ts=now - timedelta(seconds=49))
        self.env["f3d.signal"]._cron_stale()
        self.assertEqual(self.sig_press.status, "stale")
        self.assertEqual(self.sig_rv.status, "ok")
        self.assertEqual(self.sig_press._f3d_stale_after(), 50)


@tagged(*TAGS)
class TestStaleCov(ThresholdCase):
    def _mk(self, code, source, address, period=30):
        return self.env["f3d.signal"].create(
            {
                "code": code,
                "name": code,
                "kind": "gauge",
                "source_id": source.id,
                "address": address,
                "period_s": period,
            }
        )

    def _signals(self):
        return (
            self._mk("ventilation/units/COV-T/a", self.src_bac, {"object": "analog-input", "instance": 1}),
            self._mk("ventilation/units/COV-T/b", self.src_bac, {"object": "AI", "instance": 2, "mode": "cov"}),
            self._mk("ventilation/units/COV-T/c", self.src_bac, {"object": "AI", "instance": 3, "mode": "poll"}),
            self._mk("fire/groups/COV-T/d", self.src_bac_ro, {"object": "AI", "instance": 5}),
        )

    def test_stale_after_cov_poll_ro(self):
        sigs = self._signals()
        self.assertEqual([s._f3d_stale_after() for s in sigs], [900, 900, 90, 90])
        self.assertEqual(self.sig_rv._f3d_stale_after(), 60)

    def test_cron_cov_not_stale_301s(self):
        sigs = self._signals()
        now = fields.Datetime.now()
        for s in sigs:
            self.set_sql(s, status="ok", last_ts=now - timedelta(seconds=301))
        self.env["f3d.signal"]._cron_stale()
        self.assertEqual([s.status for s in sigs], ["ok", "ok", "stale", "stale"])

    def test_cron_cov_stale_901s(self):
        sigs = self._signals()
        self.set_sql(sigs[0], status="ok", last_ts=fields.Datetime.now() - timedelta(seconds=901))
        self.env["f3d.signal"]._cron_stale()
        self.assertEqual(sigs[0].status, "stale")

    def test_cov_check_s(self):
        self.assertEqual((cov_check_s(10), cov_check_s(60)), (300, 600))
