"""AC-28…AC-31, AC-66, AC-77 (M-15, M-19): заборона запису в пожежну сигналізацію, майстер BACnet device."""

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import FireCase


@tagged("post_install", "-at_install", "f3d", "f3d_fire")
class TestReadonly(FireCase):
    def fire_signal(self):
        return self.env["td.signal"].search([("code", "=", "fire/groups/FA-CUT/state")])

    def test_source_write_enabled_sudo(self):
        self.assertTrue(self.src_bac.td_fire_readonly)
        with self.assertRaises(ValidationError):
            self.src_bac.sudo().write({"write_enabled": True})
        with self.assertRaises(ValidationError):
            self.src_io.sudo().write({"write_enabled": True})
        with self.assertRaises(ValidationError):
            self.env["td.source"].sudo().create(
                {
                    "code": "MB-TEST",
                    "name": "Тест",
                    "type": "modbus_tcp",
                    "td_fire_readonly": True,
                    "params": {"host": "h", "port": 502, "unit": 1},
                    "write_enabled": True,
                    "collector_id": self.env.ref("td_telemetry.collector_main").id,
                }
            )

    def test_readonly_flag_sticky(self):
        with self.assertRaises(ValidationError):
            self.src_bac.sudo().write({"td_fire_readonly": False})
        self.assertTrue(self.src_bac.td_fire_readonly)

    def test_params_read_only(self):
        params = dict(self.src_bac.params)
        params.pop("read_only")
        with self.assertRaises(ValidationError):
            self.src_bac.sudo().write({"params": params})
        self.assertTrue(self.src_bac.params.get("read_only"))

    def test_prod_consent(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("td.base.environment", "prod")
        with self.assertRaises(ValidationError):
            self.src_bac.sudo().write({"read_enabled": False})
            self.src_bac.sudo().write({"read_enabled": True})
        self.src_bac.sudo().write({"td_fire_consent_date": "2026-10-01", "td_fire_consent_person": "Монтажник ТОВ"})
        self.src_bac.sudo().write({"read_enabled": True})

    def test_signal_write_enabled_sudo(self):
        sig = self.fire_signal()
        self.assertEqual(sig.module, "fire_safety")
        with self.assertRaises(ValidationError):
            sig.sudo().write({"write_enabled": True})
        with self.assertRaises(ValidationError):
            self.env["td.signal"].sudo().create(
                {
                    "code": "equipment/X/io",
                    "name": "Чужий сигнал",
                    "kind": "state",
                    "module": "telemetry",
                    "source_id": self.src_io.id,
                    "write_enabled": True,
                    "address": {"fc": 2, "addr": 100, "type": "bool", "unit": 85},
                }
            )

    def test_command_blocked_sudo(self):
        with self.assertRaises(ValidationError) as cm:
            self.env["td.command"].sudo().create({"signal_id": self.fire_signal().id, "text": "on"})
        self.assertIn("D-07", str(cm.exception))
        with self.assertRaises(ValidationError):
            self.env["td.command"].with_user(self.m).create({"signal_id": self.fire_signal().id, "text": "on"})

    def test_no_write_param_no_actions(self):
        icp = self.env["ir.config_parameter"].sudo()
        self.assertFalse(icp.get_param("td.fire_safety.write_enabled"))
        Data = self.env["ir.model.data"].sudo()
        bad = ("td.command", "action_request_write", 'name="write_enabled">True', "write_enabled': True")
        for model in ("ir.ui.view", "ir.actions.server", "ir.cron"):
            ids = Data.search([("module", "=", "td_fire_safety"), ("model", "=", model)]).mapped("res_id")
            for rec in self.env[model].sudo().browse(ids).exists():
                body = rec.arch_db if model == "ir.ui.view" else rec.code
                for needle in bad:
                    self.assertNotIn(needle, body or "", "%s %s" % (model, rec.display_name))
        fields_ = self.env["res.config.settings"]._fields
        self.assertFalse([f for f in fields_ if f.startswith("td_fire_") and "write" in f])

    def test_device_signals_monitor(self):
        dev = self.dev_cnc05
        dev.sudo().action_create_signals()
        self.assertTrue(dev.monitor)
        signals = dev.state_signal_id | dev.dust_signal_id
        self.assertTrue(dev.state_signal_id)
        for sig in signals:
            self.assertEqual(sig.module, "fire_safety")
            self.assertFalse(sig.write_enabled)
            self.assertEqual(sig.origin, "module")
            self.assertNotIn("device", sig.address)


@tagged("post_install", "-at_install", "f3d", "f3d_fire")
class TestBacnetDeviceWizard(FireCase):
    def wizard(self, user=None, **vals):
        vals.setdefault("panel_id", self.panel.id)
        return self.env["td.fire.bacnet.device.wizard"].with_user(user or self.a).create(vals)

    def test_wizard_defaults(self):
        action = self.panel.action_set_bacnet_device()
        self.assertEqual(action["context"]["default_old_instance"], 200)
        wiz = (
            self.env["td.fire.bacnet.device.wizard"]
            .with_user(self.a)
            .with_context(**action["context"])
            .create({"new_instance": 300})
        )
        self.assertEqual(wiz.old_instance, 200)
        expected = (
            self.env["td.signal"].with_context(active_test=False).search_count([("source_id", "=", self.src_bac.id)])
        )
        self.assertEqual(wiz.signal_count, expected)
        self.assertGreaterEqual(wiz.signal_count, 45)
        self.assertEqual(wiz.explicit_count, 0)

    def test_apply_params_device(self):
        params = dict(self.src_bac.params)
        wiz = self.wizard(new_instance=1234)
        wiz.old_instance = 200
        wiz.action_apply()
        self.assertEqual(self.src_bac.params["device"], 1234)
        for key in ("host", "port", "network", "read_only"):
            self.assertEqual(self.src_bac.params[key], params[key])
        self.assertIn(
            "BACnet device змінено: 200 → 1234 (джерело BAC-1234-FACP-1)",
            " ".join(self.panel.message_ids.mapped("body")),
        )
        self.assertEqual(self.src_bac, self.env.ref("td_fire_safety.source_bacnet_facp_1"))

    def test_code_renamed(self):
        self.wizard(new_instance=1234).action_apply()
        self.assertEqual(self.src_bac.code, "BAC-1234-FACP-1")
        self.src_bac.code = "BAC-CUSTOM"
        self.wizard(new_instance=77).action_apply()
        self.assertEqual(self.src_bac.code, "BAC-CUSTOM")
        self.assertEqual(self.src_bac.params["device"], 77)

    def test_explicit_address_updated(self):
        sig = self.env["td.signal"].create(
            {
                "code": "fire/devices/9.TST.01/state",
                "name": "Явна адреса",
                "kind": "state",
                "module": "fire_safety",
                "origin": "module",
                "source_id": self.src_bac.id,
                "address": {"device": 200, "object": "LSP", "instance": 21201, "mode": "poll"},
            }
        )
        wiz = self.wizard(new_instance=1234)
        self.assertEqual(wiz.explicit_count, 1)
        wiz.action_apply()
        self.assertEqual(sig.address["device"], 1234)
        other = self.env["td.signal"].search([("code", "=", "fire/groups/FA-CUT/state")])
        self.assertNotIn("device", other.address)

    def test_bounds_rights_no_source(self):
        with self.assertRaises(ValidationError):
            self.wizard(new_instance=4194303)
        with self.assertRaises(AccessError):
            self.wizard(user=self.m, new_instance=5).action_apply()
        wiz = self.wizard(new_instance=200)
        wiz.old_instance = 200
        result = wiz.action_apply()
        self.assertEqual(result["params"]["message"], "Без змін")
        self.assertEqual(self.src_bac.params["device"], 200)
        self.panel.source_id = False
        with self.assertRaises(UserError):
            self.wizard(new_instance=5).action_apply()
