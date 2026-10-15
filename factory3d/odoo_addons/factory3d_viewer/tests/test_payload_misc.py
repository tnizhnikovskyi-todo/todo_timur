from unittest.mock import patch

from odoo.tests import tagged

from .common import F3dViewerBase


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestQualityMaintenancePeople(F3dViewerBase):
    """Провайдери quality (M-01d), maintenance (M-01e), people (M-01f)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        # у Odoo 19 звичайний користувач бачить лише обладнання, яке «відстежує» (ir.rule maintenance)
        cls.user_maint = cls._make_user("f3d_maint", [
            "base.group_user", "factory3d_base.group_f3d_user", "maintenance.group_equipment_manager"])
        cls.category = env["maintenance.equipment.category"].create({"name": "TST Навантажувачі"})
        cls.equipment = env["maintenance.equipment"].create({
            "name": "TST forklift", "f3d_code": "TST-FL-1", "category_id": cls.category.id, "serial_no": "SN-123"})
        stage_new = env["maintenance.stage"].search([("done", "=", False)], limit=1)
        cls.request = env["maintenance.request"].create({
            "name": "TST гідравліка", "equipment_id": cls.equipment.id, "stage_id": stage_new.id,
            "maintenance_type": "corrective", "priority": "2"})
        cls.employee = env["hr.employee"].create({
            "name": "TST оператор", "f3d_code": "OP-TST-9", "job_title": "Оператор"})

    # --- M-01e
    def test_equipment_and_requests(self):
        data = self.payload(self.user_maint)
        eq = data["equipment"].get("TST-FL-1")
        self.assertTrue(eq)
        self.assertEqual((eq["name"], eq["category"], eq["serial"]), ("TST forklift", "TST Навантажувачі", "SN-123"))
        self.assertEqual(eq["maintenance_request"], "TST гідравліка")
        req = next(r for r in data["maintenance_requests"] if r["equipment"] == "TST-FL-1")
        self.assertEqual((req["id"], req["stage"], req["priority"], req["maintenance_type"]),
                         ("TST гідравліка", self.request.stage_id.name, "2", "corrective"))
        self.assertEqual(data["meta"]["sections"]["equipment"], "live")

    def test_serial_equal_code_omitted(self):
        self.equipment.serial_no = "TST-FL-1"
        self.assertNotIn("serial", self.payload(self.user_maint)["equipment"]["TST-FL-1"])

    def test_closed_request_old_is_dropped(self):
        done = self.env["maintenance.stage"].search([("done", "=", True)], limit=1)
        if not done:
            self.skipTest("немає закритої стадії")
        self.request.write({"stage_id": done.id})
        self.request.write({"close_date": "2020-01-01"})
        data = self.payload(self.user_maint)
        self.assertFalse([r for r in data["maintenance_requests"] if r["equipment"] == "TST-FL-1"])
        self.assertNotIn("maintenance_request", data["equipment"]["TST-FL-1"])

    # --- M-01f
    def test_people_public_model_no_sudo(self):
        """AC-66: читання hr.employee.public від користувача запиту, hr.employee не читається."""
        calls = []
        pub = type(self.env["hr.employee.public"])
        emp = type(self.env["hr.employee"])
        orig_pub, orig_emp = pub.search_read, emp.search_read

        def spy_pub(this, *a, **kw):
            calls.append("public")
            return orig_pub(this, *a, **kw)

        def spy_emp(this, *a, **kw):
            calls.append("employee")
            return orig_emp(this, *a, **kw)
        with patch.object(pub, "search_read", spy_pub), patch.object(emp, "search_read", spy_emp):
            data = self.payload(self.user_mrp_only)
        self.assertIn("public", calls)
        self.assertNotIn("employee", calls)
        rec = data["employees"]["OP-TST-9"]
        self.assertEqual(rec["name"], "TST оператор")
        self.assertEqual(rec["job"], "Оператор")
        self.assertEqual(set(rec) & {"name", "job", "department", "shift"}, {"name", "job", "department", "shift"})
        self.assertFalse(set(rec) - {"name", "job", "department", "shift", "workcenter", "current_workorder",
                                     "present"})

    # --- M-01d
    def test_quality_missing_without_model(self):
        data = self.payload(self.user_f3d)
        if "quality.check" in self.env:
            self.assertIn(data["meta"]["sections"]["quality_checks"], ("live", "denied"))
        else:
            self.assertEqual(data["quality_checks"], [])
            self.assertEqual(data["meta"]["sections"]["quality_checks"], "missing")
