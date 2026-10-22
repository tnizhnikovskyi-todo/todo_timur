"""DEC-20: `_cron_stale` / `_cron_offline` при паралельній транзакції (push, інший крон) — рядок, зайнятий
чи змінений після знімка REPEATABLE READ, пропускається до наступного запуску, а не валить крон."""

import time
from datetime import timedelta
from unittest.mock import patch

from psycopg2 import errors as pg_errors

from odoo import SUPERUSER_ID, api, fields, sql_db
from odoo.tests import TransactionCase, tagged

from .common import MB_ADDR, F3DTelemetryCase

TAGS = ("post_install", "-at_install", "f3d", "f3d_telemetry")
SIGNAL_MODEL = "odoo.addons.td_telemetry.models.td_signal"
COLLECTOR_MODEL = "odoo.addons.td_telemetry.models.td_collector"
UTC_NOW = "(now() AT TIME ZONE 'UTC')"  # колонки Odoo — timestamp без часової зони (UTC)


class RealDbCase(TransactionCase):
    """Колектор `COL-LK` (online, давно не виходив на зв'язок), два джерела й три сигнали зі старими показаннями,
    закомічені через справжнє з'єднання.

    Потрібне друге справжнє з'єднання: `registry.cursor()` у тесті — TestCursor на тому самому з'єднанні (блокування
    власної сесії не конфліктують), тож фікстури комітяться через `sql_db.db_connect().cursor()` і прибираються
    в `addCleanup`. Крон у тестах біжить на окремому курсорі, який не комітиться (закривається відкотом).
    """

    COLLECTOR_AGE = "1 hour"  # давність `last_seen` колектора; понад 3·status_interval_s (180 с) — його візьме крон

    def setUp(self):
        super().setUp()
        self.db = sql_db.db_connect(self.env.cr.dbname)
        self.col_id, self.source_ids, self.signal_ids = 0, [], []
        self.addCleanup(self._drop_fixtures)
        with self.db.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            col = env["td.collector"].create({"code": "COL-LK", "name": "Колектор LK"})
            sources = env["td.source"].create(
                [
                    {
                        "code": "MB-LK-%d" % i,
                        "name": "MB-LK-%d" % i,
                        "type": "modbus_tcp",
                        "collector_id": col.id,
                        "params": {**MB_ADDR, "unit": 80 + i},
                    }
                    for i in range(2)
                ]
            )
            signals = env["td.signal"].create(
                [
                    {
                        "code": "equipment/LK-T/s%d" % i,
                        "name": "LK s%d" % i,
                        "kind": "gauge",
                        "unit": "бар",
                        "source_id": sources[i % 2].id,
                        "address": {"fc": 3, "addr": 3000 + i, "type": "u16"},
                        "origin": "manual",
                        "store_period_s": 300,
                    }
                    for i in range(3)
                ]
            )
            self.col_id, self.source_ids, self.signal_ids = col.id, sources.sorted("id").ids, signals.sorted("id").ids
            cr.execute(
                "UPDATE td_signal SET status = 'ok', last_ts = " + UTC_NOW + " - interval '1 hour' WHERE id IN %s",
                [tuple(self.signal_ids)],
            )
            cr.execute("UPDATE td_source SET state = 'online' WHERE id IN %s", [tuple(self.source_ids)])
            cr.execute(
                "UPDATE td_collector SET state = 'online', last_seen = " + UTC_NOW + " - %s::interval WHERE id = %s",
                [self.COLLECTOR_AGE, self.col_id],
            )

    def _drop_fixtures(self):
        with self.db.cursor() as cr:
            env = api.Environment(cr, SUPERUSER_ID, {})
            env["td.signal"].browse(self.signal_ids).exists().unlink()
            env["td.source"].browse(self.source_ids).exists().unlink()
            env["td.collector"].browse(self.col_id).exists().unlink()

    def _snapshot_cursor(self):
        """Окрема транзакція REPEATABLE READ, що вже взяла знімку (як крон, який щойно почав роботу)."""
        cr = self.db.cursor()
        self.addCleanup(cr.close)
        cr.execute("SELECT count(*) FROM td_signal")
        cr.execute("SET lock_timeout = '3s'")  # без SKIP LOCKED тест впав би помилкою, а не завис
        return cr

    def _holder(self, table, row_id):
        """Окрема транзакція, що блокує рядок (як push)."""
        holder = self.db.cursor()
        self.addCleanup(holder.close)
        holder.execute("SELECT id FROM %s WHERE id = %%s FOR UPDATE" % table, [row_id])
        return holder

    def _commit(self, query, *params):
        """Інша транзакція (push) змінює рядок і комітить — рядок вільний, але новіший за знімку."""
        with self.db.cursor() as cr:
            cr.execute(query, params)

    def _cron(self, cr):
        started = time.monotonic()
        api.Environment(cr, SUPERUSER_ID, {})["td.signal"]._cron_stale()
        self.assertLess(time.monotonic() - started, 3, "крон чекав на заблокований рядок")

    def _states(self, cr):
        """(статуси сигналів за id, state джерел за id, state колектора) — з бази через `cr`."""
        api.Environment(cr, SUPERUSER_ID, {}).flush_all()
        cr.execute("SELECT id, status FROM td_signal WHERE id IN %s", [tuple(self.signal_ids)])
        signals = dict(cr.fetchall())
        cr.execute("SELECT id, state FROM td_source WHERE id IN %s", [tuple(self.source_ids)])
        sources = dict(cr.fetchall())
        cr.execute("SELECT state FROM td_collector WHERE id = %s", [self.col_id])
        return [signals[i] for i in self.signal_ids], [sources[i] for i in self.source_ids], cr.fetchone()[0]


