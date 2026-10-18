"""M-10, R-28: огляд будівлі (AC-46, AC-47, AC-63)."""

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import new_test_user, tagged

from .common import F3DBmsCase


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestOverview(F3DBmsCase):
    def _data(self, user=None):
        return self.env["td.bms.overview"].with_user(user or self.user_reader).get_overview_data()

    def test_structure_counts(self):
        data = self._data()
        for key in ("ts", "work_time", "plan", "zones", "groups", "panels", "units", "kpi", "heat", "deviations"):
            self.assertIn(key, data)
        self.assertTrue(data["ts"].endswith("Z"))
        self.assertEqual(data["plan"], {"width": 150.0, "depth": 72.0})
        self.assertEqual(len(data["zones"]), 34)
        for zone in data["zones"]:
            self.assertGreaterEqual(len(zone["polygon"]), 3, zone["code"])
        self.assertEqual(len(data["groups"]), 32)
        self.assertEqual(len(data["panels"]), 3)
        lp1 = next(p for p in data["panels"] if p["code"] == "LP-1")
        self.assertEqual(lp1["x"], 40.0)
        self.assertEqual(len(data["units"]), 29)
        rv5 = next(u for u in data["units"] if u["code"] == "RV-05")
        self.assertEqual((rv5["x"], rv5["y"]), (21.5, 33.5))
        kpi = data["kpi"]
        self.assertEqual((kpi["groups_total"], kpi["units_total"]), (32, 29))
        self.assertEqual(data["heat"]["design"]["total"], 753)
        self.assertLessEqual(len(data["deviations"]), 50)
        zone_groups = {z["code"]: z["group"] for z in data["zones"]}
        self.assertEqual(zone_groups["Z-CUT"], "LT-CUT")

    def test_open_deviations(self):
        sig = self.env["td.signal"].search([("module", "=", "bms")], limit=1)
        before = self._data()["kpi"]["open_deviations"]
        self.env["td.bms.deviation"].create(
            {
                "name": "Тест огляду",
                "signal_id": sig.id,
                "rule": "other",
                "started": "2026-10-14 08:00:00",
                "object_code": "LT-CUT",
            }
        )
        data = self._data()
        self.assertEqual(data["kpi"]["open_deviations"], before + 1)
        row = next(d for d in data["deviations"] if d["name"] == "Тест огляду")
        self.assertEqual(row["started"], "2026-10-14 11:00")  # Київ, літній час UTC+3

    def test_access_partial(self):
        user = new_test_user(self.env, "bms_ov_none", groups="base.group_user")
        data = self._data(user)
        self.assertEqual((data["groups"], data["panels"], data["units"], data["deviations"]), ([], [], [], []))
        self.assertEqual(data["kpi"]["units_total"], 0)

    def test_action_open(self):
        Overview = self.env["td.bms.overview"].with_user(self.user_reader)
        group = self.env["td.bms.light.group"].search([("code", "=", "LT-CUT")])
        act = Overview.action_open("td.bms.light.group", group.id, "form")
        self.assertEqual(
            (act["type"], act["res_model"], act["res_id"]), ("ir.actions.act_window", group._name, group.id)
        )
        act = Overview.action_open("td.bms.light.group", group.id, "show3d")
        self.assertEqual(act, group.action_f3d_show())
        for model in ("res.users", "res.partner"):
            with self.assertRaises(AccessError):
                Overview.action_open(model, 1, "form")


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestCommandChatter(F3DBmsCase):
    def test_failed_command_posts_once(self):
        """§11 п. 11: чаттер групи отримує «Команда #id: стан — помилка» один раз."""
        group = self.env["td.bms.light.group"].search([("code", "=", "LT-CUT")])
        self.env["ir.config_parameter"].sudo().set_param("td.telemetry.write_enabled", "True")
        group.level_signal_id.sudo().write({"write_enabled": True})
        group.level_signal_id.source_id.sudo().write({"write_enabled": True})
        cmd = (
            self.env["td.command"]
            .sudo()
            .create({"signal_id": group.level_signal_id.id, "value": 50.0, "origin": "bms"})
        )
        cmd.write({"state": "failed", "error": "роутер не відповідає"})
        check = self.env["td.bms.check"]
        now = fields.Datetime.now()
        check._notify_commands(now)
        check._notify_commands(now)
        marker = "Команда #%d" % cmd.id
        msgs = group.message_ids.filtered(lambda m: marker in (m.body or ""))
        self.assertEqual(len(msgs), 1)
        self.assertIn("роутер не відповідає", msgs.body)
        other = self.env["td.command"].sudo().create({"signal_id": group.level_signal_id.id, "origin": "x"})
        other.write({"state": "failed", "error": "e"})
        check._notify_commands(now)
        self.assertFalse(group.message_ids.filtered(lambda m: "Команда #%d:" % other.id in (m.body or "")))
