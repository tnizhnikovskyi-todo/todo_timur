"""AC-16: ТО за наробітком (R-10, M-04)."""

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .common import TAGS, ChpCase


@tagged(*TAGS)
class TestMaintenance(ChpCase):
    def setUp(self):
        super().setUp()
        self.equipment = self.env["maintenance.equipment"].create({"name": "КГУ-1 (тест)"})
        self.unit.equipment_id = self.equipment
        self.oil = self.env.ref("td_chp.rule_oil")
        self.idle(**{"eng/hours": 18400.0})

    def requests(self, rule):
        return self.env["maintenance.request"].search(
            [("equipment_id", "=", self.equipment.id), ("name", "like", rule.name)]
        )

    def test_left_and_state(self):
        self.oil._td_refresh()
        self.assertEqual((self.oil.left_h, self.oil.state), (500.0, "ok"))
        self.put({"eng/hours": 18800.0})
        self.oil._td_refresh()
        self.assertEqual((self.oil.left_h, self.oil.state), (100.0, "soon"))  # 100 ≤ 15 % від 1000
        self.put({"eng/hours": 19000.0})
        self.oil._td_refresh()
        self.assertEqual((self.oil.left_h, self.oil.state), (-100.0, "overdue"))
        dto = {r["name"]: r for r in self.pult(self.u_user).get_maintenance()}
        self.assertEqual(dto["Заміна моторного масла"]["state"], "overdue")
        self.assertEqual(len(dto), 5)

    def test_request_once_and_close(self):
        self.assertEqual(self.Rule._cron_check(), 0)  # усі в нормі
        self.put({"eng/hours": 18800.0})
        self.Rule._cron_check()
        reqs = self.requests(self.oil)
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs.maintenance_type, "preventive")
        self.assertEqual(reqs.name, "ТО КГУ: Заміна моторного масла — через 100 год")
        self.assertEqual(self.oil.request_id, reqs)
        self.assertTrue(self.events(kind="maintenance"))
        n = self.env["maintenance.request"].search_count([])
        self.Rule._cron_check()  # без дублів, поки заявка відкрита
        self.assertEqual(self.env["maintenance.request"].search_count([]), n)
        done = self.env["maintenance.stage"].search([("done", "=", True)], limit=1)
        reqs.write({"stage_id": done.id})
        self.Rule._cron_check()
        self.oil._td_refresh()
        self.assertEqual((self.oil.last_h, self.oil.request_id.id, self.oil.state), (18800.0, False, "ok"))
        self.assertEqual(self.requests(self.oil), reqs)  # нова заявка не створюється

    def test_overdue_text_and_no_equipment(self):
        self.put({"eng/hours": 19050.0})
        self.Rule._cron_check()
        self.assertEqual(self.oil.request_id.name, "ТО КГУ: Заміна моторного масла — прострочено на 150 год")
        self.unit.equipment_id = False
        rule = self.env.ref("td_chp.rule_plugs")
        self.put({"eng/hours": 19950.0})
        n = self.env["maintenance.request"].search_count([])
        self.Rule._cron_check()
        self.assertEqual(self.env["maintenance.request"].search_count([]), n)  # без обладнання заявок немає
        self.assertFalse(rule.request_id)

    def test_no_hours_skips(self):
        self.assertEqual(self.later(500)["td.chp.maintenance.rule"]._cron_check(), 0)

    def test_action_done(self):
        self.put({"eng/hours": 18800.0})
        self.Rule._cron_check()
        req = self.oil.request_id
        out = self.pult(self.u_op1).maintenance_done(self.oil.id)
        self.assertEqual(len(out), 5)
        self.oil._td_refresh()
        self.assertEqual((self.oil.last_h, self.oil.request_id.id), (18800.0, False))
        self.assertTrue(req.stage_id.done)
        with self.assertRaises(AccessError):
            self.pult(self.u_user).maintenance_done(self.oil.id)
