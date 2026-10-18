"""W1-C: хуки `td.energy.dashboard` (M-10, R-15), AC-78…AC-81, uninstall_hook (B.5), ТБ-11 (W1_SPEC B.12–B.13).

Хуки бази (`_td_genset_summary` …) пише W1-A; поки їх немає в `td_energy` (каркас), у тестах вони підставляються
заглушками з поведінкою бази (`patch`). Виклики `get_generation()`/`get_pult()` виконуються завжди (база W1-A злита).
"""

import re
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from odoo.exceptions import AccessError
from odoo.modules import get_module_path
from odoo.tests import TransactionCase, new_test_user, tagged

from odoo.addons.td_energy.models.td_energy_dashboard import TdEnergyDashboard as BaseDashboard

from .. import hooks
from ..adapters import td_genset as td
from .test_rules import GensetCase

LOGGER = "odoo.addons.td_genset_factory3d.models.td_energy_dashboard"
BASE_HOOKS = {
    "_td_genset_summary": lambda self: None,
    "_td_generation_cards": lambda self: [],
    "_td_node_facts_extra": lambda self, node: [],
    "_td_node_card_extra": lambda self, node: {},
}
LAST_TEST = {"ts": datetime(2026, 10, 18, 3, 30), "duration_min": 30.0, "result": "норма"}  # 06:30 за Києвом
NEXT_EVENT = "19.10 06:30 · пробний пуск 30 хв"
SERVICE = {
    "hours_now": 1213.0,
    "interval_h": 250.0,
    "next_service_hours": 1250.0,
    "last_service_hours": 1000.0,
    "last_service_date": None,
    "due": False,
    "hours_left": 37.0,
}


def live(online=True, state=1):
    return {"online": online, "state": state}


class BaseHooksMixin:
    """Поки W1-A не злито, база не має хуків M-27 — підставляємо їх із поведінкою бази."""

    def stub_base_hooks(self):
        for name, func in BASE_HOOKS.items():
            if not hasattr(BaseDashboard, name):
                patcher = mock.patch.object(BaseDashboard, name, func, create=True)
                patcher.start()
                self.addCleanup(patcher.stop)


