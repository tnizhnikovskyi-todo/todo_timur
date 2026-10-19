"""W1-A: AC-107…AC-113, AC-124, AC-145, AC-147, AC-153, AC-154, AC-157, AC-158 — API Пульту, мобільного, генерації."""

import json
from datetime import date, datetime, timedelta
from unittest.mock import patch

from odoo import Command
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from ..models.td_energy_dashboard import TdEnergyDashboard
from .common import NOW, TAGS, TestW1Common

COST_KEYS = {"cost_uah", "price_uah", "tariff_uah"}
TS_A = datetime(2026, 10, 17, 4, 0)  # 07:00 Київ
CONTRACT_NOTE = " договірної"


def walk_keys(data):
    if isinstance(data, dict):
        for key, value in data.items():
            yield key
            yield from walk_keys(value)
    elif isinstance(data, list):
        for item in data:
            yield from walk_keys(item)


@tagged(*TAGS)
class TestW1Dashboard(TestW1Common):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Dash = cls.env["td.energy.dashboard"]
        cls.Event.search([]).unlink()

    def pult(self, user=None, period="now", parts=None):
        return self.Dash.with_user(user or self.u_cost).get_pult(period, parts)

    def energy_slots(self):
        """AC-109: net +75, −10, +25 кВт·год у слотах 07:00, 07:15, 07:30 (Київ)."""
        self.interval("PM-Q1", TS_A, 75.0)
        self.interval("PM-Q2", TS_A + timedelta(minutes=15), 0.0, 10.0)
        self.interval("PM-Q1", TS_A + timedelta(minutes=30), 25.0)

    # --- C-02 (W4): хук кнопки «Звіт за зміну» ------------------------------------------------------------
    def test_report_hook(self):  # AC-121 (серверна частина), D-01: кнопка Пульту з'являється лише з дією від хука
        self.fixture_grid()
        self.assertIsNone(TdEnergyDashboard._td_report_action(self.Dash))  # у td_energy хук порожній
        model = type(self.Dash)
        with patch.object(model, "_td_report_action", return_value=None):
            meta = self.pult(parts=["kpis"])["meta"]
        self.assertIsNone(meta["report_action"])
        self.assertIs(meta["capabilities"]["report"], False)
        with patch.object(model, "_td_report_action", return_value="td_energy.action_td_energy_event"):
            meta = self.pult(parts=["kpis"])["meta"]
        self.assertEqual(meta["report_action"], "td_energy.action_td_energy_event")
        self.assertIs(meta["capabilities"]["report"], True)
        self.assertNotIn("report_action", self.Dash.with_user(self.u_view).get_mobile(None)["meta"])

    # --- AC-107, AC-153 ---------------------------------------------------------------------------------
    def test_cost_keys_removed(self):  # AC-107
        self.fixture_grid()
        self.energy_slots()
        for user in (self.u_view,):
            dash = self.Dash.with_user(user)
            for data in (dash.get_pult(), dash.get_node_card("BW-2"), dash.get_mobile(None)):
                self.assertFalse(COST_KEYS & set(walk_keys(data)), user.login)
                self.assertNotIn("cost", data.get("meta", {}).get("capabilities", {}))
        with_cost = self.Dash.with_user(self.u_cost)
        pult = with_cost.get_pult()
        self.assertTrue(COST_KEYS & set(walk_keys(pult)))
        self.assertTrue(pult["meta"]["capabilities"]["cost"])
        self.assertIn("cost_uah", with_cost.get_node_card("BW-2")["kpis"]["energy"])

    def test_access_denied(self):  # AC-153
        dash = self.Dash.with_user(self.u_plain)
        for call in (lambda: dash.get_pult(), lambda: dash.get_node_card("BW-2"), lambda: dash.get_mobile(),
                     lambda: dash.get_generation(), lambda: dash.get_alarms()):  # fmt: skip
            with self.assertRaises(AccessError):
                call()

    # --- KPI за R-27 ------------------------------------------------------------------------------------
    def test_kpis_live(self):  # AC-108
        self.fixture_grid()
        self.interval("PM-Q1", datetime(2026, 10, 17, 11, 0), 96.0)
        self.interval("PM-Q2", datetime(2026, 10, 17, 11, 0), 0.0, 6.5)
        kpis = self.pult(parts=["kpis"])["kpis"]
        self.assertEqual(kpis["grid"], {"kw": 358, "pct": 45, "reserve_kw": 442, "export_kw": 0})
        self.assertEqual(kpis["load"]["kw"], 667)
        self.assertEqual(kpis["load"]["pv_share_pct"], 46)
        self.assertEqual(kpis["load"]["chp_state"], "stop")
        self.assertEqual(kpis["generation"]["pv_kw"], 309)
        self.assertEqual(kpis["generation"]["pv_pct_kwp"], 34)
        self.assertEqual(kpis["generation"]["bess_soc_pct"], 82)
        self.assertIsNone(kpis["generation"]["genset"])
        cos = kpis["cos_phi"]
        self.assertEqual((cos["plant"], cos["sections"], cos["low_sections"]), (0.93, [0.95, 0.88], [2]))
        self.assertEqual((cos["target"], cos["warn"], cos["alarm"]), (0.95, 0.92, 0.9))

    def test_period_now_energy(self):  # AC-109
        self.fixture_grid()
        self.energy_slots()
        data = self.pult(parts=["kpis", "profile"])
        energy = data["kpis"]["energy"]
        self.assertEqual((energy["label"], energy["kwh"], energy["cost_uah"], energy["price_uah"]),
                         ("З мережі сьогодні", 100, 840, 8.4))  # fmt: skip
        self.assertEqual(data["kpis"]["peak"]["kw"], 300)
        self.assertEqual(data["kpis"]["peak"]["label"], "Пік доби (15 хв)")
        self.assertEqual(data["foot"]["export_kwh"], 10)

    def test_period_shift(self):  # AC-110
        self.fixture_grid()
        self.energy_slots()
        calendar = self.env["resource.calendar"].create(
            {
                "name": "W1 зміна",
                "attendance_ids": [
                    Command.create({"name": "d%d" % d, "dayofweek": str(d), "hour_from": 7.0, "hour_to": 16.0})
                    for d in range(7)
                ],
            }
        )
        self.env["ir.config_parameter"].sudo().set_param("td.energy.shift_calendar_id", str(calendar.id))
        kpis = self.pult(period="shift", parts=["kpis"])["kpis"]
        self.assertEqual(kpis["energy"]["label"], "З мережі за зміну (з 07:00)")
        self.assertEqual(kpis["energy"]["kwh"], 100)
        self.assertEqual(kpis["peak"]["label"], "Пік зміни")

    def test_period_day(self):  # AC-111
        self.fixture_grid()
        self.energy_slots()
        self.typical("PM-QF-2")
        kpis = self.pult(period="day", parts=["kpis"])["kpis"]
        # слоти 58…95: 38 · 100 кВт · 0,25 = 950 кВт·год прогнозу + 100 кВт·год факту
        self.assertEqual((kpis["energy"]["label"], kpis["energy"]["kwh"]), ("Прогноз на добу", 1050))
        self.assertEqual(kpis["peak"]["label"], "Пік доби з прогнозом")
        self.assertGreaterEqual(kpis["peak"]["kw"], 300)

    def test_period_month(self):  # AC-112
        self.fixture_grid()
        self.interval("PM-Q1", datetime(2026, 10, 9, 5, 15), 185.5)  # 742 кВт о 08:15 Київ
        self.interval("PM-Q1", datetime(2026, 10, 12, 7, 0), 100.0)
        kpis = self.pult(period="month", parts=["kpis"])["kpis"]
        self.assertEqual(kpis["peak"], {"label": "Пік місяця", "kw": 742, "note": "09.10 о 08:15 · 93 % договірної"})
        self.assertEqual(kpis["energy"]["label"], "З мережі за жовтень")
        self.assertEqual(kpis["energy"]["kwh"], 286)

    def test_stale_and_partial(self):  # AC-113
        self.clear_signals()
        data = self.pult(parts=["kpis", "profile", "sld"])
        self.assertEqual(data["meta"]["data_state"], "stale")
        kpis = data["kpis"]
        self.assertIsNone(kpis["grid"]["kw"])
        self.assertIsNone(kpis["load"]["kw"])
        self.assertIsNone(kpis["energy"]["kwh"])
        self.assertIsNone(kpis["peak"]["kw"])
        self.assertIsNone(kpis["generation"]["pv_kw"])
        self.fixture_grid()
        self.assertEqual(self.pult(parts=["kpis"])["meta"]["data_state"], "partial")  # C2 без даних
        self.fresh("energy/lines/C2/p_now", 158.0)
        self.assertEqual(self.pult(parts=["kpis"])["meta"]["data_state"], "ok")
        self.stale("energy/lines/BW-2/p_now")
        self.assertEqual(self.pult(parts=["kpis"])["meta"]["data_state"], "partial")

    def test_unknown_period(self):
        with self.assertRaisesRegex(UserError, "Невідомий період: year."):
            self.pult(period="year")

    def test_part_error_isolated(self):
        self.fixture_grid()
        from unittest.mock import patch

        from ..tools import dashboard

        with (
            patch.object(dashboard.Pult, "profile_part", side_effect=ValueError("boom")),
            self.assertLogs("odoo.addons.td_energy.tools.dashboard", level="ERROR"),
        ):
            data = self.pult(parts=["kpis", "profile", "advice"])
        self.assertEqual(data["profile"], {"error": "boom"})
        self.assertIn("grid", data["kpis"])
        self.assertIn("advice", data)

    # --- AC-124, AC-157, AC-158 --------------------------------------------------------------------------
    def bw2_consumers(self):
        bw2 = self.Node.search([("code", "=", "BW-2")])
        return self.Node.search([("id", "child_of", bw2.id), ("kind", "=", "consumer")])

    def test_idle_kpi(self):  # AC-124
        self.fixture_grid()
        idle = self.bw2_consumers().sorted("p_inst_kw", reverse=True)[:2]
        for node in self.bw2_consumers():
            self.fresh("energy/consumers/%s/p_now" % node.code, node.p_inst_kw * 0.5)
        self.fresh("energy/consumers/%s/p_now" % idle[0].code, 0.3)
        self.fresh("energy/consumers/%s/p_now" % idle[1].code, 0.0)
        card = self.Dash.with_user(self.u_view).get_node_card("BW-2")
        self.assertEqual(card["kpis"]["idle"], {"kw": 0.3, "names": sorted(idle.mapped("code"))})

    def test_sld_facts(self):  # AC-157
        self.fixture_grid()
        consumers = self.bw2_consumers()
        for node in consumers:
            self.fresh("energy/consumers/%s/p_now" % node.code, node.p_inst_kw * 0.5)
        for node in consumers.sorted("p_inst_kw", reverse=True)[:2]:
            self.fresh("energy/consumers/%s/p_now" % node.code, 0.0)
        for code, value in (("q_kvar", 105.0), ("steps_on", 3.0), ("steps_total", 10.0)):
            self.fresh("energy/cells/PFC-2/" + code, value)
        self.fresh("energy/cells/QS/state", 0.0, "open")
        sld = self.pult(parts=["sld"])["sld"]
        nodes = {n["code"]: n for n in sld["nodes"]}
        self.assertEqual(len(nodes), 21)
        bw2_taps = len(self.Node.search([("id", "child_of", self.Node.search([("code", "=", "BW-2")]).id),
                                         ("kind", "=", "tapoff")]))  # fmt: skip
        self.assertEqual(nodes["BW-2"]["facts"][0], "192 А з 630 А · 30 %")
        self.assertEqual(nodes["BW-2"]["facts"][1], "124 кВт · %d відгалужень, 2 не працюють" % bw2_taps)
        self.assertEqual(nodes["PFC-2"]["facts"][:2], ["Увімкнено 105 квар (3 з 10 ступенів)", "cos φ секції 0,88"])
        self.assertEqual(nodes["QS"]["facts"], ["Вимкнено: секції живляться окремо від T1 і T2"])
        self.assertEqual(nodes["BESS"]["facts"],
                         ["Заряд 82 %", "Очікування, 0 кВт", "Резерв на відключення мережі: 30 %"])  # fmt: skip
        for node in nodes.values():
            real = self.Node.search([("code", "=", node["code"])])
            self.assertEqual(node["title"], real.name)
            self.assertEqual(node["card"], real.kind in ("line", "transformer", "cell"), node["code"])
        self.assertEqual(nodes["GRID-10KV"]["facts"][0], "З мережі 358 кВт · договірна 800 кВт")
        self.assertEqual({e["state"] for e in sld["edges"]} - {"ok", "gen", "off"}, set())
        parents = {e["to"]: e["from"] for e in sld["edges"]}
        self.assertEqual((parents["SEC-1"], parents["BW-2"], parents["ATS-1"], parents["T1"]),
                         ("T1", "SEC-1", "SEC-2", "RM6-1"))  # fmt: skip
        self.assertNotIn("QS", parents)

    def test_side_blocks(self):  # AC-158
        self.fixture_grid()
        for node in self.Node.search([("kind", "=", "consumer")]):
            self.fresh("energy/consumers/%s/p_now" % node.code, 10.0)
        for code, kw in (
            ("DUST-1", 96),
            ("RV-ALL", 88),
            ("COMPRESSOR", 52),
            ("EDGE-1", 41),
            ("SAW-3", 31),
            ("NEST-1", 26),
        ):
            self.fresh("energy/consumers/%s/p_now" % code, float(kw))
        meter = self.Meter.search([("code", "=", "PM-QF-2")])
        meter.write({"next_verification": date(2026, 10, 26)})  # через 9 днів
        equipment = self.env["maintenance.equipment"].create({"name": "W1 обладнання"})
        self.Node.search([("code", "=", "CNC-4")]).write({"equipment_id": equipment.id})
        for name in ("Заявка 1", "Заявка 2"):
            self.env["maintenance.request"].create({"name": name, "equipment_id": equipment.id})
        side = self.pult(parts=["side"])
        self.assertEqual(
            [r["code"] for r in side["top"]], ["DUST-1", "RV-ALL", "COMPRESSOR", "EDGE-1", "SAW-3", "NEST-1"]
        )
        self.assertEqual(side["top"][0], {"code": "DUST-1", "name": "Вентилятори аспірації", "kw": 96})
        kinds = [r["kind"] for r in side["maint"]]
        self.assertEqual(kinds.count("request"), 2)
        verification = [r for r in side["maint"] if r["kind"] == "verification"]
        self.assertEqual((len(verification), verification[0]["state"], verification[0]["sub"]),
                         (1, "Заплановано", "до 26.10.2026"))  # fmt: skip
        self.assertEqual(side["mo"]["rows"], [])
        self.assertEqual(side["mo"]["pools_kwh"], 0)

    # --- AC-143, AC-145, AC-147 ---------------------------------------------------------------------------
    def test_generation_cards(self):  # AC-143
        self.fixture_grid()
        data = self.Dash.with_user(self.u_view).get_generation()
        cards = data["cards"]
        self.assertEqual([c["code"] for c in cards], ["PV-INV", "CHP", "BESS", "ATS-1"])
        self.assertEqual(
            {c["code"]: c["state"] for c in cards}, {"PV-INV": "gen", "CHP": "off", "BESS": "ok", "ATS-1": "off"}
        )
        self.assertTrue(all(c["can_3d"] is not None and c["kpis"] for c in cards))
        self.assertTrue(data["ts"])

    def test_mobile(self):  # AC-145
        self.fixture_grid()
        ev = self.Event._td_log("warn", "meter", "PM-QF-C2", "Лічильник PM-QF-C2. Немає даних.", ts=NOW,
                                 node=self.Node.search([("code", "=", "C2")]))  # fmt: skip
        ev.with_user(self.u_eng).action_take()
        mobile = self.Dash.with_user(self.u_eng).get_mobile(None)
        self.assertTrue({"state", "alarms", "scheme"} <= set(mobile))
        self.assertLessEqual(len(json.dumps(mobile)), 20 * 1024)
        self.assertEqual([r["code"] for r in mobile["scheme"]][:3], ["GRID-10KV", "T1", "T2"])
        self.assertTrue({"GRID-10KV", "T1", "T2", "BW-2", "C2", "PFC-2", "PV-INV", "BESS", "ATS-1"}
                        <= {r["code"] for r in mobile["scheme"]})  # fmt: skip
        active = mobile["alarms"]["active"]
        self.assertTrue(active and all("taken_by_me" in a for a in active))
        self.assertTrue(active[0]["taken_by_me"])
        self.assertEqual(mobile["state"]["genset_ats"]["text"], "ДГУ · АВР: мережа")
        self.assertEqual(mobile["state"]["grid_kw"], 358)
        only = self.Dash.with_user(self.u_eng).get_mobile("scheme")
        self.assertEqual(set(only), {"meta", "scheme"})
        with self.assertRaises(UserError):
            self.Dash.with_user(self.u_eng).get_mobile("round")

    def test_alarm_order_shared(self):  # однаковий порядок у get_pult і get_mobile: строгість, далі час спадно
        self.fixture_grid()
        mins = lambda n: NOW - timedelta(minutes=n)  # noqa: E731
        log = lambda text, level, ts: self.Event._td_log(level, "meter", "PM-QF-C2", text, ts=ts)  # noqa: E731
        old_warn, new_warn = log("Стара. Увага.", "warn", mins(50)), log("Нова. Увага.", "warn", mins(10))
        bad = log("Аварія. Подія.", "bad", mins(90))
        acked_warn, acked_bad = log("Підтв. Увага.", "warn", mins(5)), log("Підтв. Аварія.", "bad", mins(70))
        (acked_warn | acked_bad).with_user(self.u_eng).action_ack()
        expected = [bad.id, new_warn.id, old_warn.id, acked_bad.id, acked_warn.id]
        pult = [a["id"] for a in self.pult(self.u_eng, parts=["alarms"])["alarms"]["items"]]
        mobile = [a["id"] for a in self.Dash.with_user(self.u_eng).get_mobile("alarms")["alarms"]["active"]]
        self.assertEqual(pult, expected)
        self.assertEqual(mobile, expected)
        self.assertEqual(self.Dash.with_user(self.u_eng).get_mobile("state")["state"]["contract_kw"], 800)

    def test_show_3d(self):  # AC-147
        self.fixture_grid()
        node = self.Node.search([("code", "=", "BW-2")])
        node.write({"equipment_id": False})
        self.assertFalse(self.Dash.with_user(self.u_view).get_node_card("BW-2")["node"]["can_3d"])
        with self.assertRaises(UserError):
            node.action_td_show()
        node.write({"equipment_id": self.env["maintenance.equipment"].create({"name": "BW2-3D"}).id})
        self.assertTrue(self.Dash.with_user(self.u_view).get_node_card("BW-2")["node"]["can_3d"])
