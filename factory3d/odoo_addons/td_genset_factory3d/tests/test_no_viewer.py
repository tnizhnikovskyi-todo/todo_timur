import unittest

from odoo.tests import tagged

from .test_rules import GensetCase


@tagged("post_install", "-at_install")
class TestWithoutViewer(GensetCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "td.viewer.event" in cls.env:
            raise unittest.SkipTest("td_viewer3d встановлено")

    def test_install_publish_events(self):  # AC-71
        self.assertNotIn("td.viewer.event", self.env)
        self.link.write({"last_state_json": {"state": 1, "online": 1}})
        self.link._cron_publish()
        readings = self.env["td.reading"].search([("signal_id.code", "=like", "infra/genset/GENSET/%")])
        self.assertEqual(len(readings), 26)
        self.assertTrue(self.link.message_ids.filtered(lambda m: "Стан:" in (m.body or "")))
        self.link._cron_events()
        # провайдер існує як абстрактна модель і без viewer не викликається
        self.assertIn("td.viewer.provider.genset", self.env)
