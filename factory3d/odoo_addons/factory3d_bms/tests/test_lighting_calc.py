from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from ..tools import lighting
from .common import F3DBmsLightCase


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestNorms(F3DBmsLightCase):
    def test_norm_effective_lux(self):
        self.assertEqual(self.norms["storage_racks"].lux, 150)
        self.assertEqual(self.norms["woodworking_machine"].lux, 500)
        self.assertIn("ДБН", self.norms["spraying"].ref_dbn)

    def test_norm_constraints(self):
        Norm = self.env["f3d.bms.light.norm"]
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            Norm.create({"key": "spraying", "name": "dup", "lux": 100})
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            Norm.create({"key": "zero_lux", "name": "z", "lux": 0})
        with self.assertRaises(ValidationError):
            Norm.create({"key": "Bad-Key", "name": "b", "lux": 100})


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestGroupDesign(F3DBmsLightCase):
    # (code, zone, norm, panel, n, kind, n_required, e_calc, p_inst) — рядки Додатка A.1
    ROWS = [
        ("LT-CUT", "Z-CUT", "woodworking_machine", "lp2", 27, "highbay", 27, 509, 3.4),
        ("LT-EB", "Z-EB", "woodworking_machine", "lp2", 27, "highbay", 25, 549, 3.4),
        ("LT-FAC", "Z-FAC", "spraying", "lp2", 91, "highbay", 81, 846, 11.47),
        ("LT-SHEETS", "Z-SHEETS", "storage_floor", "lp1", 12, "highbay", 11, 115, 1.51),
        ("LT-HW", "Z-HW", "storage_racks", "lp1", 5, "highbay_rack", 5, 164, 0.63),
        ("LT-RCV-7", "Z-RCV-7", "packing_dispatch", "lp1", 4, "highbay", 4, 319, 0.5),
    ]

    def test_groups_match_macro(self):
        for code, zone, norm, panel, n, kind, n_req, e_calc, p_inst in self.ROWS:
            passport = self.pass_rack if kind == "highbay_rack" else self.pass_hb
            g = self.mk_group(
                code, zone, norm, getattr(self, panel), n, fixture_kind=kind, passport_id=passport.id
            )
            with self.subTest(code=code):
                self.assertEqual(g.n_required, n_req)
                self.assertEqual(g.e_calc, e_calc)
                self.assertAlmostEqual(g.p_inst_kw, p_inst, 2)
                self.assertTrue(g.design_ok)

    def test_formula_synthetic(self):
        g = self.mk_group("LT-T1", "Z-T1", "t_300", self.lp1, 3)
        self.assertEqual((g.n_required, g.e_calc, g.design_ok), (3, 344, True))
        self.assertAlmostEqual(g.p_inst_kw, 0.38, 2)
        g.n_fixtures = 2
        self.assertEqual((g.e_calc, g.design_ok), (230, False))
        g.n_fixtures = 27
        g.zone_id, g.norm_id = self.zones["Z-CUT"], self.norms["woodworking_machine"]
        self.assertEqual(g.e_calc, 509)
        g.n_fixtures = 26
        self.assertEqual(g.e_calc, 490)
        self.assertFalse(g.design_ok)

    def test_min_one(self):
        norm = self.env["f3d.bms.light.norm"].create({"key": "t_100", "name": "t", "lux": 10})
        g = self.mk_group("LT-T2", "Z-T1", "t_300", self.lp1, 1)
        g.norm_id = norm
        self.assertEqual(g.n_required, 1)
        self.assertEqual(lighting.n_required(100, 1.0, 20500, 0.7, 0.8), 1)

    def test_totals_panel(self):
        self.mk_group("LT-CUT", "Z-CUT", "woodworking_machine", self.lp2, 27)
        self.mk_group("LT-EB", "Z-EB", "woodworking_machine", self.lp2, 27)
        self.assertEqual((self.lp2.group_count, self.lp2.n_fixtures, self.lp2.p_inst_kw), (2, 54, 6.8))

    def test_zone_without_polygon(self):
        with self.assertRaises(ValidationError):
            self.env["f3d.bms.light.group"].create({
                "code": "LT-T0", "name": "x", "zone_id": self.zone_empty.id, "norm_id": self.norms["t_300"].id,
                "panel_id": self.lp1.id, "n_fixtures": 1, "fixture_kind": "highbay", "level_design": 1.0,
                "control_mode": "shift", "dali_group": 999,
            })

    def test_check_norm_default(self):
        g = self.mk_group("LT-T3", "Z-T1", "t_300", self.lp1, 3, control_mode="presence")
        self.assertFalse(g.check_norm)
        g.control_mode = "shift"
        self.assertTrue(g.check_norm)


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestFixture(F3DBmsLightCase):
    def test_passport_values(self):
        g = self.mk_group("LT-T1", "Z-T1", "t_300", self.lp1, 3)
        self.assertEqual((g.lumen, g.watt), (20500, 126))

    def test_defaults_without_passport(self):
        g = self.mk_group("LT-T1", "Z-T1", "t_300", self.lp1, 3, passport_id=False)
        self.assertEqual((g.lumen, g.watt), (24000, 160))
        g.fixture_kind = "highbay_rack"
        self.assertEqual((g.lumen, g.watt), (19000, 130))

    def test_manual_override(self):
        g = self.mk_group("LT-T1", "Z-T1", "t_300", self.lp1, 3)
        g.lumen = 10000
        self.assertEqual(g.lumen, 10000)
        self.assertEqual(g.e_calc, round(3 * 10000 * 0.56 / 100))


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestDali(F3DBmsLightCase):
    def test_pack_dali_function(self):
        lp2 = [("LT-CUT", 27), ("LT-EB", 27), ("LT-CNC", 27), ("LT-SORT", 12), ("LT-FAC", 91)]
        res = lighting.pack_dali(lp2, 1, 2)
        self.assertEqual(res["LT-CUT"], "@1.2.1.1-27")
        self.assertEqual(res["LT-EB"], "@1.2.1.28-54")
        self.assertEqual(res["LT-CNC"], "@1.2.2.1-27")
        self.assertEqual(res["LT-SORT"], "@1.2.2.28-39")
        self.assertEqual(res["LT-FAC"], "@1.2.3.1-64;@1.2.4.1-27")
        lp3 = [("LT-A", 58), ("LT-B", 4), ("LT-OUT-1", 4), ("LT-OUT-2", 4)]
        res = lighting.pack_dali(lp3, 1, 3)
        self.assertEqual(res["LT-B"], "@1.3.1.59-62")
        self.assertEqual(res["LT-OUT-1"], "@1.3.2.1-4")

    def test_devices_valid(self):
        g = self.mk_group("LT-CUT", "Z-CUT", "woodworking_machine", self.lp2, 27, dali_devices="@1.2.1.1-27")
        self.assertEqual(g.dali_devices, "@1.2.1.1-27")
        g2 = self.mk_group("LT-FAC", "Z-FAC", "spraying", self.lp2, 91, dali_devices="@1.2.3.1-64;@1.2.4.1-27")
        self.assertTrue(g2.dali_devices)

    def test_count_mismatch(self):
        with self.assertRaisesRegex(ValidationError, "Пристроїв DALI 26, а світильників 27."):
            self.mk_group("LT-CUT", "Z-CUT", "woodworking_machine", self.lp2, 27, dali_devices="@1.2.1.1-26")

    def test_wrong_router(self):
        with self.assertRaisesRegex(ValidationError, "Адреса @1.3.1.1 не належить щиту LP-2."):
            self.mk_group("LT-CUT", "Z-CUT", "woodworking_machine", self.lp2, 27, dali_devices="@1.3.1.1-27")

    def test_injection_rejected(self):
        for bad in ("@1.2.1.1-27#", "@1.2.1.1-27;DROP", "@1.2.1.5-1", "@1.2.9.1-27", "@1.2.1.1-65", "x"):
            with self.subTest(bad=bad), self.assertRaises(ValidationError):
                self.mk_group("LT-BAD", "Z-CUT", "woodworking_machine", self.lp2, 27, dali_devices=bad)

    def test_unique_dali_group(self):
        g = self.mk_group("LT-T1", "Z-T1", "t_300", self.lp1, 3)
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.mk_group("LT-T2", "Z-T1", "t_300", self.lp1, 3, dali_group=g.dali_group)

    def test_code_and_checks(self):
        with self.assertRaises(ValidationError):
            self.mk_group("lt-cut", "Z-CUT", "woodworking_machine", self.lp2, 27)
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.mk_group("LT-T1", "Z-T1", "t_300", self.lp1, 3, level_design=1.2)
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.mk_group("LT-T2", "Z-T1", "t_300", self.lp1, 3, uf=0)
