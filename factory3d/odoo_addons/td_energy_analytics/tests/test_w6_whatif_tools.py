"""Вау №6 (R-23): чисті функції `tools/whatif.py` — тариф, вікно, зсув, номінал, вартість, пік, сценарій (AC-73)."""

import ast
import inspect
from datetime import date

from odoo.tests import BaseCase, tagged

from odoo.addons.td_energy_analytics.tools import whatif

from .common import TAGS

SL = whatif.SLOTS
FIRST = date(2026, 9, 28)  # понеділок
N = 14
ALL = "0123456"


def zones(night=3.0, day=6.0):
    """Ніч 23:00–07:00 і день 07:00–23:00 на всі дні тижня."""
    return [
        whatif.Zone("Ніч", "night", night, ALL, 23.0, 7.0, 10),
        whatif.Zone("День", "day", day, ALL, 7.0, 23.0, 20),
    ]


def flat(value, n=N):
    return [value] * (n * SL)


def window_load(kwh, start=32, length=32, n=N):
    """Навантаження вузла: `kwh` за слот у вікні `[start, start + length)` кожної доби."""
    series = [0.0] * (n * SL)
    for d in range(n):
        for j in range(length):
            series[d * SL + start + j] = kwh
    return series


def params(**over):
    node_load = window_load(2.0)  # 8 кВт у вікні 08:00–16:00
    net = [a + b for a, b in zip(flat(25.0), node_load, strict=True)]  # 100 кВт фону + вузол
    p = {
        "first_day": FIRST, "n_days": N, "net": net, "data_ok": [True] * N,
        "nodes": [{"code": "SAW-1", "name": "Розкрій 1", "kwh": node_load, "cap_kw": None}],
        "zones": zones(), "export_price": 0.0, "capacity_price": 0.0, "contract_kw": 200.0, "warn_pct": 90.0,
        "window": (8.0, 16.0), "mode": "night", "shift_h": 2.0, "share": 1.0, "days": "work", "respect_rating": True,
        "scope_text": "ділянці «Розкрій»",
    }  # fmt: skip
    p.update(over)
    return p


