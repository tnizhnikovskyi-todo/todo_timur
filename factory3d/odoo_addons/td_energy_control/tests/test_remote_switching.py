"""AC-309, AC-310: дистанційне перемикання (D-46, Q-27): відмова при `remote_switching_enabled=False`."""

from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import convert_file

from ..tools import kinds
from .common import TAGS, TestControlCommon


@tagged(*TAGS)
class TestRemoteSwitching(TestControlCommon):
    def test_remote_switching_refused(self):  # AC-309
        self._enable_control(write=True, remote=False)
        for code in kinds.REMOTE_GATED:
            with self.assertRaisesRegex(UserError, "Дистанційне перемикання вимкнено"), self.cr.savepoint():
                self.ctl(self.u_chief).prepare(code)
        tiles = {t["code"]: t for t in self.ctl(self.u_chief).get_control()["commands"]}
        for code in ("qs_close", "bess_discharge", "chp_start", "genset_test"):
            self.assertFalse(tiles[code]["enabled"], code)
            self.assertIn("Дистанційне перемикання", tiles[code]["disabled_reason"])
        for code in ("bess_charge", "light_break", "vent_eco", "air_setpoint"):
            self.assertTrue(tiles[code]["enabled"], code)
        prep = self.ctl(self.u_chief).prepare("bess_charge")  # не зачеплена
        self.assertEqual(prep["kind"], "bess_charge")
        self._enable_control(write=True, remote=True)
        prep = self.ctl(self.u_chief).prepare("qs_close")
        self._enable_control(write=True, remote=False)
        with self.assertRaisesRegex(UserError, "Дистанційне перемикання вимкнено"):
            self.ctl(self.u_chief).confirm(prep["token"])

    def test_remote_switching_default_and_flags(self):  # AC-310
        icp = self.env["ir.config_parameter"].sudo()
        key = "td.energy_control.remote_switching_enabled"
        icp.set_param(key, "False")
        from ..tools import config_builder

        cfg = config_builder.build(self.env)
        self.assertFalse(cfg["flags"]["remote_switching_enabled"])
        e0 = config_builder.etag(cfg)
        icp.set_param(key, "True")
        cfg = config_builder.build(self.env)
        self.assertTrue(cfg["flags"]["remote_switching_enabled"])
        self.assertNotEqual(config_builder.etag(cfg), e0)
        self.assertEqual(self.ctl(self.u_chief).prepare("qs_close")["kind"], "qs_close")
        self.assertEqual(self.ctl(self.u_chief).get_control()["meta"]["remote_switching_enabled"], True)

    def test_demo_data_enables_remote(self):  # AC-310: demo-дані вмикають параметр
        icp = self.env["ir.config_parameter"].sudo()
        key = "td.energy_control.remote_switching_enabled"
        icp.set_param(key, "False")
        convert_file(self.env, "td_energy_control", "demo/ir_config_parameter_demo.xml", {}, mode="init", kind="demo")
        self.assertEqual(icp.get_param(key), "True")