@tagged(*TAGS)
class TestStaleContention(RealDbCase):
    COLLECTOR_AGE = "0 seconds"  # колектор онлайн: перевіряється лише шлях сигналів за таймаутом

    def test_locked_signal_skipped_then_processed(self):
        """Сигнал, зайнятий іншою транзакцією, пропускається без очікування; наступний запуск його обробляє."""
        _first, locked, _last = self.signal_ids
        holder = self._holder("td_signal", locked)
        cr = self._snapshot_cursor()
        self._cron(cr)
        statuses, _sources, _col = self._states(cr)
        self.assertEqual(statuses, ["stale", "ok", "stale"])
        holder.rollback()  # push завершився
        self._cron(cr)  # наступний запуск
        self.assertEqual(self._states(cr)[0], ["stale", "stale", "stale"])

    def test_signal_changed_after_snapshot_is_not_an_error(self):
        """Сигнал, змінений push після знімки (SerializationFailure на `FOR UPDATE`), пропускається, не валить крон."""
        _first, changed, _last = self.signal_ids
        cr = self._snapshot_cursor()
        self._commit("UPDATE td_signal SET last_value = 1 WHERE id = %s", changed)  # last_ts не оновлено
        with self.assertNoLogs("odoo.sql_db", "ERROR"):  # SQL блокування — без «bad query»
            self._cron(cr)
        self.assertEqual(self._states(cr)[0], ["stale", "ok", "stale"])
        cr.rollback()  # перший запуск не закомічено: його блокування не мають заважати наступному
        cr2 = self._snapshot_cursor()  # новий запуск із новою знімкою
        self._cron(cr2)
        self.assertEqual(self._states(cr2)[0], ["stale", "stale", "stale"])

    def test_fresh_reading_after_snapshot_keeps_signal_ok(self):
        """Показання, що прийшло після знімки крону, не губиться: сигнал лишається `ok`."""
        _first, fresh, _last = self.signal_ids
        cr = self._snapshot_cursor()
        self._commit("UPDATE td_signal SET last_ts = " + UTC_NOW + " WHERE id = %s", fresh)
        self._cron(cr)
        self.assertEqual(self._states(cr)[0], ["stale", "ok", "stale"])
        cr.rollback()
        cr2 = self._snapshot_cursor()
        self._cron(cr2)
        self.assertEqual(self._states(cr2)[0], ["stale", "ok", "stale"])


