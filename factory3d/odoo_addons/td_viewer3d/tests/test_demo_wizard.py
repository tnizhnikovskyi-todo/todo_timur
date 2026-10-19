import difflib
import os
from unittest.mock import patch

from odoo import SUPERUSER_ID
from odoo.exceptions import UserError
from odoo.tests import tagged

from odoo.addons.td_viewer3d.wizard import demo_steps
from odoo.addons.td_viewer3d.wizard.demo_wizard import LABELS
from odoo.addons.td_viewer3d.wizard.orm_proxy import OrmProxy, key

from .common import F3dViewerBase

PLANT = os.path.join(os.path.dirname(__file__), "..", "..", "..", "plant")
DIFF_LIMIT = 80
NEEDED = ("purchase_stock", "sale_stock", "hr_attendance", "stock_delivery", "stock_picking_batch", "stock_fleet")


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestDemoWizardGuard(F3dViewerBase):
    """Швидкі перевірки майстра демо (без заливки)."""

    def _wizard(self):
        return self.env["td.demo.wizard"].with_user(self.user_admin).create({})

    def test_blocked_on_prod(self):
        """AC-35: demo_enabled=False → UserError, нічого не поставлено в чергу."""
        self.set_param("demo_enabled", "False")
        wiz = self._wizard()
        self.assertFalse(wiz.enabled)
        with self.assertRaisesRegex(UserError, "Заливка демо вимкнена на цій базі"):
            wiz.action_run()
        self.assertEqual(wiz.state, "draft")
        self.assertFalse(self.env["ir.config_parameter"].sudo().get_param("td.viewer.demo_queue"))

    def test_steps_default_35(self):
        wiz = self._wizard()
        self.assertEqual(len(wiz.step_ids), 35)
        self.assertTrue(all(wiz.step_ids.mapped("selected")))
        self.assertEqual(wiz.step_ids.sorted("sequence").mapped("name"), demo_steps.STEPS)
        self.assertEqual(list(LABELS), demo_steps.STEPS)
        wiz.action_select_none()
        self.assertFalse(any(wiz.step_ids.mapped("selected")))
        wiz.action_select_all()
        self.assertTrue(all(wiz.step_ids.mapped("selected")))

    def test_run_queues(self):
        self.set_param("demo_enabled", "True")
        self.set_param("demo_clock", "2026-10-12 10:30")
        wiz = self._wizard()
        wiz.demo_clock = "2026-10-13 09:00"
        wiz.step_ids.filtered(lambda s: s.name != "settings").write({"selected": False})
        action = wiz.action_run()
        self.assertEqual(action["res_id"], wiz.id)
        self.assertEqual(wiz.state, "queued")
        cron = self.env.ref("td_viewer3d.cron_td_demo")
        self.assertTrue(cron.active)
        self.assertEqual(self.env["ir.config_parameter"].sudo().get_param("td.viewer.demo_clock"), "2026-10-13 09:00")
        self.assertIn('"settings"', self.env["ir.config_parameter"].sudo().get_param("td.viewer.demo_queue"))

    def test_steps_from_form_without_name(self):
        """Вебклієнт не шле readonly name: кроки з форми валідні, ключ відновлюється."""
        wiz = (
            self.env["td.demo.wizard"]
            .with_user(self.user_admin)
            .create(
                {
                    "step_ids": [
                        (0, 0, {"label": LABELS["views"], "sequence": 40, "selected": True}),
                        (0, 0, {"label": "довільна назва", "sequence": 310, "selected": True}),
                    ]
                }
            )
        )
        self.assertEqual(wiz.step_ids.mapped("name"), ["views", "iot_module"])

    def test_cron_run_does_not_touch_cron(self):
        """Крон не може змінювати сам себе (Odoo 19): _cron_run доходить до done без запису в ir.cron."""
        self.set_param("demo_enabled", "True")
        wiz = self._wizard()
        wiz.step_ids.write({"selected": False})
        wiz.step_ids.filtered(lambda s: s.name in ("views", "iot_module")).write({"selected": True})
        wiz.action_run()
        self.env["td.demo.wizard"].flush_model()

        def forbidden(self, *a, **kw):
            raise UserError("cron currently being executed")

        with patch.object(type(self.env["ir.cron"]), "write", forbidden):
            wiz.with_user(SUPERUSER_ID)._cron_run()
        wiz.invalidate_recordset()
        self.assertEqual((wiz.state, wiz.progress), ("done", 100))
        self.assertIn("cycle_check:", wiz.log)
        # після завершення кнопка «Оновити» вимикає крон, і новий запуск можливий
        wiz.action_refresh()
        self.assertFalse(self.env.ref("td_viewer3d.cron_td_demo").active)
        wiz2 = self._wizard()
        wiz2.action_run()
        self.assertEqual(wiz2.state, "queued")

    def test_rerun_after_error(self):
        self.set_param("demo_enabled", "True")
        wiz = self._wizard()
        wiz.step_ids.write({"selected": False})
        wiz.step_ids.filtered(lambda s: s.name == "calendar").write({"selected": True})
        wiz.action_run()
        with (
            patch.object(demo_steps.Runner, "run", side_effect=RuntimeError("boom")),
            self.assertLogs("odoo.addons.td_viewer3d.wizard.demo_wizard", "ERROR"),
        ):
            wiz.with_user(SUPERUSER_ID)._cron_run()
        wiz.invalidate_recordset()
        self.assertEqual(wiz.state, "error")
        self.assertIn("boom", wiz.step_ids.filtered(lambda s: s.name == "calendar").message)
        wiz2 = self._wizard()
        wiz2.action_run()  # не заблоковано
        self.assertEqual(wiz2.state, "queued")

    def test_orm_proxy(self):
        o = OrmProxy(self.env)
        pid = o("res.partner", "create", {"name": "ZZ proxy"})
        self.assertIsInstance(pid, int)
        self.assertEqual(o("res.partner", "search", [["id", "=", pid]]), [pid])
        o("res.partner", "write", [pid], {"comment": "x"})
        row = o("res.partner", "read", [pid], ["name", "create_date"])[0]
        self.assertEqual(row["name"], "ZZ proxy")
        self.assertIsInstance(row["create_date"], str)
        self.assertTrue(o.has("res.partner"))
        self.assertFalse(o.has("x.no.such"))
        self.assertEqual(o.installed("base"), {"base": "installed"})
        self.assertEqual(o.uid, self.env.uid)
        o("res.partner", "unlink", [pid])
        self.assertFalse(o("res.partner", "search_count", [["id", "=", pid]]))
        self.assertEqual(key("loc", "A-1"), "loc_a_1")
        self.assertTrue(key("партнер").startswith("_") or "_" in key("партнер"))

    def test_demo_steps_diff(self):
        """A-08: відмінність demo_steps.py від plant/odoo_push.py + odoo_flows.py ≤ 80 рядків."""
        flows = os.path.join(PLANT, "odoo_flows.py")
        push = os.path.join(PLANT, "odoo_push.py")
        if not (os.path.exists(flows) and os.path.exists(push)):
            self.skipTest("plant/ немає в збірці модуля")
        with open(demo_steps.__file__, encoding="utf-8") as fh:
            ours = fh.read()
        body = ours.split("# ===== порт plant/odoo_flows.py + plant/odoo_push.py =====\n", 1)[1]
        body = body.split("\n\n# ===== Runner =====", 1)[0]

        def read(path, start, stop=None):
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            text = text[text.index(start) :]
            return text[: text.index(stop)] if stop else text

        theirs = read(flows, "# зони, де товар").rstrip("\n") + "\n\n\n" + read(push, "MOD = ", "def main").rstrip("\n")
        diff = [
            ln
            for ln in difflib.unified_diff(theirs.splitlines(), body.rstrip("\n").splitlines(), lineterm="", n=0)
            if ln[:1] in "+-" and not ln.startswith(("+++", "---"))
        ]
        self.assertLessEqual(len(diff), DIFF_LIMIT, "\n".join(diff[:40]))