@tagged("post_install", "-at_install")
class TestW1Hooks(BaseHooksMixin, GensetCase):
    def setUp(self):
        super().setUp()
        self.stub_base_hooks()
        for name, value in (("last_test", LAST_TEST), ("next_event", NEXT_EVENT), ("service_info", SERVICE)):
            patcher = mock.patch.object(td, name, mock.MagicMock(return_value=value))
            patcher.start()
            self.addCleanup(patcher.stop)
        self.snap(fuel_pct=78, p_kw=0.0, hours=1213.0, state_raw="standby")
        self.link.last_state_json = live()
        self.Dash = self.env["td.energy.dashboard"]
        self.user_energy = new_test_user(
            self.env, login="w1c_energy", groups="base.group_user,td_energy.group_td_energy_user"
        )

    def _cards(self):
        return self.Dash.with_user(self.user_admin).get_generation()["cards"]

    def _genset_card(self):
        cards = [c for c in self._cards() if c["code"] == "GENSET"]
        return cards[0] if cards else None

    # --- AC-78 ----------------------------------------------------------------------------------------------
    def test_generation_card_reserve(self):  # AC-78
        cards = self._cards()
        self.assertEqual(cards[-1]["code"], "GENSET")
        self.assertEqual([c["code"] for c in cards], ["PV-INV", "CHP", "BESS", "ATS-1", "GENSET"])
        card = cards[-1]
        self.assertEqual(
            (card["title"], card["kind"], card["state"], card["node_code"], card["can_3d"]),
            ("ДГУ", "genset", "off", "GENSET", True),
        )
        kpis = {k["label"]: (k["value"], k["unit"]) for k in card["kpis"]}
        self.assertEqual(kpis, {"Паливо": (78, "%"), "Потужність": (0.0, "кВт"), "Мотогодини": (1213.0, "год")})
        self.assertEqual(
            card["facts"],
            ["Тест: 18.10 06:30 · норма", "Наступна подія: " + NEXT_EVENT, "До ТО: 37 мотогод"],
        )
        self.assertEqual(card["link"]["open_action"], td.open_action(self.td_gen))

    def test_card_states(self):  # R-15 п.1: стан картки за кодом зв'язки
        for code, state in ((6, "gen"), (10, "alarm"), (1, "off"), (0, "off")):
            self.link.last_state_json = live(True, code)
            self.assertEqual(self._genset_card()["state"], state, code)
        self.link.last_state_json = live(False, 6)
        self.assertEqual(self._genset_card()["state"], "off")

    def test_card_without_optional_facts(self):  # факти «якщо є»
        td.last_test.return_value = None
        td.next_event.return_value = None
        td.service_info.return_value = {**SERVICE, "hours_left": None}
        self.assertEqual(self._genset_card()["facts"], [])

    # --- AC-79 ----------------------------------------------------------------------------------------------
    def test_summary_and_ats_facts(self):  # AC-79
        self.assertEqual(self.Dash._td_genset_summary(), {"state": "reserve", "label": "резерв", "fuel_pct": 78})
        facts = self.Dash._td_node_facts_extra(SimpleNamespace(code="ATS-1"))
        self.assertEqual(
            facts, ["ДГУ в резерві · паливо 78 % · тест 18.10 06:30 норма", "Наступна подія: " + NEXT_EVENT]
        )
        genset = self.Dash._td_node_facts_extra(SimpleNamespace(code="GENSET"))
        self.assertEqual(genset[:2], facts)
        self.assertEqual(genset[-1], "Мотогодини 1213")
        self.assertEqual(self.Dash._td_node_facts_extra(SimpleNamespace(code="BW-2")), [])
        pult = self.Dash.with_user(self.user_admin).get_pult(parts=["kpis", "sld"])
        genset_kpi = pult["kpis"]["generation"]["genset"]
        self.assertEqual(genset_kpi, {"state": "reserve", "label": "резерв", "fuel_pct": 78})
        ats = next(n for n in pult["sld"]["nodes"] if n["code"] == "ATS-1")
        self.assertTrue(any(f.startswith("ДГУ в резерві · паливо 78 %") for f in ats["facts"]))

    def test_summary_states(self):  # M-10: коди 0…10
        for code, online, state, label in (
            (0, True, "offline", "немає зв'язку"),
            (10, True, "fault", "аварія"),
            (1, True, "reserve", "резерв"),
            (2, True, "running", "працює"),
            (9, True, "running", "працює"),
            (6, False, "offline", "немає зв'язку"),
        ):
            self.link.last_state_json = live(online, code)
            summary = self.Dash._td_genset_summary()
            self.assertEqual((summary["state"], summary["label"]), (state, label), code)

    def test_node_card_extra(self):  # M-10: блок `genset` картки вузла
        extra = self.Dash._td_node_card_extra(SimpleNamespace(code="GENSET"))
        self.assertEqual(extra["genset"]["link_id"], self.link.id)
        self.assertEqual(extra["genset"]["open_action"], td.open_action(self.td_gen))
        self.assertEqual(self.Dash._td_node_card_extra(SimpleNamespace(code="ATS-1")), {})

    # --- AC-80 ----------------------------------------------------------------------------------------------
    def test_offline(self):  # AC-80
        self.link.last_state_json = live(online=False, state=6)
        summary = self.Dash._td_genset_summary()
        self.assertEqual(summary, {"state": "offline", "label": "немає зв'язку", "fuel_pct": 78})

    def test_adapter_error_is_swallowed(self):  # AC-80, R-15 п.3
        td.snapshot.side_effect = NotImplementedError("ADP-03 не звірено")
        with self.assertLogs(LOGGER, "WARNING"):
            self.assertIsNone(self.Dash._td_genset_summary())
        with self.assertLogs(LOGGER, "WARNING"):
            self.assertIsNone(self._genset_card())
        with self.assertLogs(LOGGER, "WARNING"):
            self.assertEqual(self.Dash._td_node_facts_extra(SimpleNamespace(code="ATS-1")), [])

    def test_no_td_genset_record(self):  # R-15 п.3: td_genset без запису
        self.td_gen.unlink()
        self.assertIsNone(self.Dash._td_genset_summary())
        self.assertIsNone(self._genset_card())
        self.assertEqual(self.Dash._td_node_card_extra(SimpleNamespace(code="GENSET")), {})

    # --- AC-81 ----------------------------------------------------------------------------------------------
    def test_without_link(self):  # AC-81: без зв'язки хуки нічого не додають
        self.link.active = False
        self.assertIsNone(self.Dash._td_genset_summary())
        codes = [c["code"] for c in self._cards()]
        self.assertNotIn("GENSET", codes)
        self.assertEqual(len(codes), 4)
        pult = self.Dash.with_user(self.user_admin).get_pult(parts=["kpis"])
        self.assertIsNone(pult["kpis"]["generation"]["genset"])

    def test_td_energy_has_no_td_genset_references(self):  # AC-81: grep модуля td_energy
        root = Path(get_module_path("td_energy"))
        pattern = re.compile(r"\btd_genset\b|env\[['\"]td\.genset")
        found = []
        for path in root.rglob("*"):
            if path.suffix not in (".py", ".xml", ".csv", ".js") or "tests" in path.relative_to(root).parts:
                continue
            for number, line in enumerate(path.read_text(encoding="utf-8", errors="ignore").splitlines(), 1):
                if pattern.search(line):
                    found.append("%s:%d" % (path.relative_to(root), number))
        self.assertEqual(found, [])

    # --- B.5, AC-75 -----------------------------------------------------------------------------------------
    def test_restore_root_on_uninstall(self):  # AC-75
        root = self.env.ref("td_genset.menu_root")
        self.assertFalse(root.active)
        hooks._restore_td_genset_root(self.env)
        self.assertTrue(root.active)
        hooks._restore_td_genset_root(self.env)  # ідемпотентно

    def test_restore_root_without_td_genset_menu(self):  # B.5: td_genset видалено раніше — хук не падає
        self.env.ref("td_genset.menu_root").unlink()
        hooks._restore_td_genset_root(self.env)

    # --- ТБ-11 ----------------------------------------------------------------------------------------------
    def test_energy_user_has_no_td_genset_access(self):  # ТБ-11 (права; факти на справжньому td_genset — нижче)
        self.assertFalse(self.user_energy.has_group("td_genset.group_user"))
        for model in ("td.genset", "td.genset.reading", "td.genset.event", "td.genset.command"):
            with self.assertRaises(AccessError, msg=model):
                self.env[model].with_user(self.user_energy).search([])


