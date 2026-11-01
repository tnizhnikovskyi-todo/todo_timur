"""Прийом показань воріт (`_td_ingest` → `_td_yard_dispatch`): маршрутизація й відсутність зайвих UPDATE."""

from contextlib import contextmanager
from datetime import timedelta, timezone

from odoo import fields
from odoo.tests import tagged

from .gate_case import GateCase


@tagged("post_install", "-at_install", "f3d", "f3d_yard")
class TestGateIngest(GateCase):
    @contextmanager
    def capture_queries(self):
        queries = []
        yield from self._patchExecute(queries)
        queries[:] = [q.decode() if isinstance(q, bytes) else q for q in queries]

    def ingest(self, items, ago=0):
        ts = (fields.Datetime.now() - timedelta(seconds=ago)).replace(tzinfo=timezone.utc).isoformat()
        readings = [
            {"code": "yard/gates/%s/%s" % (tag, role), "ts": ts, "value": v, "q": "good"} for tag, role, v in items
        ]
        res = self.env["td.signal"].sudo()._td_ingest(readings, src="module")
        self.env.invalidate_all()
        return res

    def test_dispatch_routes_by_signal(self):
        self.ingest([("TW", "state", 1.0), ("TE", "loop", 1.0), ("ZZ", "state", 1.0)])
        self.assertEqual((self.gate_w.state, self.gate_w.loop_occupied), ("open", False))
        self.assertEqual((self.gate_e.loop_occupied, self.gate_e.photocell_blocked), (True, False))
        self.ingest([("TW", "photocell", 1.0), ("TE", "loop", 0.0)])
        self.assertEqual((self.gate_w.photocell_blocked, self.gate_e.loop_occupied), (True, False))

    def test_dispatch_selects_only_batch_gates(self):
        with self.capture_queries() as queries:
            self.env["td.yard.gate"]._td_yard_dispatch([{"code": "yard/gates/NONE/state", "ts": "x", "value": 1}])
        gate_sql = [q for q in queries if '"td_yard_gate"' in q]
        self.assertEqual(gate_sql, [])  # нема сигналів з таким кодом — ворота не читаються

    def test_stable_readings_do_not_update_gate(self):
        items = [("TW", "state", 1.0), ("TW", "loop", 0.0), ("TW", "photocell", 0.0), ("TW", "passes", 0.0),
                 ("TE", "state", 0.0), ("TE", "loop", 0.0), ("TE", "photocell", 0.0)]  # fmt: skip
        self.ingest(items, ago=5)
        self.assertEqual((self.gate_w.state, self.gate_e.state), ("open", "closed"))
        with self.capture_queries() as queries:
            self.ingest(items)
        updates = [q for q in queries if q.lstrip().upper().startswith("UPDATE") and '"td_yard_gate"' in q]
        self.assertEqual(updates, [])
        self.assertEqual((self.gate_w.state, self.gate_e.state), ("open", "closed"))
