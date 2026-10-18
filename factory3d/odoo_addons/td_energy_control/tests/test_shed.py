"""AC-171…AC-176: приоритети скидання."""

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .common import TAGS, TestControlCommon


@tagged(*TAGS)
class TestShed(TestControlCommon):
    def items(self):
        return self.Shed.search([("active", "=", True)])

    def node(self, code):
        return self.env["td.energy.node"].search([("code", "=", code)])

    def test_seed(self):  # AC-171
        rows = self.items()
        self.assertEqual(rows.mapped("node_id.code"), ["CHARGING", "RV-ALL", "DRY-1", "COMPRESSOR", "LP-1"])
        self.assertEqual(rows.mapped("kw_reducible"), [48, 60, 17, 37, 12])
        self.assertEqual(
            rows.mapped("how"),
            [
                "відкласти заряд до 30 хв",
                "знизити до 70 %",
                "пауза до 20 хв, без втрати циклу",
                "вимкнути, тиск ≥ 6,5 бар",
                "знизити до 50 %",
            ],
        )
        self.assertTrue(all(rows.mapped("signal_id")))

    def test_constraints(self):  # AC-172
        Shed = self.Shed.with_user(self.u_chief)
        lp1, dry = self.node("LP-1"), self.node("DRY-1")
        self.assertTrue(lp1.is_critical)
        self.items().filtered(lambda r: r.node_id in (lp1, dry)).sudo().write({"active": False})
        base = {"name": "t", "node_id": lp1.id, "param_value": 0, "kw_reducible": 1}
        with self.assertRaises(ValidationError), self.cr.savepoint():  # критичний: off без умови
            Shed.create(dict(base, action="off", condition="none"))
        ok = Shed.create(dict(base, action="reduce", param_value=50))
        self.assertTrue(ok.critical)
        with self.assertRaises(ValidationError), self.cr.savepoint():  # другий активний рядок на той самий вузол
            Shed.create(dict(base, action="reduce", param_value=40))
        wc = self.env["mrp.workcenter"].create({"name": "WC-TEST"})
        dry.sudo().workcenter_id = wc
        with self.assertRaises(ValidationError), self.cr.savepoint():  # станок без умови циклу
            Shed.create({"name": "m", "node_id": dry.id, "action": "pause", "param_value": 10, "condition": "none"})
        Shed.create(
            {"name": "m", "node_id": dry.id, "action": "pause", "param_value": 10, "condition": "no_active_cycle"}
        )

    def test_reorder(self):  # AC-173
        ids = self.items().ids
        new_order = list(reversed(ids))
        act = self.run_action("shed_reorder", {"order": new_order}, user=self.u_chief)
        self.assertEqual(act.state, "done")
        self.assertEqual(self.items().ids, new_order)
        prep = self.ctl(self.u_chief).undo(act.id)
        self.ctl(self.u_chief).confirm(prep["token"])
        self.assertEqual(self.items().ids, ids)
        before = self.State.get().config_version
        act2 = self.run_action("shed_reorder", {"order": new_order}, user=self.u_en1)
        self.assertEqual(act2.state, "awaiting_second")
        self.assertEqual(self.items().ids, ids)
        self.assertEqual(self.State.get().config_version, before)
        self.ctl(self.u_en2).confirm_second(act2.id)
        self.assertEqual(self.items().ids, new_order)

    def test_control_part(self):  # AC-174
        shed = self.ctl(self.u_view).get_control()["shed"]
        self.assertEqual(shed["sum_kw"], 174)
        self.assertEqual(len(shed["never"]), 5)
        self.assertEqual(shed["limit_kw"], 760)
        crit = {n.code for n in self.env["td.energy.node"].search([("is_critical", "=", True)])}
        self.assertEqual(set(shed["never_nodes"]), crit - {"COMPRESSOR", "LP-1"})
        self.assertEqual([i["n"] for i in shed["items"]], [1, 2, 3, 4, 5])

    def test_config(self):  # AC-175
        cfg = self.env["td.energy.control.state"].get()
        from ..tools import config_builder

        data = config_builder.build(self.env)
        self.assertEqual([s["seq"] for s in data["shed"]], [1, 2, 3, 4, 5])
        first = data["shed"][0]
        self.assertEqual(first["signal"], "energy_control/shed/CHARGING/limit_pct")
        self.assertFalse(first["critical"])
        self.assertTrue(data["shed"][3]["critical"])
        self.assertIn("LP-2", data["never_shed"])
        self.assertIn("EF-ELEC", data["never_shed"])
        self.assertNotIn("COMPRESSOR", data["never_shed"])
        self.assertTrue(cfg)

    def test_rights_and_log(self):  # AC-176
        item = self.items()[0]
        with self.assertRaises(AccessError):
            item.with_user(self.u_en1).write({"kw_reducible": 40})
        with self.assertRaises(AccessError):
            item.with_user(self.u_view).write({"kw_reducible": 40})
        before = self.State.get().config_version
        item.with_user(self.u_chief).write({"kw_reducible": 49})
        log = self.Action.search([("kind_code", "=", "shed_edit")], limit=1)
        self.assertEqual((log.cls, log.state, log.origin), ("B", "done", "config"))
        self.assertGreater(self.State.get().config_version, before)
