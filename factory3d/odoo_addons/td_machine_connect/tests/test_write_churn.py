"""DEC-21: зайві UPDATE `td_machine`/`td_source` — повтор показань, такт і OEE без змін нічого не пишуть,
мітки «останнє показання» — не частіше за `heartbeat_s`."""

from unittest.mock import patch

from odoo.tests import tagged

from ..models.td_machine import HEARTBEAT_S, param_int
from .common import P, F3DMachineCase, kt
from .test_concurrency import TAGS, _SqlSpy


@tagged(*TAGS)
class TestNoopWrites(F3DMachineCase):
    def _updates(self, table, fn):
        with _SqlSpy() as spy:
            fn()
        return spy.like('update "%s"' % table)

    def _working(self):
        m = self.m_ua
        self.feed(self.ua(m, "10:00:00", state="WORKING", mode="AUTOMATIC", pieces=5, job="J-1"))
        return m

    def test_repeated_tick_and_oee_do_not_write_machine_or_source(self):
        """Такт і OEE без змін стану: ні `td_machine`, ні `td_source` (стан MC-DERIVED) не оновлюються."""
        self._working()
        self.tick("10:31:00")  # перший такт і перша зміна OEE дописують, що треба
        self.oee_tick("10:31:00")
        for t in ("10:32:00", "10:33:00"):
            self.assertEqual(self._updates("td_machine", lambda t=t: self.tick(t)), [], t)
            self.assertEqual(self._updates("td_source", lambda t=t: self.tick(t)), [], t)
        for t in ("10:35:00", "10:40:00"):
            self.assertEqual(self._updates("td_machine", lambda t=t: self.oee_tick(t)), [], t)

    def test_unchanged_push_does_not_call_write(self):
        """Повтор тих самих показань (стан, режим, тривога, лічильник): `write` верстата навіть не викликається."""
        m = self._working()
        Machine = self.registry["td.machine"]
        calls = []
        orig = Machine.write

        def spy(rec, vals):
            calls.append(dict(vals))
            return orig(rec, vals)

        with patch.object(Machine, "write", spy):
            self.feed(self.ua(m, "10:00:05", state="WORKING", mode="AUTOMATIC", alarm=False, pieces=5, job="J-1"))
        self.assertEqual(calls, [])

    def test_changed_value_writes_only_changed_fields(self):
        """Лічильник змінився — пишуться `pieces_last`/`pieces_ts`/`raw_ts`; сирий стан, режим, тривога — ні."""
        m = self._working()
        Machine = self.registry["td.machine"]
        calls = []
        orig = Machine.write

        def spy(rec, vals):
            calls.append(set(vals))
            return orig(rec, vals)

        with patch.object(Machine, "write", spy):
            self.feed(self.ua(m, "10:00:05", state="WORKING", mode="AUTOMATIC", pieces=6))
        self.assertEqual(m.pieces_last, 6)
        for fields_ in calls:
            self.assertFalse(fields_ & {"raw_state", "raw_mode", "raw_alarm"}, calls)

    def test_heartbeat_default_and_param(self):
        """Мітки без змін — раз на `heartbeat_s` (за замовчуванням HEARTBEAT_S); параметр керує, сміття — умовчання."""
        m = self._working()
        self.assertEqual(param_int(self.env, "heartbeat_s", HEARTBEAT_S), HEARTBEAT_S)
        edge = "10:%02d:%02d" % divmod(HEARTBEAT_S, 60)
        before = "10:%02d:%02d" % divmod(HEARTBEAT_S - 1, 60)
        same = {"state": "WORKING", "mode": "AUTOMATIC", "pieces": 5}
        self.assertEqual(self._updates("td_machine", lambda: self.feed(self.ua(m, before, **same))), [])
        self.assertEqual(len(self._updates("td_machine", lambda: self.feed(self.ua(m, edge, **same)))), 1)
        self.assertEqual((m.raw_ts, m.pieces_ts), (kt(edge), kt(edge)))
        # параметр: 10 с → наступна мітка за 10 с
        self._icp().set_param(P + "heartbeat_s", "10")
        self.assertEqual(self._updates("td_machine", lambda: self.feed(self.ua(m, "10:02:09", **same))), [])
        self.assertEqual(len(self._updates("td_machine", lambda: self.feed(self.ua(m, "10:02:10", **same)))), 1)
        # 0 — пишемо кожне показання; нечисловий параметр — умовчання
        self._icp().set_param(P + "heartbeat_s", "0")
        self.assertEqual(len(self._updates("td_machine", lambda: self.feed(self.ua(m, "10:02:11", **same)))), 1)
        self._icp().set_param(P + "heartbeat_s", "abc")
        self.assertEqual(param_int(self.env, "heartbeat_s", HEARTBEAT_S), HEARTBEAT_S)
        self._icp().set_param(P + "heartbeat_s", "-5")
        self.assertEqual(param_int(self.env, "heartbeat_s", HEARTBEAT_S), HEARTBEAT_S)
