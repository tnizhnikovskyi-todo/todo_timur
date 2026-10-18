from odoo.tests import HttpCase, tagged

from .common import F3dViewerBase

KIOSK_JS = """
(async () => {
    const wait = (ms) => new Promise((r) => setTimeout(r, ms));
    const t0 = Date.now();
    const need = (sel) => document.querySelector(sel);
    while (!need(".o_f3d_is_kiosk .o_f3d_stage")) {
        if (Date.now() - t0 > 60000) { throw new Error("кіоск не змонтовано"); }
        await wait(200);
    }
    while (/підключення/.test((need(".o_f3d_odoo-state") || {}).textContent || "підключення")) {
        if (Date.now() - t0 > 60000) { throw new Error("кіоск не завантажив дані"); }
        await wait(200);
    }
    if (need(".o_main_navbar") || need(".o_navbar")) { throw new Error("у кіоску є навігація Odoo"); }
    if (need(".o_f3d_c-open")) { throw new Error("у кіоску є «Відкрити в Odoo»"); }
    console.log("test successful");
})();
"""


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestViewerTours(HttpCase, F3dViewerBase):
    """Тури (AC-08, AC-22, AC-23, AC-28): кнопка «Показати в 3D», зворотний перехід, сторінка кіоска."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Workcenter = env["mrp.workcenter"]
        cls.wc_saw = Workcenter.search([("td_code", "=", "SAW-1")], limit=1) or Workcenter.create(
            {"name": "Пила TST", "code": "SAW1TST", "td_code": "SAW-1"})
        product = env["product.product"].create({"name": "TST tour fin", "is_storable": True})
        comp = env["product.product"].create({"name": "TST tour cmp", "is_storable": True})
        bom = env["mrp.bom"].create({
            "product_tmpl_id": product.product_tmpl_id.id, "product_id": product.id, "product_qty": 1,
            "bom_line_ids": [(0, 0, {"product_id": comp.id, "product_qty": 1})],
            "operation_ids": [(0, 0, {"name": "Op", "workcenter_id": cls.wc_saw.id, "time_cycle_manual": 10})]})
        cls.mo = env["mrp.production"].create({"product_id": product.id, "bom_id": bom.id, "product_qty": 1})
        cls.mo.action_confirm()

    def test_show_in_3d_tour(self):
        """AC-23: кнопка на формі МО відкриває дію f3d_viewer.action з params.mo."""
        self.start_tour("/odoo/action-mrp.mrp_production_action/%d?debug=1" % self.mo.id,
                        "f3d_show_in_3d_tour", login="admin", timeout=180)

    def test_click_open_record_tour(self):
        """AC-08: клік по SAW-1 -> «Відкрити в Odoo» -> форма робочого центру."""
        # f3d_test в params дії -> нульовий рендерер (програмний WebGL у headless Chrome гальмує тур)
        self.env.ref("td_viewer3d.action_td_viewer").params = {"f3d_test": 1}
        self.start_tour("/odoo/action-td_viewer3d.action_td_viewer?debug=1",
                        "f3d_click_open_record_tour", login="admin", timeout=180)

    def test_kiosk_page_renders(self):
        """AC-28 (браузер): сторінка кіоска монтує переглядач без навігації Odoo (без tour-менеджера)."""
        token = self.env["ir.config_parameter"].sudo().get_param("td.viewer.kiosk_token")
        self.set_param("kiosk_enabled", "True")
        self.browser_js("/f3d/kiosk/%s?f3d_test=1&tab=production" % token, KIOSK_JS, timeout=180)
