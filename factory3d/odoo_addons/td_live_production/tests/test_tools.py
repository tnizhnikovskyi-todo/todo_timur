"""Юніт-тести чистих функцій `tools/` (без ORM): календар зміни, шум, планувальник, диспетчер, ціни, тариф."""

from datetime import date, datetime, timedelta

from odoo.tests import BaseCase, tagged

from ..tools import clock, dispatch, noise, planner, pricing, tariff

SHIFT = (7.0, 15.5)
D = date(2026, 10, 21)  # середа, київський літній час (UTC+3)
T0 = datetime(2026, 10, 21, 4, 0)  # 07:00 Київ


def mins(n):
    return timedelta(minutes=n)


@tagged("post_install", "-at_install", "td_live")
class TestClock(BaseCase):
    def test_shift_window_kyiv(self):
        self.assertEqual(clock.shift_window(D, SHIFT), (datetime(2026, 10, 21, 4, 0), datetime(2026, 10, 21, 12, 30)))

    def test_next_shift_start(self):
        inside = datetime(2026, 10, 21, 6, 0)
        self.assertEqual(clock.next_shift_start(inside, SHIFT), inside)
        after = datetime(2026, 10, 21, 13, 0)  # 16:00 Київ
        self.assertEqual(clock.next_shift_start(after, SHIFT), datetime(2026, 10, 22, 4, 0))
        before = datetime(2026, 10, 21, 1, 0)
        self.assertEqual(clock.next_shift_start(before, SHIFT), T0)

    def test_workdays_skip_weekend(self):
        friday_evening = datetime(2026, 10, 23, 13, 0)
        # 25.10 переведення годинника: у понеділок 07:00 Київ уже UTC+2
        self.assertEqual(clock.next_shift_start(friday_evening, SHIFT, "01234"), datetime(2026, 10, 26, 5, 0))
        with self.assertRaises(ValueError):
            clock.next_shift_start(friday_evening, SHIFT, "")

    def test_place_fits_or_moves_to_next_shift(self):
        self.assertEqual(clock.place(T0, 60, SHIFT), (T0, T0 + mins(60)))
        late = datetime(2026, 10, 21, 11, 45)  # лишилось 45 хв
        self.assertEqual(clock.place(late, 60, SHIFT), (datetime(2026, 10, 22, 4, 0), datetime(2026, 10, 22, 5, 0)))

    def test_place_longer_than_shift_starts_at_window_start(self):
        start, end = clock.place(T0, 600, SHIFT)
        self.assertEqual((start, end - start), (T0, mins(600)))

    def test_local_date_uses_kyiv(self):
        self.assertEqual(clock.local_date(datetime(2026, 10, 20, 22, 30)), D)  # 01:30 Київ


@tagged("post_install", "-at_install", "td_live")
class TestNoise(BaseCase):
    def test_deterministic_and_bounded(self):
        for i in range(200):
            a = noise.noisy_minutes(100.0, "wo%s" % i)
            self.assertEqual(a, noise.noisy_minutes(100.0, "wo%s" % i))
            self.assertTrue(85.0 <= a <= 115.0, a)
        self.assertNotEqual(noise.noisy_minutes(100.0, "wo1"), noise.noisy_minutes(100.0, "wo2"))

    def test_both_directions(self):
        values = [noise.noisy_minutes(100.0, "k%s" % i) for i in range(100)]
        self.assertTrue(min(values) < 95 and max(values) > 105)


def templates():
    """Дві лінії виробу: A (CNC-1) і B (CNC-2); 10, 20 — верстати розкрою й присадки, 30 — збирання."""
    ops_a = [
        {"wc": 10, "setup": 15, "cycle": 2.2},
        {"wc": 20, "setup": 15, "cycle": 2.0},
        {"wc": 30, "setup": 15, "cycle": 6},
    ]
    ops_b = [
        {"wc": 11, "setup": 15, "cycle": 2.2},
        {"wc": 21, "setup": 15, "cycle": 2.0},
        {"wc": 31, "setup": 15, "cycle": 6},
    ]
    return {
        "customers": [1, 2, 3],
        "products": [
            {"id": 100, "qtys": [10, 20], "variants": [{"bom_id": 1, "ops": ops_a}, {"bom_id": 2, "ops": ops_b}]},
            {"id": 101, "qtys": [], "variants": [{"bom_id": 3, "ops": ops_a}, {"bom_id": 4, "ops": ops_b}]},
        ],
    }


