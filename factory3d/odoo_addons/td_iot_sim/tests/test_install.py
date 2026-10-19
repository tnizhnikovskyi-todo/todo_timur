from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install", "f3d", "f3d_iot_sim")
class TestInstall(TransactionCase):
    def test_module_installed(self):
        mod = self.env["ir.module.module"].search([("name", "=", "td_iot_sim")])
        self.assertEqual(mod.state, "installed")

    def test_level0_models_exist(self):
        for model in ("x_f3d_signal", "x_f3d_reading"):
            self.assertIn(model, self.env, model)
            self.assertTrue(self.env["ir.model"].search([("model", "=", model)]), model)
