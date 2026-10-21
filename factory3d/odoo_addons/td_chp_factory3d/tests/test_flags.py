"""AC-B09 (флаги): `caps.bridge`, `caps.rsw` дзеркалить `td.energy_control.remote_switching_enabled`."""

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TAGS, BridgeCase


@tagged(*TAGS)
class TestFlags(BridgeCase):
    def test_caps_bridge_and_rsw(self):
        self.idle()
        caps = self.pult(self.u_en1).get_state()["caps"]
        self.assertTrue(caps["bridge"])
        self.assertTrue(caps["rsw"])
        self.assertTrue(caps["operate"])
        self.env["ir.config_parameter"].sudo().set_param("td.energy_control.remote_switching_enabled", "False")
        self.assertFalse(self.pult(self.u_en1).get_state()["caps"]["rsw"])
        # власний параметр td_chp на `rsw` у мосту не впливає
        self.env["ir.config_parameter"].sudo().set_param("td.chp.remote_switching_enabled", "True")
        self.assertFalse(self.pult(self.u_en1).get_state()["caps"]["rsw"])

    def test_remote_switching_off_start_rejected_stop_passes(self):
        self.idle()
        self.env["ir.config_parameter"].sudo().set_param("td.energy_control.remote_switching_enabled", "False")
        with self.assertRaises(UserError) as err:
            self.prepare("start")
        self.assertIn("remote_switching_enabled", str(err.exception))
        self.put({"ctl/state": 2, "eng/rpm": 1500})
        res = self.prepare("stop")
        self.assertFalse(res["blocked"])
        self.assertEqual(res["kind"], "stop")

    def test_il_has_no_rsw_item_in_bridge(self):
        self.idle()
        il = self.pult(self.u_en1).get_state()["il"]
        self.assertEqual(len(il["list"]), 13)  # 14 умов пуску без `rsw`: його замінює стоп-кран td_energy_control
        self.assertNotIn("rsw", [c["code"] for c in il["list"]])

    def test_read_only_user_sees_state_but_cannot_command(self):
        self.idle()
        self.assertTrue(self.pult(self.u_view).get_state()["caps"]["bridge"])
        self.assertFalse(self.pult(self.u_view).get_state()["caps"]["operate"])
