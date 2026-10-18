"""W1-A: AC-136 — заявка ТО з картки вузла (M-28)."""

from odoo.tests import tagged

from .common import TAGS, TestW1Common


@tagged(*TAGS)
class TestW1Ticket(TestW1Common):
    def wizard(self, node_code, **kw):
        node = self.Node.search([("code", "=", node_code)])
        vals = {
            "node_id": node.id,
            "description": "Нагрівається з'єднання\nДругий рядок",
            "maintenance_type": "corrective",
        }
        vals.update(kw)
        return self.env["td.energy.ticket.wizard"].with_user(self.u_eng).create(vals)

    def test_create_request(self):  # AC-136
        node = self.Node.search([("code", "=", "BW-2")])
        equipment = self.env["maintenance.equipment"].create({"name": "ШР-2 (тест)"})
        node.write({"equipment_id": equipment.id})
        wiz = self.wizard("BW-2", priority="3")
        self.assertEqual(wiz.equipment_id, equipment)
        self.assertTrue(wiz.team_id)
        action = wiz.action_create()
        request = self.env["maintenance.request"].browse(action["res_id"])
        self.assertEqual(
            (action["type"], action["res_model"], action["view_mode"]),
            ("ir.actions.act_window", "maintenance.request", "form"),
        )
        self.assertEqual(request.name, "ШР-2: Нагрівається з'єднання")
        self.assertEqual(
            (request.equipment_id, request.maintenance_type, request.priority), (equipment, "corrective", "3")
        )
        self.assertEqual(request.maintenance_team_id, wiz.team_id)
        self.assertNotIn("Вузол мережі", request.description or "")
        self.assertIn("Створено з картки вузла BW-2", " ".join(request.message_ids.mapped("body")))

    def test_without_equipment(self):  # AC-136
        node = self.Node.search([("code", "=", "C2")])
        node.write({"equipment_id": False})
        request = self.env["maintenance.request"].browse(self.wizard("C2").action_create()["res_id"])
        self.assertFalse(request.equipment_id)
        self.assertIn("Вузол мережі: C2", request.description)
