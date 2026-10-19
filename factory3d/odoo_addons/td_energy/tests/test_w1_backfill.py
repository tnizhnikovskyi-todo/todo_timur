"""W1-A: AC-148…AC-152 (+ТБ-10) — генератор історії (R-36, API-15)."""

import hashlib
from datetime import datetime, timedelta
from unittest.mock import patch

from psycopg2 import OperationalError

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import TAGS, TestW1Common

UNTIL = datetime(2026, 10, 12, 21, 0)  # вівторок 00:00 Київ (13.10)
SATURDAY_UNTIL = datetime(2026, 10, 19, 21, 0)  # вівторок 00:00 Київ (20.10): 10 діб від суботи 10.10


@tagged(*TAGS)
class TestW1Backfill(TestW1Common):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Interval = cls.env["td.energy.interval"]
        cls.Balance = cls.env["td.energy.balance"]

    def backfill(self, **kw):
        kw.setdefault("until", UNTIL)
        kw.setdefault("with_balance", False)
        kw.setdefault("with_events", False)
        return self.Interval._td_backfill(**kw)

    def digest(self, since, until):
        self.env.cr.execute(
            "SELECT m.code, i.ts_start, i.kwh, i.kwh_export FROM td_energy_interval i JOIN td_energy_meter m"
            " ON m.id = i.meter_id WHERE i.ts_start >= %s AND i.ts_start < %s ORDER BY 1, 2",
            (since, until),
        )
        return hashlib.sha256(repr(self.env.cr.fetchall()).encode()).hexdigest()

    def test_rows_and_properties(self):  # AC-148
        stats = self.backfill(days=2, seed=1)
        self.assertEqual((stats["meters"], stats["slots"], stats["rows"], stats["skipped"]), (67, 192, 67 * 192, 0))
        self.assertEqual(stats["since"], "2026-10-10 21:00:00")
        self.assertEqual(self.Interval.search_count([]), 12864)
        self.assertEqual(self.Interval.search_count([("is_backfill", "=", True), ("quality", "=", "measured")]), 12864)
        by_role = {}
        for iv in self.Interval.sudo().search([("ts_start", "=", UNTIL - timedelta(hours=10))]):
            by_role.setdefault(iv.role, []).append(iv.cost)
        self.assertEqual(set(by_role), {"incomer", "feeder", "consumer", "generation", "storage"})
        for role, costs in by_role.items():
            if role in ("incomer", "feeder", "consumer"):
                self.assertTrue(any(c > 0 for c in costs), role)
            else:
                self.assertEqual(set(costs), {0.0}, role)
        last = UNTIL - timedelta(minutes=15)
        starts = set(self.Meter.search([("e_import_signal_id", "!=", False)]).mapped("last_interval_start"))
        self.assertEqual(starts, {last})

    def test_security(self):  # ТБ-10
        with self.assertRaises(AccessError):
            self.Interval.with_user(self.u_eng)._td_backfill(days=1, until=UNTIL)
        with self.assertRaises(UserError):
            self.backfill(days=0)
        admin = (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "W1 адмін",
                    "login": "w1_admin",
                    "group_ids": [(6, 0, [self.env.ref("td_factory3d.group_td_admin").id])],
                }
            )
        )
        stats = self.Interval.with_user(admin)._td_backfill(days=1, until=UNTIL, with_balance=False, with_events=False)
        self.assertEqual(stats["rows"], 67 * 96)

    def test_balance_identity_and_anomaly(self):  # AC-149
        until = datetime(2026, 10, 13, 21, 0)  # середа 00:00 Київ; 11-й будній день (d % 11 == 5) — понеділок 12.10
        stats = self.backfill(days=7, until=until, seed=2, with_balance=True, with_events=True)
        self.assertGreater(stats["balance"], 0)
        rows = self.Balance.search([("hour", ">=", until - timedelta(days=7)), ("hour", "<", until)])
        self.assertEqual({r.state for r in rows} - {"ok", "deviation"}, set())
        deviations = rows.filtered(lambda r: r.state == "deviation")
        anomaly_hour = datetime(2026, 10, 12, 7, 0)
        self.assertEqual([(r.node_id.code, r.hour) for r in deviations], [("QF-1", anomaly_hour)])
        for node in ("Q1", "Q2"):
            for r in rows.filtered(lambda r, node=node: r.node_id.code == node):
                self.assertLessEqual(abs(r.diff_kwh), max(2.0, 0.03 * abs(r.expected_kwh)), (node, r.hour))
        events = self.Event.search([("is_backfill", "=", True)])
        self.assertEqual(set(events.mapped("kind")), {"peak", "ats", "balance"})
        self.assertEqual(set(events.filtered(lambda e: e.level == "warn").mapped("state")), {"resolved"})
        self.assertEqual(set(events.filtered(lambda e: e.level == "info").mapped("state")), {"na"})
        self.assertEqual(len(events.filtered(lambda e: e.kind == "balance")), 1)
        self.assertEqual(self.Event.search_count([("is_backfill", "=", False), ("kind", "=", "balance")]), 0)

    def test_idempotent_purge_deterministic(self):  # AC-150
        first = self.backfill(days=1, seed=5)
        again = self.backfill(days=1, seed=5)
        self.assertEqual((again["rows"], again["skipped"]), (0, first["rows"]))
        since = UNTIL - timedelta(days=1)
        digest = self.digest(since, UNTIL)
        real = self.Meter.search([("code", "=", "PM-QF-2")])
        purged = self.backfill(days=1, seed=5, purge=True)
        self.assertEqual(purged["purged_rows"], first["rows"])
        self.assertEqual(self.Interval.search_count([]), 0)
        self.interval("PM-QF-2", since, 9.0)  # «реальний» слот: purge його не чіпає, backfill — теж
        self.backfill(days=1, seed=5, purge=True)
        self.assertEqual(self.Interval.search_count([("is_backfill", "=", False)]), 1)
        redo = self.backfill(days=1, seed=5)
        self.assertEqual((redo["rows"], redo["skipped"]), (first["rows"] - 1, 1))
        self.assertEqual(self.Interval.search([("meter_id", "=", real.id), ("ts_start", "=", since)]).kwh, 9.0)
        self.env.cr.execute("DELETE FROM td_energy_interval")
        self.backfill(days=1, seed=5)
        self.assertEqual(self.digest(since, UNTIL), digest)
        self.env.cr.execute("DELETE FROM td_energy_interval")
        self.backfill(days=1, seed=6)
        self.assertNotEqual(self.digest(since, UNTIL), digest)

    def test_load_shape(self):  # AC-151
        self.backfill(days=10, until=SATURDAY_UNTIL, seed=3)
        self.env.cr.execute(
            """SELECT ts_start, SUM(kwh) * 4 FROM td_energy_interval WHERE role = 'consumer' GROUP BY ts_start"""
        )
        weekday_peak, night, sunday = 0.0, [], []
        from ..tools import dates

        for ts, kw in self.env.cr.fetchall():
            local = dates.to_local(ts)
            if local.weekday() < 5:
                weekday_peak = max(weekday_peak, kw)
                if local.hour < 6:
                    night.append(kw)
            elif local.weekday() == 6:
                sunday.append(kw)
        self.assertTrue(600 <= weekday_peak <= 700, weekday_peak)
        self.assertTrue(all(190 <= kw <= 230 for kw in night), (min(night), max(night)))
        self.assertLessEqual(max(sunday), 230)
        self.env.cr.execute(
            """SELECT ts_start, SUM(kwh) * 4 FROM td_energy_interval i JOIN td_energy_meter m ON m.id = i.meter_id
                WHERE m.model = 'sun2000' GROUP BY ts_start"""
        )
        pv = self.env.cr.fetchall()
        self.assertTrue(all(kw <= 920 for _ts, kw in pv))
        self.assertTrue(all(kw == 0 for ts, kw in pv if dates.to_local(ts).hour < 4 or dates.to_local(ts).hour >= 21))
        self.assertTrue(any(kw > 100 for _ts, kw in pv))

    def test_real_data_interplay(self):  # AC-152
        meter = self.Meter.search([("code", "=", "PM-QF-2")])
        real_ts = UNTIL + timedelta(hours=1)
        self.interval("PM-QF-2", real_ts, 11.0)
        meter.write({"last_interval_start": real_ts})
        self.backfill(days=1, seed=4)
        self.assertEqual(meter.last_interval_start, real_ts)  # не зменшується й не перескакує
        other = self.Meter.search([("code", "=", "PM-QF-1")])
        self.assertEqual(other.last_interval_start, UNTIL - timedelta(minutes=15))
        self.assertFalse(self.Interval.search([("ts_start", ">=", UNTIL), ("is_backfill", "=", True)]))
        # until за замовчуванням = ceil15(перше показання лічильника)
        signal = self.Meter.search([("code", "=", "PM-Q1")]).e_import_signal_id
        self.env["td.reading"].create(
            {"signal_id": signal.id, "ts": datetime(2026, 10, 17, 6, 7), "value": 1.0, "src": "module"}
        )
        stats = self.Interval._td_backfill(days=1, with_balance=False, with_events=False, seed=4)
        self.assertEqual(stats["until"], "2026-10-17 06:15:00")

    def test_sequential_windows_idempotent(self):  # стенд: історія шматками по 1 добі з якорем, потім повтор
        windows = [(1, UNTIL - timedelta(days=2)), (1, UNTIL - timedelta(days=1)), (1, UNTIL)]
        first = [self.backfill(days=d, until=u, seed=20261018, with_events=True) for d, u in windows]
        for stats in first:
            self.assertEqual((stats["rows"], stats["skipped"]), (67 * 96, 0))
        self.assertEqual(self.Interval.search_count([("is_backfill", "=", True)]), 3 * 67 * 96)
        events = self.env["td.energy.event"].search_count([("is_backfill", "=", True)])
        self.assertTrue(events)
        again = [self.backfill(days=d, until=u, seed=20261018, with_events=True) for d, u in windows]
        for stats in again:
            self.assertEqual((stats["rows"], stats["skipped"]), (0, 67 * 96))
        self.assertEqual(self.Interval.search_count([("is_backfill", "=", True)]), 3 * 67 * 96)
        self.assertEqual(self.env["td.energy.event"].search_count([("is_backfill", "=", True)]), events)

    def _failing_after_build(self, exc):
        """`_td_after_build` із SQL-помилкою (транзакція в aborted) і винятком `exc` — як SerializationFailure."""

        def after_build(model, now):
            with mute_logger("odoo.sql_db"):
                try:
                    model.env.cr.execute("SELECT 1 / 0")
                except Exception:
                    pass
            raise exc

        return patch.object(type(self.Interval), "_td_after_build", after_build)

    def test_after_build_sql_error_keeps_transaction(self):  # InFailedSqlTransaction на стенді (вікно 10)
        for exc in (OperationalError("could not serialize access due to concurrent update"), ValueError("boom")):
            self.env.cr.execute("DELETE FROM td_energy_interval")
            with self._failing_after_build(exc), self.assertLogs("odoo.addons.td_energy.tools.backfill") as logs:
                stats = self.backfill(days=1, seed=3, with_balance=True, with_events=True)
            self.assertEqual(len(logs.records), 1, exc)
            self.assertEqual(stats["rows"], 67 * 96)
            self.assertTrue(stats["balance"])
            self.env.flush_all()  # раніше тут падав flush балансу: current transaction is aborted
            self.env.cr.execute("SELECT count(*) FROM td_energy_interval WHERE is_backfill")
            self.assertEqual(self.env.cr.fetchone()[0], 67 * 96)
