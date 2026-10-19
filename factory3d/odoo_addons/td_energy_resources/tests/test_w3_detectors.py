"""W3-B: AC-34…AC-39, AC-62 — детектори резервів ядра (R-15…R-20) на фікстурах SPEC; сценарій `air_leak` (AC-62)."""

from datetime import date, datetime, timedelta
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.td_energy.tools import dates
from odoo.addons.td_energy.tools.dates import to_local

from ..tools import shifts
from ..tools.detectors import air_leaks, air_pressure, common, idle_machines, pv_export, react_section, vent_offshift
from .common import NOW, SLOT, TAGS, TestW3Common

LO = datetime(2026, 10, 9, 21, 0)  # 00:00 Київ 10.10: початок вікна L = 7 для NOW (доби 10.10…16.10)
DAYS = 7


def is_night(local):
    return local.hour >= 23 or local.hour * 60 + local.minute < 390  # 23:00…06:30 (за умовчанням)


@tagged(*TAGS)
class TestW3Detectors(TestW3Common):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["ir.config_parameter"].sudo().set_param("td.energy.shift_calendar_id", False)  # умовчання макета
        cls.sw = shifts.load_windows(cls.env)
        cls.Meter = cls.env["td.energy.meter"]

    def rule(self, code):
        return self.env.ref("td_energy_resources.rule_" + code)

    # --- фікстури -------------------------------------------------------------------------------------------
    def slots(self, days=DAYS, first=0):
        return [LO + SLOT * i for i in range(96 * first, 96 * (first + days))]

    def fill_el(self, meter_code, fn, days=DAYS):
        """`td.energy.interval` лічильника: `fn(ts, local, in_shift) -> (kwh, kwh_export, price) | None`."""
        meter = self.Meter.search([("code", "=", meter_code)])
        rows = []
        for ts in self.slots(days):
            local = to_local(ts)
            value = fn(ts, local, self.sw.is_shift(local))
            if value is None:
                continue
            kwh, export, price = value
            rows.append(
                {
                    "meter_id": meter.id,
                    "ts_start": ts,
                    "ts_end": ts + SLOT,
                    "day": local.date(),
                    "hour_local": local.hour,
                    "e_start": 0.0,
                    "e_end": kwh,
                    "kwh": kwh,
                    "kwh_export": export,
                    "kw_avg": kwh * 4,
                    "price": price,
                    "cost": round(kwh * price, 2),
                    "quality": "measured",
                    "built_at": self.now,
                }  # fmt: skip
            )
        self.env["td.energy.interval"].create(rows)
        return rows

    def fill_res(self, meter, fn, days=DAYS):
        """`td.energy.res.interval`: `fn(ts, local, in_shift, night) -> швидкість | None`; повертає Σ qty."""
        factor = meter.resource_id.rate_hour_factor or 1.0
        rows = []
        for ts in self.slots(days):
            local = to_local(ts)
            rate = fn(ts, local, self.sw.is_shift(local), is_night(local))
            if rate is None:
                continue
            rows.append(
                {
                    "meter_id": meter.id,
                    "metric": "main",
                    "ts_start": ts,
                    "ts_end": ts + SLOT,
                    "day": local.date(),
                    "hour_local": local.hour,
                    "qty": rate * factor * 0.25,
                    "rate_avg": rate,
                    "kwh_eq": 0.0,
                    "price": 0.0,
                    "cost": 0.0,
                    "quality": "measured",
                    "built_at": self.now,
                }  # fmt: skip
            )
        self.ResInterval.create(rows)
        return sum(r["qty"] for r in rows)

    def detect(self, module, code, now=NOW):
        self.env.flush_all()
        return module.detect(self.env, self.rule(code), now)

    # --- AC-34: vent_offshift
    def fill_vent(self, off_kw=50.0, days=DAYS):
        self.fill_el("PM-RV-ALL", lambda ts, local, shift: ((100.0 if shift else off_kw) / 4, 0.0, 6.0), days)

    def test_vent_offshift(self):  # AC-34
        self.fill_vent()
        found = self.detect(vent_offshift, "vent_offshift")
        self.assertEqual(len(found), 1)
        item = found[0]
        self.assertEqual((item["dedup_key"], item["title"]), ("vent_offshift:*", "Вентиляція працює поза змінами"))
        self.assertAlmostEqual(item["est_qty_month"], 7620.8, places=1)
        self.assertEqual(item["est_saving_month"], 45725.0)
        ev = item["evidence"]
        self.assertEqual(
            (ev["day_level_kw"], ev["off_level_kw"], ev["ratio"], ev["off_hours"]), (100.0, 50.0, 0.5, 88.0)
        )
        self.assertIn("RV-ALL", ev["nodes"])
        self.assertLessEqual(len(item["text"]), 400)

    def test_vent_offshift_negative(self):  # AC-34
        self.fill_vent(off_kw=30.0)  # ratio 0,30 < 0,35
        self.assertEqual(self.detect(vent_offshift, "vent_offshift"), [])

    def test_vent_offshift_no_nodes_or_data(self):  # AC-34
        self.fill_vent()
        self.env["td.energy.node"].search([("group", "=", "vent")]).write({"group": False})
        self.assertEqual(self.detect(vent_offshift, "vent_offshift"), [])

    def test_vent_offshift_few_days(self):  # AC-34: даних < 3 діб (і < 70 % слотів)
        self.fill_vent(days=2)
        self.assertEqual(self.detect(vent_offshift, "vent_offshift"), [])

    # --- AC-35: idle_machines
    def fill_alloc(self, idle_total=410.0, rc_total=6000.0, price=8.4):
        Node, Alloc = self.env["td.energy.node"], self.env["td.energy.alloc"]
        split = {"SAW-1": 0.5, "SAW-2": 0.3, "EDGE-1": 0.12, "CNC-1": 0.08}
        rows = []
        for day in (date(2026, 10, d) for d in range(12, 17)):  # 5 робочих діб
            for code, share in split.items():
                kwh = idle_total / 5 * share
                rows.append(
                    {
                        "day": day,
                        "kind": "idle",
                        "node_id": Node.search([("code", "=", code)]).id,
                        "kwh": kwh,
                        "cost": kwh * price,
                        "quality": "measured",
                    }  # fmt: skip
                )
            direct = (rc_total - idle_total) / 5
            rows.append({"day": day, "kind": "direct", "kwh": direct, "cost": direct * price, "quality": "measured"})
        Alloc.create(rows)

    def test_idle_machines(self):  # AC-35
        self.fill_alloc()
        found = self.detect(idle_machines, "idle_machines")
        self.assertEqual(len(found), 1)
        item = found[0]
        self.assertAlmostEqual(item["est_qty_month"], 1242.7, places=1)
        self.assertEqual(item["est_saving_month"], 10439.0)
        ev = item["evidence"]
        self.assertAlmostEqual(ev["share"], 410 / 6000, places=3)
        self.assertEqual(ev["top_nodes"], ["SAW-1", "SAW-2", "EDGE-1"])  # 3 вузли з найбільшим простоєм
        self.assertEqual(item["node_code"], "SAW-1")
        self.assertIn("410", item["text"].replace(" ", "").replace("\xa0", ""))
        self.assertEqual(item["dedup_key"], "idle_machines:*")

    def test_idle_machines_negative(self):  # AC-35
        self.assertEqual(self.detect(idle_machines, "idle_machines"), [])  # немає розподілу
        self.fill_alloc(idle_total=200.0)  # 3,3 % < 5 %
        self.assertEqual(self.detect(idle_machines, "idle_machines"), [])

    # --- AC-36: air_leaks
    def fill_air(self, night=1.6, day=10.0, spec=0.0883, price=8.4, skip_nights=0):
        """Магістраль повітря (`AM-MAIN`): ніч — `night`, зміни — `day`, решта 5,0; COMPRESSOR з Σ kWh = spec·Σ qty.
        `skip_nights` перших ночей вікна без нічних слотів (покриття ночі < 70 %)."""
        meter = self.Meter.search([("code", "=", "AM-MAIN")])
        first = date(2026, 10, 10)

        def rate(ts, local, shift, is_n):
            if is_n:
                morning = local.date() + timedelta(days=1 if local.hour >= 23 else 0)
                return None if morning < first + timedelta(days=skip_nights) else night
            return day if shift else 5.0

        qty = self.fill_res(meter, rate)
        slot_kwh = spec * qty / (96 * DAYS)
        self.fill_el("PM-COMPRESSOR", lambda ts, local, shift: (slot_kwh, 0.0, price))
        return qty

    def test_air_leaks(self):  # AC-36
        self.fill_air()
        found = self.detect(air_leaks, "air_leaks")
        self.assertEqual(len(found), 1)
        item = found[0]
        self.assertAlmostEqual(item["est_qty_month"], 4022.2, delta=0.5)  # kWh інтервалів округлені до 3 знаків
        self.assertAlmostEqual(item["est_saving_month"], 33787.0, delta=4)
        ev = item["evidence"]
        self.assertEqual((ev["night_flow"], ev["day_flow"], ev["share_pct"], ev["reducible"]), (1.6, 10.0, 16.0, 0.65))
        self.assertAlmostEqual(ev["spec"], 0.0883, places=4)
        self.assertEqual((item["node_code"], item["point_code"]), ("COMPRESSOR", "AIR-MAIN"))
        # дія ticket на COMPRESSOR з тегом [OPP-<id>] — після прогону правила (рушій, R-13)
        self.rule("air_leaks").action_run()
        opp = self.env["td.energy.opportunity"].search([("dedup_key", "=", "air_leaks:*")])
        ticket = opp.actions[0]
        self.assertEqual((ticket["kind"], ticket["params"]["node_code"]), ("ticket", "COMPRESSOR"))
        self.assertIn("[OPP-%d]" % opp.id, ticket["params"]["description"])

    def test_air_leaks_negative(self):  # AC-36
        self.fill_air(night=0.9)  # 9 % < 10 %
        self.assertEqual(self.detect(air_leaks, "air_leaks"), [])

    def test_air_leaks_few_nights(self):  # AC-36: менше 3 ночей з покриттям ≥ 70 %
        self.fill_air(skip_nights=5)
        self.assertEqual(self.detect(air_leaks, "air_leaks"), [])

    # --- AC-37: air_pressure
    SETPOINT = "energy_control/air/setpoint_bar"

    def fill_pressure(self, setpoint=7.0):
        self.fresh(self.signal(self.SETPOINT, unit="бар").code, setpoint)
        self.fill_res(self.Meter.search([("code", "=", "AM-PRESS1")]), lambda ts, local, shift, night: 1.9)
        self.fill_el("PM-COMPRESSOR", lambda ts, local, shift: (642.0 / 96, 0.0, 8.4))

    def test_air_pressure(self):  # AC-37
        self.fill_pressure()
        found = self.detect(air_pressure, "air_pressure")
        self.assertEqual(len(found), 1)
        item = found[0]
        self.assertAlmostEqual(item["est_qty_month"], 681.0, delta=0.3)
        self.assertAlmostEqual(item["est_saving_month"], 5721.0, delta=3)
        ev = item["evidence"]
        self.assertEqual(
            (ev["p_set"], ev["p_need"], ev["p_target"], ev["dp"], ev["consumer"]), (7.0, 6.2, 6.5, 0.5, "PRESS-1")
        )
        self.assertIn("Мембранний прес", item["text"])
        self.assertIn("6,2 бар", item["text"])
        self.assertEqual(item["dedup_key"], "air_pressure:*")

    def test_air_pressure_setpoint_sources(self):  # AC-37: сигнал, інакше параметр
        self.fill_pressure(setpoint=7.0)
        params = self.env["ir.config_parameter"].sudo()
        params.set_param("td.energy_resources.air_setpoint_bar", "6.5")
        self.assertEqual(self.detect(air_pressure, "air_pressure")[0]["evidence"]["p_set"], 7.0)  # сигнал важливіший
        self.stale(self.SETPOINT)  # сигнал застарів → параметр 6,5: dp = 0
        self.assertEqual(self.detect(air_pressure, "air_pressure"), [])
        params.set_param("td.energy_resources.air_setpoint_bar", "7.0")
        self.assertEqual(self.detect(air_pressure, "air_pressure")[0]["evidence"]["p_set"], 7.0)

    def test_air_pressure_small_dp(self):  # AC-37: dp < 0,2
        self.fill_pressure(setpoint=6.6)  # dp = 6,6 − 6,5 = 0,1
        self.assertEqual(self.detect(air_pressure, "air_pressure"), [])

    # --- AC-38: react_section
    def fill_react(self, cos=0.85, p_kw=125.0, q_kvar=68.75, limit=0.40, rate=0.24):
        tariff = self.env["td.energy.tariff"]._td_tariff_at(NOW)
        tariff.write({"tg_phi_limit": limit, "react_rate": rate})
        step = timedelta(minutes=15)
        grid = [LO - step + step * i for i in range(96 * DAYS + 3)]
        for key, value in (("cos_phi", cos), ("p_kw", p_kw), ("q_kvar", q_kvar)):
            signal = self.Signal.search([("code", "=", "energy/sections/S1/" + key)])
            self.feed(signal, [(ts, value) for ts in grid])

    def test_react_section(self):  # AC-38
        self.fill_react()
        found = self.detect(react_section, "react_section")
        self.assertEqual(len(found), 1)  # S2 без показань пропускається
        item = found[0]
        self.assertEqual((item["dedup_key"], item["node_code"]), ("react_section:S1", "PFC-1"))
        self.assertAlmostEqual(item["est_qty_month"], 13500.0, places=1)
        self.assertEqual(item["est_saving_month"], 3240.0)
        self.assertEqual(item["evidence"]["h_low_avg"], 24.0)
        self.assertIn("cos φ секції 1 — 0,85", item["text"])
        ticket = item["actions"][0]  # заявки немає → ticket на вузол PFC-1
        self.assertEqual((ticket["kind"], ticket["params"]["node_code"]), ("ticket", "PFC-1"))

    def test_react_section_open_request_link(self):  # AC-38: дія веде на відкриту заявку PFC
        self.fill_react()
        equipment = self.env["maintenance.equipment"].create({"name": "PFC-1 (тест)"})
        self.env["td.energy.node"].search([("code", "=", "PFC-1")]).equipment_id = equipment
        stage = self.env["maintenance.stage"].search([("done", "=", False)], limit=1)
        request = self.env["maintenance.request"].create(
            {"name": "Ремонт PFC-1", "equipment_id": equipment.id, "stage_id": stage.id}
        )
        link = self.detect(react_section, "react_section")[0]["actions"][0]
        self.assertEqual(link["kind"], "link")
        self.assertEqual(link["params"], {"xmlid": "maintenance.hr_equipment_request_action", "res_id": request.id})
        request.stage_id = self.env["maintenance.stage"].search([("done", "=", True)], limit=1)  # закрита — ticket
        self.assertEqual(self.detect(react_section, "react_section")[0]["actions"][0]["kind"], "ticket")

    def test_react_section_negative(self):  # AC-38
        self.fill_react(limit=0.0, rate=0.0)  # без параметрів доплати в тарифі
        with self.assertRaisesRegex(common.DetectorNote, "Немає параметрів доплати в тарифі"):
            self.detect(react_section, "react_section")
        rule = self.rule("react_section")
        rule.action_run()
        self.assertEqual(rule.last_error, "Немає параметрів доплати в тарифі")
        self.assertEqual(rule.last_count, 0)

    def test_react_section_cos_ok(self):  # AC-38: h_low_avg < 2
        self.fill_react(cos=0.95)
        self.assertEqual(self.detect(react_section, "react_section"), [])

    # --- AC-39: pv_export
    def fill_pv(self, export_price=2.0):
        tariff = self.env["td.energy.tariff"]._td_tariff_at(NOW)
        tariff.export_price = export_price
        big = {self.slots()[i] for i in (200, 201, 202, 203)}  # 4 слоти по 29,5 кВт·год (118 кВт ≥ 10)
        self.fill_el("PM-Q1", lambda ts, local, shift: (10.0, 29.5 if ts in big else 0.5, 8.4))

    def test_pv_export(self):  # AC-39
        self.fill_pv()
        found = self.detect(pv_export, "pv_export")
        self.assertEqual(len(found), 1)
        item = found[0]
        self.assertAlmostEqual(item["est_qty_month"], 510.94, places=1)
        self.assertEqual(item["est_saving_month"], 3270.0)
        self.assertEqual((item["evidence"]["export_kwh"], item["evidence"]["slots"]), (118.0, 4))
        self.assertEqual(item["dedup_key"], "pv_export:*")

    def test_pv_export_negative(self):  # AC-39: buy ≤ export
        self.fill_pv(export_price=8.4)
        self.assertEqual(self.detect(pv_export, "pv_export"), [])
        self.env["td.energy.tariff"]._td_tariff_at(NOW).export_price = 9.0
        self.assertEqual(self.detect(pv_export, "pv_export"), [])

    # --- AC-62: сценарій air_leak
    def test_scenario_air_leak(
        self,
    ):  # AC-62: ≥ 3 ночі історії → резерв; витік усунено → expired при наступному прогоні
        self.fill_air()
        rule = self.rule("air_leaks")
        self.assertEqual(rule.action_run()["created"], 1)
        opp = self.env["td.energy.opportunity"].search([("dedup_key", "=", "air_leaks:*"), ("state", "=", "open")])
        self.assertEqual(opp.resource_id.code, "air")
        note = self.env["td.energy.res.dashboard"].get_resources("air")["resource"]["notes"]
        self.assertEqual([n["id"] for n in note], [opp.id])  # блок notes екрана (API-01 ← API-02)
        self.assertEqual(note[0]["title"], "Витоки стисненого повітря")
        # сценарій зупинено: нічна витрата 4 останніх ночей падає до 0,1 → медіана нічних мінімумів < min_flow
        self.env.flush_all()
        quiet_from = dates.local_day_bounds(date(2026, 10, 13))[0]
        self.env.cr.execute(
            "UPDATE td_energy_res_interval SET rate_avg = 0.1, qty = 1.5 WHERE ts_start >= %s AND ("
            "EXTRACT(HOUR FROM ts_start AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Kyiv') >= 23 OR "
            "EXTRACT(HOUR FROM ts_start AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Kyiv') * 60 "
            "+ EXTRACT(MINUTE FROM ts_start AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Kyiv') < 390)",
            (quiet_from - timedelta(hours=1),),
        )
        self.ResInterval.invalidate_model()
        stats = rule.action_run()
        self.assertEqual((stats["created"], stats["expired"]), (0, 1))
        self.assertEqual(opp.state, "expired")
        self.assertEqual(rule.last_count, 0)

    def test_detector_registry(self):  # R-14: реєстр і сигнатура
        methods = self.env["td.energy.opportunity.rule"]._td_detector_methods()
        self.assertTrue(
            {"vent_offshift", "idle_machines", "air_leaks", "air_pressure", "react_section", "pv_export"}
            <= set(methods)
        )
        self.assertEqual(self.rule("vent_offshift")._td_detect(NOW), [])  # без даних — порожньо, без помилки
        with patch.object(common, "k_month", return_value=1.0):
            self.assertEqual(common.k_month(self.env, 7), 1.0)
        self.assertAlmostEqual(common.k_month(self.env, 7), 4.33)
        self.assertAlmostEqual(common.k_month(self.env, 14), 2.165)
