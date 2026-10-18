"""SPEC §13.1: CSV ↔ макет. Чистий Python (без БД): структура й узгодженість data/energy_*.csv, збіг із генератором."""

import csv
import importlib.util
import json
import os
import tempfile
from collections import Counter

from odoo.tests.common import BaseCase, tagged

MODULE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(MODULE, "data")
REPO = os.path.abspath(os.path.join(MODULE, "..", ".."))  # factory3d/: тут лежить plant/
KINDS = {"input", "substation", "transformer", "switchboard", "cell", "section", "line", "tapoff", "consumer",
         "generator", "storage", "ats"}  # fmt: skip


def read(name):
    with open(os.path.join(DATA, name), encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@tagged("post_install", "-at_install", "f3d", "f3d_energy")
class TestDataSync(BaseCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.nodes = read("energy_nodes.csv")
        cls.sources = read("energy_sources.csv")
        cls.signals = read("energy_signals.csv")
        cls.meters = read("energy_meters.csv")
        cls.pools = read("energy_pools.csv")
        cls.node = {r["code"]: r for r in cls.nodes}

    def test_counts(self):
        self.assertEqual(
            (len(self.nodes), len(self.sources), len(self.signals), len(self.meters), len(self.pools)),
            (123, 68, 297, 67, 5),
        )

    def test_codes_unique(self):
        for rows in (self.nodes, self.sources, self.signals, self.meters, self.pools):
            codes = [r["code"] for r in rows]
            self.assertEqual(len(codes), len(set(codes)))

    def test_nodes_integrity(self):
        pools = {p["code"] for p in self.pools}
        for r in self.nodes:
            self.assertIn(r["kind"], KINDS, r["code"])
            for col in ("parent", "cabinet", "peer"):
                if r[col]:
                    self.assertIn(r[col], self.node, "%s.%s" % (r["code"], col))
            if r["pool"]:
                self.assertIn(r["pool"], pools)
            self.assertEqual(bool(r["pool"]), r["alloc_role"] == "shared", r["code"])
        self.assertEqual(len([r for r in self.nodes if r["kind"] == "cell"]), 11)
        self.assertEqual([r["sequence"] for r in self.nodes if r["cabinet"]][:2], ["20", "100"])

    def test_nodes_counts_appendix_b(self):
        """§5.3 п. 4: equipment 80, workcenter 35, critical 10; роль direct = 35, shared 8, overhead 6."""
        self.assertEqual(sum(1 for r in self.nodes if r["equipment"]), 80)
        self.assertEqual(sum(1 for r in self.nodes if r["workcenter"]), 35)
        self.assertEqual(sum(1 for r in self.nodes if r["is_critical"]), 10)
        roles = Counter(r["alloc_role"] for r in self.nodes if r["alloc_role"])
        self.assertEqual(dict(roles), {"direct": 35, "shared": 8, "overhead": 6})
        direct = [r for r in self.nodes if r["alloc_role"] == "direct"]
        self.assertTrue(all(r["workcenter"] == r["code"] for r in direct))

    def test_nodes_spot_appendix_b(self):
        n = self.node
        self.assertEqual(
            (n["SAW-1"]["p_inst_kw"], n["SAW-1"]["load_factor"], n["SAW-1"]["idle_factor"]), ("24", "0.55", "0.12")
        )
        self.assertEqual(
            (n["SAW-1"]["cos_phi"], n["SAW-1"]["p_inst_source"], n["SAW-1"]["unit"]), ("0.84", "estimate", "11")
        )
        self.assertEqual((n["EDGE-1"]["p_inst_kw"], n["EDGE-1"]["idle_factor"]), ("67.5", "0.3"))
        self.assertEqual(
            (n["GANTRY-1"]["load_factor"], n["GANTRY-1"]["pool"], n["GANTRY-1"]["unit"]), ("0.347", "POOL-GANTRY", "46")
        )
        self.assertEqual((n["COMPRESSOR"]["pool"], n["COMPRESSOR"]["is_critical"]), ("POOL-AIR", "1"))
        self.assertEqual(n["BW-1"]["is_critical"], "1")
        self.assertEqual((n["QS"]["parent"], n["QS"]["peer"], n["QS"]["section"]), ("SEC-1", "SEC-2", "0"))
        self.assertEqual((n["PV-INV-3"]["unit"], n["PV-INV-3"]["p_inst_kw"]), ("63", "115"))
        self.assertEqual((n["CHP"]["unit"], n["BESS"]["unit"], n["ATS-1"]["unit"]), ("72", "69", "71"))
        self.assertEqual((n["GENSET"]["parent"], n["GENSET"]["p_inst_kw"]), ("ATS-1", "507"))
        self.assertEqual((n["T1"]["rating_kva"], n["Q1"]["rating_a"], n["QF-C2"]["rating_a"]), ("1000", "1600", "400"))
        self.assertEqual((n["RM6-1"]["voltage_kv"], n["GRID-10KV"]["voltage_kv"]), ("10", "10"))
        self.assertEqual(n["TAP-SAW-3"]["parent"], "BW-2")
        self.assertEqual([c["code"] for c in self.nodes[:5]], ["GRID-10KV", "RM6-1", "T1", "T2", "SWB-1"])

    def test_sections(self):
        sec = {r["code"]: r["section"] for r in self.nodes}
        self.assertEqual(
            (sec["SAW-1"], sec["SAW-3"], sec["BOILER"], sec["CHP"], sec["PV-INV-1"]), ("2", "1", "1", "2", "2")
        )
        self.assertEqual((sec["SORT-1"], sec["ASM-1"], sec["OFFICE"], sec["BW-3"]), ("2", "2", "2", "1"))

    def test_sources(self):
        units = Counter(r["unit"] for r in self.sources)
        self.assertEqual(max(units.values()), 1)
        self.assertEqual({r["host"] for r in self.sources}, {"iot-sim"})
        self.assertEqual({(r["port"], r["timeout_s"], r["retries"], r["max_block"], r["gap_max"]) for r in self.sources},
                         {("502", "3", "2", "125", "8")})  # fmt: skip
        for r in self.sources:
            self.assertTrue(r["code"].startswith("MB-U%02d-" % int(r["unit"])), r["code"])
            if r["equipment"]:
                self.assertIn(r["equipment"], self.node, r["code"])

    def test_signals(self):
        codes = {r["code"] for r in self.signals}
        src = {r["code"] for r in self.sources}
        extra = {"EN-DERIVED", "MB-U96-RTD1"}
        for r in self.signals:
            self.assertIn(r["source"], src | extra, r["code"])
            self.assertEqual(bool(r["address"]), r["source"] != "EN-DERIVED", r["code"])
            if r["address"]:
                self.assertIn("addr", json.loads(r["address"]))
            for col in ("states", "alarm_states"):
                if r[col]:
                    self.assertIsInstance(json.loads(r[col]), list)
            if r["derived_from"]:
                self.assertIn(r["derived_from"], codes)
            if r["equipment"]:
                self.assertIn(r["equipment"], self.node, r["code"])
        by_src = Counter(r["source"] == "EN-DERIVED" for r in self.signals)
        self.assertEqual(by_src[True], 75)
        self.assertEqual(sum(1 for r in self.signals if r["binding"] == "thresholds"), 2)
        self.assertEqual(
            dict(Counter(r["origin"] for r in self.signals)), {"sim_data": 87, "catalog": 63, "module": 147}
        )
        self.assertEqual(sum(1 for r in self.signals if r["source"] not in (extra | {"EN-DERIVED"})), 220 - 0)

    def test_meters(self):
        sigs = {r["code"] for r in self.signals}
        src = {r["code"] for r in self.sources}
        for r in self.meters:
            self.assertIn(r["node"], self.node)
            self.assertIn(r["source"], src)
            for col in ("p_signal", "e_import_signal", "e_export_signal"):
                if r[col]:
                    self.assertIn(r[col], sigs, r["code"])
        roles = Counter(r["role"] for r in self.meters)
        self.assertEqual(dict(roles), {"incomer": 2, "feeder": 6, "consumer": 49, "generation": 9, "storage": 1})
        self.assertEqual(len([r for r in self.meters if r["model"] == "pm5560"]), 57)

    def test_pools(self):
        pools = {p["code"]: p for p in self.pools}
        self.assertEqual(list(pools), ["POOL-AIR", "POOL-DUST", "POOL-GANTRY", "POOL-LIGHT", "POOL-HVAC"])
        self.assertEqual(pools["POOL-GANTRY"]["workcenters"], "SAW-1;SAW-2;SAW-3;NEST-1")
        self.assertEqual({p["driver"] for p in self.pools}, {"kwh", "time"})
        for p in self.pools:
            for wc in filter(None, p["workcenters"].split(";")):
                self.assertEqual(self.node[wc]["workcenter"], wc)

    def test_generator_reproducible(self):
        """Файли в data/ збігаються з виводом генератора (коли поруч лежить plant/)."""
        if not os.path.isdir(os.path.join(REPO, "plant")):
            self.skipTest("plant/ недоступний")
        spec = importlib.util.spec_from_file_location(
            "gen_energy_data", os.path.join(MODULE, "tools", "gen_energy_data.py")
        )
        gen = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gen)
        with tempfile.TemporaryDirectory() as tmp:
            gen.generate(REPO, tmp)
            for name in sorted(os.listdir(tmp)):
                with open(os.path.join(tmp, name), "rb") as a, open(os.path.join(DATA, name), "rb") as b:
                    self.assertEqual(a.read(), b.read(), name)
