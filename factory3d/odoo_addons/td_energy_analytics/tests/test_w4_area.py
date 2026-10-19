"""W4-A: ділянки й карта вузлів (AC-01, AC-02, AC-04)."""

from psycopg2 import IntegrityError

from odoo.exceptions import UserError, ValidationError
from odoo.tools import mute_logger

from odoo.addons.td_energy_analytics import hooks
from odoo.tests import tagged

from .common import TAGS, TestW4Common

GROUPS = {
    "CUT": 8, "EDGE": 3, "DRILL": 6, "FACADE": 7, "ASSY": 12, "AIR_DUST": 2, "HVAC": 6, "LIGHT_OFFICE": 5,
}  # fmt: skip
COLORS = {
    "CUT": "#5a3b52", "EDGE": "#8a6383", "DRILL": "#b79ab0", "FACADE": "#b45309", "ASSY": "#f59e0b",
    "AIR_DUST": "#0369a1", "HVAC": "#38bdf8", "LIGHT_OFFICE": "#9ca3af",
}  # fmt: skip


@tagged(*TAGS)
class TestW4Area(TestW4Common):
    def test_ac01_areas_and_map(self):
        areas = self.Area.search([])
        self.assertEqual(areas.mapped("code"), list(GROUPS))  # порядок за `sequence`
        for area in areas:
            self.assertEqual(area.color, COLORS[area.code], area.code)
            self.assertEqual(area.node_count, GROUPS[area.code], area.code)
            if area.code == "LIGHT_OFFICE":
                self.assertFalse(area.spec_driver_id)
            else:
                self.assertEqual(area.spec_driver_id.code, "plate_m2", area.code)
        with_area = self.env["td.energy.node"].search_count([("kind", "=", "consumer"), ("area_id", "!=", False)])
        self.assertEqual(with_area, 49)
        self.assertEqual(self._node("SAW-3").area_id.code, "CUT")
        self.assertEqual(self._node("EF-CHG").area_id.code, "HVAC")

    def test_ac01_idempotent_and_manual_edit_kept(self):
        self.assertEqual(hooks._load_areas(self.env), 0)
        self.assertEqual(hooks._assign_areas(self.env), 0)
        node = self._node("SAW-1")
        node.area_id = self._area("HVAC")
        hooks._assign_areas(self.env)
        self.assertEqual(node.area_id.code, "HVAC", "ручна правка не перезаписується")
        node.area_id = False
        self.assertEqual(hooks._assign_areas(self.env), 1)
        self.assertEqual(node.area_id.code, "CUT")
        self.assertEqual(self.Area.search_count([]), 8)

    def test_ac02_unlink_and_unique(self):
        with self.assertRaisesRegex(UserError, "Ділянка використовується вузлами"):
            self._area("CUT").unlink()
        empty = self.Area.create({"code": "TMP", "name": "Тимчасова", "color": "#000000"})
        self.assertEqual(empty.node_count, 0)
        empty.unlink()
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.Area.create({"code": "CUT", "name": "Дубль", "color": "#111111"})

    def test_ac04_plate_area_field(self):
        product = self.env["product.template"].create({"name": "Плита-тест"})
        self.assertEqual(product.td_plate_area_m2, 0.0)
        product.td_plate_area_m2 = 3.1
        self.assertAlmostEqual(product.td_plate_area_m2, 3.1)
        with self.assertRaises(ValidationError):
            product.td_plate_area_m2 = -1.0
