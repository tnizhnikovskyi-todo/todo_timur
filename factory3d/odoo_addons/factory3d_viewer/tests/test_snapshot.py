import base64
import gzip
from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import fields
from odoo.tests import HttpCase, tagged

from .common import F3dViewerBase

DATES_NOW = "odoo.addons.factory3d_viewer.tools.dates.now"


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestSnapshot(F3dViewerBase):
    """M-02: AC-25, AC-27."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Snap = cls.env["f3d.viewer.snapshot"].sudo()

    def setUp(self):
        super().setUp()
        self.Snap.search([]).unlink()
        self.set_param("snapshot_hours", "06:30-16:00")

    def _make(self, kind="periodic", days_ago=0, company=None):
        return self.Snap.create({
            "ts": fields.Datetime.now() - timedelta(days=days_ago), "kind": kind,
            "payload_file": self.Snap._pack({"meta": {"schema": "1.1"}}),
            "company_id": (company or self.env.company).id})

    def test_cron_window(self):
        """AC-25: 10:00 Київ (07:00 UTC) — знімок; 20:00 — ні."""
        with patch(DATES_NOW, return_value=datetime(2026, 10, 12, 7, 0)):
            self.Snap._cron_snapshot()
        snaps = self.Snap.search([])
        self.assertEqual(len(snaps), 1)
        self.assertEqual(snaps.kind, "periodic")
        self.assertGreaterEqual(snaps.size_kb, 1)
        self.assertEqual(snaps.read_payload()["meta"]["snapshot"]["id"], snaps.id)
        snaps.ts = fields.Datetime.now() - timedelta(minutes=10)
        with patch(DATES_NOW, return_value=datetime(2026, 10, 12, 17, 0)):
            self.Snap._cron_snapshot()
        self.assertEqual(len(self.Snap.search([])), 1)

    def test_window_empty_and_overnight(self):
        self.assertTrue(self.Snap._in_window("", datetime(2026, 10, 12, 17, 0)))
        self.assertTrue(self.Snap._in_window("22:00-04:00", datetime(2026, 10, 12, 21, 0)))  # 00:00 Київ
        self.assertFalse(self.Snap._in_window("22:00-04:00", datetime(2026, 10, 12, 9, 0)))

    def test_idempotent_60s(self):
        first = self.Snap._take("periodic")
        second = self.Snap._take("periodic")
        self.assertEqual(first, second)
        self.assertEqual(len(self.Snap.search([])), 1)
        manual = self.Snap._take("manual", note="x")
        self.assertNotEqual(manual, first)

    def test_events_in_snapshot(self):
        first = self.Snap._take("manual")
        self.env["f3d.viewer.event"]._notify("stock.quant", ["TST-LOC-A"], "stock")
        self.env.flush_all()
        self.env.cr.precommit.run()
        first.ts = fields.Datetime.now() - timedelta(seconds=30)
        second = self.Snap._take("manual")
        self.assertEqual(second.event_count, 1)
        self.assertEqual(second.read_payload()["meta"]["events"][0]["codes"], ["TST-LOC-A"])

    def test_rotate_keeps_install(self):
        """AC-27."""
        old = self._make("periodic", 15)
        old_install = self._make("install", 15)
        fresh = self._make("periodic", 1)
        Event = self.env["f3d.viewer.event"].sudo()
        old_ev = Event.create({"ts": fields.Datetime.now() - timedelta(days=15), "model": "m", "codes": ["A"],
                               "kind": "state"})
        fresh_ev = Event.create({"model": "m", "codes": ["B"], "kind": "state"})
        self.Snap._cron_rotate()
        self.assertFalse(old.exists())
        self.assertTrue(old_install.exists() and fresh.exists())
        self.assertFalse(old_ev.exists())
        self.assertTrue(fresh_ev.exists())

    def test_company_rule(self):
        other = self.env["res.company"].create({"name": "TST other co"})
        mine, foreign = self._make(), self._make(company=other)
        visible = self.env["f3d.viewer.snapshot"].with_user(self.user_f3d).search([])
        self.assertIn(mine, visible)
        self.assertNotIn(foreign, visible)

    def test_read_payload_gzip(self):
        snap = self._make()
        self.assertEqual(snap.read_payload(), {"meta": {"schema": "1.1"}})
        self.assertEqual(gzip.decompress(base64.b64decode(snap.payload_file))[:1], b"{")
        self.assertEqual(snap.shift_date.isoformat()[:4].isdigit(), True)
        self.assertIn("·", snap.display_name)
        action = snap.action_open_viewer()
        self.assertEqual(action["params"], {"snapshot": snap.id})
        self.assertEqual(action["tag"], "f3d_viewer.action")


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestSnapshotHttp(HttpCase, F3dViewerBase):
    """API-05, API-06: AC-26."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for user in (cls.user_f3d, cls.user_nobody):
            user.password = user.login
        cls.Snap = cls.env["f3d.viewer.snapshot"].sudo()
        cls.Snap.search([]).unlink()

    def _snap(self, hhmm):
        return self.Snap.create({
            "ts": datetime(2026, 10, 12, int(hhmm[:2]), int(hhmm[3:])), "kind": "periodic",
            "payload_file": self.Snap._pack({"meta": {"schema": "1.1"}})})

    def _get(self, url, user="f3d_user", **kw):
        self.authenticate(user, user)
        return self.url_open(url, allow_redirects=False, **kw)

    def test_list_mode(self):
        for hhmm in ("04:00", "05:00"):
            self._snap(hhmm)
        res = self._get("/f3d/viewer/snapshots?date=2026-10-12").json()
        self.assertEqual((res["mode"], len(res["snapshots"])), ("plan", 2))
        self._snap("06:00")
        self._snap("07:00")
        self._snap("08:00")
        res = self._get("/f3d/viewer/snapshots?date=2026-10-12").json()
        self.assertEqual((res["date"], res["mode"], len(res["snapshots"])), ("2026-10-12", "snapshots", 5))
        self.assertEqual(res["snapshots"][0]["ts"], "2026-10-12 07:00")
        self.assertEqual(set(res["snapshots"][0]), {"id", "ts", "kind", "size_kb", "note"})
        self.assertEqual(self._get("/f3d/viewer/snapshots?date=bad").status_code, 400)
        self.assertEqual(self._get("/f3d/viewer/snapshots", user="f3d_nobody").status_code, 403)

    def test_snapshot_download(self):
        snap = self._snap("04:00")
        res = self._get("/f3d/viewer/snapshot/%d" % snap.id, headers={"Accept-Encoding": "identity"})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json(), {"meta": {"schema": "1.1"}})
        self.assertEqual(self._get("/f3d/viewer/snapshot/99999999").status_code, 404)
        self.assertEqual(self._get("/f3d/viewer/snapshot/%d" % snap.id, user="f3d_nobody").status_code, 403)