@tagged("post_install", "-at_install", "td_live")
class TestPlanner(BaseCase):
    def test_plan_orders_deterministic(self):
        a = planner.plan_orders(templates(), 8, 20261021, 510.0, {20, 21}, 1.5, 2.5, (2, 3))
        b = planner.plan_orders(templates(), 8, 20261021, 510.0, {20, 21}, 1.5, 2.5, (2, 3))
        c = planner.plan_orders(templates(), 8, 20261022, 510.0, {20, 21}, 1.5, 2.5, (2, 3))
        self.assertEqual(a, b)
        self.assertNotEqual(a["orders"], c["orders"])
        self.assertEqual(len(a["orders"]), 8)
        for order in a["orders"]:
            self.assertIn(len(order["lines"]), (2, 3))

    def test_hot_section_gets_more_load_than_cold(self):
        res = planner.plan_orders(templates(), 8, 7, 510.0, {20, 21}, 1.5, 2.5, (2, 3))
        hot = sum(m for wc, m in res["load"].items() if wc in (20, 21))
        cold_same_op = sum(m for wc, m in res["load"].items() if wc in (10, 11))
        self.assertGreater(hot, cold_same_op * 1.5)

    def test_no_templates_no_orders(self):
        self.assertEqual(planner.plan_orders({"customers": [], "products": []}, 8, 1, 510.0)["orders"], [])

    def test_schedule_finite_capacity(self):
        mos = [
            {
                "id": i,
                "release": T0,
                "ops": [{"id": i * 10 + k, "wc": wc, "minutes": 60.0} for k, wc in enumerate((1, 2))],
            }
            for i in range(1, 5)
        ]
        plan = planner.schedule(mos, SHIFT, "0123456")
        for wc_ops in ((10, 20, 30, 40), (11, 21, 31, 41)):
            spans = sorted(plan[o] for o in wc_ops)
            for (_s1, e1), (s2, _e2) in zip(spans, spans[1:], strict=False):
                self.assertLessEqual(e1, s2)  # один наряд за раз
        for i in range(1, 5):
            self.assertLessEqual(plan[i * 10][1], plan[i * 10 + 1][0])  # наряди МО послідовно

    def test_schedule_spills_to_next_shift(self):
        mos = [{"id": i, "release": T0, "ops": [{"id": i, "wc": 1, "minutes": 200.0}]} for i in range(1, 5)]
        plan = planner.schedule(mos, SHIFT, "0123456")
        self.assertEqual(plan[3][0], datetime(2026, 10, 22, 4, 0))  # третій не вмістився у 510 хв
        self.assertGreater(planner.spill_minutes(plan, datetime(2026, 10, 21, 12, 30)), 0)

    def test_wc_free_carries_over(self):
        mos = [{"id": 1, "release": T0, "ops": [{"id": 1, "wc": 1, "minutes": 30.0}]}]
        plan = planner.schedule(mos, SHIFT, "0123456", {1: T0 + mins(90)})
        self.assertEqual(plan[1][0], T0 + mins(90))

    def test_downtimes(self):
        wc_ops = {wc: [(T0 + mins(60 * k), T0 + mins(60 * k + 50)) for k in range(6)] for wc in range(1, 21)}
        res = planner.plan_downtimes(wc_ops, 0.06, 20261021)
        self.assertEqual(res, planner.plan_downtimes(wc_ops, 0.06, 20261021))
        self.assertTrue(res)
        self.assertLessEqual(sum(d["kind"] == "fault" for d in res), planner.MAX_FAULTS)
        for d in res:
            self.assertGreaterEqual(d["minutes"], 3)  # C-LP-01: простій не коротший за 3 хв
            self.assertIn(d["reason"], planner.REASON_LABELS)
            self.assertIn(d["start"], [e for _s, e in wc_ops[d["wc"]]])
        share = sum(d["minutes"] for d in res) / sum(
            (e - s).total_seconds() / 60 for o in wc_ops.values() for s, e in o
        )
        self.assertTrue(0.02 < share < 0.15, share)

    def test_downtimes_empty(self):
        self.assertEqual(planner.plan_downtimes({}, 0.06, 1), [])
        self.assertEqual(planner.plan_downtimes({1: [(T0, T0 + mins(10))]}, 0.0, 1), [])

    def test_faults_capped_even_if_only_faults(self):
        only_fault = (("fault", "fault", 1.0, 25, 70), ("setup", "setup", 0.0001, 10, 10))
        wc_ops = {wc: [(T0, T0 + mins(50))] for wc in range(1, 30)}
        res = planner.plan_downtimes(wc_ops, 0.5, 5, only_fault)
        self.assertLessEqual(sum(d["kind"] == "fault" for d in res), planner.MAX_FAULTS)


