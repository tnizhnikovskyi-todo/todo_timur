"""DEC-19: порядок блокувань, SKIP LOCKED у кроні такту, кількість UPDATE верстата в push-шляху."""

import time
from unittest.mock import patch

from odoo import SUPERUSER_ID, api, sql_db
from odoo.tests import TransactionCase, tagged

from .common import P, F3DMachineCase

TAGS = ("post_install", "-at_install", "f3d", "f3d_machine_connect")
MODEL = "odoo.addons.factory3d_machine_connect.models.f3d_machine"


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
        """Push блокує верстати за зростанням id незалежно від порядку показань — як крон і `_f3d_mark_nodata`."""
        ids = []
        Machine = self.registry["f3d.machine"]
        orig = Machine._f3d_lock

        def lock(rec):
            ids.extend(rec.ids)
            return orig(rec)

        readings = (
            self.io(self.m_io, "10:00:00", run=True)
            + self.ua(self.m_saw, "10:00:00", state="READY")
            + self.ua(self.m_ua, "10:00:00", state="READY")
        )
        self.assertGreater(self.m_io.id, self.m_ua.id)
        with patch.object(Machine, "_f3d_lock", lock):
            self.feed(readings)
        self.assertEqual(ids, sorted((self.m_ua | self.m_saw | self.m_io).ids))

    def _machine_updates(self, readings):
        with _SqlSpy() as spy:
            self.feed(readings)
        return spy.like('update "f3d_machine"')

    def test_unchanged_push_does_not_write_machine_row(self):
        """Показання без змін не пишуть f3d_machine; мітки `raw_ts`/`pieces_ts` — не частіше за HEARTBEAT_S."""
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
        """Зміна лічильника, стану й `raw_ts` — одразу, без очікування HEARTBEAT_S."""
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
        Machine = self.registry["f3d.machine"]
        expected = self.env["f3d.machine"].search([("active", "=", True), ("read_enabled", "=", True)], order="id").ids
        self.assertGreaterEqual(len(expected), 3)
        seen = []
        orig = Machine._f3d_tick_extra

        def spy_tick(rec, now):
            seen.extend(rec.ids)
            return orig(rec, now)

        with patch(MODEL + ".TICK_BATCH", 2), patch.object(Machine, "_f3d_tick_extra", spy_tick), _SqlSpy() as sql:
            self.tick("10:30:30")
        self.assertEqual(seen, expected)
        locks = sql.like("from f3d_machine", "for update")
        self.assertEqual(len(locks), -(-len(expected) // 2), locks)
        for q in locks:
            self.assertIn("order by id for update skip locked", " ".join(q.lower().split()))


@tagged(*TAGS)
class TestTickSkipLocked(TransactionCase):
    """Крон не чекає рядка верстата, зайнятого іншою транзакцією (push), і обробляє решту.

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
            self._old_source_state = env.ref("factory3d_machine_connect.source_mc_derived").state
            icp.set_param(P + "read_enabled", "True")
            wcs = env["mrp.workcenter"].create([{"name": "Lock %d" % i, "f3d_code": "LK-%d" % i} for i in range(3)])
            machines = env["f3d.machine"].create(
                [{"workcenter_id": wc.id, "protocol": "manual", "read_enabled": True} for wc in wcs]
            )
            self.wc_ids, self.machine_ids = wcs.ids, machines.sorted("id").ids

    def _drop_fixtures(self):
        with self.db.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            env["f3d.machine"].browse(self.machine_ids).exists().unlink()
            env["mrp.workcenter"].browse(self.wc_ids).exists().unlink()
            env["ir.config_parameter"].set_param(P + "read_enabled", self._old_param or False)
            env.ref("factory3d_machine_connect.source_mc_derived").write({"state": self._old_source_state})

    def _tick(self):
        """`_cron_tick` на окремому з'єднанні; повертає (id оброблених верстатів, тривалість, с)."""
        Machine = self.registry["f3d.machine"]
        seen = []
        orig = Machine._f3d_tick_extra

        def spy(rec, now):
            seen.extend(rec.ids)
            return orig(rec, now)

        started = time.monotonic()
        with patch.object(Machine, "_f3d_tick_extra", spy), self.db.cursor() as cr:
            cr.execute("SET lock_timeout = '3s'")  # без SKIP LOCKED тест впав би помилкою, а не завис
            api.Environment(cr, SUPERUSER_ID, {})["f3d.machine"]._cron_tick()
            cr.execute("RESET lock_timeout")
        return seen, time.monotonic() - started

    def test_tick_skips_locked_machine(self):
        first, locked, last = self.machine_ids
        holder = self.db.cursor()  # окрема транзакція, як push, що блокує рядок
        self.addCleanup(holder.close)
        holder.execute("SELECT id FROM f3d_machine WHERE id = %s FOR UPDATE", [locked])
        seen, elapsed = self._tick()
        self.assertLess(elapsed, 3)
        self.assertIn(first, seen)
        self.assertIn(last, seen)
        self.assertNotIn(locked, seen)
        holder.rollback()  # push завершився
        seen, _elapsed = self._tick()
        self.assertTrue({first, locked, last} <= set(seen))
        self.assertEqual(seen, sorted(seen))  # стабільний порядок
