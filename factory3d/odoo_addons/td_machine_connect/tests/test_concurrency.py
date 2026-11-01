"""DEC-19/20: порядок блокувань, SKIP LOCKED у кроні такту, кількість UPDATE верстата в push-шляху,
паралельна транзакція (зайнятий або змінений після знімка рядок) — пропуск до наступного такту, а не помилка."""

import time
from unittest.mock import MagicMock, patch

from psycopg2 import errors as pg_errors

from odoo import SUPERUSER_ID, api, fields, sql_db
from odoo.tests import TransactionCase, tagged

from odoo.addons.td_machine_connect.models import td_machine as machine_module

from .common import P, F3DMachineCase, at

TAGS = ("post_install", "-at_install", "f3d", "f3d_machine_connect")
MODEL = "odoo.addons.td_machine_connect.models.td_machine"


class _SqlSpy:
    """Записує SQL, виконаний курсором (як `_patchExecute` у Odoo), поки діє контекст."""

    def __init__(self):
        self.queries = []

    def __enter__(self):
        orig = sql_db.Cursor.execute
        queries = self.queries

        def execute(cr, query, params=None, log_exceptions=None):
            code = getattr(query, "code", query)
            queries.append(code.decode() if isinstance(code, bytes) else code)
            return orig(cr, query, params, log_exceptions)

        self._patch = patch("odoo.sql_db.Cursor.execute", execute)
        self._patch.start()
        return self

    def __exit__(self, *exc):
        self._patch.stop()

    def like(self, *parts):
        return [q for q in self.queries if all(p.lower() in " ".join(q.split()).lower() for p in parts)]


@tagged(*TAGS)
class TestPushOrder(F3DMachineCase):
    def test_dispatch_locks_machines_in_id_order(self):
        """Push блокує верстати за зростанням id незалежно від порядку показань — як крон і `_td_mark_nodata`."""
        ids = []
        Machine = self.registry["td.machine"]
        orig = Machine._td_lock

        def lock(rec, nowait=False):
            ids.extend(rec.ids)
            return orig(rec, nowait=nowait)

        readings = (
            self.io(self.m_io, "10:00:00", run=True)
            + self.ua(self.m_saw, "10:00:00", state="READY")
            + self.ua(self.m_ua, "10:00:00", state="READY")
        )
        self.assertGreater(self.m_io.id, self.m_ua.id)
        with patch.object(Machine, "_td_lock", lock):
            self.feed(readings)
        self.assertEqual(ids, sorted((self.m_ua | self.m_saw | self.m_io).ids))

    def _machine_updates(self, readings):
        with _SqlSpy() as spy:
            self.feed(readings)
        return spy.like('update "td_machine"')

    def test_unchanged_push_does_not_write_machine_row(self):
        """Показання без змін не пишуть td_machine; мітки `raw_ts`/`pieces_ts` — не частіше за `heartbeat_s` (30 с)."""
        self._icp().set_param(P + "heartbeat_s", "30")
        m = self.m_ua
        first = self.ua(m, "10:00:00", state="WORKING", mode="AUTOMATIC", pieces=5, job="J-1")
        updates = self._machine_updates(first)
        self.assertEqual((m.state, m.raw_ts, m.pieces_ts), ("working", self.kt("10:00"), self.kt("10:00")))
        self.assertLessEqual(len(updates), 2, updates)  # стан + решта; більше за межі flush ORM не розбивається
        for sec in (5, 29):
            same = self.ua(m, "10:00:%02d" % sec, state="WORKING", mode="AUTOMATIC", pieces=5)
            self.assertEqual(self._machine_updates(same), [], "sec=%s" % sec)
        self.assertEqual((m.raw_ts, m.pieces_ts), (self.kt("10:00"), self.kt("10:00")))
        late = self.ua(m, "10:00:30", state="WORKING", mode="AUTOMATIC", pieces=5)
        updates = self._machine_updates(late)
        self.assertEqual(len(updates), 1, updates)
        self.assertEqual((m.raw_ts, m.pieces_ts), (self.kt("10:00:30"), self.kt("10:00:30")))
        self.assertEqual((m.state, m.pieces_last, m.raw_job), ("working", 5, "J-1"))

    def test_changes_are_written_at_once(self):
        """Зміна лічильника, стану й `raw_ts` — одразу, без очікування `heartbeat_s`."""
        m = self.m_ua
        self.feed(self.ua(m, "10:00:00", state="WORKING", mode="AUTOMATIC", pieces=5))
        self.feed(self.ua(m, "10:00:02", state="WORKING", mode="AUTOMATIC", pieces=6))
        self.assertEqual((m.pieces_last, m.pieces_ts, m.raw_ts), (6, self.kt("10:00:02"), self.kt("10:00:02")))
        self.feed(self.ua(m, "10:00:03", state="READY", mode="AUTOMATIC"))
        self.assertEqual((m.raw_state, m.raw_ts), ("READY", self.kt("10:00:03")))


