"""AC-69: локальний тип джерела td_genset (SPEC §13.1, TestLocalSource)."""

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.td_telemetry.tools import address

from .test_rules import GensetCase


@tagged("post_install", "-at_install")
class TestLocalSource(GensetCase):
    def test_local_type_hook(self):  # AC-69
        Source = self.env["td.source"]
        self.assertIn("td_genset", Source._td_local_types())
        self.assertEqual(address.validate_params("td_genset", {}, Source._td_local_types()), [])
        source = self.link.source_id
        self.assertEqual(source.code, "GENSET-RELAY")
        self.assertTrue(source.is_local)
        self.assertFalse(source.collector_id)
        self.assertFalse(source.params)

    def test_source_without_collector(self):  # AC-69
        second = self.env["td.source"].create(
            {"code": "GENSET-RELAY-2", "name": "Другий ретранслятор", "type": "td_genset"}
        )
        self.assertFalse(second.collector_id)

    def test_other_type_needs_collector(self):  # AC-69
        with self.assertRaises(ValidationError), mute_logger("odoo.sql_db"):
            self.env["td.source"].create({"code": "MB-NOCOL", "name": "Modbus без колектора", "type": "modbus_tcp"})