def chain_state(minutes=60.0):
    """Одна МО з двома нарядами на різних верстатах; друга МО займає той самий перший верстат."""
    wos = {
        1: {"mo": 1, "wc": 1, "state": "ready", "plan_start": T0, "minutes": minutes, "start": None, "end": None},
        2: {
            "mo": 1,
            "wc": 2,
            "state": "blocked",
            "plan_start": T0 + mins(60),
            "minutes": minutes,
            "start": None,
            "end": None,
        },
        3: {
            "mo": 2,
            "wc": 1,
            "state": "ready",
            "plan_start": T0 + mins(10),
            "minutes": minutes,
            "start": None,
            "end": None,
        },
    }
    mos = {1: {"wos": [1, 2], "so": 1, "done_at": None}, 2: {"wos": [3], "so": 2, "done_at": None}}
    sos = {1: {"mos": [1], "shipped": False}, 2: {"mos": [2], "shipped": False}}
    return {"wos": wos, "mos": mos, "sos": sos, "dts": {}}


@tagged("post_install", "-at_install", "td_live")
class TestDispatch(BaseCase):
    def run_sim(self, state, now):
        return dispatch.simulate(state, now, SHIFT, "0123456")

    def test_nothing_before_plan(self):
        events, _after = self.run_sim(chain_state(), T0 - mins(1))
        self.assertEqual(events, [])

    def test_start_when_planned_and_free(self):
        events, after = self.run_sim(chain_state(), T0 + mins(5))
        self.assertEqual([(e["kind"], e["id"]) for e in events], [("wo_start", 1)])
        self.assertEqual(after["wos"][1]["start"], T0)
        self.assertEqual(after["wos"][1]["state"], "progress")

    def test_one_work_order_per_work_center(self):
        _events, after = self.run_sim(chain_state(), T0 + mins(30))
        self.assertEqual(after["wos"][3]["state"], "ready")  # верстат 1 зайнятий нарядом 1

    def test_idempotent_second_tick_same_events_none(self):
        now = T0 + mins(20)
        events, after = self.run_sim(chain_state(), now)
        again, _ = self.run_sim(after, now)
        self.assertTrue(events)
        self.assertEqual(again, [])

    def test_catchup_full_chronology_then_mo_done_and_ship(self):
        events, after = self.run_sim(chain_state(), T0 + mins(600))
        kinds = [e["kind"] for e in events]
        self.assertEqual(kinds.count("wo_start"), 3)
        self.assertEqual(kinds.count("wo_finish"), 3)
        self.assertEqual(kinds.count("mo_done"), 2)
        self.assertEqual(kinds.count("ship"), 2)
        times = [e["t"] for e in events]
        self.assertEqual(times, sorted(times))
        self.assertTrue(all(s["shipped"] for s in after["sos"].values()))
        # наряд 2 починається не раніше за кінець наряду 1 і за свій плановий початок
        self.assertGreaterEqual(after["wos"][2]["start"], max(after["wos"][1]["end"], T0 + mins(60)))
        # нульова дельта на рівному місці: наступний тик нічого не змінює
        self.assertEqual(self.run_sim(after, T0 + mins(600))[0], [])

    def test_mo_with_all_work_orders_done_gets_mo_done_and_ship(self):
        """Порція такту скінчилась між останнім `wo_finish` і `mo_done`: МО «до закриття» не лишається назавжди."""
        state = chain_state()
        state["wos"][1].update(state="done", start=T0, end=T0 + mins(60))
        state["wos"][2].update(state="done", start=T0 + mins(60), end=T0 + mins(120))
        events, after = self.run_sim(state, T0 + mins(300))
        self.assertEqual((events[0]["kind"], events[0]["id"], events[0]["t"]), ("mo_done", 1, T0 + mins(120)))
        self.assertEqual([e["kind"] for e in events].count("mo_done"), 2)  # друга МО добігає за звичайним ланцюгом
        self.assertIn(("ship", 1), [(e["kind"], e["id"]) for e in events])
        self.assertEqual(self.run_sim(after, T0 + mins(300))[0], [])  # повтор нічого не додає
        events, _ = self.run_sim(state, T0 + mins(100))  # час закриття ще не настав
        self.assertNotIn(("mo_done", 1), [(e["kind"], e["id"]) for e in events])

    def test_actual_duration_within_noise(self):
        _e, after = self.run_sim(chain_state(100.0), T0 + mins(1000))
        for wo in after["wos"].values():
            real = (wo["end"] - wo["start"]).total_seconds() / 60
            self.assertTrue(85.0 <= real <= 115.0, real)

    def test_started_elsewhere_is_adopted_not_restarted(self):
        state = chain_state()
        state["wos"][1].update(state="progress", start=T0 + mins(2))  # запустив автостарт верстата
        events, _after = self.run_sim(state, T0 + mins(3))
        self.assertEqual(events, [])  # ні другого старту, ні зайвого завершення

    def test_start_snaps_to_shift(self):
        state = chain_state()
        state["wos"][1]["plan_start"] = datetime(2026, 10, 21, 13, 0)  # 16:00 Київ: зміна скінчилась
        events, _ = self.run_sim(state, datetime(2026, 10, 22, 5, 0))
        first = next(e for e in events if e["kind"] == "wo_start" and e["id"] == 1)
        self.assertEqual(first["t"], datetime(2026, 10, 22, 4, 0))

    def test_downtime_waits_for_busy_machine_and_blocks_it(self):
        state = chain_state(30.0)
        state["dts"] = {
            1: {
                "wc": 1,
                "plan_start": T0 + mins(5),
                "minutes": 20.0,
                "kind": "idle",
                "reason": "Налагодження",
                "state": "planned",
                "start": None,
                "end": None,
            }
        }
        events, after = self.run_sim(state, T0 + mins(400))
        by = {(e["kind"], e["id"]): e["t"] for e in events}
        self.assertGreaterEqual(by[("dt_start", 1)], by[("wo_finish", 1)])  # простій після наряду, не посеред
        self.assertEqual(by[("dt_end", 1)] - by[("dt_start", 1)], mins(20))
        self.assertGreaterEqual(by[("wo_start", 3)], by[("dt_end", 1)])  # наступний наряд верстата — після простою
        self.assertEqual(after["dts"][1]["state"], "done")

    def test_machine_targets(self):
        state = chain_state()
        now = T0 + mins(5)
        _e, after = self.run_sim(state, now)
        targets = dispatch.machine_targets(after, now)
        self.assertEqual(len(targets), 1)
        target = targets[0]
        self.assertEqual((target["wc"], target["state"], target["reason"]), (1, "working", None))
        end = T0 + mins(dispatch.actual_minutes(1, 60.0))
        self.assertEqual(target["until"], min(end + mins(dispatch.TARGET_PAD_MIN), now + mins(dispatch.HORIZON_MIN)))

    def test_machine_targets_downtime_kinds(self):
        after = chain_state()
        after["dts"] = {
            1: {
                "wc": 5,
                "plan_start": T0,
                "minutes": 30.0,
                "kind": "setup",
                "reason": "Налагодження",
                "state": "active",
                "start": T0,
                "end": None,
            },
            2: {
                "wc": 6,
                "plan_start": T0,
                "minutes": 40.0,
                "kind": "fault",
                "reason": "Поломка",
                "state": "active",
                "start": T0,
                "end": None,
            },
        }
        now = T0 + mins(10)
        got = {t["wc"]: t for t in dispatch.machine_targets(after, now)}
        self.assertEqual((got[5]["state"], got[5]["reason"]), ("idle", "Налагодження"))  # наладка — не аварія
        self.assertEqual((got[6]["state"], got[6]["reason"]), ("down", "Поломка"))
        self.assertEqual(got[5]["until"], now + mins(dispatch.HORIZON_MIN))  # кінець за 30 хв, але не далі 15 хв

    def test_targets_for_every_machine(self):
        """35 верстатів, 3 активні наряди: 35 цілей, 3 `working` і 32 `idle` «Немає завдання»."""
        state = {"wos": {}, "mos": {}, "sos": {}, "dts": {}}
        for wc in (1, 2, 3):
            state["wos"][wc] = {
                "mo": wc,
                "wc": wc,
                "state": "progress",
                "plan_start": None,
                "minutes": 60.0,
                "start": T0,
                "end": None,
            }
            state["mos"][wc] = {"wos": [wc], "so": None, "done_at": None}
        now = T0 + mins(5)
        targets = dispatch.machine_targets(state, now, machines=list(range(1, 36)), shift=SHIFT)
        self.assertEqual(len(targets), 35)
        working = [t for t in targets if t["state"] == "working"]
        idle = [t for t in targets if t["state"] == "idle"]
        self.assertEqual((len(working), len(idle)), (3, 32))
        self.assertEqual({t["reason"] for t in idle}, {dispatch.IDLE_REASON})
        self.assertTrue(all(now < t["until"] <= now + mins(dispatch.HORIZON_MIN) for t in targets))
        # без `machines` — старий режим: лише зайняті
        self.assertEqual(len(dispatch.machine_targets(state, now)), 3)

    def test_targets_off_shift_and_next_change(self):
        state = {"wos": {}, "mos": {}, "sos": {}, "dts": {}}
        night = datetime(2026, 10, 21, 13, 0)  # 16:00 Київ: зміна скінчилась
        off = dispatch.machine_targets(state, night, machines=[1, 2], shift=SHIFT)
        self.assertEqual({t["reason"] for t in off}, {dispatch.OFF_REASON})
        self.assertTrue(all(t["state"] == "idle" for t in off))
        # у зміні: найближча зміна — плановий старт наряду цього верстата (+2 хв запасу), а не 15 хв
        state["wos"][7] = {
            "mo": 7,
            "wc": 20,
            "state": "ready",
            "plan_start": T0 + mins(8),
            "minutes": 30.0,
            "start": None,
            "end": None,
        }
        state["mos"][7] = {"wos": [7], "so": None, "done_at": None}
        got = {t["wc"]: t for t in dispatch.machine_targets(state, T0 + mins(1), machines=[20, 21], shift=SHIFT)}
        self.assertEqual(got[20]["until"], T0 + mins(8 + dispatch.TARGET_PAD_MIN))
        self.assertEqual(got[21]["until"], T0 + mins(1 + dispatch.HORIZON_MIN))
        self.assertEqual(got[20]["reason"], dispatch.IDLE_REASON)

    def test_targets_follow_work_center_calendar(self):
        """«Поза зміною» — за календарем РЦ (обід, вихідні), а не за глобальною зміною; `until` — межа календаря."""
        state = {"wos": {}, "mos": {}, "sos": {}, "dts": {}}
        calendar = {1: [(T0, T0 + mins(270)), (T0 + mins(300), T0 + mins(510))], 2: []}  # 2 — вихідний: плану немає
        got = {
            t["wc"]: t
            for t in dispatch.machine_targets(state, T0 + mins(100), machines=[1, 2], shift=SHIFT, calendar=calendar)
        }
        self.assertEqual((got[1]["kind"], got[1]["reason"]), ("no_task", dispatch.IDLE_REASON))
        self.assertEqual(got[1]["until"], T0 + mins(100 + dispatch.HORIZON_MIN))  # межа далеко: до 15 хв
        self.assertEqual((got[2]["kind"], got[2]["reason"]), ("off", dispatch.OFF_REASON))
        lunch = {
            t["wc"]: t
            for t in dispatch.machine_targets(state, T0 + mins(290), machines=[1], shift=SHIFT, calendar=calendar)
        }
        self.assertEqual((lunch[1]["kind"], lunch[1]["reason"]), ("off", dispatch.OFF_REASON))
        self.assertEqual(lunch[1]["until"], T0 + mins(300 + dispatch.TARGET_PAD_MIN))  # обід закінчується о 12:00
        near = dispatch.machine_targets(state, T0 + mins(265), machines=[1], shift=SHIFT, calendar=calendar)[0]
        self.assertEqual(near["until"], T0 + mins(270 + dispatch.TARGET_PAD_MIN))  # до обіду 5 хв

    def test_catchup_chain(self):
        wos = [
            {"id": 1, "state": "progress", "start": T0, "plan_start": T0, "plan_end": T0 + mins(60), "minutes": 60},
            {
                "id": 2,
                "state": "blocked",
                "start": None,
                "plan_start": T0 + mins(30),
                "plan_end": T0 + mins(40),
                "minutes": 5,
            },
            {"id": 3, "state": "blocked", "start": None, "plan_start": None, "plan_end": None, "minutes": 15},
        ]
        chain = dispatch.catchup_chain(wos, None)
        self.assertEqual(chain[0], (1, T0, T0 + mins(60)))
        self.assertEqual(chain[1], (2, T0 + mins(60), T0 + mins(65)))  # не раніше кінця попереднього
        self.assertEqual(chain[2], (3, T0 + mins(65), T0 + mins(80)))  # без плану — тривалість