@tagged(*TAGS)
class TestOfflineContention(RealDbCase):
    def test_offline_marks_collector_sources_and_signals(self):
        """Без конкуренції: колектор, його джерела й сигнали — offline/stale (бізнес-поведінка R-25 не змінилась)."""
        cr = self._snapshot_cursor()
        self._cron(cr)
        self.assertEqual(self._states(cr), (["stale"] * 3, ["offline"] * 2, "offline"))

    def test_locked_collector_skipped_then_processed(self):
        holder = self._holder("td_collector", self.col_id)
        cr = self._snapshot_cursor()
        self._cron(cr)
        statuses, sources, col = self._states(cr)
        self.assertEqual((sources, col), (["online"] * 2, "online"))  # колектор лишився як був, повтор за хвилину
        self.assertEqual(statuses, ["stale"] * 3)  # сигнали без колектора — за таймаутом, як і раніше
        holder.rollback()
        self._cron(cr)
        self.assertEqual(self._states(cr)[1:], (["offline"] * 2, "offline"))

    def test_collector_pushed_after_snapshot_stays_online(self):
        """Колектор вийшов на зв'язок після знімки крону: `last_seen` змінено — він не стає offline."""
        cr = self._snapshot_cursor()
        self._commit("UPDATE td_collector SET last_seen = " + UTC_NOW + " WHERE id = %s", self.col_id)
        with self.assertNoLogs("odoo.sql_db", "ERROR"):
            self._cron(cr)
        self.assertEqual(self._states(cr)[1:], (["online"] * 2, "online"))

    def test_locked_source_defers_whole_collector(self):
        """Зайняте джерело: колектор не стає offline окремо від джерел (інакше розбіжність лишилась би назавжди)."""
        holder = self._holder("td_source", self.source_ids[1])
        cr = self._snapshot_cursor()
        self._cron(cr)
        _statuses, sources, col = self._states(cr)
        self.assertEqual((sources, col), (["online"] * 2, "online"))
        holder.rollback()
        self._cron(cr)
        self.assertEqual(self._states(cr), (["stale"] * 3, ["offline"] * 2, "offline"))

    def test_locked_signal_of_offline_collector_deferred(self):
        """Сигнал зайнятий: колектор і джерела обробляються, сигнал лишається `ok` (далі — за таймаутом)."""
        first = self.signal_ids[0]
        self._commit(
            "UPDATE td_signal SET last_ts = " + UTC_NOW + " WHERE id IN %s", tuple(self.signal_ids)
        )  # не за таймаутом
        holder = self._holder("td_signal", first)
        cr = self._snapshot_cursor()
        self._cron(cr)
        self.assertEqual(self._states(cr), (["ok", "stale", "stale"], ["offline"] * 2, "offline"))
        holder.rollback()


@tagged(*TAGS)
class TestMarkStaleContention(F3DTelemetryCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_telemetry_fixtures()

    def _ok(self, *signals):
        for sig in signals:
            self.set_sql(sig, status="ok", last_ts=fields.Datetime.now() - timedelta(hours=1))

    def test_contention_on_write_skips_one_signal(self):
        """`SerializationFailure` у записі одного сигналу не валить решту: він лишається `ok` до наступного запуску."""
        self._ok(self.sig_press, self.sig_bat)
        Signal = self.registry["td.signal"]
        orig = Signal.write

        def write(rec, vals):
            if rec == self.sig_press and vals.get("status") == "stale":
                raise pg_errors.SerializationFailure("could not serialize access due to concurrent update")
            return orig(rec, vals)

        with patch.object(Signal, "write", write), self.assertLogs(SIGNAL_MODEL, "INFO") as logs:
            (self.sig_press | self.sig_bat).with_context(td_skip_locked=True)._mark_stale("timeout")
        self.assertEqual((self.sig_press.status, self.sig_bat.status), ("ok", "stale"))
        self.assertTrue(all(not rec.exc_info for rec in logs.records))
        (self.sig_press | self.sig_bat).with_context(td_skip_locked=True)._mark_stale("timeout")  # наступний запуск
        self.assertEqual((self.sig_press.status, self.sig_bat.status), ("stale", "stale"))
        self.assertEqual(len(self.sig_bat.message_ids.filtered(lambda m: "Немає даних" in (m.body or ""))), 1)

    def test_without_context_nothing_is_skipped(self):
        """Поза кроном (API, дії користувача) `_mark_stale` не пропускає рядки: поведінка як раніше."""
        self._ok(self.sig_press)
        with patch(SIGNAL_MODEL + ".lock_skip_locked", lambda recs: recs.browse()):
            self.sig_press._mark_stale("disabled")
        self.assertEqual(self.sig_press.status, "stale")

    def test_cron_uses_skip_locked(self):
        """Крон блокує сигнали й колектор через `lock_skip_locked`; зайняті рядки — не помилка."""
        self._ok(self.sig_press)
        self.set_sql(self.col, state="online", last_seen=fields.Datetime.now() - timedelta(hours=1))
        with (
            patch(SIGNAL_MODEL + ".lock_skip_locked", side_effect=lambda recs: recs.browse()) as sig_lock,
            patch(COLLECTOR_MODEL + ".lock_skip_locked", side_effect=lambda recs: recs.browse()) as col_lock,
        ):
            self.env["td.signal"]._cron_stale()
        self.assertTrue(sig_lock.called and col_lock.called)
        self.assertEqual(self.sig_press.status, "ok")
        self.assertEqual(self.col.state, "online")
        self.env["td.signal"]._cron_stale()
        self.assertEqual((self.sig_press.status, self.col.state), ("stale", "offline"))
