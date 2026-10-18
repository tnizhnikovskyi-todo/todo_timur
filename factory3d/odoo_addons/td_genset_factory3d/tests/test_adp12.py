"""ADP-12 (W2, R-67): `start_test` / `test_facts` — тест ДГУ без навантаження (AC-275, AC-276)."""

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from ..adapters import td_genset as td


@tagged("post_install", "-at_install", "td_genset_factory3d")
class TestAdp12(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.genset = cls.env["td.genset"].create(
            {
                "name": "ADP-12",
                "controller_model_id": cls.env.ref("td_genset.controller_hgm6120n").id,
                "power_kw": 12.0,
                "tank_volume_l": 145.0,
            }
        )
        cls.user = new_test_user(cls.env, login="adp12_user", groups="base.group_user")

    def test_start_test_idle(self):  # AC-275
        res = td.start_test(self.genset, "idle", self.user)
        self.assertEqual(set(res), {"accepted", "minutes", "test_end", "ref"})
        self.assertTrue(res["accepted"])
        self.assertEqual(res["ref"], {"model": "td.genset", "id": self.genset.id})
        minutes = self.env["td.genset.config"].sudo().get().test_minutes or 3
        self.assertEqual(res["minutes"], minutes)
        self.assertEqual(self.genset.test_mode, "idle")
        self.assertEqual(self.genset.control_source, "test")
        self.assertEqual(res["test_end"], self.genset.test_end.strftime("%Y-%m-%dT%H:%M:%SZ"))
        with self.assertRaisesRegex(UserError, "Тест уже йде"):
            td.start_test(self.genset, "idle", self.user)

    def test_load_refused(self):  # AC-275
        with self.assertRaisesRegex(UserError, "Лише тест без навантаження"):
            td.start_test(self.genset, "load", self.user)
        self.assertFalse(self.genset.test_end)

    def test_test_facts(self):  # AC-276
        keys = {"fuel_pct", "running", "test_running", "island", "coolant_c"}
        empty = td.test_facts(self.genset)
        self.assertEqual(set(empty), keys)
        self.assertEqual(
            (empty["fuel_pct"], empty["coolant_c"], empty["running"], empty["test_running"]), (None, None, False, False)
        )
        self.assertFalse(empty["island"])
        reading = self.env["td.genset.reading"].create(
            {"genset_id": self.genset.id, "relay_id": 1, "ts": fields.Datetime.now()}
        )
        self.genset.write(
            {"last_reading_id": reading.id, "link_state": "online", "genset_status": "7", "mains_ok": False,
             "fuel_level": 78.0, "water_temp": 42.0, "current_a": 1.0, "current_b": 1.0, "current_c": 1.0,
             "gen_uab": 400.0, "gen_ubc": 400.0, "gen_uca": 400.0, "oil_pressure": 300.0}
        )  # fmt: skip
        facts = td.test_facts(self.genset)
        self.assertEqual((facts["fuel_pct"], facts["coolant_c"]), (78.0, 42.0))
        self.assertTrue(facts["running"])
        self.assertTrue(facts["island"])
        td.start_test(self.genset, "idle", self.user)
        self.assertTrue(td.test_facts(self.genset)["test_running"])
