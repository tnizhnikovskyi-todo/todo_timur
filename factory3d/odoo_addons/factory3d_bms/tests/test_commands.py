from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged

from .. import hooks
from .common import F3DBmsCase

P = "factory3d.bms."


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestWriteFlags(F3DBmsCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.sysadmin = new_test_user(
            cls.env, "bms_sysadmin", groups="base.group_user,base.group_system,factory3d_base.group_f3d_admin"
        )

    def _settings(self, user, **vals):
        if user == self.user_admin:
            user = self.sysadmin  # настройки доступны группе base.group_system
        return self.env["res.config.settings"].with_user(user).create(vals)

    def test_enable_disable(self):
        Signal, Source = self.env["f3d.signal"].sudo(), self.env["f3d.source"].sudo()
        self._settings(self.user_admin, f3d_bms_write_enabled=True).set_values()
        self.assertEqual(Signal.search_count([("module", "=", "bms"), ("write_enabled", "=", True)]), 142)
        sources = Source.search([("module", "=", "bms"), ("write_enabled", "=", True)])
        self.assertEqual(len(sources), 29)
        self.assertFalse(sources.filtered(lambda s: s.code.startswith(("BAC-131", "BAC-132", "BAC-133", "BAC-140"))))
        self.env["ir.config_parameter"].sudo().set_param("factory3d.telemetry.write_enabled", "True")
        sig = Signal.search([("code", "=", "lighting/groups/LT-CUT/level")])
        cmd = self.env["f3d.command"].sudo().create({"signal_id": sig.id, "value": 50.0, "origin": "bms"})
        self.assertEqual(cmd.state, "queued")
        self._settings(self.user_admin, f3d_bms_write_enabled=False).set_values()
        self.assertEqual(Signal.search_count([("module", "=", "bms"), ("write_enabled", "=", True)]), 0)
        self.assertEqual(Source.search_count([("module", "=", "bms"), ("write_enabled", "=", True)]), 0)
        self.assertEqual(cmd.state, "cancelled")

    def test_manager_rpc_denied(self):
        with self.assertRaises(AccessError):
            self._settings(self.user_manager, f3d_bms_write_enabled=True).set_values()
        self.assertEqual(self.env["ir.config_parameter"].sudo().get_param(P + "write_enabled"), "False")

    def test_ranges(self):
        with self.assertRaises(ValidationError):
            self._settings(self.user_admin, f3d_bms_light_check_delay_min=0).set_values()
        with self.assertRaises(ValidationError):
            self._settings(self.user_admin, f3d_bms_light_norm_tolerance_pct=60.0).set_values()


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestWizards(F3DBmsCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        icp = cls.env["ir.config_parameter"].sudo()
        icp.set_param(P + "write_enabled", "True")
        icp.set_param("factory3d.telemetry.write_enabled", "True")
        hooks.write_flags(cls.env, enabled=True)
        Group = cls.env["f3d.bms.light.group"]
        cls.maint, cls.cut, cls.eb = (
            Group.search([("code", "=", c)], limit=1) for c in ("LT-MAINT", "LT-CUT", "LT-EB")
        )
        cls.scene = cls.env["f3d.bms.light.scene"].search([("number", "=", 3)], limit=1)
        cls.rv5 = cls.env["f3d.bms.hvac.unit"].search([("code", "=", "RV-05")], limit=1)

    def light(self, user=None, **vals):
        vals.setdefault("group_ids", [(6, 0, self.maint.ids)])
        return self.env["f3d.bms.light.command.wizard"].with_user(user or self.user_operator).create(vals)

    def hvac(self, **vals):
        vals.setdefault("unit_ids", [(6, 0, self.rv5.ids)])
        return self.env["f3d.bms.hvac.command.wizard"].with_user(self.user_operator).create(vals)

    def commands(self, action):
        return self.env["f3d.command"].search(action["domain"])

    def test_light_scene(self):
        self.assertTrue(self.scene)
        wiz = self.light(action="scene", scene_id=self.scene.id, fade_s=2.0)
        before = fields.Datetime.now()
        cmd = self.commands(wiz.action_apply())
        self.assertEqual(len(cmd), 1)
        self.assertEqual(cmd.signal_id.code, "lighting/groups/LT-MAINT/scene")
        self.assertEqual((cmd.value, cmd.text, cmd.origin, cmd.state), (3.0, "fade=2.0", "bms", "queued"))
        self.assertEqual(cmd.requested_by, self.user_operator)
        self.assertAlmostEqual(cmd.expires_at, before + timedelta(minutes=10), delta=timedelta(seconds=30))
        self.assertTrue(any("Надіслано команду" in (m.body or "") for m in self.maint.message_ids))

    def test_light_level_multi(self):
        wiz = self.light(group_ids=[(6, 0, (self.cut | self.eb).ids)], action="level", level_pct=50)
        cmds = self.commands(wiz.action_apply())
        self.assertEqual(
            sorted(cmds.mapped("signal_id.code")),
            ["lighting/groups/LT-CUT/level", "lighting/groups/LT-EB/level"],
        )
        self.assertEqual(set(cmds.mapped("value")), {50.0})

    def test_refusals(self):
        wiz = self.light(action="level", level_pct=50)
        with self.assertRaises(AccessError):
            self.light(user=self.user_reader, action="level", level_pct=50).action_apply()
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(P + "write_enabled", "False")
        with self.assertRaisesRegex(UserError, "модуль «Будівля»"):
            wiz.action_apply()
        icp.set_param(P + "write_enabled", "True")
        icp.set_param("factory3d.telemetry.write_enabled", "False")
        with self.assertRaisesRegex(UserError, "телеметрія"):
            wiz.action_apply()
        icp.set_param("factory3d.telemetry.write_enabled", "True")
        self.maint.level_signal_id.source_id.sudo().write_enabled = False
        with self.assertRaisesRegex(UserError, r"Запис вимкнено на: LT-MAINT \(джерело HN-LP-3\)"):
            wiz.action_apply()
        self.maint.level_signal_id.source_id.sudo().write_enabled = True
        with self.assertRaises(ValidationError):
            self.light(action="level", level_pct=120).action_apply()

    def test_hvac_mode_setpoint(self):
        cmd = self.commands(self.hvac(action="mode", mode="VEL").action_apply())
        self.assertEqual((cmd.signal_id.code, cmd.text), ("ventilation/units/RV-05/mode", "VEL"))
        cmd = self.commands(self.hvac(action="setpoint_night", value_c=12.0).action_apply())
        self.assertEqual((cmd.signal_id.code, cmd.value), ("ventilation/units/RV-05/setpoint_night_c", 12.0))
        ef = self.env["f3d.bms.hvac.unit"].search([("code", "=", "EF-ELEC")], limit=1)
        with self.assertRaises(ValidationError):
            self.hvac(unit_ids=[(6, 0, ef.ids)], action="mode", mode="ST").action_apply()

    def test_forbidden_write_flags(self):
        Signal = self.env["f3d.signal"].sudo()
        for code in (
            "ventilation/units/EF-ELEC/state",
            "equipment/BOILER/return_c",
            "ventilation/units/RV-05/heating_valve",
        ):
            sig = Signal.search([("code", "=", code)], limit=1)
            self.assertTrue(sig, code)
            with self.assertRaisesRegex(ValidationError, "не керується"):
                sig.write_enabled = True
