"""W3-E: AC-21…AC-31, AC-64 — API екрана `td.energy.res.dashboard` (M-08, API-01, API-10, R-08…R-12, R-25)."""

import json
from datetime import datetime
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from ..tools import resource_data as rd
from .common import SLOT, T0, TAGS, TestW3Common

COST_KEYS = {"cost_uah", "save_uah_month", "price_uah"}
DAY0 = datetime(2026, 10, 16, 21, 0)  # 00:00 Київ 17.10 (UTC)
FRI = datetime(2026, 10, 16, 4, 0)  # 07:00 Київ п'ятниці — початок «Зміни 1»
DASH = "odoo.addons.td_energy_resources.models.td_energy_res_dashboard.TdEnergyResDashboard"


def walk_keys(data):
    if isinstance(data, dict):
        for key, value in data.items():
            yield key
            yield from walk_keys(value)
    elif isinstance(data, list):
        for item in data:
            yield from walk_keys(item)


@tagged(*TAGS)
class TestW3Dashboard(TestW3Common):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Dash = cls.env["td.energy.res.dashboard"]
        cls.Meter = cls.env["td.energy.meter"]

    # --- фікстури «макет 14:20» -------------------------------------------------------------------------------
    def get(self, code=None, user=None):
        return self.Dash.with_user(user or self.u_cost).get_resources(code)

    def mcode(self, code):
        return self.Meter.search([("code", "=", code)])

    def fill(self, meter, start, n, rate, price=0.0):
        """`n` слотів зі сталою швидкістю `rate` (qty — округлена до 3 знаків, як у збирачі)."""
        factor = meter.resource_id.rate_hour_factor or 1.0
        qty = round(rate * factor / 4.0, 3)
        for k in range(n):
            self.res_interval(meter, start + k * SLOT, qty, rate=rate, cost=round(qty * price, 2))

    def kpis(self, data):
        return {k["id"]: k for k in data["resource"]["kpis"]}

    def fx_el(self):
        """AC-22: імпорт 6 284 кВт·год (8,40 ₴), СЕС 1 742, навантаження 7 900, Q = 2 514, експорт 26 о 14:00."""
        self.fixture_grid()
        self.el_interval("PM-Q1", T0, 6284.0)
        self.el_interval("PM-Q2", T0 + 20 * SLOT, 0.0, kwh_export=26.0)
        self.el_interval("SUN-1", T0, 1742.0)
        self.el_interval("PM-QF-1", T0, 7900.0)
        self.res_interval(self.mcode("PM-Q1"), T0, 2514.0, metric="react")
        for code, kw in (("DUST-1", 96.0), ("COMPRESSOR", 52.0), ("EDGE-1", 41.0), ("SAW-3", 31.0), ("NEST-1", 26.0)):
            self.fresh("energy/consumers/%s/p_now" % code, kw)

    def fx_gas(self):
        """AC-23: витрата 46, за добу 612 м³ (19,80 ₴), котельня 540 м³; BOILER 41, DRY-1 4, CHP 0, CANTEEN 1 м³/год."""
        for code, value in (
            ("infra/gas/flow_m3h", 46.0),
            ("infra/gas/m3_total", 18400.0),
            ("equipment/BOILER/gas_m3h", 41.0),
            ("infra/chp/gas_m3h", 0.0),
        ):
            self.fresh(code, value)
        self.fresh("infra/chp/state", 0.0, "stop")
        main = self.mcode("GM-MAIN")
        for k in range(21):
            qty = 30.0 if k < 20 else 12.0
            self.res_interval(main, T0 + k * SLOT, qty, cost=round(qty * 19.8, 2))
        self.res_interval(self.mcode("GM-BOILER"), T0, 540.0)
        self.res_interval(self.mcode("GM-DRY1"), T0 + 20 * SLOT, 1.0, quality="estimated")
        self.res_interval(self.mcode("GM-CANTEEN"), T0 + 20 * SLOT, 0.25, quality="estimated")

    def fx_heat(self, rows=True):
        """Теплосчётчик котельні `HM-BOILER` вручну (без моста): 5 183 кВт·год за добу, зараз 390 кВт."""
        meter = self.mcode("HM-BOILER")
        if not meter:
            flow = self.signal("test/hm_boiler_kw", unit="кВт")
            self.fresh(flow.code, 390.0)
            meter = self.meter("HM-BOILER", self.point("HEAT-BOILER", "heat", "source"), "flow_integrate", flow=[flow])
        if rows:
            self.res_interval(meter, T0, 5085.5)
            self.res_interval(meter, T0 + 20 * SLOT, 97.5)

    def fx_air(self):
        """AC-24: витрата 9,8, p_now 52, тиск 7,1, уставка 7,0, COMPRESSOR 642 кВт·год, ніч 1,6, день 10,0."""
        for code, value in (
            ("air/flow_m3min", 9.8),
            ("air/pressure_bar", 7.1),
            ("air/m3_total", 1000.0),
            ("energy/consumers/COMPRESSOR/p_now", 52.0),
        ):
            self.fresh(code, value)
        self.fresh(self.signal("energy_control/air/setpoint_bar", unit="бар").code, 7.0)
        self.el_interval("PM-COMPRESSOR", T0, 642.0)
        air = self.mcode("AM-MAIN")
        self.fill(air, DAY0, 26, 1.6)  # ніч 00:00–06:30
        self.fill(air, DAY0 + 28 * SLOT, 29, 9.8)  # 07:00–14:00
        self.fill(air, FRI, 64, 10.0)  # п'ятниця 07:00–23:00 — `day_mean`

    def fx_water(self):
        """AC-25: за добу 4,2 м³ (60 ₴), підживлення 0,3, ніч 0,05 м³/год, зараз 0,4."""
        for code, value in (
            ("infra/water/flow_m3h", 0.4),
            ("infra/water/m3_total", 500.0),
            ("infra/water/boiler_m3_total", 50.0),
        ):
            self.fresh(code, value)
        main = self.mcode("WM-MAIN")
        for k in range(26):  # ніч: 26 слотів × 0,013 = 0,338 м³
            self.res_interval(main, DAY0 + k * SLOT, 0.013, rate=0.05, cost=0.78)
        self.res_interval(main, T0, 3.862, cost=231.72)  # разом 4,2 м³ і 252 ₴
        self.res_interval(self.mcode("WM-BOILER"), T0, 0.3)

    def fx_all(self):
        self.fx_el()
        self.fx_gas()
        self.fx_heat()
        self.fx_air()
        self.fx_water()

    # --- AC-21 ------------------------------------------------------------------------------------------------
    def test_access_and_cost_keys(self):  # AC-21
        self.fx_all()
        with self.assertRaises(AccessError):
            self.get(user=self.u_plain)
        for code in ("el", "gas", "heat", "air", "water"):
            data = self.get(code, self.u_view)
            self.assertFalse(COST_KEYS & set(walk_keys(data)), code)
            self.assertNotIn("₴", json.dumps(data, ensure_ascii=False), code)
            self.assertNotIn("cost", data["meta"]["capabilities"])
            self.assertFalse(data["meta"]["capabilities"]["manage"])
            self.assertNotIn("cost_uah", data["meta"]["total"])
            full = self.get(code, self.u_cost)
            self.assertIn("₴", json.dumps(full, ensure_ascii=False), code)
            self.assertTrue(full["meta"]["capabilities"]["cost"])
            self.assertIn("cost_uah", full["meta"]["total"])
            self.assertLess(len(json.dumps(full, ensure_ascii=False).encode()), 25 * 1024, code)  # розмір ≤ 25 КБ
        self.assertTrue(self.get("gas", self.u_eng)["meta"]["capabilities"]["manage"])

    # --- AC-22 ------------------------------------------------------------------------------------------------
    def test_kpis_el(self):  # AC-22
        self.fx_el()
        data = self.get("el")
        kpis = self.kpis(data)
        self.assertEqual([k["id"] for k in data["resource"]["kpis"]], ["grid_now", "today", "generation", "reactive"])
        self.assertEqual((kpis["grid_now"]["value"], kpis["grid_now"]["note"]), (358, "45 % договірної 800 кВт"))
        self.assertEqual(kpis["grid_now"]["tone"], "good")
        self.assertEqual((kpis["today"]["value"], kpis["today"]["note"]), (6284, "52 786 ₴ · 8,40 ₴/кВт·год"))
        self.assertEqual(kpis["generation"]["value"], 1742)
        self.assertEqual(kpis["generation"]["note"], "СЕС 100 % · КГУ 0 % · частка 22 %")
        self.assertEqual((kpis["reactive"]["value"], kpis["reactive"]["note"]), (2514, "tg φ 0,40"))
        self.assertEqual(kpis["reactive"]["tone"], "neutral")
        # дані — ті самі, що в Пульті W1 (розрахунок не відрізняється): звіряємо з `get_pult`
        pult = self.env["td.energy.dashboard"].with_user(self.u_cost).get_pult("now", ["kpis", "profile", "side"])
        self.assertEqual(kpis["grid_now"]["value"], pult["kpis"]["grid"]["kw"])
        self.assertEqual(kpis["today"]["value"], pult["kpis"]["energy"]["kwh"])
        self.assertEqual(data["tabs"][0]["cost_uah"], pult["kpis"]["energy"]["cost_uah"])
        self.assertEqual(data["resource"]["chart"]["series"], pult["profile"]["grid"])
        self.assertEqual(data["resource"]["chart"]["limit"], pult["meta"]["contract_kw"])
        self.assertEqual(
            [(i["code"], i["value"]) for i in data["resource"]["list"]["items"]],
            [(r["code"], r["kw"]) for r in pult["top"]],
        )

    def test_kpis_el_risk_and_tone(self):  # AC-22: «ризик доплати» (D-44), `bad` від `peak_warn_pct`
        self.fx_el()
        self.env["td.energy.tariff"].search([], limit=1).write({"tg_phi_limit": 0.3, "react_rate": 0.24})
        reactive = self.kpis(self.get("el"))["reactive"]
        self.assertEqual((reactive["note"], reactive["tone"]), ("tg φ 0,40 · ризик доплати", "bad"))
        self.fresh("infra/totals/grid_kw", 760.0)
        grid = self.kpis(self.get("el"))["grid_now"]
        self.assertEqual((grid["value"], grid["note"], grid["tone"]), (760, "95 % договірної 800 кВт", "bad"))
        self.env.cr.execute("DELETE FROM td_energy_res_interval WHERE metric = 'react'")
        self.env["td.energy.res.interval"].invalidate_model()
        reactive = self.kpis(self.get("el"))["reactive"]
        self.assertEqual((reactive["value"], reactive["note"]), (None, "—"))

    # --- AC-23 ------------------------------------------------------------------------------------------------
    def test_kpis_gas(self):  # AC-23
        self.fx_gas()
        self.fx_heat()
        kpis = self.kpis(self.get("gas"))
        self.assertEqual((kpis["rate"]["value"], kpis["rate"]["note"]), (46, "котельня BOILER · КГУ стоїть"))
        self.assertEqual((kpis["today"]["value"], kpis["today"]["note"]), (612, "12 118 ₴ · 19,80 ₴/м³"))
        self.assertEqual((kpis["limit"]["value"], kpis["limit"]["note"]), (1200, "використано 51 %"))
        self.assertEqual(kpis["limit"]["tone"], "good")
        eff = kpis["eff"]
        self.assertEqual((eff["value"], eff["note"], eff["quality"]), (91.4, "норма ≥ 90 %", "estimated"))
        self.assertEqual(eff["tone"], "good")
        self.fresh("infra/chp/state", 1.0, "running")
        self.assertEqual(self.kpis(self.get("gas"))["rate"]["note"], "котельня BOILER · КГУ працює")
        self.res_interval(self.mcode("GM-MAIN"), T0 + 21 * SLOT, 600.0)  # ≥ 90 % ліміту — `bad`
        self.assertEqual(self.kpis(self.get("gas"))["limit"]["tone"], "bad")

    def test_gas_eff_without_heat_meter(self):  # R-09: немає теплосчётчика котельні — `null`
        self.fx_gas()
        eff = self.kpis(self.get("gas"))["eff"]
        self.assertEqual((eff["value"], eff["tone"], eff["quality"]), (None, "neutral", "estimated"))

    def test_gas_partial_slot(self):  # R-08 п. 2: неповний слот [floor15(now), now) додається до «сьогодні»
        self.fx_gas()
        self.env.cr.execute(
            "UPDATE td_energy_res_interval SET price = 19.8 WHERE ts_start = %s AND meter_id = %s",
            (T0 + 20 * SLOT, self.mcode("GM-MAIN").id),
        )
        self.env["td.energy.res.interval"].invalidate_model()
        # 14:20 Київ: слот 14:15 (11:15 UTC) триває 5 хв; лічильник +10 м³ за 5 хв (120 м³/год < max_rate 200)
        signal = self.mcode("GM-MAIN").qty_signal_id
        self.feed(signal, [(self.now.replace(minute=15), 18400.0), (self.now, 18410.0)])
        today = self.kpis(self.get("gas"))["today"]
        self.assertEqual(today["value"], 622)  # 612 + 10
        self.assertEqual(today["note"], "12 316 ₴ · 19,80 ₴/м³")  # 12 117,6 + 10 × 19,80

    # --- AC-24 ------------------------------------------------------------------------------------------------
    def test_kpis_air(self):  # AC-24
        self.fx_air()
        kpis = self.kpis(self.get("air"))
        self.assertEqual((kpis["rate"]["value"], kpis["rate"]["note"]), (9.8, "тиск 7,1 бар · уставка 7,0"))
        spec = kpis["spec"]
        self.assertEqual((spec["value"], spec["note"], spec["tone"]), (5.3, "норма ≤ 6,0", "good"))
        self.assertEqual((kpis["today_el"]["value"], kpis["today_el"]["note"]), (642, "5 393 ₴"))
        leak = kpis["night_leak"]
        self.assertEqual((leak["value"], leak["note"], leak["tone"]), (1.6, "16 % від денної витрати", "bad"))

    def test_air_setpoint_fallback_and_spec(self):  # розд. 11: немає сигналу уставки — параметр; flow < 1 — `null`
        self.fx_air()
        self.env.cr.execute("UPDATE td_signal SET last_ts = NULL WHERE code = 'energy_control/air/setpoint_bar'")
        self.env["td.signal"].invalidate_model()
        note = self.kpis(self.get("air"))["rate"]["note"]
        self.assertEqual(note, "тиск 7,1 бар · уставка 7,0 (задана в налаштуваннях)")
        self.fresh("air/flow_m3min", 0.6)
        self.assertIsNone(self.kpis(self.get("air"))["spec"]["value"])

    # --- AC-25 ------------------------------------------------------------------------------------------------
    def test_kpis_water(self):  # AC-25
        self.fx_water()
        kpis = self.kpis(self.get("water"))
        self.assertEqual((kpis["rate"]["value"], kpis["rate"]["note"]), (0.4, "основний ввід"))
        self.assertEqual((kpis["today"]["value"], kpis["today"]["note"]), (4.2, "252 ₴"))
        night = kpis["night"]
        self.assertEqual((night["value"], night["note"], night["tone"]), (0.05, "норма ≤ 0,05", "good"))
        boiler = kpis["boiler"]
        self.assertEqual((boiler["value"], boiler["note"], boiler["tone"]), (0.3, "норма ≤ 0,5 м³/добу", "good"))
        # покриття нічного вікна < 70 % (менше 21 зі 30 слотів) — `null`
        self.env.cr.execute(
            "DELETE FROM td_energy_res_interval WHERE ts_start >= %s AND ts_start < %s",
            (DAY0 + 10 * SLOT, DAY0 + 26 * SLOT),
        )
        self.env["td.energy.res.interval"].invalidate_model()
        night = self.kpis(self.get("water"))["night"]
        self.assertEqual((night["value"], night["tone"]), (None, "neutral"))

    # --- AC-26 ------------------------------------------------------------------------------------------------
    def test_tabs_and_total(self):  # AC-26, R-12, D-31, D-32
        self.fx_all()
        data = self.get("gas")
        tabs = {t["code"]: t for t in data["tabs"]}
        self.assertEqual(list(tabs), ["el", "gas", "heat", "air", "water"])
        self.assertEqual(tabs["el"]["sub"], "358 кВт · 52 786 ₴")
        self.assertEqual((tabs["gas"]["rate"], tabs["gas"]["cost_uah"]), (46, 12118))
        self.assertEqual(tabs["gas"]["sub"], "46 м³/год · 12 118 ₴")
        self.assertEqual(tabs["heat"]["sub"], "390 кВт · з BMS")
        self.assertNotIn("cost_uah", tabs["heat"])
        self.assertEqual(tabs["air"]["sub"], "9,8 м³/хв · 5 393 ₴")
        self.assertEqual(tabs["water"]["sub"], "0,4 м³/год · 252 ₴")
        total = "Сьогодні разом: 65 156 ₴ · Електрика, Газ, Вода. Похідні не додаються: Тепло, Стиснене повітря."
        self.assertEqual(data["meta"]["total"], {"cost_uah": 65156, "text": total})  # air і heat не додаються
        plain = self.get("gas", self.u_view)
        self.assertEqual(plain["meta"]["total"], {"text": "Сьогодні: 5 ресурсів"})
        self.assertEqual((plain["tabs"][1]["sub"], plain["tabs"][2]["sub"]), ("46 м³/год", "390 кВт · з BMS"))
        self.assertEqual(data["meta"]["now"], "2026-10-17T11:20:00")
        self.assertEqual((data["meta"]["now_local"], data["meta"]["refresh_s"]), ("14:20", 30))

    # --- AC-27 ------------------------------------------------------------------------------------------------
    def test_chart_el(self):  # AC-27: 96 локальних слотів, `now_slot` — живе значення, ліміт = договірна
        self.fixture_grid()
        self.el_interval("PM-Q1", datetime(2026, 10, 17, 4, 30), 157.75)  # 07:30 Київ, 631 кВт
        self.el_interval("PM-Q2", T0 + 20 * SLOT, 0.0, kwh_export=26.0)  # експорт з 14:00
        chart = self.get("el")["resource"]["chart"]
        series = chart["series"]
        self.assertEqual((len(series), chart["now_slot"], chart["step_min"]), (96, 57, 15))
        self.assertEqual((series[30], series[56], series[57]), (631.0, 0.0, 358.0))
        self.assertEqual(series[58:], [None] * 38)
        self.assertEqual((chart["limit"], chart["y_max"], chart["ticks"]), (800, 900, [300, 600, 900]))
        self.assertEqual((chart["title"], chart["unit"]), ("Імпорт з мережі, кВт", "кВт"))
        self.assertEqual(chart["note"], "ліміт — договірна 800 кВт")
        foot = "Пік доби 631 кВт о 07:30. З 14:00 частина енергії СЕС віддавалась у мережу (26 кВт·год)."
        self.assertEqual(chart["foot"], foot)
        self.env.cr.execute("DELETE FROM td_energy_interval WHERE kwh_export > 0")
        self.env["td.energy.interval"].invalidate_model()
        self.assertEqual(self.get("el")["resource"]["chart"]["foot"], "Пік доби 631 кВт о 07:30.")

    def test_chart_gas(self):  # AC-27
        self.fresh("infra/gas/flow_m3h", 46.0)
        gas = self.mcode("GM-MAIN")
        self.fill(gas, DAY0, 26, 22.0)  # ніч
        self.fill(gas, DAY0 + 28 * SLOT, 17, 46.0)
        self.fill(gas, DAY0 + 45 * SLOT, 1, 48.0)  # пік 11:15
        self.fill(gas, DAY0 + 46 * SLOT, 10, 46.0)
        self.fill(gas, FRI, 64, 46.0)
        chart = self.get("gas")["resource"]["chart"]
        series = chart["series"]
        picks = (series[0], series[25], series[26], series[28], series[45], series[55], series[56])
        self.assertEqual(picks, (22.0, 22.0, None, 46.0, 48.0, 46.0, None))
        self.assertEqual((series[57], series[58:]), (46, [None] * 38))
        self.assertEqual((chart["limit"], chart["y_max"], chart["ticks"]), (80, 90, [30, 60, 90]))
        self.assertEqual(chart["note"], "ліміт години — 80 м³/год")
        self.assertEqual(chart["foot"], "Нічна витрата 22 м³/год, у зміну 46 м³/год. Пік 48 м³/год о 11:15.")

    def test_chart_air_and_leak_branches(self):  # AC-27: `leak_sentence` (> 10 % і норма), y_max 12
        self.fx_air()
        chart = self.get("air")["resource"]["chart"]
        self.assertEqual((chart["y_max"], chart["ticks"], chart["limit"]), (12, [4, 8, 12], None))
        self.assertEqual(chart["foot"], "Вночі витрата 1,6 м³/хв — це витоки в мережі.")
        self.env.cr.execute(
            "UPDATE td_energy_res_interval SET rate_avg = 0.5 WHERE ts_start < %s AND rate_avg = 1.6", (T0,)
        )
        self.env["td.energy.res.interval"].invalidate_model()
        self.assertEqual(self.get("air")["resource"]["chart"]["foot"], "Нічна витрата 0,5 м³/хв в межах норми.")

    def test_chart_water_and_norm_branches(self):  # AC-27: y_max 0,6; `norm_sentence`
        main = self.mcode("WM-MAIN")
        self.fresh("infra/water/flow_m3h", 0.4)
        self.fill(main, DAY0, 26, 0.05)
        self.fill(main, DAY0 + 28 * SLOT, 29, 0.42)
        self.fill(main, FRI, 64, 0.42)
        chart = self.get("water")["resource"]["chart"]
        self.assertEqual((chart["y_max"], chart["ticks"]), (0.6, [0.2, 0.4, 0.6]))
        self.assertEqual((chart["series"][57], chart["series"][30]), (0.4, 0.42))
        self.assertEqual(chart["foot"], "Нічна витрата 0,05 м³/год в нормі.")
        self.env.cr.execute("UPDATE td_energy_res_interval SET rate_avg = 0.08 WHERE rate_avg = 0.05")
        self.env["td.energy.res.interval"].invalidate_model()
        foot = self.get("water")["resource"]["chart"]["foot"]
        self.assertEqual(foot, "Нічна витрата 0,08 м³/год вища за норму 0,05.")

    def test_chart_no_data(self):  # R-10: слоти без даних — `null`, речення без даних опускаються
        chart = self.get("gas")["resource"]["chart"]
        self.assertEqual(chart["series"], [None] * 96)
        self.assertEqual(chart["foot"], "")

    # --- AC-28 ------------------------------------------------------------------------------------------------
    def test_list_gas_water(self):  # AC-28
        self.fx_gas()
        gas = self.get("gas")["resource"]["list"]
        self.assertEqual((gas["title"], gas["basis"], gas["unit"]), ("Споживачі газу", "rate", "м³/год"))
        self.assertEqual(
            [(i["code"], i["value"], i["share"]) for i in gas["items"]],
            [("BOILER", 41, 1.0), ("DRY-1", 4, 0.098), ("CANTEEN", 1, 0.024), ("CHP", 0, 0.0)],
        )
        self.assertEqual([i["quality"] for i in gas["items"]], ["measured", "estimated", "estimated", "measured"])
        for code, qty in (("WM-SOCIAL", 2.6), ("WM-CANTEEN", 1.1), ("WM-BOILER", 0.3), ("WM-SPRAY", 0.2)):
            self.res_interval(self.mcode(code), T0, qty, quality="estimated")
        water = self.get("water")["resource"]["list"]
        self.assertEqual((water["basis"], water["unit"]), ("qty_day", "м³"))
        self.assertEqual(
            [(i["code"], i["value"], i["share"]) for i in water["items"]],
            [("SOCIAL", 2.6, 1.0), ("CANTEEN", 1.1, 0.423), ("BOILER", 0.3, 0.115), ("SPRAY-1", 0.2, 0.077)],
        )

    def test_list_max_eight(self):  # R-11: максимум 8, нулі показуються
        self.fx_gas()
        params = {"from_h": 0, "to_h": 24, "rate": 1.0}
        for k in range(9):
            point = self.point("X%d" % k, "gas", "consumer", estimate_method="schedule", estimate_params=params)
            self.res_interval(self.meter("XM%d" % k, point, "estimate"), T0 + 20 * SLOT, 0.5 + k)
        items = self.get("gas")["resource"]["list"]["items"]
        self.assertEqual(len(items), 8)
        self.assertEqual([i["value"] for i in items], sorted((i["value"] for i in items), reverse=True))
        self.assertEqual(items[0]["code"], "BOILER")

    def test_list_air_load_share(self):  # R-11 п. 1: `load_share` — за живою `p_now` вузла (R-04 п. 1)
        self.fresh("energy/consumers/EDGE-1/p_now", 41.0)
        node = self.env["td.energy.node"].search([("code", "=", "EDGE-1")])
        point = self.env["td.energy.point"].search([("code", "=", "EDGE-1"), ("resource_id.code", "=", "air")])
        expected = rd.estimate.load_share(41.0, node.p_inst_kw, point.rate_nominal, node.load_factor, node.idle_factor)
        items = {i["code"]: i for i in self.get("air")["resource"]["list"]["items"]}
        self.assertEqual(items["EDGE-1"]["value"], rd.r_rate(expected))
        self.assertGreater(expected, 0)

    # --- AC-29 ------------------------------------------------------------------------------------------------
    def test_balance(self):  # AC-29
        self.fx_gas()
        self.assertEqual(self.get("gas")["resource"]["list"]["unaccounted"], {"value": 0.0, "pct": 0.0})
        self.fresh("equipment/BOILER/gas_m3h", 44.68)  # споживачі 49,68 проти вводу 46 — на 8 % більше
        un = self.get("gas")["resource"]["list"]["unaccounted"]
        self.assertEqual((un["value"], un["pct"], un["inconsistent"]), (-3.7, -8.0, True))
        self.fresh("equipment/BOILER/gas_m3h", 36.0)  # залишок 5 м³/год
        un = self.get("gas")["resource"]["list"]["unaccounted"]
        self.assertEqual((un["value"], un["pct"]), (5.0, 10.9))
        self.assertNotIn("inconsistent", un)
        self.env["td.energy.point"].search([("code", "=", "GAS-MAIN")]).write({"active": False})  # немає source
        self.assertIsNone(self.get("gas")["resource"]["list"]["unaccounted"])

    # --- AC-30 ------------------------------------------------------------------------------------------------
    def test_stale_and_partial(self):  # AC-30
        self.fx_heat(rows=False)
        self.env.cr.execute("UPDATE td_signal SET last_ts = NULL, last_value = NULL, status = 'unknown'")
        self.env["td.signal"].invalidate_model()
        for code in ("el", "gas", "heat", "air", "water"):
            data = self.get(code)  # без винятків
            self.assertEqual(data["meta"]["data_state"], "stale", code)
            self.assertIsNone(data["meta"]["age_s"])
            self.assertIsNone(data["resource"]["kpis"][0]["value"], code)
            tab = next(t for t in data["tabs"] if t["code"] == code)
            self.assertIsNone(tab["rate"])
            self.assertTrue(tab["sub"].startswith("—"), tab["sub"])
        self.fresh("infra/gas/m3_total", 18400.0)
        self.fresh("equipment/BOILER/gas_m3h", 41.0)  # лічильник КГУ без свіжого сигналу — частково
        gas = self.get("gas")
        self.assertEqual((gas["meta"]["data_state"], gas["meta"]["age_s"]), ("partial", 0))
        self.fresh("infra/chp/gas_m3h", 0.0)
        self.assertEqual(self.get("gas")["meta"]["data_state"], "ok")
        self.stale("infra/gas/m3_total", 10)  # 10 хв > max(3·60, 120) с
        self.assertEqual(self.get("gas")["meta"]["data_state"], "partial")

    # --- AC-31 ------------------------------------------------------------------------------------------------
    def test_hidden_tabs(self):  # AC-31, D-48
        self.assertIn("air", [t["code"] for t in self.get()["tabs"]])
        self.Meter.search([("resource_id.code", "=", "heat")]).write({"active": False})
        self.assertNotIn("heat", [t["code"] for t in self.get()["tabs"]])  # тепло без лічильників
        self.resource("air").write({"active": False})
        self.assertNotIn("air", [t["code"] for t in self.get()["tabs"]])
        with self.assertRaisesRegex(UserError, "Невідомий ресурс: air."):
            self.get("air")
        self.Resource.with_context(active_test=False).search([("code", "=", "air")]).write({"active": True})
        self.assertIn("air", [t["code"] for t in self.get()["tabs"]])
        self.Meter.search([("resource_id.code", "=", "air")]).write({"active": False})
        self.assertNotIn("air", [t["code"] for t in self.get()["tabs"]])
        with self.assertRaisesRegex(UserError, "Невідомий ресурс: air."):
            self.get("air")
        with self.assertRaisesRegex(UserError, "Невідомий ресурс: xx."):
            self.get("xx")
        self.assertEqual(self.get()["resource"]["code"], "el")  # за умовчанням — перша вкладка

    # --- AC-64, хуки ядра -------------------------------------------------------------------------------------
    def test_core_hooks_and_heat_without_bridge(self):  # AC-64
        if self.env["ir.module.module"].search_count(
            [("name", "=", "td_energy_resources_bms"), ("state", "=", "installed")]
        ):
            self.skipTest("міст td_energy_resources_bms встановлено — хуки не порожні")
        ctx = {}
        self.assertEqual(self.Dash._td_heat_kpis(ctx), [])
        self.assertIsNone(self.Dash._td_heat_list(ctx))
        self.assertIsNone(self.Dash._td_heat_chart_note(ctx))
        self.assertEqual(self.Dash._td_resource_extra("heat", ctx), {})
        self.assertEqual(self.env["td.energy.point"]._td_bind_extra(), {})
        self.fx_heat()
        data = self.get("heat")  # на вручну створених лічильниках, без BMS
        self.assertEqual([k["id"] for k in data["resource"]["kpis"]], ["power", "today"])
        kpis = self.kpis(data)
        self.assertEqual((kpis["power"]["value"], kpis["power"]["note"]), (390, "—"))
        self.assertEqual((kpis["today"]["value"], kpis["today"]["note"]), (5183, "теплобаланс BMS"))
        self.assertEqual(data["resource"]["chart"]["note"], "теплобаланс цеху з BMS")  # без «котли {capacity} кВт»
        self.assertIsNone(data["resource"]["chart"]["limit"])
        self.assertEqual(data["resource"]["list"]["items"], [])

    def test_bridge_hooks_applied(self):  # C-04: хуки моста — merge KPI, список, `{capacity}`, додаткові блоки
        self.fx_heat()
        extra = [
            {"id": "power", "note": "подача 70 °C · зворот 52 °C"},
            {
                "id": "indoor", "label": "Температура в цеху", "value": 18.4, "unit": "°C", "note": "уставка 18 °C",
                "tone": "good", "quality": "measured",
            },
        ]  # fmt: skip
        items = [
            {"code": "RV-ALL", "name": "Дахові установки RoofVent", "value": 228.0},
            {"code": "AHU-1", "name": "Припливна дільниці фасадів", "value": 74.0, "quality": "estimated"},
            {"code": "DOCK", "name": "Втрати через ворота", "value": 46.0, "quality": "estimated"},
            {"code": "OFFICE", "name": "Офіс і побутові", "value": 42.0, "quality": "estimated"},
        ]
        with (
            patch(DASH + "._td_heat_kpis", lambda self, ctx: extra),
            patch(DASH + "._td_heat_list", lambda self, ctx: items),
            patch(DASH + "._td_heat_chart_note", lambda self, ctx: "520"),
            patch(
                DASH + "._td_resource_extra", lambda self, code, ctx: {"bridge": {"code": code, "rate": ctx["rate"]}}
            ),
        ):
            data = self.get("heat")
        block = data["resource"]
        kpis = self.kpis(data)
        self.assertEqual([k["id"] for k in block["kpis"]], ["power", "today", "indoor"])
        self.assertEqual((kpis["power"]["value"], kpis["power"]["note"]), (390, "подача 70 °C · зворот 52 °C"))
        self.assertEqual(kpis["indoor"]["value"], 18.4)
        self.assertEqual(block["chart"]["note"], "теплобаланс цеху з BMS · котли 520 кВт")
        lst = block["list"]
        self.assertEqual(
            [(i["code"], i["value"], i["quality"]) for i in lst["items"]][:2],
            [("RV-ALL", 228, "measured"), ("AHU-1", 74, "estimated")],
        )
        self.assertEqual(lst["unaccounted"], {"value": 0, "pct": 0.0})  # вводи 390 кВт = Σ споживачів
        self.assertEqual(block["bridge"], {"code": "heat", "rate": 390.0})
        self.assertEqual(block["chart"]["foot"], "Найбільша частка тепла — Дахові установки RoofVent (58 %).")

    # --- блок notes (API-02) ----------------------------------------------------------------------------------
    def test_notes_from_opportunities(self):  # API-02 через patch: модель резервів — воркер B
        calls = []

        def get_list(self, resource_code=None, states=("open",)):
            calls.append((resource_code, states))
            item = {
                "id": 31, "code": "preheat_early", "resource": "gas", "title": "Розігрів зарано", "text": "Цех…",
                "save_uah_month": 6900, "in_plan": False, "state": "open", "actions": [{"code": "open"}],
            }  # fmt: skip
            return {"items": [item], "plan_sum": 0, "all_sum": 6900}

        with patch.object(type(self.env["td.energy.opportunity"]), "get_list", get_list, create=True):
            notes = self.get("gas")["resource"]["notes"]
            plain = self.get("gas", self.u_view)["resource"]["notes"]
        self.assertEqual(calls[0], ("gas", ("open",)))
        note = {"id": 31, "title": "Розігрів зарано", "text": "Цех…", "save_uah_month": 6900}
        self.assertEqual(notes, [dict(note, actions=[{"code": "open"}])])
        self.assertEqual(set(plain[0]), {"id", "title", "text", "actions"})  # без вартості (ТБ-02)

    def test_part_error_isolated(self):  # розд. 11: збій частини — `{"error": …}`, решта відповіді ціла
        self.fx_gas()
        with (
            patch.object(rd.Screen, "kpis_gas", side_effect=ValueError("boom")),
            self.assertLogs("odoo.addons.td_energy_resources", level="ERROR"),
        ):
            data = self.get("gas")
        res = data["resource"]
        self.assertEqual(res["kpis"], {"error": "boom"})
        self.assertEqual(len(res["chart"]["series"]), 96)
        self.assertTrue(res["list"]["items"])
        self.assertIsInstance(res["notes"], list)
        self.assertEqual(len(data["tabs"]), 4)

    # --- API-10 -----------------------------------------------------------------------------------------------
    def test_totals(self):  # API-10
        self.fx_el()
        self.fx_gas()
        self.env.flush_all()  # `resource_id` — пов'язане збережене поле: пишеться при flush
        self.env.cr.execute(
            "UPDATE td_energy_res_interval SET kwh_eq = qty * 10.5 WHERE resource_id = %s", (self.resource("gas").id,)
        )
        self.env["td.energy.res.interval"].invalidate_model()
        rows = self.Dash.with_user(self.u_cost)._td_totals("2026-10-17", "2026-10-17")
        by = {r["resource"]: r for r in rows}
        self.assertLessEqual({"el", "gas", "air", "water"}, set(by))
        el = by["el"]  # електрика — потік `import`
        self.assertEqual((el["qty"], el["kwh_eq"], el["cost"], el["co2_kg"]), (6284.0, 6284.0, 52785.6, 2325.08))
        gas = by["gas"]  # решта — `supply`
        self.assertEqual((gas["qty"], gas["kwh_eq"], gas["cost"], gas["co2_kg"]), (612.0, 6426.0, 12117.6, 1199.52))
        self.assertEqual(by["water"]["qty"], 0.0)
        only = self.Dash.with_user(self.u_cost)._td_totals("2026-10-17", "2026-10-17", resource_codes=["gas"])
        self.assertEqual([r["resource"] for r in only], ["gas"])
        plain = self.Dash.with_user(self.u_view)._td_totals("2026-10-17", "2026-10-17")
        self.assertTrue(all("cost" not in r for r in plain))
        self.assertEqual({r["resource"]: r["qty"] for r in plain}["gas"], 612.0)
        with self.assertRaises(AccessError):
            self.Dash.with_user(self.u_plain)._td_totals("2026-10-17", "2026-10-17")
        with self.assertRaises(UserError):
            self.Dash._td_totals("2026-10-17;DROP", "2026-10-17")

    # --- R-25, R-10 п. 3: чисті функції ----------------------------------------------------------------------
    def test_number_formats(self):  # R-25
        self.assertEqual([rd.r_rate(v) for v in (46.3, 9.84, 0.42, 12.0)], [46, 9.8, 0.4, 12])
        self.assertEqual([rd.r_rate(v, "water") for v in (0.05, 0.42, 2.14)], [0.05, 0.42, 2.1])
        self.assertEqual([rd.r_day(v) for v in (612.4, 4.25, 99.96)], [612, 4.2, 100])
        self.assertEqual([rd.fmt_int(65156), rd.fmt_dec(8.4, 2), rd.fmt_dec(1234.5, 1)], ["65 156", "8,40", "1 234,5"])
        self.assertEqual([rd.fmt_auto(v) for v in (90, 6.0, 7.1, 0.05, 0.5)], ["90", "6,0", "7,1", "0,05", "0,5"])
        self.assertEqual([rd.t_rate(v) for v in (None, 46, 9.8, 0.05, 0.4)], ["—", "46", "9,8", "0,05", "0,4"])
        self.assertEqual([rd.nice(x) for x in (29.33, 293.3, 3.593, 0.154, 0.0)], [30, 300, 4, 0.2, 1.0])
        self.assertEqual(rd.axis([22.0, None, 46.0], 80), (90, [30, 60, 90]))
        self.assertEqual(rd.axis([631.0], 800), (900, [300, 600, 900]))
        self.assertEqual(rd.axis([9.8], None), (12, [4, 8, 12]))
        self.assertEqual(rd.axis([0.42], None), (0.6, [0.2, 0.4, 0.6]))