@tagged(*TAGS)
class TestW6WhatIfTools(BaseCase):
    # --- тариф ----------------------------------------------------------------------------------------
    def test_price_table_and_night(self):
        table = whatif.price_table(zones())
        self.assertEqual([z.code for z in table["zones"]], ["night", "day"])
        self.assertEqual(table["price"][2][0], 3.0)  # 00:00
        self.assertEqual(table["price"][2][28], 6.0)  # 07:00
        self.assertEqual(table["price"][2][91], 6.0)  # 22:45
        self.assertEqual(table["price"][2][92], 3.0)  # 23:00
        self.assertEqual(whatif.night_zone_indexes(table["zones"]), {0})

    def test_night_zone_rules(self):
        flat_zone = [whatif.Zone("Цілодобова", "flat", 8.4, ALL, 0.0, 24.0, 10)]
        self.assertEqual(whatif.night_zone_indexes(flat_zone), set())  # одна зона — різниці цін немає
        same = [whatif.Zone("A", "night", 5.0, "01234", 0.0, 24.0, 1), whatif.Zone("B", "day", 5.0, "56", 0.0, 24.0, 2)]
        self.assertEqual(whatif.night_zone_indexes(same), set())  # однакові ціни — не нічна зона
        no_code = [
            whatif.Zone("Дешева", "day", 4.0, ALL, 0.0, 6.0, 1),
            whatif.Zone("Середня", "day", 6.0, ALL, 6.0, 20.0, 2),
            whatif.Zone("Дорога", "peak", 9.0, ALL, 20.0, 24.0, 3),
        ]
        self.assertEqual(whatif.night_zone_indexes(no_code), {0})  # без коду — найдешевша

    def test_uncovered_quarter(self):
        part = [whatif.Zone("День", "day", 6.0, "01234", 8.0, 20.0, 1)]
        table = whatif.price_table(part)
        self.assertEqual(table["zone"][0][0], -1)
        self.assertEqual(table["price"][0][0], 0.0)
        self.assertEqual(table["zone"][5][40], -1)  # субота

    # --- вікно й зсув ---------------------------------------------------------------------------------
    def test_window_slots(self):
        self.assertEqual(whatif.window_slots(8, 16), (32, 32))
        self.assertEqual(whatif.window_slots(22, 6), (88, 32))  # через північ
        self.assertEqual(whatif.window_slots(0, 24), (0, 96))
        self.assertEqual(whatif.window_slots(8.25, 9), (33, 3))

    def test_night_shift(self):
        table = whatif.price_table(zones())
        night = whatif.night_zone_indexes(table["zones"])
        self.assertEqual(whatif.night_shift(table, night, 0, 32), 60)  # 08:00 → 23:00
        self.assertEqual(whatif.night_shift(table, night, 0, 92), 0)  # вікно вже в ночі
        self.assertEqual(whatif.night_shift(table, night, 3, 80), 12)  # 20:00 → 23:00
        only_weekend = [
            whatif.Zone("Ніч", "night", 3.0, "5", 0.0, 24.0, 1),
            whatif.Zone("Д", "day", 6.0, "0123", 0.0, 24.0, 2),
        ]
        table = whatif.price_table(only_weekend)
        # ніч — лише субота: від пн 08:00 до сб 00:00 — 5 діб − 8 год
        self.assertEqual(whatif.night_shift(table, {0}, 0, 32), 5 * SL - 32)

    def test_plan_moves_days_and_cycle(self):
        # 3 доби, вікно 20:00–24:00, зсув +2 год; середа не переноситься; ціль останньої доби — на початок ряду
        pairs = whatif.plan_moves(3, (80, 16), [True, False, True], 8)
        self.assertEqual(len(pairs), 32)
        self.assertEqual(pairs[0], (80, 88))
        self.assertIn((2 * SL + 95, 2 * SL + 95 + 8 - 3 * SL), pairs)  # ціль останньої доби — на початок ряду
        # доби без повних даних не беруть участі ні як джерело, ні як ціль
        pairs = whatif.plan_moves(3, (80, 16), [True, True, True], 8, valid=[True, False, True])
        self.assertTrue(all(s // SL != 1 and t // SL != 1 for s, t in pairs))
        # нульовий зсув — перенесення немає
        self.assertEqual(whatif.plan_moves(3, (80, 16), [True] * 3, 0), [])

    def test_plan_moves_window_across_midnight(self):
        pairs = whatif.plan_moves(2, (88, 32), [True, True], 4)  # 22:00–06:00
        sources = {s for s, _t in pairs}
        self.assertIn(88, sources)
        self.assertNotIn(2 * SL, sources)  # друга доба: слот 2·96 — поза рядом
        self.assertTrue(all(s < 2 * SL for s in sources))

    # --- перенос ---------------------------------------------------------------------------------------
    def test_apply_moves_conserves_energy_and_share(self):
        base = window_load(2.0, n=3)
        pairs = whatif.plan_moves(3, (32, 32), [True, True, True], 60)
        new, flows, blocked = whatif.apply_moves(base, pairs, 0.5)
        self.assertAlmostEqual(sum(new), sum(base), places=6)
        self.assertAlmostEqual(sum(a for _s, _t, a in flows), 0.5 * sum(base), places=6)
        self.assertEqual(blocked, 0.0)
        self.assertAlmostEqual(new[32], 1.0)  # половина лишилась на місці
        self.assertAlmostEqual(new[92], 1.0)  # і половина прийшла вночі

    def test_apply_moves_overlapping_shift(self):
        # вікно 4 слоти, зсув +2: ланцюжок — слот 2 віддає у 4, слот 0 у 2; підсумок зберігає енергію
        base = [4.0, 3.0, 2.0, 1.0, 0.0, 0.0, 0.0, 0.0]
        new, flows, _blocked = whatif.apply_moves(base, [(0, 2), (1, 3), (2, 4), (3, 5)], 1.0)
        self.assertEqual(new, [0.0, 0.0, 4.0, 3.0, 2.0, 1.0, 0.0, 0.0])
        self.assertAlmostEqual(sum(a for *_x, a in flows), 10.0)

    def test_apply_moves_respects_rating(self):
        # номінал 3 кВт·год за слот: у ціль 2 (вже 2) влізає лише 1 з 2
        base = [2.0, 0.0, 2.0, 0.0]
        new, flows, blocked = whatif.apply_moves(base, [(0, 2)], 1.0, cap=3.0)
        self.assertEqual(new, [1.0, 0.0, 3.0, 0.0])
        self.assertAlmostEqual(blocked, 1.0)
        self.assertEqual([round(a, 6) for *_x, a in flows], [1.0])
        # без номінала переноситься все
        new, _flows, blocked = whatif.apply_moves(base, [(0, 2)], 1.0)
        self.assertEqual(new, [0.0, 0.0, 4.0, 0.0])
        self.assertEqual(blocked, 0.0)

    def test_aggregates(self):
        net = [4.0, -1.0, 2.0, 0.0]
        price = [10.0, 10.0, 5.0, 5.0]
        self.assertAlmostEqual(whatif.energy_cost(net, price), 4 * 10 + 2 * 5)
        self.assertAlmostEqual(whatif.energy_cost(net, price, export_price=3.0), 50 - 3.0)  # віддача — кредит
        self.assertAlmostEqual(whatif.energy_cost(net, price, mask=[True, True, False, False]), 40.0)
        self.assertEqual(whatif.peak(net), (16.0, 0))
        self.assertEqual(whatif.peak([-1.0, 0.0]), (0.0, None))
        self.assertEqual(whatif.zone_energy(net, [0, 0, 1, 1]), {0: 4.0, 1: 2.0})
        day = whatif.average_day([2.0] * SL + [4.0] * SL, [0, 1])
        self.assertEqual(day, [12.0] * SL)  # (2 + 4) / 2 · 4 кВт
        self.assertEqual(whatif.average_day([], []), [0.0] * SL)

    # --- сценарій --------------------------------------------------------------------------------------
    def test_night_scenario_saving_and_zones(self):
        res = whatif.run(params())
        t = res["tiles"]
        # 10 робочих діб × 64 кВт·год × (6 − 3) ₴ = 1 920 ₴ за 14 діб → на 30 діб
        self.assertAlmostEqual(t["saving_month"], round(1920 * 30 / 14, 2), places=2)
        self.assertAlmostEqual(t["moved_kwh_month"], round(640 * 30 / 14, 1), places=1)
        self.assertAlmostEqual(t["cost_before"] - t["cost_after"], t["saving_month"], places=1)
        self.assertEqual(t["peak_before_kw"], 108.0)
        self.assertEqual(t["peak_after_kw"], 108.0)  # ніч: 100 + 8 кВт
        self.assertEqual(t["limit_kw"], 200.0)
        zones_by_code = {z["code"]: z for z in res["zones"]}
        self.assertGreater(zones_by_code["night"]["after_pct"], zones_by_code["night"]["before_pct"])
        self.assertAlmostEqual(sum(z["after_pct"] for z in res["zones"]), 100.0, delta=0.2)
        self.assertEqual(len(res["profile"]["base_kw"]), SL)
        self.assertEqual(len(res["profile"]["scenario_kw"]), SL)
        self.assertEqual(res["profile"]["limit_kw"], 200.0)
        # середня доба (робочі): у вікні було 108, стало 100; уночі навпаки
        self.assertEqual(res["profile"]["base_kw"][40], 108.0)
        self.assertEqual(res["profile"]["scenario_kw"][40], 100.0)
        self.assertEqual(res["profile"]["scenario_kw"][95], 108.0)
        codes = {w["code"] for w in res["warnings"]}
        self.assertIn("night_shift", codes)  # нічна зміна: потрібні люди на ділянці
        self.assertNotIn("peak_over_limit", codes)
        night = next(w for w in res["warnings"] if w["code"] == "night_shift")
        self.assertIn("ділянці «Розкрій»", night["text"])

    def test_share_scales_saving(self):
        full = whatif.run(params())["tiles"]["saving_month"]
        half = whatif.run(params(share=0.5))["tiles"]["saving_month"]
        self.assertAlmostEqual(half, full / 2, delta=0.02)

    def test_days_mode_all(self):
        work = whatif.run(params())["tiles"]["moved_kwh_month"]
        every = whatif.run(params(days="all"))["tiles"]["moved_kwh_month"]
        self.assertAlmostEqual(every / work, 14 / 10, places=2)

    def test_shift_mode_and_flat_tariff(self):
        res = whatif.run(params(mode="shift", shift_h=2.0, zones=[whatif.Zone("Ц", "flat", 8.4, ALL, 0.0, 24.0, 1)]))
        self.assertEqual(res["tiles"]["saving_month"], 0.0)  # одна ціна — економії вартості немає
        self.assertIn("flat_tariff", {w["code"] for w in res["warnings"]})
        self.assertFalse(res["meta"]["zone_prices_differ"])

    def test_night_mode_needs_night_zone(self):
        with self.assertRaises(whatif.WhatIfError) as ctx:
            whatif.run(params(zones=[whatif.Zone("Ц", "flat", 8.4, ALL, 0.0, 24.0, 1)]))
        self.assertIn("нічної зони", str(ctx.exception))

    def test_peak_over_limit_warning(self):
        # фон уночі 90 кВт, удень 50: перенос 8 кВт у ніч → пік 98 кВт проти ліміту 95
        base = [0.0] * (N * SL)
        for d in range(N):
            for k in range(SL):
                base[d * SL + k] = 22.5 if (k >= 92 or k < 28) else 12.5
        node = window_load(2.0)
        net = [a + b for a, b in zip(base, node, strict=True)]
        res = whatif.run(
            params(net=net, nodes=[{"code": "A", "name": "A", "kwh": node, "cap_kw": None}], contract_kw=95.0)
        )
        self.assertEqual(res["tiles"]["peak_before_kw"], 90.0)
        self.assertEqual(res["tiles"]["peak_after_kw"], 98.0)
        self.assertEqual(res["tiles"]["peak_delta_kw"], 8.0)
        warn = next(w for w in res["warnings"] if w["code"] == "peak_over_limit")
        self.assertEqual(warn["level"], "danger")
        self.assertIn("на 3 кВт о 23:00", warn["text"])  # «пік перевищує ліміт на X кВт о 23:15»-формат
        self.assertIn("кВт о", warn["text"])
        self.assertNotIn("уже перевищувався", warn["text"])

    def test_peak_near_limit_warning(self):
        base = [22.5 if (k >= 92 or k < 28) else 12.5 for _d in range(N) for k in range(SL)]
        node = window_load(2.0)
        net = [a + b for a, b in zip(base, node, strict=True)]
        res = whatif.run(
            params(net=net, nodes=[{"code": "A", "name": "A", "kwh": node, "cap_kw": None}], contract_kw=105.0)
        )
        warn = next(w for w in res["warnings"] if w["code"] == "peak_near_limit")  # 98 ≥ 90 % від 105 і пік виріс
        self.assertEqual(warn["level"], "warning")

    def test_rating_cap_blocks_part(self):
        # вузол 8 кВт у вікні 08–16; переносимо 08–10 на +4 год (12:00–14:00), де вузол уже працює;
        # номінал 12 кВт (3 кВт·год за слот) пускає 1 з 2 кВт·год кожного слота
        node = window_load(2.0)
        net = [a + b for a, b in zip(flat(25.0), node, strict=True)]
        nodes = [{"code": "A", "name": "A", "kwh": node, "cap_kw": 12.0}]
        kw = {"net": net, "nodes": nodes, "mode": "shift", "shift_h": 4.0, "window": (8.0, 10.0), "days": "all"}
        capped = whatif.run(params(**kw))
        free = whatif.run(params(respect_rating=False, **kw))
        warn = next(w for w in capped["warnings"] if w["code"] == "rating_limit")
        self.assertIn("50,0 %", warn["text"])
        self.assertNotIn("rating_limit", {w["code"] for w in free["warnings"]})
        self.assertAlmostEqual(capped["tiles"]["moved_kwh_month"] * 2, free["tiles"]["moved_kwh_month"], delta=0.2)
        self.assertEqual(capped["tiles"]["peak_after_kw"], 112.0)  # 100 + 12 кВт — не вище номіналу вузла
        self.assertEqual(free["tiles"]["peak_after_kw"], 116.0)  # 100 + 8 + 8 кВт

    def test_capacity_fee(self):
        # плата за потужність 100 ₴/кВт·міс; пік не змінюється → плата однакова, економія лише за енергію
        res = whatif.run(params(capacity_price=100.0))["tiles"]
        self.assertAlmostEqual(res["capacity_fee_before"], 10800.0)
        self.assertAlmostEqual(res["capacity_fee_after"], 10800.0)
        self.assertAlmostEqual(res["saving_month"], round(1920 * 30 / 14, 2), places=2)
        # зсув у час нижчого фону знижує пік → економія і на потужності
        base = [30.0 if 44 <= k < 52 else 20.0 for _d in range(N) for k in range(SL)]  # пік 120 кВт о 11:00
        node = window_load(2.0, start=44, length=8)
        net = [a + b for a, b in zip(base, node, strict=True)]
        res = whatif.run(
            params(
                net=net,
                nodes=[{"code": "A", "name": "A", "kwh": node, "cap_kw": None}],
                capacity_price=100.0,
                window=(11.0, 13.0),
                mode="shift",
                shift_h=3.0,
                days="all",
            )
        )["tiles"]
        self.assertLess(res["peak_after_kw"], res["peak_before_kw"])
        self.assertGreater(res["capacity_fee_before"] - res["capacity_fee_after"], 0)

    def test_incomplete_days_excluded(self):
        ok = [True] * N
        ok[3] = ok[4] = False
        res = whatif.run(params(data_ok=ok))
        self.assertEqual(res["meta"]["days_used"], N - 2)
        self.assertIn("days_skipped", {w["code"] for w in res["warnings"]})
        with self.assertRaises(whatif.WhatIfError):
            whatif.run(params(data_ok=[True] * 4 + [False] * (N - 4)))

    def test_errors(self):
        with self.assertRaises(whatif.WhatIfError):
            whatif.run(params(zones=[]))
        with self.assertRaises(whatif.WhatIfError):
            whatif.run(params(nodes=[]))

    def test_nothing_moved_warning(self):
        res = whatif.run(params(window=(18.0, 20.0)))  # у цьому вікні вузол не працює
        self.assertEqual(res["tiles"]["moved_kwh_month"], 0.0)
        self.assertIn("nothing_moved", {w["code"] for w in res["warnings"]})

    def test_no_orm(self):
        """AC-73: `tools/whatif.py` — без ORM (імпортує лише чисті модулі)."""
        tree = ast.parse(inspect.getsource(whatif))
        names = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names |= {a.name for a in node.names}
            elif isinstance(node, ast.ImportFrom):
                names.add(("." * node.level) + (node.module or ""))
        self.assertNotIn("odoo", names)
        self.assertEqual({n for n in names if n.startswith("odoo")}, {"odoo.addons.td_energy.tools.tariff"})
