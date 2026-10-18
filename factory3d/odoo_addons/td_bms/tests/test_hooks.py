import csv
import json

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tools import file_open, mute_logger

from .. import hooks
from .common import F3DBmsCase

DERIVED = "BMS-DERIVED"

# Додаток A.1: code -> (n, площа, E_н, e_calc, level, control, dali_devices, p_inst)
A1 = {
    "LT-RCV-1": (4, 118.4, 300, 388, 1.0, "shift", "@1.1.1.1-4", 0.5),
    "LT-RCV-2": (4, 124.2, 300, 370, 1.0, "shift", "@1.1.1.5-8", 0.5),
    "LT-RCV-3": (4, 124.2, 300, 370, 1.0, "shift", "@1.1.1.9-12", 0.5),
    "LT-RCV-4": (4, 124.2, 300, 370, 1.0, "shift", "@1.1.1.13-16", 0.5),
    "LT-RCV-5": (4, 124.2, 300, 370, 1.0, "shift", "@1.1.1.17-20", 0.5),
    "LT-RCV-6": (4, 124.2, 300, 370, 1.0, "shift", "@1.1.1.21-24", 0.5),
    "LT-RCV-7": (4, 144.0, 300, 319, 1.0, "shift", "@1.1.1.25-28", 0.5),
    "LT-SHEETS": (12, 1200.6, 100, 115, 0.8, "presence", "@1.1.1.29-40", 1.51),
    "LT-HW": (5, 350.5, 150, 164, 0.7, "presence", "@1.1.1.41-45", 0.63),
    "LT-EDGE": (3, 167.6, 150, 205, 0.7, "presence", "@1.1.1.46-48", 0.38),
    "LT-PKS": (2, 142.2, 100, 161, 0.6, "presence", "@1.1.1.49-50", 0.25),
    "LT-CUT": (27, 609.3, 500, 509, 1.0, "shift", "@1.2.1.1-27", 3.4),
    "LT-EB": (27, 564.5, 500, 549, 1.0, "shift", "@1.2.1.28-54", 3.4),
    "LT-CNC": (27, 564.5, 500, 549, 1.0, "shift", "@1.2.2.1-27", 3.4),
    "LT-SORT": (12, 439.0, 300, 314, 1.0, "shift", "@1.2.2.28-39", 1.51),
    "LT-FAC": (91, 1235.0, 750, 846, 1.0, "shift", "@1.2.3.1-64;@1.2.4.1-27", 11.47),
    "LT-ASM": (15, 498.8, 300, 345, 1.0, "shift", "@1.3.1.1-15", 1.89),
    "LT-PRE": (4, 268.3, 150, 171, 0.8, "presence", "@1.3.1.16-19", 0.5),
    "LT-MAINT": (4, 125.4, 300, 366, 1.0, "shift", "@1.3.1.20-23", 0.5),
    "LT-PACK": (12, 382.8, 300, 360, 1.0, "shift", "@1.3.1.24-35", 1.51),
    "LT-POST": (3, 297.0, 100, 116, 0.8, "presence", "@1.3.1.36-38", 0.38),
    "LT-CMP": (2, 63.8, 200, 360, 0.5, "presence", "@1.3.1.39-40", 0.25),
    "LT-CHG": (2, 63.8, 200, 360, 0.5, "presence", "@1.3.1.41-42", 0.25),
    "LT-FG": (12, 835.0, 150, 165, 0.6, "presence", "@1.3.1.43-54", 1.51),
    "LT-ELEC": (4, 118.8, 200, 387, 0.5, "presence", "@1.3.1.55-58", 0.5),
    "LT-OUT-1": (4, 124.0, 300, 370, 1.0, "shift", "@1.3.1.59-62", 0.5),
    "LT-OUT-2": (4, 130.0, 300, 353, 1.0, "shift", "@1.3.2.1-4", 0.5),
    "LT-OUT-3": (4, 130.0, 300, 353, 1.0, "shift", "@1.3.2.5-8", 0.5),
    "LT-OUT-4": (4, 130.0, 300, 353, 1.0, "shift", "@1.3.2.9-12", 0.5),
    "LT-OUT-5": (4, 130.0, 300, 353, 1.0, "shift", "@1.3.2.13-16", 0.5),
    "LT-OUT-6": (4, 130.0, 300, 353, 1.0, "shift", "@1.3.2.17-20", 0.5),
    "LT-OUT-7": (4, 150.8, 300, 305, 1.0, "shift", "@1.3.2.21-24", 0.5),
}
NORMS = {
    "woodworking_machine": 500,
    "woodworking_bench": 300,
    "spraying": 750,
    "sanding": 750,
    "quality_control": 1000,
    "storage_racks": 150,
    "storage_floor": 100,
    "packing_dispatch": 300,
    "loading_ramps": 150,
    "switchgear_room": 200,
    "compressor_room": 200,
    "battery_charging": 200,
    "corridors_traffic": 150,
}


