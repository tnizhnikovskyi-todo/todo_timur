"""W1-A: AC-122…AC-129 — картка вузла (R-30, API-07)."""

from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import NOW, TAGS, TestW1Common


@tagged(*TAGS)
class TestW1Card(TestW1Common):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Dash = cls.env["td.energy.dashboard"]
        cls.bw2 = cls.Node.search([("code", "=", "BW-2")])
        cls.consumers = cls.Node.search([("id", "child_of", cls.bw2.id), ("kind", "=", "consumer")])

    def card(self, code="BW-2", user=None):
        return self.Dash.with_user(user or self.u_cost).get_node_card(code)

    def set_phases(self):
        for phase, value in (("a", 188.0), ("b", 195.0), ("c", 193.0)):
            self.fresh("energy/lines/BW-2/i_%s" % phase, value)

    def run_consumers(self):
        for node in self.consumers:
            self.fresh("energy/consumers/%s/p_now" % node.code, round(node.p_inst_kw * 0.5, 1))

    def test_kpis(self):  # AC-122
        self.fixture_grid()
        self.set_phases()
        card = self.card()
        self.assertEqual(card["kpis"]["current"], {"a": 192, "pct": 30, "phases": [188, 195, 193], "rating_a": 630})
        self.assertEqual(card["kpis"]["power"]["kw"], 124)
        self.assertEqual(card["kpis"]["power"]["p_inst_kw"], round(sum(self.consumers.mapped("p_inst_kw"))))
        self.assertEqual(card["kpis"]["power"]["cos_phi"], 0.91)
        self.assertEqual(len(card["chart"]["a"]), 96)
        self.assertEqual(
            (card["chart"]["rating_a"], card["chart"]["warn_a"], card["chart"]["now_slot"]), (630, 504, 57)
        )
        self.assertEqual(card["kpis"]["peak"]["warn_a"], 504)
        self.assertEqual(card["node"]["path"][-1]["code"], "BW-2")
        self.assertEqual([p["code"] for p in card["node"]["path"]][:2], ["SWB-1", "SEC-1"])
        self.assertEqual(card["node"]["kind_label"], "Шинопровід 630 А")

    def test_taps(self):  # AC-123
        self.fixture_grid()
        self.run_consumers()
        by_code = {n.code: n for n in self.consumers}
        cnc4, vsaw = by_code["CNC-4"], by_code["VSAW-1"]
        equipment = self.env["maintenance.equipment"].create({"name": "CNC-4 тест"})
        cnc4.write({"equipment_id": equipment.id})
        self.env["maintenance.request"].create(
            {"name": "CNC-4 · заміна шпинделя", "equipment_id": equipment.id, "maintenance_type": "corrective"}
        )
        self.fresh("energy/consumers/VSAW-1/p_now", 0.3)  # < 5 % від 7,3 кВт
        saw = by_code["SAW-3"]
        wc = self.env["mrp.workcenter"].create({"name": "W1-SAW3", "code": "W1-SAW3"})
        saw.write({"workcenter_id": wc.id})
        product = self.env["product.product"].create({"name": "W1-тест", "is_storable": True, "type": "consu"})
        mo = self.env["mrp.production"].create({"product_id": product.id, "product_qty": 1.0})
        wo = self.env["mrp.workorder"].create(
            {
                "name": "розкрій плит",
                "production_id": mo.id,
                "workcenter_id": wc.id,
                "product_uom_id": mo.product_uom_id.id,
            }
        )
        self.env.cr.execute("UPDATE mrp_workorder SET state = 'progress' WHERE id = %s", (wo.id,))
        wo.invalidate_recordset()
        taps = self.card()["taps"]
        rows = {r["code"]: r for r in taps["rows"]}
        self.assertEqual(len(taps["rows"]), 10)
        self.assertEqual((rows["CNC-4"]["state"], rows["VSAW-1"]["state"]), ("mnt", "idle"))
        self.assertTrue(all(r["state"] == "run" for c, r in rows.items() if c not in ("CNC-4", "VSAW-1")))
        self.assertEqual(rows["SAW-3"]["job"], "%s · розкрій плит" % mo.name)
        self.assertEqual(rows["CNC-4"]["job"], "заявка ТО · CNC-4 · заміна шпинделя")
        self.assertEqual(rows["VSAW-1"]["job"], "немає завдання")
        self.assertEqual(rows["SAW-3"]["tap"], "TAP-SAW-3")
        total = round(sum(r["now_kw"] for r in taps["rows"]), 1)
        self.assertEqual((taps["sum_kw"], taps["aux_kw"], taps["count"]), (total, round(124.0 - total, 1), 10))
        self.assertIs(vsaw.id in self.consumers.ids, True)

    def test_meter_and_verification(self):  # AC-125
        self.fixture_grid()
        meter = self.Meter.search([("code", "=", "PM-QF-2")])
        meter.write({"next_verification": date(2026, 10, 30), "ct_ratio": "630/5"})
        self.env["td.energy.balance"].create(
            {
                "node_id": meter.node_id.id,
                "hour": NOW - timedelta(hours=2),
                "day": NOW.date(),
                "measured_kwh": 98.8,
                "expected_kwh": 100.0,
                "diff_kwh": -1.2,
                "diff_pct": -1.2,
                "state": "ok",
            }  # fmt: skip
        )
        block = self.card()["meter"]
        self.assertEqual(
            (block["code"], block["ct_ratio"], block["next_verification"]), ("PM-QF-2", "630/5", "2026-10-30")
        )
        self.assertEqual(block["balance_pct"], -1.2)
        with self.assertRaises(ValidationError):
            meter.write({"verification_months": 0})
        meter.write({"last_verification": date(2025, 10, 30), "verification_months": 12})
        self.assertEqual(meter.next_verification, date(2026, 10, 30))

    def test_protection_and_trips(self):  # AC-126
        self.fixture_grid()
        qf2 = self.Node.search([("code", "=", "QF-2")])
        qf2.write({"protection_ir_ratio": 0.9, "protection_trip_unit": "електронний"})
        for k in range(2):
            self.Event._td_log(
                "warn", "trip", "QF-2", "Спрацював захист QF-2", ts=NOW - timedelta(days=30 + k), node=qf2
            )
        block = self.card()["protection"]
        self.assertEqual((block["breaker"], block["rating_a"], block["trip_unit"]), ("QF-2", 630, "електронний"))
        self.assertEqual(block["ir"], {"ratio": 0.9, "a": 567})
        self.assertEqual(block["trips_year"], 2)
        # перехід стану автомата в `tripped` створює подію
        self.Event.search([]).unlink()
        real_now = fields.Datetime.now()
        self.env.cr.execute(
            "UPDATE td_signal SET last_text = 'closed', last_ts = %s, status = 'ok' WHERE code = %s",
            (real_now - timedelta(minutes=5), "energy/lines/BW-2/state"),
        )
        self.env["td.signal"].invalidate_model()
        self.env["td.signal"]._td_ingest([{"code": "energy/lines/BW-2/state", "ts": real_now, "text": "tripped"}])
        trip = self.Event.search([("kind", "=", "trip")])
        self.assertEqual(
            (trip.level, trip.state, trip.node_id.code, trip.title), ("warn", "active", "QF-2", "Спрацював захист QF-2")
        )

    def test_events_and_maintenance(self):  # AC-127
        self.fixture_grid()
        node = self.Node.search([("code", "=", "BW-2")])
        stamps = [NOW - timedelta(hours=1), NOW - timedelta(days=1), NOW - timedelta(days=3)] + [
            NOW - timedelta(days=4, hours=k) for k in range(6)
        ]
        for k, ts in enumerate(stamps):
            self.Event._td_log("info", "peak", "SWB-1", "Подія %d. Деталі." % k, ts=ts, node=node)
        equipment = self.env["maintenance.equipment"].create({"name": "ШР-2 обладнання", "td_code": "W1-BW2"})
        self.Node.search([("code", "=", "CNC-4")]).write({"equipment_id": equipment.id})
        request = self.env["maintenance.request"].create({"name": "Перевірка", "equipment_id": equipment.id})
        events = self.card()["events"]
        self.assertEqual(len(events), 6)
        self.assertTrue(any(e["text"].endswith("переведено в ТО") for e in events))
        events_only = [e for e in events if e["kind"] == "peak"]
        self.assertEqual(events_only[0]["time"], "13:20")
        self.assertEqual(events_only[1]["time"], "учора 14:20")
        self.assertEqual(events_only[2]["time"], "14.10 14:20")
        maint = self.card()["maintenance"]
        self.assertEqual([m["id"] for m in maint], [request.id])
        self.assertEqual(maint[0]["title"], "Перевірка")

    def test_energy_without_counter_readings(self):  # R-30: демо-історія (R-36) без показань — сума інтервалів доби
        self.fixture_grid()
        for k in (1, 2):
            self.interval("PM-QF-2", NOW - timedelta(hours=k), 10.0)
        energy = self.card()["kpis"]["energy"]
        self.assertEqual((energy["kwh"], energy["cost_uah"]), (20, 168))

    def test_blocks_by_kind(self):  # AC-128
        self.fixture_grid()
        t1 = self.card("T1")
        self.assertEqual(set(t1["kpis"]), {"current", "power", "energy", "peak"})
        self.assertTrue({"chart", "events", "maintenance", "extra", "outage"} <= set(t1))
        self.assertTrue(not ({"taps", "protection"} & set(t1)) and "idle" not in t1["kpis"])
        self.assertIsNone(t1["outage"])
        consumer = self.card("SAW-3")
        self.assertEqual(set(consumer["kpis"]), {"power", "energy"})
        self.assertEqual(set(consumer) - {"node", "kpis", "events", "maintenance", "extra"}, set())
        full = self.card("BW-2")
        self.assertTrue({"taps", "meter", "protection", "chart", "outage"} <= set(full))
        self.assertEqual(set(self.card("PFC-2")), {"node", "events", "maintenance", "outage", "extra"})
        self.assertEqual(full["extra"], {})

    def test_errors(self):  # AC-129
        with self.assertRaises(UserError) as caught:
            self.card("NOPE")
        self.assertEqual(str(caught.exception), "Невідомий вузол: NOPE.")
        with self.assertRaises(AccessError):
            self.card("BW-2", user=self.u_plain)
        with self.assertRaises(UserError):
            self.Dash.with_user(self.u_view).get_node_card("BW-2", period="week")
