from datetime import timedelta

from odoo import SUPERUSER_ID
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import F3DTelemetryCase

TAGS = ("post_install", "-at_install", "f3d", "f3d_telemetry")


@tagged(*TAGS)
class TestCommandCreate(F3DTelemetryCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_telemetry_fixtures()

    def setUp(self):
        super().setUp()
        self.icp = self.env["ir.config_parameter"].sudo()

    def flags(self, module=True, source=True, signal=True):
        self.icp.set_param("td.telemetry.write_enabled", "True" if module else "False")
        self.src_bac.write_enabled = source
        self.sig_valve.write_enabled = signal

    def create(self, user=None, sig=None, **kw):
        Command = self.env["td.command"]
        if user:
            Command = Command.with_user(user)
        return Command.create({"signal_id": (sig or self.sig_valve).id, "value": 80, **kw})

    def test_flags_order(self):
        self.flags(False, False, False)
        with self.assertRaisesRegex(UserError, "параметр модуля"):
            self.create(self.user_manager)
        self.flags(True, False, False)
        with self.assertRaisesRegex(UserError, "джерело BAC-T-105"):
            self.create(self.user_manager)
        self.flags(True, True, False)
        with self.assertRaisesRegex(UserError, "сигнал ventilation/units/RV-05-T/heating_valve"):
            self.create(self.user_manager)

    def test_all_flags_ok(self):
        self.flags()
        cmd = self.create(self.user_manager)
        self.assertEqual(cmd.state, "queued")
        self.assertEqual(cmd.requested_by, self.user_manager)
        self.assertEqual(cmd.expires_at, cmd.requested_at + timedelta(minutes=10))

    def test_reader_denied(self):
        self.flags()
        with self.assertRaises(AccessError):
            self.create(self.user_reader)

    def test_read_only_source(self):
        self.flags()
        self.set_sql(self.sig_fire, write_enabled=True)
        self.set_sql(self.src_bac_ro, write_enabled=True)
        with self.assertRaisesRegex(UserError, "Джерело лише для читання."):
            self.create(self.user_manager, sig=self.sig_fire)

    def test_su_guards_still_apply(self):
        self.flags()
        as_reader = self.env["td.command"].with_user(self.user_reader).sudo()
        cmd = as_reader.create({"signal_id": self.sig_valve.id, "value": 1})
        self.assertEqual((cmd.state, cmd.requested_by), ("queued", self.user_reader))
        self.assertEqual(
            self.env["td.command"].with_user(SUPERUSER_ID).create({"signal_id": self.sig_valve.id, "value": 1}).state,
            "queued",
        )
        with self.assertRaises(AccessError):
            self.env["td.command"].with_user(self.user_reader).create({"signal_id": self.sig_valve.id, "value": 1})
        self.flags(source=False)
        with self.assertRaisesRegex(UserError, "джерело BAC-T-105"):
            as_reader.create({"signal_id": self.sig_valve.id, "value": 1})
        self.flags(module=False)
        with self.assertRaisesRegex(UserError, "параметр модуля"):
            as_reader.create({"signal_id": self.sig_valve.id, "value": 1})
        self.flags()
        self.set_sql(self.sig_fire, write_enabled=True)
        self.set_sql(self.src_bac_ro, write_enabled=True)
        with self.assertRaisesRegex(UserError, "Джерело лише для читання."):
            as_reader.create({"signal_id": self.sig_fire.id, "value": 1})
