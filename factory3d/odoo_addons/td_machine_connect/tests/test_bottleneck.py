"""AC-111…AC-115: вузьке місце заводу (R-30) — чисті функції `tools/bottleneck.py`: показники, вибір, «що якщо»."""

from datetime import datetime

from odoo.tests import BaseCase, tagged

from ..tools import bottleneck as bn

D = (2026, 10, 12)


def at(h, m=0, day=D):
    return datetime(*day, h, m)


def order(oid, mo, seq, station, ready, start, finish, qty=0.0):
    return {
        "id": oid,
        "mo": mo,
        "seq": seq,
        "station": station,
        "ready_at": ready,
        "start_at": start,
        "finish_at": finish,
        "qty": qty,
    }


def stations(a_run=270.0, b_run=60.0):
    return {
        "A": {"name": "Розкрій", "codes": ["A-1"], "machines": 1, "run_min": a_run, "avail_min": 300.0},
        "B": {"name": "Присадка", "codes": ["B-1"], "machines": 1, "run_min": b_run, "avail_min": 300.0},
        "C": {"name": "Порожня", "codes": [], "machines": 0, "run_min": 0.0, "avail_min": 0.0},
    }


# Вікно 02:30–10:00. Маршрут МО: A → B.
ORDERS = [
    order(1, 1, 1, "A", at(0), at(1), at(3), 10.0),  # стартувало до вікна
    order(2, 1, 2, "B", at(3), at(4, 30), at(5, 30), 10.0),  # очікувало 90 хв
    order(3, 2, 1, "A", at(2), at(5), at(6), 20.0),  # чекало на 02:30, стартувало о 05:00
    order(4, 2, 2, "B", at(6), None, None),  # чекає на 10:00 (від 06:00)
    order(5, 3, 1, "A", at(8), None, None),  # чекає на 10:00 (від 08:00)
    order(6, 3, 2, "B", None, None, None),  # попередня операція не завершена
]
T0, T1 = at(2, 30), at(10)


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestBottleneckTools(BaseCase):
    def rows(self, **kw):
        return {r["key"]: r for r in bn.station_rows(stations(**kw), ORDERS, T0, T1)}

    # --- період -----------------------------------------------------------------------------------
    def test_period_window(self):
        now = at(7, 30)
        self.assertEqual(bn.period_window("shift", now), (datetime(2026, 10, 11, 21), now))  # київська доба, EEST
        self.assertEqual(bn.period_window("day", now), (datetime(2026, 10, 11, 7, 30), now))
        self.assertEqual(bn.period_window("week", now), (datetime(2026, 10, 5, 7, 30), now))
        winter = datetime(2026, 12, 10, 12)
        self.assertEqual(bn.period_window("shift", winter)[0], datetime(2026, 12, 9, 22))  # EET
        with self.assertRaises(ValueError):
            bn.period_window("month", now)

    # --- завантаження, черга, очікування, випуск (AC-111…AC-113) ----------------------------------------
    def test_load_and_empty_station_skipped(self):
        rows = self.rows()
        self.assertEqual(set(rows), {"A", "B"})  # «C» без даних і без завдань не потрапляє в рейтинг
        self.assertAlmostEqual(rows["A"]["load"], 0.9)
        self.assertAlmostEqual(rows["B"]["load"], 0.2)

    def test_load_without_available_time_is_none(self):
        st = stations()
        st["A"]["avail_min"] = 0.0
        row = next(r for r in bn.station_rows(st, ORDERS, T0, T1) if r["key"] == "A")
        self.assertIsNone(row["load"])
        self.assertIsNone(row["capacity"])

    def test_queue_is_finished_predecessor_and_not_started(self):
        rows = self.rows()
        self.assertEqual((rows["A"]["queue"], rows["A"]["queue_start"], rows["A"]["queue_delta"]), (1, 1, 0))
        self.assertEqual((rows["B"]["queue"], rows["B"]["queue_start"], rows["B"]["queue_delta"]), (1, 0, 1))
        # №6: попередня операція не завершена — у черзі немає
        self.assertFalse(bn.waiting_at(ORDERS[5], T1))
        # №3 чекало на 02:30, але на 05:00 уже стартувало
        self.assertTrue(bn.waiting_at(ORDERS[2], at(2, 30)))
        self.assertFalse(bn.waiting_at(ORDERS[2], at(5)))

    def test_wait_average(self):
        rows = self.rows()
        self.assertEqual(
            rows["A"]["wait_n"], 2
        )  # №3 (стартувало о 05:00 після 02:00 = 180) і №5 (чекає до 10:00 від 08:00 = 120)
        self.assertAlmostEqual(rows["A"]["wait_min"], 150.0)
        self.assertAlmostEqual(rows["B"]["wait_min"], 165.0)  # №2: 90, №4: 240
        self.assertIsNone(bn.order_wait(ORDERS[0], T0, T1))  # стартувало до вікна
        self.assertIsNone(bn.order_wait(ORDERS[5], T0, T1))  # не готове
        # старт раніше за готовність (шум даних) → 0, а не від'ємне очікування
        self.assertEqual(bn.order_wait(order(9, 9, 1, "A", at(5), at(4), None), at(0), at(10)), 0.0)

    def test_output_is_quantity_finished_in_window(self):
        rows = self.rows()
        self.assertEqual((rows["A"]["output"], rows["A"]["done"]), (30.0, 2))
        self.assertEqual((rows["B"]["output"], rows["B"]["done"]), (10.0, 1))
        self.assertAlmostEqual(rows["A"]["capacity"], 30.0 / 0.9)  # випуск при 100 % завантаженні

    # --- вибір вузького місця (AC-114) ------------------------------------------------------------------
    def test_queue_not_growing_is_queue_verdict(self):
        rows = list(self.rows().values())
        self.assertEqual(bn.find_bottleneck(rows), ("A", "queue"))

    def test_growing_queue_beats_higher_load(self):
        """ТОС: серед ділянок із чергою, що росте, — не просто найбільш завантажена."""
        rows = list(self.rows(b_run=240.0).values())  # B: 0,8 і черга росте (+1); A: 0,9, черга стоїть
        self.assertEqual(bn.find_bottleneck(rows), ("B", "growing"))

    def test_load_only_without_queue(self):
        rows = [{**r, "queue": 0, "queue_delta": 0} for r in self.rows().values()]
        self.assertEqual(bn.find_bottleneck(rows), ("A", "load"))

    def test_low_load_with_queue_is_low_verdict_candidate(self):
        rows = list(self.rows(a_run=90.0, b_run=60.0).values())  # A: 0,3; B: 0,2 — нижче порога 0,5
        self.assertEqual(bn.find_bottleneck(rows), ("A", "low"))

    def test_low_load_without_queue_has_no_bottleneck(self):
        rows = [{**r, "queue": 0, "queue_delta": 0, "load": 0.2} for r in self.rows().values()]
        self.assertEqual(bn.find_bottleneck(rows), (None, None))
        self.assertEqual(bn.find_bottleneck([]), (None, None))

    def test_tie_prefers_bigger_queue_then_key(self):
        base = {"name": "x", "load": 0.8, "queue": 1, "queue_delta": 1}
        rows = [{**base, "key": "b"}, {**base, "key": "a", "queue": 3}, {**base, "key": "c"}]
        self.assertEqual(bn.find_bottleneck(rows), ("a", "growing"))
        rows[1]["queue"] = 1
        self.assertEqual(bn.find_bottleneck(rows), ("a", "growing"))  # рівно: за ключем

    def test_rank_puts_bottleneck_first(self):
        ranked = bn.rank_rows(list(self.rows(b_run=240.0).values()), "B")
        self.assertEqual([(r["rank"], r["key"], r["bottleneck"]) for r in ranked], [(1, "B", True), (2, "A", False)])

    # --- маршрути й «що якщо» (AC-115) -----------------------------------------------------------------------
    def test_build_routes_merges_adjacent_stations(self):
        extra = [
            order(7, 4, 1, "A", None, None, None),
            order(8, 4, 2, "A", None, None, None),
            order(9, 4, 3, "B", None, None, None),
        ]
        routes = bn.build_routes(ORDERS + extra)
        self.assertEqual(routes, [{"stations": ["A", "B"], "orders": 4}])

    def test_what_if_not_capped(self):
        cap = {"A": 100.0, "B": 150.0}
        res = bn.what_if(cap, [{"stations": ["A", "B"], "orders": 2}], "A", 20.0)
        self.assertAlmostEqual(res["gain_pct"], 20.0)
        self.assertEqual((res["next"], res["capped"]), ("B", False))

    def test_what_if_capped_by_next_station(self):
        cap = {"A": 100.0, "B": 110.0}
        res = bn.what_if(cap, [{"stations": ["A", "B"], "orders": 2}], "A", 20.0)
        self.assertAlmostEqual(res["gain_pct"], 10.0)  # далі обмежує B: 110 / 100
        self.assertEqual((res["next"], res["capped"]), ("B", True))

    def test_what_if_zero_gain_when_not_the_limiter(self):
        cap = {"A": 100.0, "B": 50.0}
        res = bn.what_if(cap, [{"stations": ["A", "B"], "orders": 2}], "A", 20.0)
        self.assertAlmostEqual(res["gain_pct"], 0.0)
        self.assertEqual(res["next"], "B")

    def test_line_capacity_shares_station_between_routes(self):
        routes = [{"stations": ["A", "B"], "orders": 3}, {"stations": ["A", "C"], "orders": 1}]
        line = bn.line_capacity({"A": 100.0, "B": 60.0, "C": 10.0}, routes)
        self.assertEqual([r["limiter"] for r in line["routes"]], ["B", "C"])
        self.assertAlmostEqual(line["total"], 60.0 + 10.0)
        res = bn.what_if({"A": 100.0, "B": 60.0, "C": 10.0}, routes, "C", 100.0)
        self.assertAlmostEqual(res["gain_pct"], 10.0 / 70.0 * 100)  # C: 10 → 20 на маршруті з 25 від A
        self.assertEqual((res["next"], res["capped"]), ("A", False))

    def test_stations_without_capacity_do_not_limit(self):
        line = bn.line_capacity({"A": 100.0, "B": None}, [{"stations": ["A", "B"], "orders": 1}])
        self.assertEqual((line["total"], line["routes"][0]["limiter"]), (100.0, "A"))
        self.assertIsNone(bn.what_if({"A": None}, [{"stations": ["A"], "orders": 1}], "A", 20.0))
        self.assertIsNone(bn.what_if({"A": 5.0}, [], "A", 20.0))

    def test_hint_text_and_number_format(self):
        names = {"A": "Розкрій", "B": "Присадка"}
        res = {"station": "A", "boost_pct": 20.0, "gain_pct": 13.46, "next": "B"}
        self.assertEqual(
            bn.hint_text(res, names), "+20 % потужності на Розкрій → +13,5 % випуску, далі обмежує Присадка"
        )
        self.assertEqual(
            bn.hint_text({**res, "next": None, "gain_pct": 20.0}, names).split("→")[1],
            " +20 % випуску, інших обмежень у даних немає",
        )
        self.assertEqual(bn.hint_text(None, names), "")
        self.assertEqual([bn.fmt_num(x) for x in (14.0, 14.26, 0.0, -0.04, 100)], ["14", "14,3", "0", "0", "100"])

    def test_main_upstream(self):
        routes = [
            {"stations": ["S", "A", "B"], "orders": 1},
            {"stations": ["T", "A"], "orders": 3},
            {"stations": ["A", "B"], "orders": 2},
        ]
        self.assertEqual(bn.main_upstream(routes, "A"), "T")
        self.assertEqual(bn.main_upstream(routes, "B"), "A")
        self.assertIsNone(bn.main_upstream(routes, "S"))

    # --- повний розрахунок -------------------------------------------------------------------------------
    def test_analyze_end_to_end(self):
        res = bn.analyze(stations(), ORDERS, T0, T1, boost_pct=20.0)
        self.assertEqual((res["bottleneck"], res["verdict"]), ("A", "queue"))
        self.assertEqual([r["key"] for r in res["rows"]], ["A", "B"])
        self.assertEqual(res["routes"], [{"stations": ["A", "B"], "orders": 3}])
        # потужність A = 30 / 0,9 = 33,3; B = 10 / 0,2 = 50: +20 % на A → 40, далі обмежує B не раніше 50
        self.assertAlmostEqual(res["what_if"]["gain_pct"], 20.0)
        self.assertEqual(res["hint"], "+20 % потужності на Розкрій → +20 % випуску, далі обмежує Присадка")
        self.assertEqual(res["upstream"], None)  # Розкрій завжди перший
        no_data = bn.analyze({}, [], T0, T1)
        self.assertEqual((no_data["bottleneck"], no_data["rows"], no_data["hint"]), (None, [], ""))
