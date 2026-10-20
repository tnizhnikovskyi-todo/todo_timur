"""AC-04 (get_state, DTO), AC-05 (застарівання, зв'язок)."""

import json

from odoo.tests import tagged
from odoo.tools import file_open

from .common import TAGS, ChpCase


@tagged(*TAGS)
class TestStateApi(ChpCase):
    def test_dto(self):  # AC-04
        self.idle()
        self.put({"gas/flow": 109.0, "gen/p_kw": 400.0, "ht/q_total": 497.0, "eng/rpm": 1500.0, "cyl/A1/t": 470.0})
        dto = self.pult(self.u_user).get_state()
        for key in ("ver", "ts", "read_enabled", "stale", "age_s", "unit", "caps", "v", "u", "st", "k", "cyl", "alarm",
                    "trip", "il", "pending", "jr", "to"):  # fmt: skip
            self.assertIn(key, dto)
        self.assertFalse(dto["stale"])
        self.assertEqual(dto["unit"]["code"], "CHP")
        self.assertEqual(dto["unit"]["th"]["gas_min_bar"], 1.5)
        self.assertEqual(dto["unit"]["passport"]["engine"], "MWM TCG 3016 V16")
        self.assertEqual(dto["v"]["gas/p_in"], 2.1)
        self.assertEqual(dto["u"]["gas/p_in"], "бар")
        self.assertEqual(dto["st"]["gas/p_in"], "ok")
        self.assertIsNone(dto["v"]["cyl/B8/t"])  # не надходило
        self.assertEqual(dto["st"]["cyl/B8/t"], "stale")
        self.assertEqual(len(dto["v"]), 230)
        self.assertEqual(len(dto["cyl"]), 16)
        self.assertEqual(dto["k"]["fuel_kw"], 1035.5)
        self.assertEqual(len(dto["il"]["list"]), 14)
        self.assertEqual(len(dto["to"]), 5)
        self.assertEqual(
            dto["caps"],
            {"operate": False, "chief": False, "sim": False, "write": True, "rsw": True, "bridge": False},
        )
        self.assertIsNone(dto["alarm"])
        self.assertIsNone(dto["trip"])
        # ver змінюється зі значенням; повтор з etag — not_modified
        again = self.pult(self.u_user).get_state(etag=dto["ver"])
        self.assertEqual(again, {"not_modified": True})
        self.put({"gas/flow": 110.0})
        changed = self.pult(self.u_user).get_state(etag=dto["ver"])
        self.assertNotEqual(changed["ver"], dto["ver"])
        caps = self.pult(self.u_chief).get_state()["caps"]
        self.assertTrue(caps["operate"] and caps["chief"])
        self.assertTrue(self.pult(self.u_mgr).get_state()["caps"]["sim"])

    def test_read_disabled_and_unknown_unit(self):
        self.env["ir.config_parameter"].sudo().set_param("td.chp.read_enabled", "False")
        self.assertEqual(self.pult(self.u_user).get_state(), {"read_disabled": True})
        self.env["ir.config_parameter"].sudo().set_param("td.chp.read_enabled", "True")
        from odoo.exceptions import UserError

        with self.assertRaises(UserError):
            self.pult(self.u_user).get_state(unit="NOPE")

    def test_stale_and_comm_events(self):  # AC-05
        self.idle()
        late = self.later(200)
        self.assertEqual(late["td.chp.event"]._cron_stale(), 1)
        self.assertEqual(late["td.chp.event"]._cron_stale(), 0)  # без дубліката
        comm = self.events(kind="comm")
        self.assertEqual(len(comm), 1)
        self.assertEqual((comm.level, comm.ack_state), ("warn", "new"))
        self.assertIn("Втрата зв'язку з КГУ: немає даних", comm.text)
        dto = late["td.chp.pult"].with_user(self.u_user).get_state()
        self.assertTrue(dto["stale"])
        self.assertIsNone(dto["v"]["gas/p_in"])
        self.assertEqual(dto["st"]["gas/p_in"], "stale")
        self.put({"ctl/state": 0})  # нові дані
        comm = self.events(kind="comm")
        self.assertEqual(len(comm), 2)
        self.assertEqual(comm.filtered(lambda e: e.level == "info").text, "Зв'язок з КГУ відновлено")
        self.assertEqual(self.later(200)["td.chp.event"]._cron_stale(), 1)  # знову втрата — новий запис

    def test_cron_noop_when_read_disabled(self):
        self.idle()
        self.env["ir.config_parameter"].sudo().set_param("td.chp.read_enabled", "False")
        self.assertEqual(self.later(200)["td.chp.event"]._cron_stale(), 0)
        self.assertEqual(self.later(200)["td.chp.command"]._cron_expire(), 0)
        self.assertEqual(self.env["td.chp.maintenance.rule"]._cron_check(), 0)
        self.assertFalse(self.events(kind="comm"))

    def test_fixture_matches_dto(self):  # контракт C-chp-02: фікстура клієнта = форма DTO
        with file_open("td_chp/static/tests/fixtures/state.json", "rb") as fh:
            fixture = json.loads(fh.read().decode("utf-8"))
        self.idle()
        self.put({"cyl/A1/t": 470.0})
        self.Event._td_log(self.unit, "info", "state", "подія")
        prep = self.pult(self.u_op1).command("prepare", kind="set_cos", params={"cos": 0.97})
        self.pult(self.u_op1).command("confirm", ref=prep["ref"], token=prep["token"])
        dto = self.pult(self.u_user).get_state()
        self.assertEqual(set(fixture), set(dto))
        for key in ("unit", "caps", "k", "il"):
            self.assertEqual(set(fixture[key]), set(dto[key]), key)
        self.assertEqual(set(fixture["unit"]["th"]), set(dto["unit"]["th"]))
        self.assertEqual(set(fixture["unit"]["passport"]), set(dto["unit"]["passport"]))
        for key in ("v", "u", "st"):
            self.assertEqual(set(fixture[key]), set(dto[key]), key)
        self.assertEqual(fixture["cyl"][0].keys(), dto["cyl"][0].keys())
        self.assertEqual(len(fixture["cyl"]), len(dto["cyl"]))
        self.assertEqual(fixture["il"]["list"][0].keys(), dto["il"]["list"][0].keys())
        self.assertEqual(fixture["jr"][0].keys(), dto["jr"][0].keys())
        self.assertEqual(fixture["to"][0].keys(), dto["to"][0].keys())
        self.assertEqual({i["code"] for i in fixture["il"]["list"]}, {i["code"] for i in dto["il"]["list"]})