@tagged(*TAGS)
class TestTickOrder(F3DMachineCase):
    def test_tick_batches_in_id_order_skip_locked(self):
        """Крон: верстати за id, пачками по TICK_BATCH, блокування `FOR UPDATE SKIP LOCKED` (без очікування)."""
        Machine = self.registry["td.machine"]
        expected = self.env["td.machine"].search([("active", "=", True), ("read_enabled", "=", True)], order="id").ids
        self.assertGreaterEqual(len(expected), 3)
        seen = []
        orig = Machine._td_tick_extra

        def spy_tick(rec, now):
            seen.extend(rec.ids)
            return orig(rec, now)

        with patch(MODEL + ".TICK_BATCH", 2), patch.object(Machine, "_td_tick_extra", spy_tick), _SqlSpy() as sql:
            self.tick("10:30:30")
        self.assertEqual(seen, expected)
        locks = sql.like("from td_machine", "for update")
        self.assertEqual(len(locks), -(-len(expected) // 2), locks)
        for q in locks:
            self.assertIn("order by id for update skip locked", " ".join(q.lower().split()))


class RealDbCase(TransactionCase):
    """Верстати `LK-0…2`, закомічені через справжнє з'єднання.

    Потрібне друге справжнє з'єднання: `registry.cursor()` у тесті — TestCursor на тому самому з'єднанні (блокування
    власної сесії не конфліктують), тому фікстури комітяться через `sql_db.db_connect().cursor()` і прибираються
    в `addCleanup`.
    """

    def setUp(self):
        super().setUp()
        self.db = sql_db.db_connect(self.env.cr.dbname)
        self.addCleanup(self._drop_fixtures)
        with self.db.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            icp = env["ir.config_parameter"]
            self._old_param = icp.get_param(P + "read_enabled")
            self._old_source_state = env.ref("td_machine_connect.source_mc_derived").state
            icp.set_param(P + "read_enabled", "True")
            wcs = env["mrp.workcenter"].create([{"name": "Lock %d" % i, "td_code": "LK-%d" % i} for i in range(3)])
            machines = env["td.machine"].create(
                [{"workcenter_id": wc.id, "protocol": "manual", "read_enabled": True} for wc in wcs]
            )
            self.wc_ids, self.machine_ids = wcs.ids, machines.sorted("id").ids

    def _drop_fixtures(self):
        with self.db.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            env["td.machine"].browse(self.machine_ids).exists().unlink()
            env["mrp.workcenter"].browse(self.wc_ids).exists().unlink()
            env["ir.config_parameter"].set_param(P + "read_enabled", self._old_param or False)
            env.ref("td_machine_connect.source_mc_derived").write({"state": self._old_source_state})

    def _snapshot_cursor(self):
        """Окрема транзакція REPEATABLE READ, що вже взяла знімку (як крон, який щойно почав роботу)."""
        cr = self.db.cursor()
        self.addCleanup(cr.close)
        cr.execute("SELECT count(*) FROM td_machine")
        return cr

    def _commit_update(self, machine_id):
        """Інша транзакція (push) змінює верстат і комітить — рядок вільний, але новіший за знімку."""
        with self.db.cursor() as cr:
            cr.execute("UPDATE td_machine SET pieces_last = pieces_last + 1 WHERE id = %s", [machine_id])


@tagged(*TAGS)
class TestTickSkipLocked(RealDbCase):
    """Крон не чекає рядка верстата, зайнятого іншою транзакцією (push), і обробляє решту."""

    def _tick(self):
        """`_cron_tick` на окремому з'єднанні; повертає (id оброблених верстатів, тривалість, с)."""
        Machine = self.registry["td.machine"]
        seen = []
        orig = Machine._td_tick_extra

        def spy(rec, now):
            seen.extend(rec.ids)
            return orig(rec, now)

        started = time.monotonic()
        with patch.object(Machine, "_td_tick_extra", spy), self.db.cursor() as cr:
            cr.execute("SET lock_timeout = '3s'")  # без SKIP LOCKED тест впав би помилкою, а не завис
            api.Environment(cr, SUPERUSER_ID, {})["td.machine"]._cron_tick()
            cr.execute("RESET lock_timeout")
        return seen, time.monotonic() - started

    def test_tick_skips_locked_machine(self):
        first, locked, last = self.machine_ids
        holder = self.db.cursor()  # окрема транзакція, як push, що блокує рядок
        self.addCleanup(holder.close)
        holder.execute("SELECT id FROM td_machine WHERE id = %s FOR UPDATE", [locked])
        seen, elapsed = self._tick()
        self.assertLess(elapsed, 3)
        self.assertIn(first, seen)
        self.assertIn(last, seen)
        self.assertNotIn(locked, seen)
        holder.rollback()  # push завершився
        seen, _elapsed = self._tick()
        self.assertTrue({first, locked, last} <= set(seen))
        self.assertEqual(seen, sorted(seen))  # стабільний порядок


@tagged(*TAGS)
class TestLockContention(RealDbCase):
    """DEC-20: верстат, змінений паралельною транзакцією після знімки REPEATABLE READ, пропускається (не помилка)."""

    def test_skip_locked_survives_serialization_failure(self):
        first, changed, last = self.machine_ids
        cr = self._snapshot_cursor()
        self._commit_update(changed)
        machines = api.Environment(cr, SUPERUSER_ID, {})["td.machine"].browse(self.machine_ids)
        with self.assertRaises(pg_errors.SerializationFailure), cr.savepoint(flush=False):  # без обробки впав би крон
            cr.execute(
                "SELECT id FROM td_machine WHERE id IN %s FOR UPDATE SKIP LOCKED",
                (tuple(self.machine_ids),),
                log_exceptions=False,
            )
        self.assertEqual(machines._td_lock_skip_locked().ids, [first, last])
        self.assertEqual(machines.browse(changed)._td_lock_skip_locked().ids, [])  # змінений — до наступного такту

    def test_skip_locked_still_skips_locked_rows(self):
        first, locked, last = self.machine_ids
        holder = self.db.cursor()
        self.addCleanup(holder.close)
        holder.execute("SELECT id FROM td_machine WHERE id = %s FOR UPDATE", [locked])
        cr = self._snapshot_cursor()
        machines = api.Environment(cr, SUPERUSER_ID, {})["td.machine"].browse(self.machine_ids)
        self.assertEqual(machines._td_lock_skip_locked().ids, [first, last])

    def test_mark_nodata_skips_busy_machines(self):
        """`_td_mark_nodata` (крон stale) не чекає зайнятого й не пробиває змінений рядок: повертає лише оброблені."""
        first, locked, changed = self.machine_ids
        holder = self.db.cursor()
        self.addCleanup(holder.close)
        holder.execute("SELECT id FROM td_machine WHERE id = %s FOR UPDATE", [locked])
        cr = self._snapshot_cursor()
        self._commit_update(changed)
        cr.execute("SET lock_timeout = '3s'")  # без SKIP LOCKED тест впав би помилкою, а не завис
        machines = api.Environment(cr, SUPERUSER_ID, {})["td.machine"].browse(self.machine_ids)
        started = time.monotonic()
        done = machines._td_mark_nodata(fields.Datetime.now(), "timeout")
        self.assertLess(time.monotonic() - started, 3)
        self.assertEqual(done.ids, [first])


@tagged(*TAGS)
class TestContentionHandling(F3DMachineCase):
    """DEC-20: паралельна транзакція — пропуск з повтором наступним тактом, а не `ERROR` із трейсбеком."""

    def test_dispatch_contention_is_skipped_not_error(self):
        """Push: верстат, який не вдалось заблокувати (SerializationFailure), пропускається; решта обробляється."""
        Machine = self.registry["td.machine"]
        orig = Machine._td_lock
        busy = self.m_io

        def lock(rec, nowait=False):
            if rec == busy:
                raise pg_errors.SerializationFailure("could not serialize access due to concurrent update")
            return orig(rec, nowait=nowait)

        readings = self.io(busy, "10:00:00", run=True) + self.ua(self.m_ua, "10:00:00", state="READY")
        with patch.object(Machine, "_td_lock", lock), self.assertLogs(MODEL, "WARNING") as logs:
            stats = self.env["td.machine"]._td_dispatch(readings, "collector")
        self.assertEqual((stats["errors"], stats["locked"], stats["machines"]), ([], [busy.code], 1))
        self.assertTrue(all(rec.levelname == "WARNING" and not rec.exc_info for rec in logs.records))
        self.env.invalidate_all()
        self.assertEqual((self.m_ua.state, busy.state), ("idle", "nodata"))  # пропущений верстат не зачеплений

    def test_tick_contention_skips_machine_and_goes_on(self):
        """Такт: SerializationFailure в одному верстаті не зупиняє решту й не пишеться як помилка."""
        Machine = self.registry["td.machine"]
        busy = self.m_ua
        seen = []
        orig = Machine._td_tick_extra

        def tick_extra(rec, now):
            if rec == busy:
                raise pg_errors.SerializationFailure("could not serialize access due to concurrent update")
            seen.extend(rec.ids)
            return orig(rec, now)

        with patch.object(Machine, "_td_tick_extra", tick_extra), self.assertLogs(MODEL, "WARNING") as logs:
            self.tick("10:30:30")
        self.assertIn(self.m_io.id, seen)
        self.assertNotIn(busy.id, seen)
        self.assertEqual([rec.levelname for rec in logs.records], ["WARNING"])
        self.assertFalse(logs.records[0].exc_info)

    def test_mark_stale_busy_machine_retried_by_cron(self):
        """Верстат зайнятий: сигнал лишається у статусі `ok` (його візьме наступний `_cron_stale`), потім — nodata."""
        m, sig = self.m_ua, self.sig_ua_state
        self.feed(self.ua(m, "10:00:00", state="WORKING", mode="AUTOMATIC"))
        self.assertEqual((m.state, sig.status), ("working", "ok"))
        Machine = self.registry["td.machine"]
        with patch.object(Machine, "_td_lock_skip_locked", lambda rec: rec.browse()):
            sig._mark_stale("timeout")
        self.env.invalidate_all()
        self.assertEqual((m.state, sig.status), ("working", "ok"))
        sig._mark_stale("timeout")
        self.env.invalidate_all()
        self.assertEqual((m.state, sig.status), ("nodata", "stale"))

    def test_oee_cron_writes_machine_link_once(self):
        """OEE: `oee_shift_id` пишеться лише при зміні посилання; наступний запуск не оновлює рядок верстата."""
        self.env["td.machine.state.log"].sudo().create(
            {
                "machine_id": self.m_saw.id,
                "state": "working",
                "date_start": self.kt("07:00"),
                "date_end": self.kt("10:00"),
            }
        )
        self.oee_tick("10:30")
        self.assertTrue(self.m_saw.oee_shift_id)
        with _SqlSpy() as spy:
            self.oee_tick("10:35")
        self.assertEqual(spy.like('update "td_machine"'), [])

    def test_oee_cron_skips_locked_machine_row(self):
        """OEE: зайнятий рядок верстата не блокує крон; посилання на зміну виправить наступний запуск."""
        Machine = self.registry["td.machine"]
        self.env["td.machine.state.log"].sudo().create(
            {
                "machine_id": self.m_saw.id,
                "state": "working",
                "date_start": self.kt("07:00"),
                "date_end": self.kt("10:00"),
            }
        )
        with patch.object(Machine, "_td_lock_skip_locked", lambda rec: rec.browse()):
            self.oee_tick("10:30")
        self.assertFalse(self.m_saw.oee_shift_id)
        self.oee_tick("10:35")
        self.assertTrue(self.m_saw.oee_shift_id)


@tagged(*TAGS)
class TestIdleFinishLockedWorkorder(F3DMachineCase):
    def test_idle_finish_waits_for_busy_workorder(self):
        """Автозавершення за простоєм: завдання зайняте — крок пропущено, наступний такт завершує."""
        self.enable_autostart()
        m = self.m_io
        wo = self.make_mo(self.wc_io, qty=8).workorder_ids[:1]
        with at("10:31:05"):
            self.feed(self.io(m, "10:31:00", run=True, pieces=0))
        with at("10:35:05"):
            self.feed(self.io(m, "10:35:00", pieces=8))
        with at("10:40:00"):
            self.feed(self.io(m, "10:40:00", run=False))
        Machine = self.registry["td.machine"]
        with patch.object(Machine, "_td_lock_wo", lambda rec, wo: False):
            self.tick("10:41:01")
        self.assertEqual(wo.state, "progress")
        self.tick("10:42:01")
        self.assertEqual((wo.state, wo.qty_produced), ("done", 8))


@tagged(*TAGS)
class TestPushBacklog(F3DMachineCase):
    """Показання, які push не зміг застосувати (верстат зайнятий), потрапляють у чергу, а не зникають; крон такту
    не голодує хвостові верстати; зайнятий сигнал не ставить `nodata`; OEE комітить по верстату."""

    def _contend(self, busy):
        Machine = self.registry["td.machine"]
        orig = Machine._td_lock

        def lock(rec, nowait=False):
            if rec == busy:
                raise pg_errors.LockNotAvailable("could not obtain lock on row in relation td_machine")
            return orig(rec, nowait=nowait)

        return patch.object(Machine, "_td_lock", lock)

    def _rows(self, m):
        return self.env["td.machine.backlog"].sudo().search([("machine_id", "=", m.id)])

    def test_push_locks_machine_row_nowait(self):
        """Push не чекає рядок верстата, зайнятий тактом чи OEE: `FOR UPDATE NOWAIT`."""
        with _SqlSpy() as spy:
            self.feed(self.ua(self.m_ua, "10:00:00", state="READY"))
        locks = spy.like("from td_machine", "for update")
        self.assertTrue(locks)
        self.assertTrue(all("for update nowait" in " ".join(q.lower().split()) for q in locks), locks)

    def test_contended_readings_are_queued_then_applied_by_tick(self):
        m = self.m_ua
        with self._contend(m), self.assertLogs(MODEL, "WARNING"):
            stats = self.env["td.machine"]._td_dispatch(
                [dict(r, i=i) for i, r in enumerate(self.ua(m, "10:00:00", state="WORKING", mode="AUTOMATIC"))],
                "collector",
            )
        self.assertEqual((stats["locked"], stats["queued"], stats["errors"]), ([m.code], 2, []))
        self.assertEqual(len(self._rows(m)), 1)
        self.assertEqual(sorted(it["role"] for it in self._rows(m)._td_items()), ["mode", "state"])
        self.assertEqual(m.state, "nodata")
        self.tick("10:00:30")
        self.env.invalidate_all()
        self.assertFalse(self._rows(m))
        self.assertEqual(m.state, "working")

    def test_next_push_applies_queue_first(self):
        m = self.m_ua
        with self._contend(m):
            self.feed(self.ua(m, "10:00:00", state="WORKING", mode="AUTOMATIC"))
        self.assertTrue(self._rows(m))
        self.feed(self.ua(m, "10:00:20", pieces=3))
        self.assertFalse(self._rows(m))
        self.assertEqual((m.state, m.raw_state), ("working", "WORKING"))

    def test_stale_queue_is_purged_not_applied(self):
        m = self.m_ua
        with self._contend(m):
            self.feed(self.ua(m, "10:00:00", state="WORKING"))
        self.assertTrue(self._rows(m))
        self.tick("11:45:00")  # від постановки (10:30) минуло понад BACKLOG_TTL
        self.env.invalidate_all()
        self.assertFalse(self._rows(m))
        self.assertEqual(m.state, "nodata")

    def test_poisoned_queue_is_dropped_and_does_not_block_machine(self):
        m = self.m_ua
        with self._contend(m):
            self.feed(self.ua(m, "10:00:00", state="WORKING"))
        Machine = self.registry["td.machine"]

        def boom(rec, items):
            raise ValueError("poison")

        with patch.object(Machine, "_td_apply", boom), self.assertLogs(MODEL, "ERROR"):
            self.tick("10:30:30")
        self.assertFalse(self._rows(m))
        self.feed(self.ua(m, "10:31:00", state="READY"))
        self.assertEqual(m.state, "idle")

    def test_tick_resumes_after_budget_instead_of_restarting(self):
        """Бюджет вичерпано посеред обходу: наступний виклик продовжує з наступного верстата, а не з першого."""
        Machine = self.registry["td.machine"]
        self.addCleanup(machine_module._TICK_CURSOR.clear)
        expected = self.env["td.machine"].search([("active", "=", True), ("read_enabled", "=", True)], order="id").ids
        self.assertGreaterEqual(len(expected), 3)
        seen = []
        orig = Machine._td_tick_extra

        def spy_tick(rec, now):
            seen.extend(rec.ids)
            return orig(rec, now)

        readings = iter([0.0, 0.0, 0.0, 100.0])  # старт, перевірки перед 1-ю, 2-ю й 3-ю пачками: бюджет вичерпано
        fake_time = MagicMock()
        fake_time.monotonic.side_effect = lambda: next(readings, 0.0)
        with (
            patch(MODEL + ".TICK_BATCH", 1),
            patch(MODEL + ".time", fake_time),
            patch.object(Machine, "_td_tick_extra", spy_tick),
        ):
            self.tick("10:30:30")
            self.assertEqual(seen, expected[:2])
            self.tick("10:31:30")
            self.assertEqual(seen, expected)  # решта, без повторів
            self.tick("10:32:30")
            self.assertEqual(seen[len(expected) :], expected)  # обхід завершено: лічильник скинуто, знову з початку

    def test_tick_yields_when_worker_time_is_up(self):
        calls = []

        def fake_commit(this, processed=0, *, remaining=None, deactivate=False):
            calls.append((processed, remaining))
            return 0.0

        with at("10:30:30"):
            ctx = {"ir_cron_progress_id": 1, "cron_id": 0, "cron_end_time": time.monotonic() - 1}
            with (
                patch.object(type(self.env["ir.cron"]), "_commit_progress", fake_commit),
                patch.object(self.registry["td.machine"], "_td_tick_extra") as tick_extra,
            ):
                self.env["td.machine"].with_context(**ctx)._cron_tick()
        self.assertEqual(calls, [(0, 1)])
        self.assertFalse(tick_extra.called)

    def test_mark_stale_skipped_signal_does_not_set_nodata(self):
        """Сигнал зайнято (його push щойно приніс показання): stale не ставиться, отже верстат не блимає в `nodata`."""
        m, sig = self.m_ua, self.sig_ua_state
        self.feed(self.ua(m, "10:00:00", state="WORKING", mode="AUTOMATIC"))
        self.assertEqual((m.state, sig.status), ("working", "ok"))
        cron_sig = sig.with_context(td_skip_locked=True)
        with patch("odoo.addons.td_telemetry.models.td_signal.lock_skip_locked", lambda recs: recs.browse()):
            cron_sig._mark_stale("timeout")
        self.env.invalidate_all()
        self.assertEqual((m.state, sig.status), ("working", "ok"))
        cron_sig._mark_stale("timeout")
        self.env.invalidate_all()
        self.assertEqual((m.state, sig.status), ("nodata", "stale"))

    def test_oee_cron_commits_per_machine(self):
        """OEE: commit після кожного верстата (`_commit_progress`), а не один у кінці запуску."""
        calls = []

        def fake_commit(this, processed=0, *, remaining=None, deactivate=False):
            calls.append((processed, remaining))
            return 0.0

        total = self.env["td.machine"].search_count([("active", "=", True), ("read_enabled", "=", True)])
        self.assertGreaterEqual(total, 3)
        with (
            patch("odoo.modules.module.current_test", False),
            patch.object(type(self.env["ir.cron"]), "_commit_progress", fake_commit),
        ):
            self.oee_tick("10:30")
        self.assertEqual(calls, [(1, total - 1 - pos) for pos in range(total)])
