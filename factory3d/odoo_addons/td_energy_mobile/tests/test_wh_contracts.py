"""Менеджер: заморожені контракти W4 мобільного модуля (C-06, C-07, C-08, API-H1) — `contracts/*.json` = реєстр Odoo
й файли клієнта `td_energy`. Тест змінює лише менеджер. Форма відповіді `get_mobile` — після появи методу (воркер C)."""

import importlib
import json
from pathlib import Path

from odoo.tests import tagged
from odoo.tools import file_open

from .common import TAGS, TestWHCommon

CONTRACTS = Path(__file__).resolve().parent.parent / "contracts"
FILES = (
    "api_h1_get_mobile.json", "api_h1_rules.json", "c06_mobile_tabs.json", "c07_energy_core.json",
    "c08_round_optional.json",
)  # fmt: skip


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
class TestWHContracts(TestWHCommon):
    def test_files(self):
        self.assertEqual(sorted(p.name for p in CONTRACTS.glob("*.json")), sorted(FILES))
        readme = (CONTRACTS / "README.md").read_text(encoding="utf-8")
        for name in FILES:
            load(name)  # валідний JSON
            self.assertIn(name, readme, name)

    def test_models_methods_tools_params(self):  # C-07, C-08: моделі, поля, методи, функції, параметри, групи
        for name in ("c07_energy_core.json", "c08_round_optional.json"):
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
            for group in contract.get("groups", []):
                self.assertTrue(self.env.ref(group), group)

    def test_c08_round_and_event_kind(self):  # C-08, M-H6: поля `td.energy.round`, вид події `round`
        contract = load("c08_round_optional.json")
        states = {key for key, _label in self.env["td.energy.round"]._fields["state"].selection}
        self.assertEqual(states, set(contract["states"]))
        kind = contract["event_kind"]
        values = {key for key, _label in self.env[kind["model"]]._fields[kind["field"]].selection}
        self.assertIn(kind["value"], values)

    def test_c06_client_registry(self):  # C-06: клієнт `td_energy` (реєстр вкладок, bus, useEnergyActions)
        contract = load("c06_mobile_tabs.json")
        for path, needles in contract["td_energy_files_must_contain"].items():
            with file_open(path, "r") as f:
                source = f.read()
            for needle in needles:
                self.assertIn(needle, source, "%s: %s" % (path, needle))
        self.assertEqual(set(contract["entry_example"]) - set(contract["entry"]), set())
        self.assertNotIn("badge", contract["entry_example"])  # D-78

    def test_api_h1_example(self):  # API-H1: еталон узгоджений із правилами (форма відповіді — SPEC H.7)
        data, rules = load("api_h1_get_mobile.json"), load("api_h1_rules.json")
        self.assertEqual(set(data), set(rules["top_keys"]))
        self.assertIn(data["round"]["state"], rules["states"])
        for item in data["round"]["items"]:
            self.assertIn(item["result"], rules["results"])
        self.assertEqual(data["round"]["can_finish"], data["round"]["finish_blocked"] is None)
        self.assertLess(len(json.dumps(data)), rules["limits"]["max_bytes"])

    def test_api_h1_live(self):  # API-H1: відповідь `get_mobile` = еталон (після реалізації воркером C)
        model = self.env["td.energy.round"]
        if not hasattr(model, "get_mobile"):
            self.skipTest("W4-C: get_mobile ще не реалізовано")
        got = model.with_user(self.u_eng).get_mobile()
        want = load("api_h1_get_mobile.json")
        self.assertEqual(set(got), set(want))
        check_shape(self, want["meta"], got["meta"], "$.meta")
        if got["round"]:
            check_shape(self, want["round"], got["round"], "$.round")
        else:
            check_shape(self, want["next"] or {"slot": None, "starts_local": None}, got["next"], "$.next")
        check_shape(self, want["history"], got["history"], "$.history")
