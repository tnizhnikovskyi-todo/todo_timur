"""19.0.1.1.5: менше записів у `td_signal` (відкладений `last_*`) і мінімальний ефективний період опитування."""

from datetime import timedelta

from freezegun import freeze_time

from odoo.tests import tagged

from ..tools.ingest import Ingester
from .common import F3DTelemetryCase

TAGS = ("post_install", "-at_install", "f3d", "f3d_telemetry")


class ChurnCase(F3DTelemetryCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_telemetry_fixtures()

    def setUp(self):
        super().setUp()
        frozen = freeze_time("2026-10-14 08:00:00")
        frozen.start()
        self.addCleanup(frozen.stop)
        # як у проді: параметри відкладеного запису й мінімального періоду — за замовчуванням коду
        icp = self.env["ir.config_parameter"].sudo()
        for key in ("last_write_min_s", "last_deadband_pct", "min_period_s", "min_period_exempt"):
            icp.search([("key", "=", "td.telemetry." + key)]).unlink()

    def set_params(self, **kw):
        icp = self.env["ir.config_parameter"].sudo()
        for key, val in kw.items():
            icp.set_param("td.telemetry." + key, str(val))

    def db_last(self, sig):
        self.env.cr.execute(
            "SELECT last_value, last_ts, last_stored_ts, last_quality, last_text FROM td_signal WHERE id = %s",
            (sig.id,),
        )
        return self.env.cr.fetchone()

    def at(self, seconds):
        return self.T0 + timedelta(seconds=seconds)


@tagged(*TAGS)
class TestDeferredLast(ChurnCase):
    def setUp(self):
        super().setUp()
        self.sig = self.sig_flx  # gauge без порогів, store_period_s = 60
        self.sig.write({"decimals": 1})

    def test_unchanged_within_window_not_written(self):
        self.push([self.rd(self.sig, 10.0, at=0)])
        self.assertEqual(self.db_last(self.sig)[:2], (10.0, self.at(0)))
        res = self.push([self.rd(self.sig, 10.0, at=5)])
        self.assertEqual(res["accepted"], 1)
        self.assertEqual(res["changed_codes"], [])
        self.assertEqual(self.db_last(self.sig)[:2], (10.0, self.at(0)))
        self.push([self.rd(self.sig, 10.04, at=10)])  # 0.04 < 0.05 (0.5 % від 10.0)
        self.assertEqual(self.db_last(self.sig)[:2], (10.0, self.at(0)))

    def test_change_beyond_deadband_written(self):
        self.push([self.rd(self.sig, 10.0, at=0)])
        res = self.push([self.rd(self.sig, 10.2, at=5)])
        self.assertEqual(self.db_last(self.sig)[:2], (10.2, self.at(5)))
        self.assertEqual(res["changed_codes"], [self.sig.code])

    def test_deadband_is_relative_to_stored_value(self):
        """Повільний дрейф накопичується відносно збереженого значення й урешті вигрібається записом."""
        self.push([self.rd(self.sig, 100.0, at=0)])
        for k, v in enumerate((100.2, 100.4, 100.45), start=1):
            self.push([self.rd(self.sig, v, at=k)])
            self.assertEqual(self.db_last(self.sig)[0], 100.0)
        self.push([self.rd(self.sig, 100.6, at=4)])
        self.assertEqual(self.db_last(self.sig)[:2], (100.6, self.at(4)))

    def test_freshness_write_after_interval(self):
        self.push([self.rd(self.sig, 10.0, at=0)])
        for t in (5, 10, 14):
            self.push([self.rd(self.sig, 10.0, at=t)])
            self.assertEqual(self.db_last(self.sig)[1], self.at(0))
        self.push([self.rd(self.sig, 10.0, at=15)])
        self.assertEqual(self.db_last(self.sig)[1], self.at(15))

    def test_freshness_limited_by_half_of_stale_window(self):
        self.set_params(last_write_min_s=600, stale_min_s=20)  # вікно stale 30 с (3·10) → не рідше за 15 с
        self.push([self.rd(self.sig, 10.0, at=0)])
        self.push([self.rd(self.sig, 10.0, at=14)])
        self.assertEqual(self.db_last(self.sig)[1], self.at(0))
        self.push([self.rd(self.sig, 10.0, at=15)])
        self.assertEqual(self.db_last(self.sig)[1], self.at(15))

    def test_text_and_quality_change_written(self):
        st = self.sig_flstate
        self.push([self.rd(st, text="idle", at=0)])
        self.push([self.rd(st, text="idle", at=5)])
        self.assertEqual(self.db_last(st)[1], self.at(0))
        res = self.push([self.rd(st, text="busy", at=6)])
        self.assertEqual(self.db_last(st)[1], self.at(6))
        self.assertEqual(self.db_last(st)[4], "busy")
        self.assertEqual(res["changed_codes"], [st.code])
        self.push([self.rd(self.sig, 10.0, at=20)])
        self.push([self.rd(self.sig, 10.0, at=21, q="uncertain")])
        self.assertEqual(self.db_last(self.sig)[1:4:2], (self.at(21), "uncertain"))

    def test_counter_any_change_written(self):
        c = self.sig_hours
        self.push([self.rd(c, 100.0, at=0)])
        self.push([self.rd(c, 100.0, at=5)])
        self.assertEqual(self.db_last(c)[1], self.at(0))
        self.push([self.rd(c, 100.001, at=6)])
        self.assertEqual(self.db_last(c)[:2], (100.001, self.at(6)))

    def test_store_policy_intact(self):
        for t in range(0, 130, 5):
            self.push([self.rd(self.sig, 10.0, at=t)])
        rows = self.env["td.reading"].search([("signal_id", "=", self.sig.id)], order="ts")
        self.assertEqual(rows.mapped("ts"), [self.at(0), self.at(60), self.at(120)])
        self.assertEqual(self.db_last(self.sig)[2], self.at(120))

    def test_breach_since_not_lost_in_deadband(self):
        sig = self.sig_press  # alarm_low 6.0, min_duration_s 30, decimals 2
        self.push([self.rd(sig, 6.02, at=0)])
        self.push([self.rd(sig, 5.99, at=5)])  # 0.03 < 0.5 % від 6.02, але поріг перетнуто
        self.env.flush_all()
        self.env.cr.execute("SELECT breach_since FROM td_signal WHERE id = %s", (sig.id,))
        self.assertEqual(self.env.cr.fetchone()[0], self.at(5))
        self.push([self.rd(sig, 5.99, at=40)])
        self.assertEqual(sig.status, "alarm")

    def test_status_change_written_immediately(self):
        sig = self.sig_press
        sig.min_duration_s = 0
        self.push([self.rd(sig, 6.5, at=0)])
        self.push([self.rd(sig, 5.0, at=2)])
        self.assertEqual(sig.status, "alarm")
        self.assertEqual(self.db_last(sig)[:2], (5.0, self.at(2)))

    def test_param_zero_disables(self):
        self.set_params(last_write_min_s=0)
        self.push([self.rd(self.sig, 10.0, at=0)])
        self.push([self.rd(self.sig, 10.0, at=1)])
        self.assertEqual(self.db_last(self.sig)[1], self.at(1))

    def test_module_source_not_deferred(self):
        self.push([self.rd(self.sig, 10.0, at=0)], src="module")
        self.push([self.rd(self.sig, 10.0, at=1)], src="module")
        self.assertEqual(self.db_last(self.sig)[1], self.at(1))

    def test_safety_and_event_signals_not_deferred(self):
        fire = self.sig_fire  # fire/… — безпековий префікс
        self.push([self.rd(fire, text="normal", at=0)])
        self.push([self.rd(fire, text="normal", at=1)])
        self.assertEqual(self.db_last(fire)[1], self.at(1))
        plate = self.sig_plate
        self.push([self.rd(plate, text="AA1234BB", at=2)])
        self.push([self.rd(plate, text="AA1234BB", at=3)])
        self.assertEqual(self.db_last(plate)[1], self.at(3))

    def test_ingester_counts_skipped(self):
        self.push([self.rd(self.sig, 10.0, at=0)])
        ing = Ingester(self.env, src="collector", collector=self.col)
        ing.run([self.rd(self.sig, 10.0, at=5)])
        self.assertEqual(ing.skipped_last, 1)


@tagged(*TAGS)
class TestStaleWithDeferredLast(ChurnCase):
    def setUp(self):
        super().setUp()
        self.sig = self.sig_flx  # period_s 10 → stale через 60 с
        self.sig.write({"decimals": 1})

    def _tick(self, t):
        with freeze_time(self.at(t)):
            self.push([self.rd(self.sig, 10.0, at=t)])
            self.env["td.signal"]._cron_stale()

    def test_steady_signal_never_stale(self):
        for t in range(0, 600, 5):
            self._tick(t)
            self.assertEqual(self.sig.status, "ok", "t=%s" % t)

    def test_dead_signal_becomes_stale(self):
        for t in range(0, 120, 5):
            self._tick(t)
        with freeze_time(self.at(115 + 20)):
            self.env["td.signal"]._cron_stale()
        self.assertEqual(self.sig.status, "ok")
        with freeze_time(self.at(115 + 61)):
            self.env["td.signal"]._cron_stale()
        self.assertEqual(self.sig.status, "stale")

    def test_lag_of_last_ts_within_half_window(self):
        worst = timedelta(0)
        for t in range(0, 300, 5):
            self._tick(t)
            worst = max(worst, self.at(t) - self.db_last(self.sig)[1])
        self.assertLess(worst, timedelta(seconds=30))


@tagged(*TAGS)
class TestMinPeriod(ChurnCase):
    def setUp(self):
        super().setUp()
        n = [0]

        def mk(code, period, kind="gauge", **kw):
            n[0] += 1
            return self.env["td.signal"].create(
                {
                    "code": code,
                    "name": code,
                    "kind": kind,
                    "source_id": self.src_mb.id,
                    "address": {"fc": 3, "addr": 4100 + n[0], "type": "u16"},
                    "origin": "manual",
                    "period_s": period,
                    **kw,
                }
            )

        self.fast1 = mk("equipment/CHURN-T/fast1", 1)
        self.fast2 = mk("equipment/CHURN-T/fast2", 2)
        self.mid = mk("equipment/CHURN-T/mid", 7)
        self.slow = mk("equipment/CHURN-T/slow", 30)
        self.fire = mk("fire/groups/FA-CH/state", 2, kind="state", states_text="normal, alarm")
        self.gas = mk("plant/gas/CH4/ppm", 2)
        self.safe = mk("plant/safe/estop_loop", 1)
        self.gate = mk("yard/gates/GATE-W/photocell", 1)
        self.scale = mk("yard/scale/TRUCK-SCALE/weight_kg", 1)
        self.alarm_state = mk("workcenters/CH-1/alarm", 1, kind="state", states_text="off, on", alarm_states_text="on")
        self.ctl = mk("plant/ctl/mode", 2)

    def periods(self):
        body = self.col._config_payload()
        mb = next(s for s in body["sources"] if s["code"] == "MB-T-U70")
        return {s["code"]: s["period_s"] for s in mb["signals"]}

    def test_default_min_period_applied_with_exceptions(self):
        got = self.periods()
        for sig in (self.fast1, self.fast2, self.ctl):
            self.assertEqual(got[sig.code], 5, sig.code)
        self.assertEqual(got[self.mid.code], 7)
        self.assertEqual(got[self.slow.code], 30)
        self.assertEqual(got[self.sig_press.code], 10)
        for sig, period in (
            (self.fire, 2),
            (self.gas, 2),
            (self.safe, 1),
            (self.gate, 1),
            (self.scale, 1),
            (self.alarm_state, 1),
        ):
            self.assertEqual(got[sig.code], period, sig.code)

    def test_db_period_unchanged(self):
        self.periods()
        self.assertEqual((self.fast1.period_s, self.fast2.period_s, self.fire.period_s), (1, 2, 2))

    def test_param_changes_threshold_and_etag(self):
        etag = self.col._config_payload()["etag"]
        self.set_params(min_period_s=15)
        body = self.col._config_payload()
        self.assertNotEqual(body["etag"], etag)
        mb = next(s for s in body["sources"] if s["code"] == "MB-T-U70")
        got = {s["code"]: s["period_s"] for s in mb["signals"]}
        self.assertEqual(got[self.fast1.code], 15)
        self.assertEqual(got[self.mid.code], 15)
        self.assertEqual(got[self.sig_press.code], 15)
        self.assertEqual(got[self.slow.code], 30)
        self.assertEqual(got[self.fire.code], 2)

    def test_zero_disables(self):
        self.set_params(min_period_s=0)
        got = self.periods()
        self.assertEqual((got[self.fast1.code], got[self.fast2.code], got[self.fire.code]), (1, 2, 2))

    def test_exempt_list_configurable(self):
        self.set_params(min_period_exempt="ctl, , CH4")
        got = self.periods()
        self.assertEqual(got[self.ctl.code], 2)
        self.assertEqual(got[self.gas.code], 2)
        self.assertEqual(got[self.fire.code], 5)  # fire більше не виняток
        self.assertEqual(got[self.alarm_state.code], 1)  # alarm_states — виняток завжди
        self.assertEqual(got[self.fast1.code], 5)

    def test_stale_window_uses_effective_period(self):
        self.set_params(stale_min_s=5, stale_periods=3)
        self.assertEqual(self.fast1._td_stale_after(), 15)
        self.assertEqual(self.fire._td_stale_after(), 6)
        self.set_params(min_period_s=0)
        self.assertEqual(self.fast1._td_stale_after(), 5)
