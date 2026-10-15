from odoo.tests import TransactionCase, tagged

from ..adapters import td_genset as td

PARAMS = {
    "read_enabled", "requests_enabled", "write_enabled", "amf_master", "offline_min", "ats_position_code",
    "ats_src1_code", "ats_src2_code", "ats_position_i_value", "ats_position_ii_value", "critical_codes",
    "publish_period_s", "service_warn_h", "migration_report",
}


@tagged("post_install", "-at_install")
class TestInstall(TransactionCase):
    def test_module_installed(self):
        mod = self.env["ir.module.module"].search([("name", "=", "factory3d_genset")])
        self.assertEqual(mod.state, "installed")

    def test_params(self):
        icp = self.env["ir.config_parameter"].sudo()
        for key in PARAMS:
            self.assertTrue(icp.search_count([("key", "=", "factory3d.genset." + key)]), key)
        self.assertEqual(icp.get_param("factory3d.genset.offline_min"), "5")

    def test_adapter_stub(self):
        with self.assertRaises(NotImplementedError):
            td.snapshot(None)
