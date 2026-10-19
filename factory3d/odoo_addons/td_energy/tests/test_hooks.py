"""AC-12…AC-14, AC-70…AC-72, AC-74: post_init_hook, повтор прив'язки, uninstall_hook.
Стендові частини AC-13 (копія демо) та AC-73 (API колектора) — W6."""

import csv
import json
import os

from odoo.addons.td_telemetry.tools import address as address_tools
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from .. import hooks
from .common import TAGS, F3DEnergyCase

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def csv_rows(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@tagged(*TAGS)
class TestHooks(F3DEnergyCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Signal = cls.env["td.signal"].with_context(active_test=False)
        cls.models = ("td.energy.node", "td.energy.meter", "td.energy.pool", "td.energy.tariff")

    def counts(self):
        return {m: self.env[m].with_context(active_test=False).search_count([]) for m in self.models} | {
            "source": self.env["td.source"].with_context(active_test=False).search_count([]),
            "signal": self.Signal.search_count([]),
        }

    def test_install_report(self):  # AC-12 (звіт установки; кількості, що не залежать від наявності обладнання)
        report = json.loads(self.env["ir.config_parameter"].get_param("td.energy.install_report"))
        for key, value in {"nodes": 124, "sources": 69, "meters": 67, "pools": 5}.items():
            self.assertEqual(report[key], value, key)
        self.assertEqual(report["equipment_linked"] + report["unmatched_equipment"], 80)
        self.assertEqual(report["workcenter_linked"] + report["direct_without_wc"], 35)
        self.assertEqual(report["critical"], 10)
        self.assertEqual(report["signals"]["created"] + report["signals"]["updated"], 312)
        self.assertEqual(report["signals"]["module_energy"], 312)
        partial = report["unmatched_equipment"] > 0 or report["direct_without_wc"] > 0
        self.assertEqual(report["state"], "partial" if partial else "done")
        t1 = self.Signal.search([("code", "=", "energy/transformers/T1/temp_c")])
        self.assertEqual(t1.source_id.code, "MB-U96-RTD1")
        self.assertTrue(t1.address)

    def test_rebind_idempotent(self):  # AC-14
        before = self.counts()
        node = self.env["td.energy.node"]
        result = node.with_user(self.u_admin).action_td_energy_rebind()
        self.assertEqual(result["tag"], "display_notification")
        report = json.loads(self.env["ir.config_parameter"].get_param("td.energy.install_report"))
        self.assertEqual(report["signals"]["created"], 0)
        self.assertEqual(report["derived_source"]["created"], 0)
        self.assertEqual(self.counts(), before)
        with self.assertRaises(AccessError):
            node.with_user(self.u_energy).action_td_energy_rebind()

    def test_addresses(self):  # AC-70
        def sig(code):
            rec = self.Signal.search([("code", "=", code)])
            self.assertTrue(rec, code)
            return rec

        p = sig("energy/consumers/SAW-1/p_now")
        self.assertEqual((p.address["fc"], p.address["addr"], p.address["type"]), (3, 3059, "f32"))
        self.assertEqual((p.source_id.code, p.source_id.params["unit"]), ("MB-U11-PM-SAW-1", 11))
        k = sig("energy/consumers/SAW-1/kwh_total")
        self.assertEqual((k.address["addr"], k.address["type"], k.address["scale"]), (3203, "i64", 0.001))
        pv = sig("infra/pv/PV-INV-3/p_kw")
        self.assertEqual((pv.address["addr"], pv.address["type"], pv.address["scale"]), (32080, "i32", 0.001))
        self.assertEqual(pv.source_id.code, "MB-U63-SUN-3")
        ats = sig("infra/ats/position")
        self.assertEqual((ats.address["addr"], ats.kind, len(ats.states)), (20483, "state", 4))
        self.assertEqual(sig("infra/chp/state").address["addr"], 40000)
        expected = [r for r in csv_rows("energy_signals.csv") if r["address"]]
        self.assertTrue(expected)
        for row in expected:
            rec = sig(row["code"])
            self.assertFalse(address_tools.validate_address("modbus_tcp", rec.address), row["code"])

    def test_derived_source(self):  # AC-71
        derived = self.env.ref("td_energy.source_en_derived")
        self.assertEqual((derived.code, derived.type, derived.module), ("EN-DERIVED", "f3d_energy", "energy"))
        self.assertFalse(derived.collector_id)
        self.assertIn("f3d_energy", self.env["td.source"]._td_local_types())
        shifts = self.Signal.search([("code", "=like", "energy/consumers/%/kwh_shift")])
        self.assertEqual(len(shifts), 49)
        for s in shifts:
            self.assertEqual(s.source_id, derived)
            self.assertEqual(s.derived_from_id.code, s.code.replace("kwh_shift", "kwh_total"))

    def test_thresholds_binding(self):  # AC-72
        t1 = self.Signal.search([("code", "=", "energy/transformers/T1/temp_c")])
        address, source = t1.address, t1.source_id
        t1.write({"warn_high": 100, "alarm_high": 110, "hysteresis": 0})
        hooks.run_bind(self.env)
        self.assertEqual((t1.address, t1.source_id), (address, source))
        self.assertEqual((t1.warn_high, t1.alarm_high, t1.hysteresis, t1.min_duration_s), (130, 140, 2, 60))

    def test_write_forbidden(self):  # A-15
        sig = self.Signal.search([("code", "=", "energy/consumers/SAW-1/p_now")])
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            sig.write_enabled = True

    def test_uninstall(self):  # AC-74
        migrated = self.Signal.search([("code", "=", "energy/consumers/SAW-1/p_now")])
        self.env["ir.model.data"].search([("model", "=", "td.signal"), ("res_id", "=", migrated.id)]).unlink()
        migrated.origin = "sim_data"
        created = self.env["ir.model.data"].search([("model", "=", "td.signal"), ("name", "=like", "sig\\_%")])
        created_ids = set(created.mapped("res_id"))
        self.assertTrue(created_ids)
        hooks.uninstall_hook(self.env)
        self.assertFalse(self.env["ir.config_parameter"].search([("key", "=like", "td.energy.%")]))
        codes = [r["code"] for r in csv_rows("energy_signals.csv")]
        signals = self.Signal.search([("code", "in", codes)])
        self.assertFalse(signals.filtered("source_id"))
        self.assertTrue(migrated.active)
        self.assertFalse(signals.filtered(lambda s: s.id in created_ids and s.active))
        sources = self.env["td.source"].with_context(active_test=False).search([("code", "=like", "MB-U%-%")])
        self.assertFalse(sources.filtered(lambda s: s.module == "energy" and s.active))
