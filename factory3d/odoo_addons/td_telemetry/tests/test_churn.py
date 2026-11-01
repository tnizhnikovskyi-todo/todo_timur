"""19.0.1.1.5/19.0.1.1.6: менше записів у `td_signal` (відкладений `last_*`), мінімальний ефективний період
опитування, вік `last_ts` у вікнах свіжості споживачів і монотонність `last_*`."""

from datetime import timedelta

from freezegun import freeze_time

from odoo.tests import tagged

from ..tools import periods
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
        frozen = freeze_time(self.T0)
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

    def push(self, readings, collector=None, src="collector", arrive=None):
        """Пакет надходить одразу після останнього показання (`arrive` — час прийому в секундах від T0 інакше)."""
        when = self.at(arrive) if arrive is not None else max(r["ts"] for r in readings) + timedelta(seconds=1)
        with freeze_time(when):
            return super().push(readings, collector=collector, src=src)

    def mk_signal(self, code, period, kind="gauge", **kw):
        ChurnCase._n = getattr(ChurnCase, "_n", 0) + 1
        return self.env["td.signal"].create(
            {
                "code": code,
                "name": code,
                "kind": kind,
                "source_id": self.src_mb.id,
                "address": {"fc": 3, "addr": 4200 + ChurnCase._n, "type": "u16"},
                "origin": "manual",
                "period_s": period,
                "store_period_s": 0,
                **kw,
            }
        )

    def run_collector(self, sig, push_s, total_s=600, value=lambda t: 10.0, text=None, offset=0, cron=False):
        """Колектор опитує сигнал із його ефективним періодом і відправляє пакет кожні `push_s` с.

        Повертає (найбільший вік збереженого `last_ts` у момент перед прийомом пакета, кількість записів `last_ts`).
        Саме тоді споживач бачить найстаріший `last_ts`. `cron=True` — ще й `_cron_stale` у ці моменти.
        """
        self.col.push_interval_s = push_s
        period = sig._td_effective_period_s()
        worst, writes, prev_ts, next_t = timedelta(0), 0, None, offset
        for arrive in range(push_s, total_s + 1, push_s):
            with freeze_time(self.at(arrive)):
                row = self.db_last(sig)
                if row[1] is not None:
                    worst = max(worst, self.at(arrive) - row[1])
                if cron:
                    self.env["td.signal"]._cron_stale()
                    self.assertNotEqual(sig.status, "stale", "stale перед пакетом t=%s" % arrive)
            readings = []
            while next_t <= arrive:
                readings.append(self.rd(sig, value(next_t), text=text, at=next_t))
                next_t += period
            if readings:
                self.push(readings, arrive=arrive)
            ts = self.db_last(sig)[1]
            writes += ts != prev_ts
            prev_ts = ts
        return worst, writes


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
        self.sig.period_s = 60
        self.set_params(last_fresh_s=1000)  # вікно споживачів не обмежує: лишається лише last_write_min_s = 15
        self.push([self.rd(self.sig, 10.0, at=0)])
        for t in (5, 10, 14):
            self.push([self.rd(self.sig, 10.0, at=t)])
            self.assertEqual(self.db_last(self.sig)[1], self.at(0))
        self.push([self.rd(self.sig, 10.0, at=15)])
        self.assertEqual(self.db_last(self.sig)[1], self.at(15))

    def test_freshness_write_before_consumer_window_exceeded(self):
        """period_s 10, відправка раз на 5 с: вікно 30 с, пропуск ≤ 30 − 2 − 5 − 10 = 13 с після запису."""
        self.push([self.rd(self.sig, 10.0, at=0)])
        for t in (5, 10):
            self.push([self.rd(self.sig, 10.0, at=t)])
            self.assertEqual(self.db_last(self.sig)[1], self.at(0))
        self.push([self.rd(self.sig, 10.0, at=14)])
        self.assertEqual(self.db_last(self.sig)[1], self.at(14))

    def test_freshness_limited_by_half_of_stale_window(self):
        self.sig.period_s = 20
        self.set_params(last_write_min_s=600, last_fresh_s=1000, stale_min_s=20, stale_periods=1)  # stale 20 с → 10 с
        self.push([self.rd(self.sig, 10.0, at=0)])
        self.push([self.rd(self.sig, 10.0, at=9)])
        self.assertEqual(self.db_last(self.sig)[1], self.at(0))
        self.push([self.rd(self.sig, 10.0, at=10)])
        self.assertEqual(self.db_last(self.sig)[1], self.at(10))

    def test_text_and_quality_change_written(self):
        st = self.sig_flstate
        st.period_s = 10  # при period_s 5 і відправці раз на 5 с (вікно 15 с) показання пишуться завжди
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
        c.period_s = 10
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
        self.col.push_interval_s = 1
        self.assertEqual(self.fast1._td_stale_after(), 15)
        self.assertEqual(self.fire._td_stale_after(), 6)
        self.set_params(min_period_s=0)
        self.assertEqual(self.fast1._td_stale_after(), 5)