@tagged("post_install", "-at_install")
class TestW1Security(BaseHooksMixin, TransactionCase):
    """ТБ-11 на справжньому td_genset (адаптер не замокано): факти ДГУ читач енергетики бачить лише через хуки."""

    def test_facts_for_energy_user_without_td_genset_rights(self):  # ТБ-11
        env = self.env
        self.stub_base_hooks()
        passport = env["td.equipment.passport"].search([("role", "=", "genset")], limit=1) or env[
            "td.equipment.passport"
        ].create({"role": "genset", "manufacturer": "KOHLER-SDMO", "model": "D700"})
        equipment = env["maintenance.equipment"].create(
            {"name": "ДГУ ТБ-11", "serial_no": "GENSET-TB11", "td_code": "GENSET-TB11", "td_passport_id": passport.id}
        )
        genset = env["td.genset"].create(
            {
                "name": "ТБ-11",
                "controller_model_id": env.ref("td_genset.controller_hgm6120n").id,
                "power_kw": 12.0,
                "tank_volume_l": 145.0,
            }
        )
        reading = env["td.genset.reading"].create({"genset_id": genset.id, "relay_id": 1, "ts": "2026-10-18 10:00:00"})
        genset.write(
            {"last_reading_id": reading.id, "link_state": "online", "genset_status": "0", "run_hours_total": 12.5}
        )
        link = env["td.genset3d.link"].create(
            {
                "equipment_id": equipment.id,
                "td_genset_ref": "td.genset,%d" % genset.id,
                "profile_id": env.ref("td_genset_factory3d.profile_d700").id,
            }
        )
        link.last_state_json = live()
        user = new_test_user(env, login="w1c_tb11", groups="base.group_user,td_energy.group_td_energy_user")
        with self.assertRaises(AccessError):
            env["td.genset"].with_user(user).search([])
        dash = env["td.energy.dashboard"].with_user(user)
        summary = dash._td_genset_summary()
        self.assertEqual((summary["state"], summary["label"]), ("reserve", "резерв"))
        card = dash._td_generation_cards()[-1]
        self.assertEqual(card["code"], "GENSET")
        self.assertEqual({k["label"] for k in card["kpis"]}, {"Паливо", "Потужність", "Мотогодини"})
        self.assertIn(("Мотогодини", 12.5), [(k["label"], k["value"]) for k in card["kpis"]])
