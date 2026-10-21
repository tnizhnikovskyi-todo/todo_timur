"""AC-10: блокування R-07 (золоті випадки, застарілий вхід)."""

from odoo.tests import tagged

from ..tools import interlocks
from ..tools.signals import Snapshot
from .common import TAGS, ChpCase

START_CODES = [
    "not_cooling", "no_alarm", "permit", "gas_pressure", "remote", "rsw", "grid", "no_rocof", "lel_lt", "no_fire",
    "ret_temp", "jacket_temp", "battery", "oil_estop",
]  # fmt: skip


@tagged(*TAGS)
class TestInterlocks(ChpCase):
    def check(self, code, **values):
        return interlocks.CHECKS[code](self.unit, {k.replace("__", "/"): v for k, v in values.items()})[0]

    def test_golden(self):
        c = self.check
        self.assertEqual([c("gas_pressure", gas__p_in=p) for p in (2.10, 1.15, None)], ["ok", "fail", "unknown"])
        self.assertEqual([c("ret_temp", ht__t_ret=t) for t in (58, 72, None)], ["ok", "fail", "unknown"])
        self.assertEqual([c("lel_lt", safe__lel=x) for x in (0.6, 12, None)], ["ok", "fail", "unknown"])
        self.assertEqual(c("oil_estop", oil__level=66.8, safe__estop_loop=1), "ok")
        self.assertEqual(c("oil_estop", oil__level=35, safe__estop_loop=1), "fail")
        self.assertEqual(c("oil_estop", oil__level=66.8, safe__estop_loop=0), "fail")
        self.assertEqual(c("oil_estop", oil__level=66.8), "unknown")
        self.assertEqual(c("no_fire", safe__fire=0, safe__ext_state=1), "fail")
        self.assertEqual(c("not_cooling", ctl__state=4), "fail")
        self.assertEqual(c("no_alarm", ctl__state=3), "fail")
        self.assertEqual(c("state_run", ctl__state=2), "ok")
        self.assertEqual(c("state_run", ctl__state=0), "fail")
        self.assertEqual(c("manual_mode", ctl__mode=3), "ok")
        self.assertEqual(c("battery", eng__bat_v=23.0), "fail")
        self.assertEqual(c("jacket_temp", eng__t_jacket_out=95.0), "fail")
        # деталі
        self.assertEqual(
            interlocks.CHECKS["gas_pressure"](self.unit, {"gas/p_in": 1.15})[1], "тиск газу 1,15 бар < 1,5 бар"
        )
        self.assertEqual(interlocks.CHECKS["gas_pressure"](self.unit, {"gas/p_in": 2.1})[1], "зараз 2,1 бар")

    def test_start_list_and_stale(self):
        self.idle()
        checks = interlocks.build_checks(self.unit, "start", Snapshot(self.env))
        self.assertEqual([c["code"] for c in checks], START_CODES)
        self.assertTrue(all(c["state"] == "ok" and c["hard"] for c in checks), checks)
        self.assertEqual(interlocks.verdict(checks, "start"), (False, ""))
        late = Snapshot(self.later(200))  # усі входи застаріли
        stale = interlocks.build_checks(self.unit, "start", late)
        self.assertEqual({c["state"] for c in stale if c["code"] != "rsw"}, {"unknown"})
        blocked, reason = interlocks.verdict(stale, "start")
        self.assertTrue(blocked)
        self.assertIn("немає свіжих даних", reason)
        # аварійний стоп: `unknown` не блокує
        es = interlocks.build_checks(self.unit, "estop", late)
        self.assertEqual(es[0]["state"], "unknown")
        self.assertEqual(interlocks.verdict(es, "estop"), (False, ""))
        self.idle(**{"ctl/state": 3})
        es = interlocks.build_checks(self.unit, "estop", Snapshot(self.env))
        self.assertTrue(interlocks.verdict(es, "estop")[0])

    def test_routed_skips_rsw(self):
        self.idle()
        checks = interlocks.build_checks(self.unit, "start", Snapshot(self.env), routed=True)
        codes = [c["code"] for c in checks]
        self.assertNotIn("rsw", codes)
        self.assertEqual(len(codes), 13)
