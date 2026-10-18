"""AC-165, AC-228: заборонені системи, тип джерела `energy_ctl`, валідатори."""

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .common import TAGS, TestControlCommon


@tagged(*TAGS)
class TestSourceSignal(TestControlCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Signal = cls.env["td.signal"].sudo()
        cls.Source = cls.env["td.source"].sudo()
        cls.src = cls.Source.search([("code", "=", "ENERGY-CTL")])

    def make(self, code, **kw):
        vals = {"code": code, "name": code, "kind": "gauge", "module": "energy_control", "source_id": self.src.id}
        vals.update(kw)
        return self.Signal.create(vals)

    def test_forbidden_codes(self):  # AC-165
        for code in ("fire/panel/x", "workcenters/saw-1/x", "access/x", "evacuation/lights/x", "sprinklers/x"):
            with self.assertRaisesRegex(ValidationError, "керування цією системою заборонене"), self.cr.savepoint():
                self.make(code)
        for module in ("fire_safety", "access", "machine_connect"):
            src = self.Source.create(
                {"code": "SRC-" + module.upper().replace("_", "-"), "name": module, "type": "modbus_tcp",
                 "collector_id": self.src.collector_id.id, "params": {"host": "h", "port": 502, "unit": 1}, "module": module}
            )  # fmt: skip
            with self.assertRaises(ValidationError), self.cr.savepoint():
                self.make("energy_control/x/%s" % module, source_id=src.id)
        self.make("energy_control/test/ok")
        with self.assertRaises(ValidationError), self.cr.savepoint():  # W1 AC-81
            self.Signal.create(
                {"code": "energy/x/y", "name": "y", "kind": "gauge", "module": "energy", "write_enabled": True}
            )

    def test_source_type(self):  # AC-228
        ok = self.Source.create(
            {"code": "ECTL-T", "name": "t", "type": "energy_ctl", "collector_id": self.src.collector_id.id,
             "params": {"engine": {"tick_s": 2}}, "module": "energy_control"}
        )  # fmt: skip
        self.assertEqual(ok.type, "energy_ctl")
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.Source.create(
                {"code": "ECTL-X", "name": "t", "type": "energy_ctl", "params": {}, "module": "energy_control"}
            )
        with self.assertRaises(ValidationError), self.cr.savepoint():
            ok.params = {"engine": {"tick_s": 50}}
        with self.assertRaises(ValidationError), self.cr.savepoint():
            ok.params = {"engine": {"tick_s": 2}, "password": "x"}
        self.assertFalse(self.Source.with_context().search([("type", "=", "energy_ctl"), ("collector_id", "=", False)]))
