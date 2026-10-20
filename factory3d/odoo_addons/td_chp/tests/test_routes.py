"""AC-18 (доступ), AC-20 (шина td_chp/update): HTTP/JSON маршрути API-01…07 і права."""

import json
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from ..tools import bus
from .common import TAGS, ChpCase, ChpHttpCase


@tagged(*TAGS)
class TestRoutes(ChpHttpCase):
    def rpc(self, path, **params):
        body = json.dumps({"jsonrpc": "2.0", "method": "call", "params": params})
        resp = self.url_open(path, data=body, headers={"Content-Type": "application/json"})
        return resp.json()

    def error_name(self, res):
        self.assertIn("error", res, res)
        return res["error"].get("data", {}).get("name", "")

    def test_no_session(self):  # AC-18
        for path in ("/td_chp/state", "/td_chp/journal", "/td_chp/cmd"):
            self.assertIn("error", self.rpc(path))

    def test_no_group(self):
        self.authenticate("chp_plain", "chp_plain")
        res = self.rpc("/td_chp/state")
        self.assertIn("AccessError", self.error_name(res))
        self.assertIn("Немає доступу до Когенерації", res["error"]["data"]["message"])

    def test_user_read_only(self):
        self.idle()
        self.authenticate("chp_user", "chp_user")
        state = self.rpc("/td_chp/state")["result"]
        self.assertEqual(state["unit"]["code"], "CHP")
        self.assertEqual(self.rpc("/td_chp/state", etag=state["ver"])["result"], {"not_modified": True})
        self.assertEqual(len(self.rpc("/td_chp/trend", range_h=1)["result"]["series"]["pel"]), 120)
        self.assertIn("items", self.rpc("/td_chp/journal", limit=5)["result"])
        self.assertEqual(len(self.rpc("/td_chp/maintenance")["result"]), 5)
        for path, kw in (
            ("/td_chp/ack", {}),
            ("/td_chp/cmd", {"op": "prepare", "kind": "start"}),
            ("/td_chp/maintenance", {"rule_id": 1}),
            ("/td_chp/sim", {"op": "list"}),
        ):
            self.assertIn("AccessError", self.error_name(self.rpc(path, **kw)), path)

    def test_operator_and_manager(self):
        self.idle()
        self.authenticate("chp_op1", "chp_op1")
        self.assertEqual(self.rpc("/td_chp/ack")["result"], {"acked": 0})
        prep = self.rpc("/td_chp/cmd", op="prepare", kind="set_cos", params={"cos": 0.97})["result"]
        self.assertTrue(prep["token"])
        res = self.rpc("/td_chp/cmd", op="confirm", ref=prep["ref"], token=prep["token"])["result"]
        self.assertEqual(res["state"], "queued")
        self.assertEqual(self.rpc("/td_chp/cmd", op="get", ref=prep["ref"])["result"]["state"], "queued")
        self.assertIn("AccessError", self.error_name(self.rpc("/td_chp/sim", op="list")))  # sim — лише менеджер
        done = self.rpc("/td_chp/maintenance", rule_id=self.env.ref("td_chp.rule_oil").id)["result"]
        self.assertEqual(len(done), 5)
        self.authenticate("chp_mgr", "chp_mgr")
        sim = self.rpc("/td_chp/sim", op="list")["result"]
        if "td.sim.scenario" not in self.env:
            self.assertEqual(sim, {"available": False, "scenarios": []})
        else:
            self.assertTrue(sim["available"])


@tagged(*TAGS)
class TestBusAndAccess(ChpCase):
    def sendone(self):
        return patch.object(self.registry["bus.bus"], "_sendone")

    def test_bus_throttle(self):  # AC-20
        bus.reset()
        with self.sendone() as sendone:
            self.idle()
            self.env.cr.precommit.run()
            self.assertEqual(sendone.call_count, 1)
            channel, mtype, payload = sendone.call_args.args
            self.assertEqual((channel, mtype), ("td_chp", "td_chp/update"))
            self.assertIn("state", payload["kinds"])
            self.assertNotIn("ts", payload)  # повідомлення без даних
            self.put({"ctl/state": 1})  # у межах throttle — окремого повідомлення немає
            self.env.cr.precommit.run()
            self.assertEqual(sendone.call_count, 1)
            self.assertIn("state", bus._STATE[self.env.cr.dbname]["pending"])
        bus.reset()
        with self.sendone() as sendone:
            self.put({"ctl/state": 2})
            self.env.cr.precommit.run()
            self.assertEqual(sendone.call_count, 1)

    def test_bus_failure_swallowed(self):  # AC-20
        bus.reset()
        with self.sendone() as sendone:
            sendone.side_effect = RuntimeError("шина недоступна")
            self.idle()
            self.env.cr.precommit.run()  # не кидає
        self.assertEqual(self.unit.state_code, 0)
        self.assertEqual(self.Signal.search([("code", "=", "chp/gas/p_in")]).last_value, 2.1)  # ingest відпрацював

    def test_bus_kinds_for_commands_and_events(self):
        bus.reset()
        self.idle()
        self.env.cr.precommit.run()
        bus.reset()
        with self.sendone() as sendone:
            prep = self.pult(self.u_op1).command("prepare", kind="set_cos", params={"cos": 0.97})
            self.pult(self.u_op1).command("confirm", ref=prep["ref"], token=prep["token"])
            self.env.cr.precommit.run()
            kinds = sendone.call_args.args[2]["kinds"]
            self.assertIn("command", kinds)
            self.assertIn("journal", kinds)

    def test_access_matrix(self):  # AC-18
        for fn, user in (
            (lambda p: p.get_state(), self.u_plain),
            (lambda p: p.get_trend(), self.u_plain),
            (lambda p: p.get_journal(), self.u_plain),
            (lambda p: p.get_maintenance(), self.u_plain),
            (lambda p: p.ack(), self.u_user),
            (lambda p: p.command("prepare", kind="start"), self.u_user),
            (lambda p: p.maintenance_done(1), self.u_user),
            (lambda p: p.sim("list"), self.u_op1),
            (lambda p: p.sim("list"), self.u_user),
        ):
            with self.assertRaises(AccessError):
                fn(self.pult(user))
        with self.assertRaises(AccessError):
            self.pult(self.u_admin).get_state()  # admin без груп КГУ
        self.assertTrue(self.pult(self.u_op1).get_state())
        self.assertTrue(self.pult(self.u_chief).get_state())
        with self.assertRaises(UserError):
            self.pult(self.u_user).get_state(unit="ZZZ")
