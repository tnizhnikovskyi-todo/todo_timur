"""W4-A: розрізи, «До бази», деталізація, резерви (AC-35…AC-43)."""

from datetime import date, timedelta

from odoo.exceptions import UserError

from odoo.tests import tagged

from .common import TAGS, TODAY, TestW4Common

WINDOW = (TODAY - timedelta(days=29), TODAY)
BASE = (date(2025, 11, 1), date(2025, 11, 30))


@tagged(*TAGS)
class TestW4Cuts(TestW4Common):
    def _cost_cut(self, dim, period="m"):
        return self.Api.with_user(self.u_cost).get_cut(dim, period)

    def _rows(self, cut):
        return {r["key"]: r for r in cut["rows"]}

    def _area_fixture(self, with_base=True):
        """Вікно: CUT 26 100 (SAW-1 21 000 + SAW-2 5 100), HVAC 9 000, LIGHT_OFFICE 3 000; плит 38 400."""
        if with_base:
            self._approved_baseline(BASE, {"plate_m2": 4.1}, 1820.0)
        for day in self._days(WINDOW[0], 30):
            self._daily(day, scope="node", node="SAW-1", qty=700.0, cost=5880.0)
            self._daily(day, scope="node", node="SAW-2", qty=170.0, cost=1428.0)
            self._daily(day, scope="node", node="RV-ALL", qty=300.0, cost=2520.0)
            self._daily(day, scope="node", node="OFFICE", qty=100.0, cost=840.0)
            self._driver_value("plate_m2", day, 1280.0)
        for day in self._days(BASE[0], 30):
            self._daily(day, scope="node", node="SAW-1", qty=708.3)
            self._driver_value("plate_m2", day, 1000.0)

    # --- AC-35 -----------------------------------------------------------------------------------------
    def test_ac35_area_cut(self):
        self._area_fixture()
        cut = self._cost_cut("area")
        self.assertEqual(
            (cut["dim"], cut["dim_name"], cut["col_name"], cut["col_spec"]),
            ("area", "Ділянки", "Ділянка", "кВт·год/м²"),
        )
        rows = self._rows(cut)
        self.assertEqual([r["key"] for r in cut["rows"]], ["CUT", "HVAC", "LIGHT_OFFICE"], "сортування за kwh")
        cutr = rows["CUT"]
        self.assertEqual(
            (cutr["kwh"], cutr["cost_uah"], cutr["spec"], cutr["spec_text"]), (26100, 219240, 0.68, "0,68")
        )
        self.assertEqual(cutr["name"], "Розкрій")
        total = 26100 + 9000 + 3000
        self.assertEqual(cutr["share_pct"], round(26100 / total * 100))
        self.assertAlmostEqual(cutr["bar"], 1.0)
        self.assertAlmostEqual(rows["HVAC"]["bar"], 9000 / 26100, places=3)
        self.assertEqual((rows["LIGHT_OFFICE"]["spec"], rows["LIGHT_OFFICE"]["spec_text"]), (None, "—"))
        self.assertAlmostEqual(rows["HVAC"]["spec"], 9000 / 38400, places=2)
        # без групи вартості — ключа cost_uah немає
        plain = self.Api.with_user(self.u_view).get_cut("area", "m")
        self.assertTrue(all("cost_uah" not in r for r in plain["rows"]))
        self.assertEqual(plain["rows"][0]["kwh"], 26100)

    def test_ac35_node_without_area_row(self):
        self._area_fixture()
        self._node("LP-1").area_id = False
        for day in self._days(WINDOW[0], 30):
            self._daily(day, scope="node", node="LP-1", qty=10.0)
        rows = self._rows(self._cost_cut("area"))
        self.assertEqual((rows["NONE"]["name"], rows["NONE"]["kwh"]), ("Без ділянки", 300))

    # --- AC-36 -----------------------------------------------------------------------------------------
    def test_ac36_equipment_cut(self):
        day = TODAY - timedelta(days=3)
        self._daily(day, scope="node", node="SAW-3", qty=7400.0, cost=62160.0, minutes=15300.0)
        self._daily(day, scope="node", node="RV-ALL", qty=3000.0, cost=0.0, minutes=0.0)
        self._daily(day, scope="node", node="CNC-1", qty=900.0, minutes=60.0)
        self._daily(day, scope="node", node="CNC-2", qty=500.0, minutes=30.0)  # < 1 мотогод → null
        self._param("top_equipment", 3)
        cut = self._cost_cut("eq")
        self.assertEqual(cut["col_spec"], "кВт·год/мотогод")
        keys = [r["key"] for r in cut["rows"]]
        self.assertEqual(keys, ["SAW-3", "RV-ALL", "CNC-1", "OTHER"], "понад top_equipment — «Інші»")
        rows = self._rows(cut)
        self.assertEqual(rows["SAW-3"]["spec"], 29.0)
        self.assertEqual((rows["SAW-3"]["spec_text"], rows["SAW-3"]["name"].startswith("SAW-3 · ")), ("29,0", True))
        self.assertEqual((rows["RV-ALL"]["spec"], rows["RV-ALL"]["spec_text"]), (None, "—"))
        self.assertEqual(rows["CNC-1"]["spec"], 900.0)
        self.assertEqual((rows["OTHER"]["kwh"], rows["OTHER"]["name"], rows["OTHER"]["spec"]), (500, "Інші", None))
        self.assertEqual(sum(r["share_pct"] for r in cut["rows"]), 100)

    # --- AC-37, AC-38 ----------------------------------------------------------------------------------
    def _mo_fixture(self):
        product = self._product("W4-CUT-A", 1.0)
        day = TODAY - timedelta(days=2)
        mo1 = self._mo(product, 60, name="WH/MO/00391")
        mo2 = self._mo(product, 30, name="WH/MO/00392")
        mo3 = self._mo(self._product("W4-CUT-B", 2.0), 10, name="WH/MO/00393")
        node = self._node("SAW-1")
        self._alloc(mo1, node, day, kwh=2470.0)
        self._alloc(mo2, node, day, kwh=500.0)
        self._alloc(mo3, node, day, kwh=40.0)
        self._mo(product, 5, name="WH/MO/00394")  # без рядків alloc — не показується
        return product, (mo1, mo2, mo3)

    def test_ac37_mo_cut(self):
        product, _mos = self._mo_fixture()
        self._param("top_mo", 2)
        cut = self._cost_cut("mo")
        self.assertEqual((cut["col_name"], cut["col_spec"]), ("Замовлення", "кВт·год/шт"))
        self.assertEqual([r["key"] for r in cut["rows"]], ["WH/MO/00391", "WH/MO/00392", "OTHER"])
        first = cut["rows"][0]
        self.assertEqual(first["name"], "WH/MO/00391 · W4-CUT-A × 60")
        self.assertEqual((first["kwh"], first["spec"], first["spec_text"]), (2470, 41.2, "41,2"))
        self.assertEqual(cut["rows"][2]["kwh"], 40)
        self._param("top_mo", 20)
        keys = [r["key"] for r in self._cost_cut("mo")["rows"]]
        self.assertNotIn("WH/MO/00394", keys)

    def test_ac38_product_cut(self):
        product, _mos = self._mo_fixture()
        rows = self._rows(self._cost_cut("prod"))
        row = rows[str(product.id)]
        self.assertEqual(row["name"], product.display_name)
        self.assertEqual(row["kwh"], 2970)
        self.assertAlmostEqual(row["spec"], 2970 / 90, places=1)
        self.assertEqual(self._cost_cut("prod")["col_spec"], "кВт·год/од.")

    # --- AC-39 -----------------------------------------------------------------------------------------
    def test_ac39_shift_cut(self):
        self._calendar_two_shifts()
        days = self._days(WINDOW[0], 30)
        for day in days:
            self._daily(
                day, shift1_qty=1000.0, shift2_qty=600.0, off_qty=200.0, cost_s1=8400.0, cost_s2=5040.0,
                cost_off=1680.0, plate_s1=500.0, plate_s2=300.0, plate_off=0.0,
            )  # fmt: skip
        cut = self._cost_cut("shift")
        self.assertEqual([r["name"] for r in cut["rows"]], [
            "Зміна 1 · 07:00–16:00", "Зміна 2 · 16:00–23:00", "Ночі й вихідні · без виробництва",
        ])  # fmt: skip
        s1, s2, off = cut["rows"]
        self.assertEqual((s1["kwh"], s1["cost_uah"], s1["spec"]), (30000, 252000, 2.0))
        self.assertEqual((s2["kwh"], s2["spec"]), (18000, 2.0))
        weekdays = sum(1 for d in days if d.weekday() < 5)
        off_hours = weekdays * 8 + (30 - weekdays) * 24
        avg = 6000.0 / off_hours
        self.assertEqual(off["spec_text"], "база %d кВт" % round(avg))
        self.assertIsNone(off["spec"])

    # --- AC-40 -----------------------------------------------------------------------------------------
    def test_ac40_zero_denominators(self):
        day = TODAY - timedelta(days=1)
        self._daily(day, scope="node", node="SAW-1", qty=100.0, minutes=0.0)
        self._daily(day, shift1_qty=50.0, plate_s1=0.0)
        for dim in ("area", "eq", "mo", "prod", "shift"):  # у т.ч. порожні розрізи без винятків
            cut = self._cost_cut(dim)
            for row in cut["rows"]:
                if row["spec"] is None:
                    self.assertEqual(row["spec_text"][:1] in ("—", "б"), True, (dim, row))
        self.assertEqual(self._rows(self._cost_cut("area"))["CUT"]["spec"], None)
        self.assertEqual(self._rows(self._cost_cut("eq"))["SAW-1"]["spec"], None)

    # --- AC-41 -----------------------------------------------------------------------------------------
    def test_ac41_to_baseline(self):
        self._area_fixture()
        rows = self._rows(self._cost_cut("area"))
        self.assertEqual(rows["CUT"]["delta_pct"], -4)
        self.assertIsNone(rows["HVAC"]["delta_pct"], "немає даних у вікні бази")
        self.assertIsNone(rows["LIGHT_OFFICE"]["delta_pct"])

    def test_ac41_no_baseline_all_null(self):
        self._area_fixture(with_base=False)
        self.assertTrue(all(r["delta_pct"] is None for r in self._cost_cut("area")["rows"]))

    def test_ac41_mo_vs_product_in_base(self):
        self._approved_baseline(BASE, {"plate_m2": 4.1}, 1820.0)
        product = self._product("W4-DELTA", 1.0)
        node = self._node("SAW-1")
        base_mo = self._mo(product, 50, name="WH/MO/B0001")
        self._alloc(base_mo, node, date(2025, 11, 10), kwh=2000.0)  # 40 кВт·год/од.
        mo = self._mo(product, 60, name="WH/MO/00391")
        self._alloc(mo, node, TODAY - timedelta(days=2), kwh=2470.0)  # 41,17
        row = self._rows(self._cost_cut("mo"))["WH/MO/00391"]
        self.assertEqual(row["delta_pct"], 3)
        prod = self._rows(self._cost_cut("prod"))[str(product.id)]
        self.assertEqual(prod["delta_pct"], 3)

    # --- AC-42 -----------------------------------------------------------------------------------------
    def test_ac42_open_cut_actions(self):
        first, last = WINDOW
        win = [("day", ">=", first), ("day", "<=", last)]
        api = self.Api.with_user(self.u_view)
        act = api.action_open_cut("area", "CUT", "m")
        self.assertEqual((act["type"], act["res_model"]), ("ir.actions.act_window", "td.energy.interval"))
        self.assertEqual(act["domain"], [("role", "=", "consumer"), ("node_id.area_id.code", "=", "CUT")] + win)
        self.assertEqual(act["context"]["pivot_row_groupby"], ["node_id"])
        self.assertEqual(
            api.action_open_cut("eq", "SAW-1", "m")["domain"],
            [("role", "=", "consumer"), ("node_id.code", "=", "SAW-1")] + win,
        )
        product = self._product("W4-OPEN", 1.0)
        self._mo(product, 1, name="WH/MO/00391")
        mo_act = api.action_open_cut("mo", "WH/MO/00391", "m")
        self.assertEqual(
            (mo_act["res_model"], mo_act["domain"][0]), ("td.energy.alloc", ("production_id.name", "=", "WH/MO/00391"))
        )
        prod_act = api.action_open_cut("prod", str(product.id), "q")
        self.assertEqual(prod_act["domain"][0], ("product_id", "=", product.id))
        self.assertIn(("day", ">=", TODAY - timedelta(days=90)), prod_act["domain"])
        shift_act = api.action_open_cut("shift", "shift1", "w")
        self.assertEqual(shift_act["domain"][0], ("role", "=", "feeder"))
        self.assertEqual(shift_act["context"]["pivot_row_groupby"], ["hour_local"])
        self.assertTrue(all(v[1] in ("list", "pivot", "graph") for v in act["views"]))
        for bad in (("area", "OTHER"), ("eq", "OTHER"), ("area", "NOPE"), ("mo", "NOPE"), ("prod", "x")):
            with self.assertRaisesRegex(UserError, "Невідомий ключ"):
                api.action_open_cut(*bad, "m")
        with self.assertRaisesRegex(UserError, "Невідомий розріз"):
            api.action_open_cut("zzz", "k", "m")

    # --- AC-43 -----------------------------------------------------------------------------------------
    def _opps(self):
        rule = self.env.ref("td_energy_resources.rule_vent_offshift")
        Opp = self.env["td.energy.opportunity"]
        recs = Opp
        for i, saving in enumerate((15500.0, 12000.0, 5500.0)):
            recs |= Opp.create(
                {
                    "rule_id": rule.id, "dedup_key": "w4:%d" % i, "title": "Резерв %d" % i, "text": "Текст",
                    "est_saving_month": saving, "est_qty_month": 100.0,
                    "actions": [{"code": "night_mode", "label": "Сценарій BMS", "kind": "control",
                                 "params": {"intent": "vent_night_mode"}}],
                }
            )  # fmt: skip
        recs[0].with_user(self.u_eng).action_plan_toggle()
        return recs

    def test_ac43_opportunities(self):
        recs = self._opps()
        Opp = self.env["td.energy.opportunity"]
        cost = self.Api.with_user(self.u_cost).get_dashboard("m", "area", ["opps"])["opps"]
        w3 = Opp.with_user(self.u_cost).get_list()
        summary = Opp.with_user(self.u_cost).get_plan_summary()
        self.assertEqual([i["id"] for i in cost["items"]], [i["id"] for i in w3["items"]])
        self.assertEqual((cost["plan_sum"], cost["all_sum"]), (w3["plan_sum"], w3["all_sum"]))
        self.assertEqual((cost["plan_sum"], cost["all_sum"]), (15500, 33000))
        self.assertEqual((cost["plan_count"], cost["open_count"]), (summary["plan_count"], summary["open_count"]))
        self.assertEqual((cost["plan_count"], cost["open_count"]), (1, 3))
        self.assertEqual(cost, self.Api.with_user(self.u_cost).get_opportunities())
        first = cost["items"][0]
        self.assertEqual((first["id"], first["in_plan"], first["save_uah_month"]), (recs[0].id, True, 15500))
        # control без td_energy_control: enabled=False + запасна дія
        night = [a for a in first["actions"] if a["code"] == "night_mode"][0]
        self.assertEqual(night["enabled"], self.env["td.energy.advice"]._td_control_available())
        if not night["enabled"]:
            self.assertTrue(any(a["enabled"] for a in first["actions"]))
        # без групи вартості
        plain = self.Api.with_user(self.u_view).get_opportunities()
        self.assertEqual(set(plain), {"items", "plan_count", "open_count"})
        self.assertTrue(all("save_uah_month" not in i for i in plain["items"]))
        # перемикання «у плані» через W3 змінює plan_sum
        recs[1].with_user(self.u_eng).action_plan_toggle()
        self.assertEqual(self.Api.with_user(self.u_cost).get_opportunities()["plan_sum"], 27500)