def _csv_rows():
    with file_open("factory3d_bms/data/bms_signals.csv", "rb") as f:
        return list(csv.DictReader(f.read().decode("utf-8").splitlines()))


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestData(F3DBmsCase):
    """Дані з макета (A.0, A.1): норми, групи, адресація DALI."""

    def test_13_norms_effective_lux(self):
        norms = self.env["f3d.bms.light.norm"].search([])
        self.assertEqual({n.key: n.lux for n in norms}, NORMS)
        racks = norms.filtered(lambda n: n.key == "storage_racks")
        self.assertTrue(racks.ref_en.startswith("EN 12464-1"))

    def test_6_scenes(self):
        scenes = self.env["f3d.bms.light.scene"].search([])
        self.assertEqual(
            [(s.number, s.level_pct) for s in scenes], [(1, 100), (2, 75), (3, 50), (4, 25), (5, 10), (6, 0)]
        )

    def test_32_groups_match_macro(self):
        groups = self.env["f3d.bms.light.group"].search([])
        self.assertEqual(len(groups), 32)
        self.assertEqual(sum(groups.mapped("n_fixtures")), 320)
        self.assertAlmostEqual(sum(groups.mapped("p_inst_kw")), 40.32, delta=0.1)
        self.assertEqual(len(groups.filtered(lambda g: g.control_mode == "shift")), 22)
        for g in groups:
            n, area, e_norm, e_calc, level, control, _devs, p_inst = A1[g.code]
            with self.subTest(code=g.code):
                self.assertEqual(g.n_fixtures, n)
                self.assertAlmostEqual(g.area_m2, area, 1)
                self.assertEqual(g.e_norm, e_norm)
                self.assertEqual(g.e_calc, e_calc)
                self.assertEqual(g.level_design, level)
                self.assertEqual(g.control_mode, control)
                self.assertAlmostEqual(g.p_inst_kw, p_inst, 2)
                self.assertEqual((g.lumen, g.watt), (20500, 126))
                self.assertEqual(g.name, "Освітлення: " + g.zone_id.name)

    def test_devices_match_appendix(self):
        groups = self.env["f3d.bms.light.group"].search([], order="sequence")
        self.assertEqual([g.dali_group for g in groups], list(range(1, 33)))
        for g in groups:
            self.assertEqual(g.dali_devices, A1[g.code][6], g.code)
        panels = {p.code: p for p in self.env["f3d.bms.light.panel"].search([])}
        self.assertEqual(sorted(panels), ["LP-1", "LP-2", "LP-3"])
        self.assertEqual(
            (panels["LP-1"].n_fixtures, panels["LP-2"].n_fixtures, panels["LP-3"].n_fixtures), (50, 184, 86)
        )
        self.assertEqual([panels[c].source_id.code for c in sorted(panels)], ["HN-LP-1", "HN-LP-2", "HN-LP-3"])

    def test_units(self):
        units = self.env["f3d.bms.hvac.unit"].search([])
        self.assertEqual(len(units), 29)
        rv5 = units.filtered(lambda u: u.code == "RV-05")
        self.assertEqual((rv5.bacnet_device, rv5.source_id.code, rv5.mode_design), (105, "BAC-105-RV-05", "AQ"))
        self.assertEqual((rv5.airflow_nom, rv5.heat_nom_kw, rv5.p_inst_kw), (8000.0, 116.8, 8.6))
        ef = units.filtered(lambda u: u.code == "EF-ELEC")
        self.assertEqual((ef.fan_count, ef.airflow_nom, ef.required_in_work), (2, 14120.0, False))
        self.assertEqual(units.filtered(lambda u: u.code == "EF-CHG").required_m3h, 158.4)
        self.assertEqual(units.filtered(lambda u: u.code == "AHU-1").t_supply_design, 21.0)

    def test_balance_753(self):
        bal = self.env["f3d.bms.heat.balance"].search([])
        self.assertEqual(len(bal), 1)
        self.assertEqual(bal.total_kw, 753)
        self.assertEqual(len(bal.line_ids), 4)

    def test_sources(self):
        sources = self.env["f3d.source"].search([("module", "=", "bms")])
        self.assertEqual(len(sources), 33)
        derived = sources.filtered(lambda s: s.code == "BMS-DERIVED")
        self.assertEqual((derived.type, derived.collector_id.id, derived.period_s_default), ("f3d_bms", False, 60))
        self.assertEqual(self.env.ref("factory3d_bms.source_bms_derived"), derived)
        self.assertEqual(len(sources.filtered(lambda s: s.type == "bacnet_ip")), 29)
        self.assertEqual(len(sources.filtered(lambda s: s.type == "helvarnet")), 3)


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestInstall(F3DBmsCase):
    """AC-48, AC-51, AC-53…AC-56: хук установки, сигнали, прапори, деінсталяція."""

    def setUp(self):
        super().setUp()
        self.icp = self.env["ir.config_parameter"].sudo()
        self.Signal = self.env["f3d.signal"].with_context(active_test=False)

    def _module_signals(self):
        return self.Signal.search([("module", "=", "bms")])

    def test_counts(self):
        report = json.loads(self.icp.get_param("factory3d.bms.install_report"))
        self.assertIn(report["state"], ("done", "partial"))
        self.assertEqual(len(self._module_signals()), 549)
        self.assertEqual(report["created"] + report["updated"], 549)
        if report["state"] == "partial":
            self.assertGreater(report["not_found"], 0)
        else:
            self.assertEqual(report["not_found"], 0)

    def test_signal_count_and_origins(self):
        sigs = self._module_signals()
        by_origin = {o: len(sigs.filtered(lambda s, o=o: s.origin == o)) for o in ("sim_data", "catalog", "module")}
        # CSV: catalog 176 + sim_data 81 (створюються як catalog, DEC-7; на демо-копії — можливо вже sim_data);
        # module 292
        self.assertEqual(by_origin["catalog"] + by_origin["sim_data"], 257)
        self.assertEqual(by_origin["module"], 292)
        self.assertEqual(len(sigs.filtered("source_id.module")), 549)
        self.assertEqual(len(sigs.filtered(lambda s: s.source_id.code == "BMS-DERIVED")), 59)
        self.assertFalse(sigs.filtered("write_enabled"))

    def test_signal_definitions(self):
        sig = self.Signal.search([("code", "=", "ventilation/units/RV-05/filter_dp_pa")])
        self.assertEqual(sig.source_id.code, "BAC-105-RV-05")
        self.assertEqual(
            sig.address,
            {
                "object": "AI",
                "instance": 4,
                "property": "present-value",
                "mode": "poll",
                "doc": "AI:4 RV-05_FreshAirFilterDp",
            },
        )
        self.assertEqual((sig.period_s, sig.store_period_s, sig.alarm_high, sig.hysteresis), (30, 600, 250.0, 5.0))
        self.assertTrue(sig.alarm_high_on)
        lvl = self.Signal.search([("code", "=", "lighting/groups/LT-CUT/level")])
        self.assertEqual(lvl.source_id.code, "HN-LP-2")
        self.assertEqual(
            lvl.address, {"group": 12, "query": "level", "devices": ["@1.2.1.1-27"], "sample": 3, "fade_s": 2.0}
        )
        self.assertEqual((lvl.unit, lvl.period_s, lvl.store_period_s), ("%", 60, 900))
        chk = self.Signal.search([("code", "=", "lighting/groups/LT-CUT/check")])
        self.assertEqual(
            (chk.source_id.code, chk.kind, len(chk.states), len(chk.alarm_states)), ("BMS-DERIVED", "state", 6, 2)
        )
        self.assertFalse(chk.viewer_visible)
        mode = self.Signal.search([("code", "=", "ventilation/units/RV-05/mode")])
        self.assertEqual(len(mode.states), 8)
        self.assertEqual(sorted(mode.address["map"], key=int), [str(i) for i in range(1, 9)])
        rows = _csv_rows()
        self.assertEqual(len(rows), 549)
        for row in rows:
            sig = self.Signal.search([("code", "=", row["code"])])
            self.assertEqual(sig.module, "bms", row["code"])
            self.assertEqual(sig.source_id.code, row["source"], row["code"])
            self.assertEqual(sig.address or {}, json.loads(row["address"]), row["code"])
            self.assertFalse(sig.write_enabled)

    def test_links(self):
        unit = self.env["f3d.bms.hvac.unit"].search([("code", "=", "RV-05")])
        self.assertEqual(unit.filter_signal_id.code, "ventilation/units/RV-05/filter_dp_pa")
        self.assertEqual(unit.check_signal_id.code, "ventilation/units/RV-05/check")
        group = self.env["f3d.bms.light.group"].search([("code", "=", "LT-CUT")])
        self.assertEqual(group.level_signal_id.code, "lighting/groups/LT-CUT/level")
        self.assertEqual(group.faulty_signal_id.code, "lighting/groups/LT-CUT/faulty")
        panel = self.env["f3d.bms.light.panel"].search([("code", "=", "LP-2")])
        self.assertEqual(panel.state_signal_id.code, "lighting/panels/LP-2/state")
        bal = self.env["f3d.bms.heat.balance"].search([], limit=1)
        self.assertEqual(bal.outdoor_signal_id.code, "ventilation/totals/outdoor_c")
        self.assertEqual(bal.boiler_state_signal_id.code, "equipment/BOILER/state")
        self.assertEqual(bal.check_signal_id.code, "ventilation/heat_plant/check")
        if self.Signal.search_count([("code", "=", "equipment/BOILER/supply_c")]):  # сигнал telemetry є на демо
            self.assertEqual(bal.boiler_supply_signal_id.code, "equipment/BOILER/supply_c")

    def test_reinstall_idempotent(self):
        before = {
            m: self.env[m].with_context(active_test=False).search_count([])
            for m in ("f3d.bms.light.norm", "f3d.bms.light.group", "f3d.bms.hvac.unit", "f3d.signal", "f3d.source")
        }
        report = hooks.run_install(self.env)
        self.assertEqual(report["created"], 0)
        self.assertEqual(report["derived_created"], 0)
        self.assertEqual(report["updated"], 549)
        after = {m: self.env[m].with_context(active_test=False).search_count([]) for m in before}
        self.assertEqual(before, after)
        self.assertEqual(report["total_kw"], 753)
        self.assertEqual(json.loads(self.icp.get_param("factory3d.bms.install_report"))["state"], report["state"])

    def test_params_environment(self):
        keys = self.icp.search([("key", "=like", "factory3d.bms.%")]).mapped("key")
        self.assertGreaterEqual(len(keys), 15)
        self.icp.set_param("factory3d.base.environment", "prod")
        hooks.params(self.env)
        hooks.read_flags(self.env)
        self.assertEqual(self.icp.get_param("factory3d.bms.read_enabled"), "False")
        sources = self.env["f3d.source"].search([("module", "=", "bms")])
        self.assertEqual(len(sources), 33)
        self.assertFalse(sources.filtered("read_enabled"))
        self.assertEqual(set(sources.mapped("state")), {"disabled"})
        self.icp.set_param("factory3d.base.environment", "test")
        hooks.params(self.env)
        res = hooks.read_flags(self.env)
        self.assertEqual(res["sources_read"], 33)
        self.assertEqual(self.icp.get_param("factory3d.bms.read_enabled"), "True")
        self.assertEqual(len(sources.filtered("read_enabled")), 33)

    def test_write_flags(self):
        res = hooks.write_flags(self.env, enabled=True)
        self.assertEqual((res["sources_write"], res["signals_write"]), (29, 142))
        sigs = self._module_signals().filtered("write_enabled")
        self.assertEqual(len(sigs), 142)
        self.assertEqual(len(sigs.filtered(lambda s: s.code.endswith(("/level", "/scene")))), 64)
        srcs = self.env["f3d.source"].search([("module", "=", "bms"), ("write_enabled", "=", True)])
        self.assertFalse(srcs.filtered(lambda s: s.code in ("BAC-131-EF-ELEC", "BAC-133-EF-CHG", DERIVED)))
        res = hooks.write_flags(self.env, enabled=False)
        self.assertEqual((res["sources_write"], res["signals_write"]), (0, 0))

    def test_write_constraint(self):
        for code in (
            "ventilation/units/RV-05/airflow_m3h",
            "ventilation/units/EF-CMP/state",
            "equipment/BOILER/state",
            "lighting/groups/LT-CUT/faults",
        ):
            sig = self.Signal.search([("code", "=", code)])
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                sig.write({"write_enabled": True})
        ok = self.Signal.search([("code", "=", "ventilation/units/RV-05/setpoint_day_c")])
        ok.write({"write_enabled": True})
        self.assertTrue(ok.write_enabled)

    def test_uninstall_hook(self):
        sigs = self._module_signals()
        sim = sigs.filtered(lambda s: s.origin == "sim_data")
        hooks.uninstall_hook(self.env)
        self.assertFalse(self.icp.search([("key", "=like", "factory3d.bms.%")]))
        owned = self._module_signals().filtered(lambda s: s.origin in ("catalog", "module"))
        self.assertTrue(owned)
        self.assertFalse(owned.filtered("active"))
        self.assertFalse(owned.filtered("source_id"))
        self.assertFalse(sim.filtered("source_id"))
        self.assertFalse(sim.filtered("address"))
        self.assertEqual(len(self._module_signals()), 549)

    @mute_logger("odoo.sql_db")
    def test_neutralize(self):
        hooks.write_flags(self.env, enabled=True)
        self.env.flush_all()
        with file_open("factory3d_bms/data/neutralize.sql", "r") as f:
            self.env.cr.execute(f.read())
        self.env.invalidate_all()
        for key in ("read_enabled", "write_enabled"):
            self.assertEqual(self.icp.get_param("factory3d.bms." + key), "False")
        sources = self.env["f3d.source"].search([("module", "=", "bms")])
        self.assertFalse(sources.filtered(lambda s: s.read_enabled or s.write_enabled or s.state != "disabled"))
        self.assertFalse(self._module_signals().filtered("write_enabled"))
