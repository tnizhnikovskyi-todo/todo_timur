import re

from odoo.tests import HttpCase, tagged
from odoo.tools import file_open

from .common import F3dViewerBase


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestNeutralize(HttpCase, F3dViewerBase):
    """ТК-12: `data/neutralize.sql` на копії бази (транзакція відкочується)."""

    def _neutralize(self):
        self.env.flush_all()  # відкладений ORM-запис інакше перезапише результат SQL при invalidate_all
        with file_open("td_viewer3d/data/neutralize.sql") as fh:
            self.env.cr.execute(fh.read())
        self.env.invalidate_all()
        self.env.registry.clear_cache("stable")  # get_param кешується в ormcache, а SQL його обходить

    def test_neutralize_sql(self):
        params = self.env["ir.config_parameter"].sudo()
        old_token = params.get_param("td.viewer.kiosk_token")
        self.assertTrue(old_token)
        self.set_param("demo_enabled", "True")
        self._neutralize()
        self.assertEqual(params.get_param("td.viewer.demo_enabled"), "False")
        self.assertEqual(params.get_param("td.viewer.kiosk_enabled"), "False")
        self.assertEqual(params.get_param("td.viewer.bus_enabled"), "False")
        token = params.get_param("td.viewer.kiosk_token")
        self.assertRegex(token, r"^[0-9a-f]{32}$")
        self.assertNotEqual(token, old_token)
        crons = (
            self.env["ir.cron"]
            .sudo()
            .with_context(active_test=False)
            .search(
                [
                    (
                        "id",
                        "in",
                        self.env["ir.model.data"]
                        .sudo()
                        .search([("module", "=", "td_viewer3d"), ("model", "=", "ir.cron")])
                        .mapped("res_id"),
                    )
                ]
            )
        )
        self.assertGreaterEqual(len(crons), 4)
        self.assertFalse(crons.filtered("active"))
        # повторний запуск ідемпотентний і знову міняє токен
        self._neutralize()
        self.assertNotEqual(params.get_param("td.viewer.kiosk_token"), token)

    def test_neutralize_kiosk_404_and_demo_blocked(self):
        old_token = self.env["ir.config_parameter"].sudo().get_param("td.viewer.kiosk_token")
        self._neutralize()
        res = self.url_open(f"/f3d/kiosk/{old_token}/static", allow_redirects=False)
        self.assertEqual(res.status_code, 404)
        self.assertFalse(re.search(r"[0-9a-f]{32}", res.text or ""))