@tagged("post_install", "-at_install", "td_live")
class TestPricingTariff(BaseCase):
    def test_order_price_margin_band(self):
        for i in range(300):
            cost = 1000.0 + 37 * i
            price = pricing.order_price(cost * 1.5, cost, "k%s" % i)
            m = pricing.margin_pct(price, cost)
            self.assertTrue(25.0 <= m <= 40.0, (cost, price, m))

    def test_order_price_without_cost_is_list_price_range(self):
        price = pricing.order_price(6400.0, 0.0, "x")
        self.assertTrue(6000 <= price <= 7000)

    def test_guess_cost(self):
        self.assertEqual(pricing.guess_unit_cost("DSP16-SON"), 2050.0)
        self.assertEqual(pricing.guess_unit_cost("EB2-WHT"), 34.0)
        self.assertEqual(pricing.guess_unit_cost("NEW-1", "Фурнітура"), 90.0)
        self.assertEqual(pricing.guess_unit_cost("NEW-1", ""), pricing.COST_DEFAULT)

    def test_tariff_zones(self):
        rows = tariff.zone_rows(8.4)
        self.assertTrue(tariff.covers_day(rows))
        price = {r["code"]: r["price"] for r in rows}
        self.assertEqual((price["night"], price["half_peak"], price["peak"]), (4.2, 8.4, 12.6))
        self.assertFalse(tariff.covers_day(rows[1:]))
