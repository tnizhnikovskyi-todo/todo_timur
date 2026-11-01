from datetime import timedelta
from unittest.mock import patch

from odoo import fields, sql_db
from odoo.tests import tagged

from odoo.addons.td_viewer3d.models import viewer_event
from odoo.addons.td_viewer3d.tools import dates
from odoo.addons.td_viewer3d.tools.payload import DeltaBuilder

from .common import F3dViewerBase


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestEventPurge(F3dViewerBase):
    """Журнал td.viewer.event потрібен лише дельті (event_keep_hours): чистка пакетами, індекси, без зайвих UPDATE."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Event = cls.env["td.viewer.event"].sudo()

    def setUp(self):
        super().setUp()
        self.Event.search([]).unlink()
        self.set_param("event_keep_hours", "24")

    def _make(self, n, age):
        ts = fields.Datetime.now() - age
        return self.Event.create([{"ts": ts, "model": "m", "codes": ["A", "B"], "kind": "state"} for _ in range(n)])

    def test_purge_old_removes_only_expired(self):
        old = self._make(25, timedelta(hours=30))
        fresh = self._make(5, timedelta(hours=2))
        self.assertEqual(self.Event._purge_old(batch=10), 25)
        self.assertFalse(old.exists())
        self.assertEqual(len(fresh.exists()), 5)
        self.assertEqual(self.Event._purge_old(batch=10), 0)

    def test_purge_batches_and_time_cap(self):
        old = self._make(25, timedelta(hours=30))
        # max_seconds=0: після першого пакета зупиняємось, решта — наступним запуском
        self.assertEqual(self.Event._purge_old(batch=10, max_seconds=0), 10)
        self.assertEqual(len(old.exists()), 15)
        self.assertEqual(self.Event._purge_old(batch=10), 15)
        self.assertFalse(old.exists())

    def test_purge_uses_param_and_cron(self):
        stale = self._make(3, timedelta(hours=2))
        fresh = self._make(3, timedelta(minutes=30))
        self.set_param("event_keep_hours", "1")
        self.Event._cron_purge()
        self.assertFalse(stale.exists())
        self.assertEqual(len(fresh.exists()), 3)
        self.set_param("event_keep_hours", "bad")  # невалідне значення → умовчання 24 год
        old = self._make(2, timedelta(hours=25))
        self.assertEqual(self.Event._purge_old(), 2)
        self.assertFalse(old.exists())

    def test_purge_cron_registered(self):
        cron = self.env.ref("td_viewer3d.cron_td_event_purge")
        self.assertEqual((cron.interval_number, cron.interval_type), (1, "hours"))
        self.assertIn("_cron_purge", cron.code)

    def test_since_matches_purge_window(self):
        """Подія в межах keep лишається видимою дельті, старша за keep — «повний»."""
        self._make(1, timedelta(hours=1))
        self.assertEqual(self.Event._since(fields.Datetime.now() - timedelta(hours=2)), {"m": {"A", "B"}})
        self.assertIsNone(self.Event._since(fields.Datetime.now() - timedelta(hours=25)))

    def test_create_has_no_follow_up_update(self):
        """`n` передається в create: збережене поле не дає другого UPDATE (мертві кортежі) на кожну подію."""
        self.env.flush_all()
        statements = []
        cr = self.env.cr
        original = cr.execute

        def spy(query, *args, **kwargs):
            statements.append(str(getattr(query, "code", query)))
            return original(query, *args, **kwargs)

        cr.execute = spy
        try:
            self.env["td.viewer.event"]._notify("stock.quant", ["TST-A", "TST-B"], "stock")
            self.env.flush_all()
            self.env.cr.precommit.run()
            self.env.flush_all()
        finally:
            del cr.execute
        events = self.Event.search([])
        self.assertEqual((len(events), events.n), (1, 2))
        self.assertFalse(
            [q for q in statements if q.lstrip().upper().startswith('UPDATE "TD_VIEWER_EVENT"')], statements
        )

    def test_indexes(self):
        """Лишається лише індекс по ts (+ pkey): (ts, model), model, kind подвоювали вартість кожного INSERT."""
        self.env.cr.execute("SELECT indexname FROM pg_indexes WHERE tablename = 'td_viewer_event'")
        names = {r[0] for r in self.env.cr.fetchall()}
        self.assertIn("td_viewer_event__ts_index", names)
        self.assertFalse({n for n in names if n.endswith(("_ts_model_idx", "_model_index", "_kind_index"))}, names)

    def test_late_committed_event_reaches_next_delta(self):
        """Подія з `ts` на момент precommit, закомічена після дельти, не губиться: курсор дельти відстає від «зараз»."""
        cursor = dates.parse_iso_utc(DeltaBuilder(self.env, None, changes={}).build()["ts"])
        self.Event.create(
            {"ts": dates.real_now() - timedelta(seconds=1), "model": "m", "codes": ["A"], "kind": "state"}
        )
        self.assertEqual(self.Event._since(cursor), {"m": {"A"}})

    def test_purge_commits_each_batch_in_cron_only(self):
        """У кроні кожен пакет фіксується (`_commit_progress`), поза кроном (тести, RPC) commit-ів немає."""
        self._make(25, timedelta(hours=30))
        calls = []

        def fake_commit(this, processed=0, *, remaining=None, deactivate=False):
            calls.append(processed)
            return 0.0

        cron_env = self.Event.with_context(ir_cron_progress_id=1, cron_id=0)
        with patch.object(type(self.env["ir.cron"]), "_commit_progress", fake_commit):
            self.assertEqual(self.Event._purge_old(batch=10), 25)
            self.assertEqual(calls, [])  # без контексту крона
            self._make(25, timedelta(hours=30))
            with patch("odoo.modules.module.current_test", False):
                self.assertEqual(cron_env._purge_old(batch=10), 25)
        self.assertEqual(calls, [10, 10, 5])

    def test_purge_skips_when_another_run_holds_the_lock(self):
        """Щогодинний крон і щодобова ротація не чистять одночасно: хто не дістав блокування, пропускає."""
        old = self._make(5, timedelta(hours=30))
        holder = sql_db.db_connect(self.env.cr.dbname).cursor()
        self.addCleanup(holder.close)
        self.addCleanup(holder.rollback)  # advisory xact lock знімається разом із транзакцією
        holder.execute("SELECT pg_advisory_xact_lock(%s)", [viewer_event.PURGE_LOCK])
        self.assertEqual(self.Event._purge_old(), 0)
        self.assertEqual(len(old.exists()), 5)
        holder.rollback()
        self.assertEqual(self.Event._purge_old(), 5)