@tagged("post_install", "-at_install", "f3d", "f3d_viewer", "f3d_demo")
class TestDemoWizard(F3dViewerBase):
    """AC-33. Повільний (≈ хвилини): виконується, лише коли на базі стоять CE-модулі заливки
    (інакше skipTest, щоб типовий прогін /td_viewer3d лишався швидким); окремий прогін
    /td_viewer3d:TestDemoWizard.

    База з td_factory3d + td_viewer3d і CE-модулями кроку «modules»
    (F3D_TEST_INSTALL=td_viewer3d,purchase_stock,sale_stock,hr_attendance,stock_delivery,
    stock_picking_batch,stock_fleet)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        missing = [
            m
            for m in NEEDED
            if cls.env["ir.module.module"].search_count([("name", "=", m), ("state", "=", "installed")]) == 0
        ]
        if missing:
            cls.skipTest(cls, "заливка потребує модулів: " + ", ".join(missing))
        cls.env["ir.config_parameter"].sudo().set_param("td.viewer.demo_enabled", "True")

    def _run_all(self):
        wiz = self.env["td.demo.wizard"].with_user(self.user_admin).create({})
        wiz.action_run()
        self.assertEqual(wiz.state, "queued")
        wiz.with_user(SUPERUSER_ID)._cron_run()  # крон працює від base.user_root
        wiz.invalidate_recordset()
        return wiz

    def _count(self, model):
        return self.env["ir.model.data"].sudo().search_count([("module", "=", "factory3d"), ("model", "=", model)])

    def test_run_all_on_empty_db(self):
        """AC-33: усі 35 кроків, цикл замкнений, WH/MO/00231 і 35 центрів."""
        wiz = self._run_all()
        failed = [(s.name, s.message) for s in wiz.step_ids if s.state == "error"]
        self.assertEqual(wiz.state, "done", f"{failed}\n{(wiz.log or '')[-1500:]}")
        self.assertEqual(len(wiz.step_ids), 35)
        self.assertTrue(all(s.state in ("done", "skipped") for s in wiz.step_ids))
        skipped = {s.name for s in wiz.step_ids if s.state == "skipped"}
        self.assertTrue({"views", "iot_module"} <= skipped, skipped)
        line = next(x for x in wiz.log.splitlines() if x.startswith("cycle_check:"))
        rest = [i for i in line[len("cycle_check:") :].split(";") if i.strip() not in ("OK", "")]
        self.assertEqual(rest, [], line)
        self.assertEqual(wiz.progress, 100)
        self.assertGreater(wiz.new_records, 0)
        self.assertTrue(self.env["mrp.production"].search([("name", "=", "WH/MO/00231")]))
        self.assertEqual(self._count("mrp.workcenter"), 35)
        self.assertEqual(self._count("mrp.production"), 32)
        wiz.action_refresh()  # поза кроном крон вимикається
        self.assertFalse(self.env.ref("td_viewer3d.cron_td_demo").active)

    def test_idempotent_rerun(self):
        """AC-33: повторний запуск не створює нових записів."""
        self._run_all()
        wiz = self._run_all()
        self.assertEqual(wiz.state, "done", (wiz.log or "")[-1500:])
        self.assertEqual(wiz.new_records, 0)
