"""Менеджер: заморожені контракти W4 (C-01…C-05, API-01) — `contracts/*.json` = реєстр Odoo й відповіді API.

Тест змінює лише менеджер. Форма відповіді `get_dashboard` перевіряється після появи методу (воркер A).
"""

import importlib
import json
from pathlib import Path

from odoo.tests import tagged
from odoo.tools import file_open

from .common import TAGS, TestW4Common

CONTRACTS = Path(__file__).resolve().parent.parent / "contracts"
FILES = (
    "api01_get_dashboard.json", "api01_rules.json", "c01_w3_resources.json", "c02_report_hook.json",
    "c03_energy_w1.json", "c04_mrp_stock.json", "c05_telemetry.json",
)  # fmt: skip
XMLID_ACTION = "td_energy_analytics.action_td_energy_shift_report"


def load(name):
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def check_shape(case, want, got, path="$"):
    """Набір ключів `got` = `want` (рекурсивно); списки — за першим елементом; `null` не порівнюється."""
    if want is None or got is None:
        return
    if isinstance(want, dict):
        case.assertIsInstance(got, dict, path)
        case.assertEqual(set(got), set(want), path)
        for key, value in want.items():
            check_shape(case, value, got[key], "%s.%s" % (path, key))
    elif isinstance(want, list) and want and got:
        case.assertIsInstance(got, list, path)
        check_shape(case, want[0], got[0], path + "[0]")


@tagged(*TAGS)
class TestW4Contracts(TestW4Common):
    def test_files(self):
        self.assertEqual(sorted(p.name for p in CONTRACTS.glob("*.json")), sorted(FILES))
        readme = (CONTRACTS / "README.md").read_text(encoding="utf-8")
        for name in FILES:
            load(name)  # валідний JSON
            self.assertIn(name, readme, name)

    def test_models_methods_tools_params(self):  # C-01, C-03, C-04, C-05: моделі, поля, методи, функції, параметри
        for name in ("c01_w3_resources.json", "c03_energy_w1.json", "c04_mrp_stock.json", "c05_telemetry.json"):
            contract = load(name)
            for model, names in contract["models"].items():
                self.assertIn(model, self.env, "%s: модель %s" % (name, model))
                missing = set(names) - set(self.env[model]._fields)
                self.assertFalse(missing, "%s: %s не має полів %s" % (name, model, sorted(missing)))
            for sign in contract.get("methods", []):
                model, method = sign.split("(")[0].rsplit(".", 1)
                self.assertTrue(callable(getattr(self.env[model], method, None)), "%s: %s" % (name, sign))
            for module, names in contract.get("tools", {}).items():
                mod = importlib.import_module("odoo.addons." + module)
                for item in names:
                    self.assertTrue(hasattr(mod, item), "%s: %s.%s" % (name, module, item))
            for key in contract.get("params", []):
                self.assertTrue(self.env["ir.config_parameter"].sudo().search_count([("key", "=", key)]), key)

    def test_c01_shift_windows(self):  # C-01: `tools/shifts` W3
        contract = load("c01_w3_resources.json")
        shifts = importlib.import_module("odoo.addons.td_energy_resources.tools.shifts")
        for method in contract["shift_windows_methods"]:
            self.assertTrue(callable(getattr(shifts.ShiftWindows, method, None)), method)
        self.assertIsInstance(shifts.load_windows(self.env), shifts.ShiftWindows)

    def test_c04_own_fields(self):  # C-04, C-02: власні поля модуля (`td_plate_area_m2`, `area_id`, `product_id`)
        for model, names in load("c04_mrp_stock.json")["own_fields"].items():
            self.assertFalse(set(names) - set(self.env[model]._fields), model)
        extensions = load("c02_report_hook.json")["extensions_owned_by_analytics"]
        for model, names in extensions.items():
            self.assertFalse(set(names) - set(self.env[model]._fields), model)
        self.assertTrue(self.env["td.energy.alloc"]._fields["product_id"].store)

    def test_c02_report_hook(self):  # C-02: хук W1 + кнопка Пульту
        contract = load("c02_report_hook.json")
        dash = self.env["td.energy.dashboard"]
        self.assertEqual(dash._td_report_action(), contract["analytics_value"])
        meta = dash.with_user(self.u_view).get_pult(parts=["kpis"])["meta"]
        self.assertEqual(meta["report_action"], contract["analytics_value"])
        self.assertIs(meta["capabilities"]["report"], True)
        client = contract["client"]
        with file_open(client["file"], "r") as f:
            source = f.read()
        self.assertIn(client["getter"], source)
        self.assertIn("meta.report_action", source)
        if not self.env.ref(XMLID_ACTION, raise_if_not_found=False):
            self.skipTest("Серверну дію V-13 створює W4-B (report/report_shift.xml)")
        self.assertEqual(self.env.ref(XMLID_ACTION)._name, "ir.actions.server")

    def test_api01_example(self):  # API-01: еталон узгоджений із правилами (форма відповіді — SPEC розд. 7)
        data, rules = load("api01_get_dashboard.json"), load("api01_rules.json")
        self.assertEqual(set(data), set(rules["always"]) | set(rules["parts"]))
        self.assertEqual([k["id"] for k in data["kpis"]], rules["kpi_ids"])
        for kpi in data["kpis"]:
            self.assertEqual(set(kpi), set(rules["kpi_keys"]), kpi["id"])
            self.assertIn(kpi["tone"], rules["tones"])
        cells = data["heatmap"]["cells"]
        self.assertEqual((len(cells), {len(row) for row in cells}), (rules["heatmap_shape"]["rows"], {24}))
        self.assertEqual(len(data["heatmap"]["days"]), 7)
        self.assertLess(len(json.dumps(data)), rules["limits"]["max_bytes"])
        cost_keys = set(rules["cost_keys_removed_without_group"]["keys"])
        present = set(data["enpi"]) | set(data["budget"]) | set(data["cut"]["rows"][0]) | set(data["opps"])
        present |= set(data["opps"]["items"][0])
        self.assertFalse(cost_keys - present, cost_keys - present)

    def test_api01_live(self):  # API-01: відповідь `get_dashboard` = еталон (після реалізації воркером A)
        model = self.env["td.energy.analytics"]
        if not hasattr(model, "get_dashboard"):
            self.skipTest("W4-A: get_dashboard ще не реалізовано")
        rules = load("api01_rules.json")
        got = model.with_user(self.u_cost).get_dashboard("m", "area", None)
        check_shape(self, load("api01_get_dashboard.json"), got)
        part = model.with_user(self.u_cost).get_dashboard("w", "area", ["kpis"])
        self.assertEqual(set(part), {"meta", "kpis"})
        view = model.with_user(self.u_view).get_dashboard("m", "area", None)
        self.assertNotIn("cost", [k["id"] for k in view["kpis"]])
        self.assertNotIn("cost", view["meta"]["capabilities"])
        self.assertIn(rules["parts"][0], got)