@tagged(*TAGS)
class TestFreshnessBudget(ChurnCase):
    """Вік збереженого `last_ts` у момент перед прийомом наступного пакета не виходить за вікно споживачів, а
    відкладення лишається там, де воно безпечне (ефективні налаштування за замовчуванням: min_period_s 5)."""

    def test_ats_state_written_with_every_packet(self):
        """`infra/ats/*`: period_s 5, АВР td_energy свіжий ≤ 3·5 = 15 с (раніше вік доходив до ~20 с)."""
        for push_s in (1, 5, 10):
            sig = self.mk_signal("infra/ats/position_t%s" % push_s, 5, kind="state", states_text="pos_I, pos_II")
            worst, writes = self.run_collector(sig, push_s, total_s=300, text="pos_I", offset=2)
            self.assertLessEqual(worst, timedelta(seconds=15), "push %s" % push_s)
            if push_s >= 5:
                self.assertEqual(writes, 300 // push_s, "кожен пакет — запис (push %s)" % push_s)
        # push 10 с, опитування зі зсувом: 10 + 3 с (запас до вікна 15 с — 2 с)
        self.assertEqual(worst, timedelta(seconds=13))

    def test_ats_state_defers_only_with_fast_push(self):
        sig = self.mk_signal("infra/ats/src1_state_t", 5, kind="state", states_text="under, available")
        worst, writes = self.run_collector(sig, 1, total_s=300, text="available")
        self.assertLessEqual(worst, timedelta(seconds=13))  # 15 − запас 2 с
        self.assertLess(writes, 300 * 0.7)

    def test_chp_like_gauge_with_slow_push(self):
        """`chp/ctl/*`: period_s 2 → 5 с, td_chp свіжий ≤ 30 с; відправка раз на 10 с не дає віку ≥ 30 с."""
        sig = self.mk_signal("chp/ctl/setpoint_t", 2)
        worst, writes = self.run_collector(sig, 10, total_s=300, offset=3)
        self.assertLessEqual(worst, timedelta(seconds=15))
        self.assertEqual(writes, 30)

    def test_gauge_period_10_still_deferred(self):
        sig = self.mk_signal("equipment/CHURN-T/mid10", 10)
        worst, writes = self.run_collector(sig, 5, total_s=600)
        self.assertLessEqual(worst, timedelta(seconds=28))  # вікно споживачів 3·10 = 30 с − запас 2 с
        self.assertLess(writes, 120 * 0.7)

    def test_slow_signals_unchanged(self):
        sig = self.mk_signal("equipment/CHURN-T/slow60", 60)
        worst, writes = self.run_collector(sig, 5, total_s=600)
        self.assertEqual(writes, 11)  # кожне показання (раз на 60 с, t = 0…600) — запис
        self.assertLessEqual(worst, timedelta(seconds=60))

    def test_cron_stale_window_covers_push_interval(self):
        """Колектор відправляє раз на 60 с: вікно stale ≥ 2·60 с (раніше `max(3·період, 60)` хибно давало stale)."""
        sig = self.mk_signal("equipment/CHURN-T/slow_push", 10)
        self.assertEqual(sig._td_stale_after(), 60)
        self.col.push_interval_s = 60
        self.assertEqual(sig._td_stale_after(), 120)
        self.run_collector(sig, 60, total_s=600, offset=3, cron=True)
        self.assertEqual(sig.status, "ok")

    def test_age_math(self):
        self.assertEqual(periods.fresh_window_s(5), 15)
        self.assertEqual(periods.fresh_window_s(10), 30)
        self.assertEqual(periods.fresh_window_s(60), 30)
        self.assertEqual(periods.fresh_window_s(0), 30)
        self.assertEqual(periods.max_skip_gap_s(5, 5, 5), 3)  # показання раз на 5 с завжди «пізніше»
        self.assertEqual(periods.max_skip_gap_s(5, 5, 10), -2)
        self.assertEqual(periods.max_skip_gap_s(5, 5, 1), 7)
        self.assertEqual(periods.max_skip_gap_s(10, 10, 5), 13)
        self.assertLess(periods.max_skip_gap_s(60, 60, 5), 0)
        self.assertEqual(periods.stale_window_s(5, 3, 60, 5), 60)
        self.assertEqual(periods.stale_window_s(5, 3, 60, 60), 120)


@tagged(*TAGS)
class TestLastMonotonic(ChurnCase):
    """`last_value`/`last_ts` не повертаються до старішого показання (повторна відправка, запізнілий пакет)."""

    def setUp(self):
        super().setUp()
        self.sig = self.sig_flx  # period_s 10: пропуск ≤ 13 с після запису
        self.sig.write({"decimals": 1})
        self.push([self.rd(self.sig, 10.0, at=0)])
        self.push([self.rd(self.sig, 10.02, at=5)])  # у мертвій зоні: не записано
        self.assertEqual(self.db_last(self.sig)[:2], (10.0, self.at(0)))

    def test_late_retry_does_not_regress(self):
        res = self.push([self.rd(self.sig, 12.0, at=3)], arrive=60)  # повтор пакета, прийнятий через хвилину
        self.assertEqual(res["accepted"], 1)
        self.assertEqual(self.db_last(self.sig)[:2], (10.0, self.at(0)))
        self.assertEqual(res["changed_codes"], [])
        self.push([self.rd(self.sig, 10.0, at=70)])
        self.assertEqual(self.db_last(self.sig)[1], self.at(70))

    def test_on_time_reading_is_written(self):
        self.push([self.rd(self.sig, 12.0, at=7)], arrive=8)
        self.assertEqual(self.db_last(self.sig)[:2], (12.0, self.at(7)))

    def test_backfill_beyond_skip_window_is_written(self):
        """Після простою колектора перше показання за межею пропуску стає `last_*`, хоч і надійшло пізно."""
        self.push([self.rd(self.sig, 12.0, at=100)], arrive=300)
        self.assertEqual(self.db_last(self.sig)[:2], (12.0, self.at(100)))

    def test_older_than_stored_still_ignored(self):
        self.push([self.rd(self.sig, 12.0, at=-30)], arrive=60)
        self.assertEqual(self.db_last(self.sig)[:2], (10.0, self.at(0)))

    def test_no_deferral_means_no_fence(self):
        """АВР (вузьке вікно) пишеться з кожним показанням: нічого не пропущено, запізніле показання теж `last_*`."""
        self.col.push_interval_s = 10  # вікно 15 с, відправка 10 с + період 5 с: відкладати нічого
        ats = self.mk_signal("infra/ats/gen_start_t", 5, kind="state", states_text="off, on")
        self.push([self.rd(ats, text="off", at=0)])
        self.push([self.rd(ats, text="off", at=5)])
        self.assertEqual(self.db_last(ats)[1], self.at(5))
        self.push([self.rd(ats, text="on", at=8)], arrive=60)
        self.assertEqual(self.db_last(ats)[1], self.at(8))
