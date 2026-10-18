"""AC-211…AC-216: розклад і план дня (R-54)."""

from datetime import date, timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from ..tools import planner
from .common import NOW, TAGS, TestControlCommon

DAY = date(2026, 10, 17)


@tagged(*TAGS)
class TestSchedule(TestControlCommon):
    def rows(self, day=None):
        return {r["resource"]: r for r in self.ctl(self.u_view).get_schedule(day)["rows"]}

    def test_rows_shape(self):  # AC-211
        res = self.ctl(self.u_view).get_schedule()
        self.assertEqual(
            [r["name"] for r in res["rows"]],
            ["BESS", "КГУ", "Вентиляція RoofVent", "Освітлення цеху", "Зарядна станція", "ДГУ"],
        )
        self.assertAlmostEqual(res["now"], 14.333, places=2)
        for row in res["rows"]:
            froms = [b["from"] for b in row["bars"]]
            self.assertEqual(froms, sorted(froms))
            for bar in row["bars"]:
                self.assertTrue(0 <= bar["from"] < bar["to"] <= 24)
        self.assertEqual(res["day"], "2026-10-17")

    def test_fallback_plan_and_bess_function(self):  # AC-212
        self.Slot.sudo()._td_plan_day(DAY)
        bars = self.rows("2026-10-17")["bess"]["bars"]
        self.assertEqual(
            [(b["from"], b["to"], b["cls"]) for b in bars], [(7.5, 11.0, "d"), (11.0, 16.0, "c"), (16.0, 17.5, "d")]
        )
        cons = [100.0] * 96
        pv = [0.0] * 96
        for i in range(30, 44):  # 07:30–11:00 — високе навантаження
            cons[i] = 900.0
        for i in range(44, 64):  # 11:00–16:00 — надлишок СЕС
            pv[i] = 400.0
        peak = {"limit_kw": 760, "activate_margin_kw": 30, "bess_max_kw": 100}
        got = planner.bess_plan(cons, pv, peak, {"export_max_kw": 20, "bess_max_kw": 100})
        self.assertEqual([(f, t, m) for f, t, m, *_ in got], [(7.5, 11.0, "discharge"), (11.0, 16.0, "charge")])
        self.assertTrue(all(0 <= f < t <= 24 for f, t, *_ in got))

    def test_night_and_chp_bars(self):  # AC-213
        self.Slot.sudo()._td_plan_day(DAY)
        rows = self.rows("2026-10-17")
        self.assertEqual([(b["from"], b["to"], b["label"]) for b in rows["vent"]["bars"]],
                         [(0.0, 6.5, "ніч 30 %"), (6.5, 23.0, "день 100 %"), (23.0, 24.0, "ніч 30 %")])  # fmt: skip
        self.assertEqual([b["label"] for b in rows["light"]["bars"]], ["черговий", "робочий", "черговий"])
        self.assertEqual(rows["chp"]["bars"], [])
        night = self.Scenario.search([("code", "=", "night")])
        night.sudo().with_context(td_energy_control_internal=True).enabled = False
        self.Slot.sudo()._td_plan_day(DAY)
        self.assertEqual([b["label"] for b in self.rows("2026-10-17")["vent"]["bars"]], ["день 100 %"])
        zones = [{"from": 0.0, "to": 7.0, "price": 3.4}, {"from": 7.0, "to": 23.0, "price": 8.4}]
        self.assertEqual(planner.chp_bars(zones, 4.95, 0.5), [(7.0, 23.0, "run", "пуск за ціною")])

    def test_slot_rights(self):  # AC-214
        vals = {
            "resource": "bess",
            "date": DAY,
            "time_from": 18.0,
            "time_to": 19.0,
            "mode": "charge",
            "source": "manual",
        }
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self.Slot.with_user(self.u_chief).create(dict(vals, time_to=17.0))
        with self.assertRaises(AccessError):
            self.Slot.with_user(self.u_en1).create(vals)
        before = self.State.get().config_version
        slot = self.Slot.with_user(self.u_chief).create(vals)
        log = self.Action.search([("kind_code", "=", "schedule_edit")], limit=1)
        self.assertEqual((log.cls, log.state), ("B", "done"))
        self.assertGreater(self.State.get().config_version, before)
        self.assertTrue(slot.executes)
        with self.assertRaises(AccessError):
            slot.with_user(self.u_chief).write({"source": "plan"})

    def test_manual_overrides_plan(self):  # AC-215
        self.Slot.sudo()._td_plan_day(DAY)
        self.Slot.with_user(self.u_chief).create(
            {
                "resource": "bess",
                "date": DAY,
                "time_from": 8.0,
                "time_to": 9.0,
                "mode": "charge",
                "source": "manual",
                "label": "руч.",
            }
        )
        bars = self.rows("2026-10-17")["bess"]["bars"]
        self.assertEqual([(b["from"], b["to"], b["source"]) for b in bars][:3],
                         [(7.5, 8.0, "plan"), (8.0, 9.0, "manual"), (9.0, 11.0, "plan")])  # fmt: skip
        plan = self.Slot.search([("resource", "=", "bess"), ("source", "=", "plan")])
        self.assertFalse(any(plan.mapped("executes")))
        from ..tools import config_builder

        slots = config_builder.build(self.env)["slots"]
        self.assertTrue(all(s["resource"] in ("bess", "chp") for s in slots))
        self.assertIn("руч.", self.Slot.search([("executes", "=", True)]).mapped("label"))

    def test_plan_idempotent(self):  # AC-216
        self.Slot.sudo()._td_plan_day(DAY)
        n1 = self.Slot.search_count([("date", "=", DAY)])
        self.Slot.sudo()._td_plan_day(DAY)
        self.assertEqual(self.Slot.search_count([("date", "=", DAY)]), n1)
        old = (
            self.Slot.sudo()
            .with_context(td_energy_control_internal=True)
            .create(
                {
                    "resource": "bess",
                    "date": DAY - timedelta(days=5),
                    "time_from": 1.0,
                    "time_to": 2.0,
                    "mode": "charge",
                    "source": "plan",
                }
            )
        )
        self.Slot.sudo()._td_plan_all()
        self.assertFalse(old.exists())
        dst = date(2026, 10, 25)  # перехід на зимовий час: доба 25 год — слоти лишаються в 0…24
        self.Slot.sudo()._td_plan_day(dst)
        for rec in self.Slot.search([("date", "=", dst)]):
            self.assertTrue(0 <= rec.time_from < rec.time_to <= 24)
        self.assertGreaterEqual(self.Slot.search_count([]), 10)
        self.assertEqual(NOW.year, 2026)
