"""W1-A: AC-101, AC-102 — шина `td_energy` (R-33): throttle, повідомлення без даних."""

from datetime import timedelta
from unittest.mock import patch

from odoo.tests import tagged

from ..tools import bus
from .common import NOW, TAGS, TestW1Common


@tagged(*TAGS)
class TestW1Bus(TestW1Common):
    def setUp(self):
        super().setUp()
        bus.reset()

    def kinds(self):
        return set(self.env.cr.precommit.data.get(bus._KEY, ()))

    def test_throttle_one_message(self):  # AC-101
        with (
            patch.object(self.registry["bus.bus"], "_sendone") as sendone,
            patch.object(bus.time, "monotonic") as clock,
        ):
            clock.return_value = 100.0
            for _k in range(10):
                bus.tick(self.env, "alarm")
            self.env.cr.precommit.run()
            self.assertEqual(sendone.call_count, 1)
            target, kind, payload = sendone.call_args.args
            self.assertEqual((target, kind), ("td_energy", "td_energy/update"))
            self.assertEqual(payload["kinds"], ["alarm"])
            clock.return_value = 102.0  # у межах throttle: накопичується
            bus.tick(self.env, "profile")
            self.env.cr.precommit.run()
            self.assertEqual(sendone.call_count, 1)
            clock.return_value = 106.0
            bus.tick(self.env, "kpi")
            self.env.cr.precommit.run()
            self.assertEqual(sendone.call_count, 2)
            self.assertEqual(sendone.call_args.args[2]["kinds"], ["kpi", "profile"])

    def test_payload_no_values(self):  # AC-101
        self.fresh("energy/totals/p_now", 667.0)
        with patch.object(self.registry["bus.bus"], "_sendone") as sendone:
            bus.tick(self.env, "kpi")
            self.env.cr.precommit.run()
        payload = sendone.call_args.args[2]
        self.assertEqual(set(payload), {"kinds", "ts"})
        text = repr(payload)
        for word in ("cost", "price", "kwh", "667"):
            self.assertNotIn(word, text)

    def test_actions_add_kinds(self):  # AC-102
        ev = self.Event._f3d_log("warn", "meter", "PM-QF-C2", "Лічильник. Немає даних.", ts=NOW)
        self.assertIn("alarm", self.kinds())
        self.env.cr.precommit.data.pop(bus._KEY)
        ev.with_user(self.u_eng).action_ack()
        self.assertEqual(self.kinds(), {"alarm"})
        self.env.cr.precommit.data.pop(bus._KEY)
        ev.with_user(self.u_eng).action_take()
        self.assertEqual(self.kinds(), {"alarm"})
        self.env.cr.precommit.data.pop(bus._KEY)
        plan = (
            self.env["td.energy.outage.plan"]
            .with_user(self.u_eng)
            .create(
                {
                    "node_id": self.Node.search([("code", "=", "BW-2")]).id,
                    "start": NOW + timedelta(days=1),
                    "end": NOW + timedelta(days=1, hours=2),
                }  # fmt: skip
            )
        )
        plan.action_cancel()
        self.assertIn("state", self.kinds())
        advice = self.env["td.energy.advice"]._td_demo_seed()
        self.env.cr.precommit.data.pop(bus._KEY)
        advice.with_user(self.u_eng).action_snooze()
        self.assertIn("advice", self.kinds())
