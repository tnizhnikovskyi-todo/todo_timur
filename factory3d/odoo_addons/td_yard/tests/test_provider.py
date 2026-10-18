from datetime import timedelta

from odoo.tests import tagged

from .flow import at, freeze
from .gate_case import GateCase

PROVIDER = "td.viewer.provider.yard"


@tagged("post_install", "-at_install", "f3d", "f3d_yard")
class TestYardProvider(GateCase):
    def setUp(self):
        super().setUp()
        self.provider = self.env[PROVIDER]
        self.ctx = {"user": self.user_guard, "kiosk": False, "now_local": "2026-10-12 12:45"}

    def _collect(self, payload=None, **ctx):
        payload = {} if payload is None else payload
        self.provider._f3d_viewer_collect(payload, dict(self.ctx, **ctx))
        return payload

    def _visit_at(self, plate, state, dock=None, **vals):
        visit = self._visit(plate=plate, batch_id=self._batch().id)
        visit.action_arrive(ts=at(12, 30))
        self._force(visit, state, **vals)
        return visit

    def test_registry(self):  # AC-65
        provider = self.env[PROVIDER]
        self.assertEqual(provider._f3d_sequence, 160)
        self.assertEqual(provider._f3d_sections, ("yard",))
        self.assertEqual(provider._f3d_group, "td_factory3d.group_td_user")
        self.assertEqual(provider._f3d_viewer_bus_models(), ["td.yard.visit", "td.yard.gate", "td.yard.scale"])
        patch_ = {}
        provider._f3d_viewer_delta(patch_, {"changes": {}})
        self.assertEqual(patch_, {})
        provider._f3d_viewer_delta(patch_, {"user": self.user_guard, "changes": {"td.yard.visit": {"YV/1"}}})
        self.assertIn("yard", patch_)

    def test_collect_sections_and_positions(self):  # AC-62
        self.dock_t1.write({"td_x": 0.0, "td_y": 5.0})
        self.dock_t3.write({"td_x": 150.0, "td_y": 15.0})
        with freeze(at(12, 45)):
            west = self._visit_at("АА1111КТ", "handling")
            west.booking_id = self._booking(west, self.dock_t1, at(12), at(13), confirm=True)
            east = self._visit(plate="АА2222КТ", visit_type="outgoing", batch_id=self._batch("outgoing").id)
            self._booking(east, self.dock_t3, at(12), at(13), confirm=True)
            east.action_arrive(ts=at(12, 30))
            self._force(east, "handling")
            arrived = self._visit_at("АА3333КТ", "arrived")
            q1 = self._visit_at("АА4444КТ", "queued", admitted_at=at(12, 31))
            q2 = self._visit_at("АА5555КТ", "queued", admitted_at=at(12, 32))
            weighed = self._visit_at("АА6666КТ", "weighed", weighed_out_at=at(12, 44))
            weighed.weighed_out_at = at(12, 45) - timedelta(seconds=30)
            payload = self._collect()
        yard = payload["yard"]
        for key in ("gates", "scale", "trucks", "queue", "kpp", "stats", "updated"):
            self.assertIn(key, yard)
        trucks = {t["visit"]: t for t in yard["trucks"]}
        self.assertEqual((trucks[west.name]["x"], trucks[west.name]["y"], trucks[west.name]["rz"]), (-7.3, 5.0, 0))
        self.assertEqual((trucks[east.name]["x"], trucks[east.name]["y"], trucks[east.name]["rz"]), (157.3, 15.0, 180))
        self.assertEqual((trucks[arrived.name]["x"], trucks[arrived.name]["y"]), (-20.0, -22.0))
        self.assertEqual(trucks[arrived.name]["rz"], 90)
        self.assertEqual(yard["queue"]["west"], [q1.name, q2.name])
        self.assertEqual((trucks[q1.name]["x"], trucks[q1.name]["y"]), (-26.0, 9.0))
        self.assertEqual((trucks[q2.name]["x"], trucks[q2.name]["y"], trucks[q2.name]["rz"]), (-26.0, 25.0, 90))
        self.assertEqual((trucks[weighed.name]["x"], trucks[weighed.name]["y"]), (172.0, -14.0))
        self.assertEqual(yard["kpp"]["west"], [arrived.name])
        self.assertEqual(yard["stats"]["on_site"], 6)
        self.assertEqual(yard["updated"], "2026-10-12 12:45")
        self.assertIsNotNone(yard["trucks"][0]["plate"])

    def test_privacy(self):  # AC-62
        self.gate_w.sudo().write({"last_plate": "АА4512КТ", "last_plate_at": at(9, 10)})
        guard = self._collect()["yard"]
        self.assertEqual(guard["gates"]["GATE-W"]["last_plate"], "АА4512КТ")
        self.assertIsNotNone(guard["stats"]["unmatched"])
        reader = self._collect(user=self.user_reader)["yard"]
        self.assertIsNone(reader["gates"]["GATE-W"]["last_plate"])
        self.assertIsNone(reader["stats"]["unmatched"])
        kiosk = self._collect(kiosk=True)["yard"]
        self.assertIsNone(kiosk["gates"]["GATE-W"]["last_plate"])
        visit = self._visit_at("АА1111КТ", "queued")
        kiosk = self._collect(kiosk=True)["yard"]
        self.assertIsNone(next(t for t in kiosk["trucks"] if t["visit"] == visit.name)["plate"])

    def test_infra_cards(self):  # AC-63
        self.gate_w.sudo().write({"last_plate": "АА4512КТ", "last_plate_at": at(9, 10), "passes_today": 7})
        scale = self.env.ref("td_yard.scale_truck")
        self.env["td.yard.weighing"].sudo().create(
            {"scale_id": scale.id, "kind": "check", "weight_kg": 21380.0, "plate": "АА4512КТ", "source": "manual"}
        )
        payload = {"infra": {"cards": {"GATE-W": {}, "TRUCK-SCALE": {}}}}
        self._collect(payload)
        gate_rows = dict(map(tuple, payload["infra"]["cards"]["GATE-W"]["rows"]))
        self.assertEqual(gate_rows["Сьогодні проїздів"], "7")
        self.assertEqual(gate_rows["Режим"], "ручний")
        self.assertIn("Стан", gate_rows)
        self.assertTrue(gate_rows["Останній номер"].startswith("АА 4512 КТ · "))
        scale_rows = dict(map(tuple, payload["infra"]["cards"]["TRUCK-SCALE"]["rows"]))
        self.assertEqual(scale_rows["Остання машина"], "АА 4512 КТ · брутто 21 380 кг · —")
        self.assertEqual(scale_rows["Сьогодні зважувань"], "1")
        self.assertNotIn("GATE-E", payload["infra"]["cards"])
        self.assertNotIn("infra", self._collect({}))

    def test_delta_deep_merge(self):  # AC-87
        infra = {
            "totals": {"genset_kw": 348},
            "cards": {"GENSET": {"rows": [["Стан", "резерв"]]}, "GATE-W": {"title": "КПП"}},
        }
        patch_ = {"infra": infra}
        self.provider._f3d_viewer_delta(patch_, dict(self.ctx, changes={"td.yard.gate": {"GATE-W"}}))
        self.assertIs(patch_["infra"], infra)
        self.assertEqual(infra["totals"], {"genset_kw": 348})
        self.assertEqual(infra["cards"]["GENSET"], {"rows": [["Стан", "резерв"]]})
        self.assertEqual(infra["cards"]["GATE-W"]["title"], "КПП")
        for code in ("GATE-W", "GATE-E", "TRUCK-SCALE"):
            self.assertTrue(infra["cards"][code]["rows"], code)
        self.assertIn("gates", patch_["yard"])
