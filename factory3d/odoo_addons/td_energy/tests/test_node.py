"""AC-01…AC-06: вузли мережі, лічильники (дані після post_init_hook)."""

from collections import Counter

from psycopg2 import IntegrityError

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import TAGS, F3DEnergyCase


@tagged(*TAGS)
class TestNodes(F3DEnergyCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Node = cls.env["td.energy.node"]
        cls.Meter = cls.env["td.energy.meter"]

    def node(self, code):
        rec = self.Node.search([("code", "=", code)])
        self.assertTrue(rec, "немає вузла %s" % code)
        return rec

    def test_123_nodes(self):  # AC-01
        nodes = self.Node.search([])
        self.assertEqual(len(nodes), 123)
        self.assertEqual(
            dict(Counter(nodes.mapped("kind"))),
            {"input": 1, "substation": 1, "transformer": 2, "switchboard": 1, "section": 2, "cell": 11, "line": 6,
             "tapoff": 36, "consumer": 49, "generator": 12, "storage": 1, "ats": 1},
        )  # fmt: skip
        for code, parent in (("QF-1", "SEC-2"), ("BW-1", "QF-1"), ("SAW-1", "TAP-SAW-1"), ("TAP-SAW-1", "BW-1"),
                             ("COMPRESSOR", "C1")):  # fmt: skip
            self.assertEqual(self.node(code).parent_id.code, parent, code)
        self.assertEqual(self.node("QS").peer_id.code, "SEC-2")
        self.assertEqual(set(nodes.filtered(lambda n: n.kind == "cell").cabinet_id.mapped("code")), {"SWB-1"})
        self.assertEqual(self.node("SAW-1").section, 2)
        self.assertEqual(self.node("SAND-1").section, 1)

    def test_node_constraints(self):  # AC-02
        sec1 = self.node("SEC-1")
        wc = self.env["mrp.workcenter"].create({"name": "EN-WC-1"})

        def new(**kw):
            vals = {"code": "TST-1", "name": "Тест", "kind": "consumer", "parent_id": sec1.id}
            vals.update(kw)
            return self.Node.create(vals)

        pool = self.env["td.energy.pool"].create({"code": "POOL-TST", "name": "Тест"})
        bad = [
            {"code": "saw-1"},
            {"alloc_role": "direct"},
            {"alloc_role": "shared"},
            {"alloc_role": "direct", "workcenter_id": wc.id, "pool_id": pool.id},
            {"kind": "cell"},
            {"kind": "line"},
            {"section": 3},
            {"parent_id": False},
            {"kind": "tapoff", "workcenter_id": wc.id},
        ]
        for vals in bad:
            with self.subTest(vals=vals), self.assertRaises(ValidationError), self.env.cr.savepoint():
                new(**vals)
        child = new(code="TST-2")
        with self.assertRaises(ValidationError), self.env.cr.savepoint():
            sec1.write({"parent_id": child.id})
        new(code="TST-3", alloc_role="direct", workcenter_id=wc.id)
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.env.cr.savepoint():
            new(code="TST-4", workcenter_id=wc.id)
            self.env.flush_all()

    def test_tree(self):  # AC-03
        qf1 = self.node("QF-1")
        tree = self.Node.search([("id", "child_of", qf1.id)])
        codes = set(tree.mapped("code"))
        self.assertIn("BW-1", codes)
        self.assertEqual(len(tree.filtered(lambda n: n.kind == "tapoff")), 7)
        consumers = tree.filtered(lambda n: n.kind == "consumer")
        self.assertEqual(
            set(consumers.mapped("code")), {"SAW-1", "SAW-2", "EDGE-1", "EDGE-2", "CNC-1", "CNC-2", "SORT-1"}
        )
        # AC-03: «1 201» у SPEC — Σ p_inst_kw усіх 49 споживачів (R-06), а не піддерева QF-1 (207,5)
        self.assertAlmostEqual(sum(consumers.mapped("p_inst_kw")), 207.5, delta=0.1)
        total = self.Node.search([("kind", "=", "consumer")])
        self.assertEqual(len(total), 49)
        self.assertAlmostEqual(sum(total.mapped("p_inst_kw")), 1201.0, delta=0.1)
        meters = self.node("QF-3")._td_descendant_meters()
        self.assertEqual(
            set(meters.node_id.mapped("code")),
            {"SAND-1", "AUTOSPRAY-1", "UV-1", "HINGE-1", "GLUE-1", "PRESS-1", "SPRAY-1", "DRY-1"},
        )
        self.assertEqual(len(meters), 8)
        self.assertNotIn("PM-QF-3", meters.mapped("code"))

    def test_critical(self):  # AC-04
        critical = self.Node.search([("is_critical", "=", True)])
        self.assertEqual(
            set(critical.mapped("code")),
            {"LP-1", "LP-2", "LP-3", "DUST-1", "COMPRESSOR", "BOILER", "OFFICE", "EF-ELEC", "EF-CHG", "BW-1"},
        )

    def test_67_meters(self):  # AC-05
        meters = self.Meter.search([("e_import_signal_id", "!=", False)])  # без лічильників ресурсів
        self.assertEqual(len(meters), 67)
        self.assertEqual(dict(Counter(meters.mapped("model"))),
                         {"pm5560": 57, "sun2000": 8, "luna2000": 1, "tedom": 1})  # fmt: skip
        pm = meters.filtered(lambda m: m.model == "pm5560")
        self.assertEqual(dict(Counter(pm.mapped("role"))), {"incomer": 2, "feeder": 6, "consumer": 49})
        by_code = {m.code: m for m in meters}
        self.assertEqual(by_code["PM-Q1"].e_export_signal_id.code, "energy/cells/Q1/kwh_export")
        saw = by_code["PM-SAW-1"]
        self.assertEqual(saw.e_import_signal_id.code, "energy/consumers/SAW-1/kwh_total")
        self.assertEqual(saw.p_signal_id.code, "energy/consumers/SAW-1/p_now")
        self.assertEqual(saw.max_kw, 48)
        self.assertEqual(by_code["PM-Q1"].max_kw, 1109)
        self.assertEqual(by_code["LUNA-1"].e_export_signal_id.code, "infra/bess/kwh_discharge_total")
        self.assertEqual(self.node("SAW-1").meter_id, saw)

    def test_meter_signal_checks(self):  # AC-06
        meter = self.Meter.search([("code", "=", "PM-SAW-1")])
        Signal = self.env["td.signal"]
        gauge = Signal.create({"code": "energy/test/gauge_kwh", "name": "Тест", "kind": "gauge", "unit": "кВт·год"})
        counter_kw = Signal.create({"code": "energy/test/counter_kw", "name": "Тест", "kind": "counter", "unit": "кВт"})
        with self.assertRaisesRegex(ValidationError, "накопичувальним"), self.env.cr.savepoint():
            meter.e_import_signal_id = gauge
        with self.assertRaisesRegex(ValidationError, "в кВт·год"), self.env.cr.savepoint():
            meter.e_import_signal_id = counter_kw
        with self.assertRaisesRegex(ValidationError, "в кВт"), self.env.cr.savepoint():
            meter.p_signal_id = gauge
