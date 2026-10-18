"""AC-177, AC-178, AC-181, AC-194: види команд, плитки, параметри, доступність."""

from unittest.mock import patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from ..tools import genset_link
from .common import TAGS, TestControlCommon

TILES = [
    "qs_close",
    "bess_charge",
    "bess_discharge",
    "chp_start",
    "genset_test",
    "light_break",
    "vent_eco",
    "air_setpoint",
]
CLASS_A = {"bess_charge", "bess_stop", "light_break", "light_restore", "vent_eco", "vent_restore"}


@tagged(*TAGS)
class TestKinds(TestControlCommon):
    def test_seed(self):  # AC-177
        kinds_ = self.Kind.search([])
        self.assertEqual(len(kinds_), 16)
        self.assertEqual(self.Kind.search([("tile", "=", True)]).mapped("code"), TILES)
        for k in kinds_:
            self.assertEqual(k.cls, "A" if k.code in CLASS_A else "B", k.code)
        qs = self.Kind.search([("code", "=", "qs_close")])
        self.assertEqual((qs.executor, qs.resource), ("intent", "qs"))
        self.assertEqual([c["code"] for c in qs.checks][-1], "qs_current_ok")
        self.assertEqual(self.Kind.search([("code", "=", "genset_test")]).executor, "genset")
        self.assertEqual(self.Kind.search([("code", "=", "qs_close")]).undo_kind_id.code, "qs_open")

    def test_tiles(self):  # AC-178
        tiles = {t["code"]: t for t in self.ctl(self.u_en1).get_control()["commands"]}
        self.assertEqual(list(tiles), TILES)
        self.assertEqual(tiles["bess_charge"]["label"], "Заряд BESS 50 кВт")
        self.assertEqual(tiles["bess_charge"]["sub"], "до 16:00 або 95 %")
        self.assertEqual(tiles["light_break"]["label"], "Освітлення цеху · сценарій «Перерва»")
        self.assertEqual(tiles["light_break"]["sub"], "50 % на 30 хв")
        view = {t["code"]: t for t in self.ctl(self.u_view).get_control()["commands"]}
        self.assertFalse(view["bess_charge"]["enabled"])
        self.assertEqual(view["bess_charge"]["disabled_reason"], "Немає прав: потрібна роль «Енергетик»")
        self._enable_control(write=False, remote=True)
        off = {t["code"]: t for t in self.ctl(self.u_en1).get_control()["commands"]}
        self.assertFalse(off["bess_charge"]["enabled"])
        self.assertFalse(off["qs_close"]["enabled"])

    def test_param_bounds(self):  # AC-181
        k = self.Kind.search([("code", "=", "bess_charge")])
        with self.assertRaisesRegex(ValidationError, "поза межами 1…100 кВт"):
            k.normalize({"power_kw": 500})
        with self.assertRaises(ValidationError):
            k.normalize({"soc_limit_pct": 40})
        with self.assertRaises(UserError):  # «до» у минулому: 14:20 Київ
            k.normalize({"until": "13:00"})
        self.assertEqual(k.normalize({}), {"power_kw": 50.0, "until": "16:00", "soc_limit_pct": 95.0})

    def test_genset_availability(self):  # AC-194
        k = self.Kind.search([("code", "=", "genset_test")])
        self.assertTrue(k.available)
        with patch.object(genset_link, "adapter", return_value=None):
            k.invalidate_recordset(["available", "unavailable_reason"])
            self.assertFalse(k.available)
            self.assertEqual(k.unavailable_reason, "Не встановлено міст td_genset_factory3d")
            with self.assertRaises(UserError):
                self.ctl(self.u_chief).prepare("genset_test")
