import inspect

from odoo.tests import TransactionCase, tagged

from . import (
    test_booking,
    test_commands,
    test_cron,
    test_gate,
    test_install,
    test_kpp,
    test_lpr,
    test_migration,
    test_picking,
    test_provider,
    test_reports,
    test_scale,
    test_security,
    test_visit,
)

TAGS = {"post_install", "f3d", "f3d_yard"}
TEST_MODULES = (
    test_booking,
    test_commands,
    test_cron,
    test_gate,
    test_install,
    test_kpp,
    test_lpr,
    test_migration,
    test_picking,
    test_provider,
    test_reports,
    test_scale,
    test_security,
    test_visit,
)


@tagged("post_install", "-at_install", "f3d", "f3d_yard")
class TestYardContracts(TransactionCase):
    """AC-78: контракти з суміжними модулями (CY-01…CY-08)."""

    def test_signal_ingest(self):
        self.assertTrue(callable(self.env["f3d.signal"]._f3d_ingest))
        params = inspect.signature(self.env["f3d.signal"]._f3d_ingest).parameters
        self.assertTrue({"readings", "src", "collector"} <= set(params))

    def test_command_fields(self):
        fields_ = self.env["f3d.command"]._fields
        for name in ("signal_id", "value", "state", "origin", "expires_at", "requested_by", "done_at", "error"):
            self.assertIn(name, fields_)

    def test_push_handler_routes(self):
        self.assertIn("lpr", self.env["f3d.push.handler.yard"]._f3d_push_routes)
        self.assertTrue(hasattr(self.env["f3d.push.handler"], "_f3d_push_routes"))

    def test_batch_fields(self):
        for name in ("dock_id", "end_date", "f3d_code"):
            self.assertIn(name, self.env["stock.picking.batch"]._fields)

    def test_scene_api(self):
        self.assertTrue(hasattr(self.env["maintenance.equipment"], "search_f3d"))
        self.assertTrue(hasattr(self.env["f3d.zone"], "zone_at"))

    def test_test_tags(self):
        for module in TEST_MODULES:
            for name, cls in inspect.getmembers(module, inspect.isclass):
                if cls.__module__ != module.__name__ or not issubclass(cls, TransactionCase):
                    continue
                if name.startswith("Test"):
                    msg = "%s.%s: теги %s" % (module.__name__, name, cls.test_tags)
                    self.assertTrue(TAGS <= set(cls.test_tags), msg)
                    self.assertNotIn("at_install", cls.test_tags, msg)
