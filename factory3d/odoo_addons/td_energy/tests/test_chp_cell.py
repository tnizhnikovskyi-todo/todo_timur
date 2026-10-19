"""QF-CHP: шафа вводу КГУ на секції 2 ГРЩ (`cell_type='generator'`): дерево, схема, картка, баланс секцій, міграція.

КГУ (`CHP`, TEDOM Quanto D800, 800 кВт) живиться від секції 2 через автомат `QF-CHP` (1600 А); показники шафи беруться
з вимірювань КГУ (`infra/totals/chp_kw`, лічильник TEDOM-1) — окремих сигналів шафа не має.
"""

import math

from odoo.tests import tagged

from .. import hooks
from ..tools import sld
from .common import TAGS, TestW1Common

SQRT3 = math.sqrt(3)


@tagged(*TAGS)
class TestChpCell(TestW1Common):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cell = cls.Node.search([("code", "=", "QF-CHP")])
        cls.chp = cls.Node.search([("code", "=", "CHP")])
        cls.Dash = cls.env["td.energy.dashboard"]

    def snap(self):
        return sld.Snap(self.env(su=True), self.now)

    def run_chp(self, kw=400.0):
        self.fixture_grid()
        self.fresh("infra/chp/state", 2.0, "running")
        self.fresh("infra/totals/chp_kw", kw)

    # --- дані: дерево вузлів ----------------------------------------------------------------------------
    def test_tree(self):
        cell, chp = self.cell, self.chp
        self.assertEqual((cell.kind, cell.cell_type), ("cell", "generator"))
        self.assertEqual((cell.parent_id.code, cell.cabinet_id.code, cell.section), ("SEC-2", "SWB-1", 2))
        self.assertEqual((chp.kind, chp.gen_kind, chp.parent_id), ("generator", "chp", cell))
        self.assertEqual(self.Node.search([("id", "child_of", cell.id)]), cell | chp)
        # номінал автомата за рядом 1250/1600: 800 кВт / (√3 · 0,4 кВ · 0,95) ≈ 1215 А — запас лишається лише в 1600 А
        i_nom = chp.p_inst_kw * 1000 / (SQRT3 * 400 * 0.95)
        self.assertEqual(round(i_nom), 1216)
        self.assertEqual(cell.rating_a, 1600)
        self.assertGreater(cell.rating_a, i_nom * 1.25)
        seq = {n.code: n.sequence for n in self.Node.search([("kind", "=", "cell")])}
        self.assertTrue(seq["Q2"] < seq["QF-CHP"] < seq["PFC-2"])
        cells = self.Node.search([("kind", "=", "cell"), ("section", "=", 2)]).mapped("code")
        self.assertEqual(cells, ["QF-1", "QF-4", "QF-C2", "Q2", "QF-CHP", "PFC-2"])
        self.assertEqual(chp.meter_ids.mapped("code"), ["TEDOM-1"])  # вимірювання лишається на КГУ
        self.assertFalse(cell.meter_ids)  # окремих лічильників і сигналів шафа не має

    def test_cell_type_selection_and_constraints(self):
        selection = dict(self.Node._fields["cell_type"].selection)
        self.assertEqual(selection["generator"], "Ввід генератора")
        self.assertEqual(set(selection), {"incomer", "feeder", "cable", "coupler", "pfc", "generator"})

    # --- схема Пульту -----------------------------------------------------------------------------------
    def test_sld_layout_and_edges(self):
        snap = self.snap()
        shown = [r for r in snap.sld_rows() if r["sld_shape"] in ("box", "bar", "switch") and r["sld_w"] and r["sld_h"]]
        self.assertEqual(len(shown), 22)
        by = snap.by_code
        qf, chp = by["QF-CHP"], by["CHP"]
        self.assertEqual((qf["sld_shape"], qf["sld_x"], qf["sld_y"]), ("box", 1214, 192))
        self.assertLess(chp["sld_y"] + chp["sld_h"], qf["sld_y"])  # КГУ над шафою, шафа над шиною секції 2
        self.assertLess(qf["sld_y"] + qf["sld_h"], by["SEC-2"]["sld_y"])
        for i, a in enumerate(shown):  # блоки схеми не накладаються
            for b in shown[i + 1 :]:
                apart = (
                    a["sld_x"] + a["sld_w"] <= b["sld_x"] or b["sld_x"] + b["sld_w"] <= a["sld_x"]
                    or a["sld_y"] + a["sld_h"] <= b["sld_y"] or b["sld_y"] + b["sld_h"] <= a["sld_y"]
                )  # fmt: skip
                self.assertTrue(apart, "%s накладається на %s" % (a["code"], b["code"]))
        sec2 = by["SEC-2"]  # шафа в межах шини за x, щоб ребро QF-CHP → шина було вертикаллю
        self.assertTrue(sec2["sld_x"] <= qf["sld_x"] + qf["sld_w"] / 2 <= sec2["sld_x"] + sec2["sld_w"])
        edges = {(e["from"], e["to"]) for e in snap.edges()}
        self.assertIn(("SEC-2", "QF-CHP"), edges)
        self.assertIn(("QF-CHP", "CHP"), edges)
        self.assertNotIn(("SEC-2", "CHP"), edges)  # КГУ більше не підключена прямо до секції

    def test_pult_sld_part(self):  # API-05: блоки схеми з якорями, текстом і ознакою картки
        self.run_chp(400.0)
        sld_part = self.Dash.with_user(self.u_cost).get_pult("now", ["sld"])["sld"]
        nodes = {n["code"]: n for n in sld_part["nodes"]}
        self.assertEqual(len(nodes), 22)
        self.assertEqual((nodes["QF-CHP"]["anchor"], nodes["CHP"]["anchor"]), ("SEC-2", "QF-CHP"))
        self.assertEqual(nodes["QF-CHP"]["lines"], ["QF-CHP", "400 кВт"])
        self.assertEqual((nodes["QF-CHP"]["state"], nodes["CHP"]["state"]), ("gen", "gen"))
        self.assertTrue(nodes["QF-CHP"]["card"])
        self.assertFalse(nodes["CHP"]["card"])
        self.assertEqual(nodes["QF-CHP"]["title"], "Ввід КГУ · TEDOM Quanto D800")
        parents = {e["to"]: e["from"] for e in sld_part["edges"]}
        self.assertEqual((parents["QF-CHP"], parents["CHP"]), ("SEC-2", "QF-CHP"))
        states = {e["to"]: e["state"] for e in sld_part["edges"]}
        self.assertEqual((states["QF-CHP"], states["CHP"]), ("gen", "gen"))

    def test_state_lines_facts(self):
        self.fixture_grid()
        snap = self.snap()
        row = snap.by_code["QF-CHP"]
        self.assertEqual(snap.state(row), "off")  # КГУ зупинена
        self.assertEqual(snap.lines(row), ["QF-CHP", "немає даних"])
        self.run_chp(400.0)
        snap = self.snap()
        row = snap.by_code["QF-CHP"]
        self.assertEqual(snap.state(row), "gen")
        self.assertEqual(snap.state(snap.by_code["CHP"]), "gen")
        self.assertEqual(snap.lines(row), ["QF-CHP", "400 кВт"])
        i = 400 * 1000 / (SQRT3 * 380 * 0.95)
        self.assertAlmostEqual(snap.generator_current(row), i, places=3)
        self.assertEqual(round(snap.load_pct(row)), round(i / 1600 * 100))
        facts = snap.facts(row)
        self.assertEqual(facts[0], "Ввід КГУ TEDOM Quanto D800 на секцію шин 2")
        self.assertIn("Номінал 1600 А", facts)
        self.assertEqual(facts[-1], "Видає 400 кВт · ≈ %d А" % round(i))
        self.fresh("infra/chp/state", 3.0, "fault")
        snap = self.snap()
        self.assertEqual(snap.state(snap.by_code["QF-CHP"]), "alarm")

    # --- картка вузла -----------------------------------------------------------------------------------
    def test_node_card(self):
        self.run_chp(400.0)
        card = self.Dash.with_user(self.u_cost).get_node_card("QF-CHP")
        self.assertEqual([p["code"] for p in card["node"]["path"]], ["SWB-1", "SEC-2", "QF-CHP"])
        self.assertEqual((card["node"]["kind"], card["node"]["kind_label"]), ("cell", "Шафа ГРЩ"))
        self.assertIn({"text": "Генерує", "state": "ok"}, card["node"]["chips"])
        self.assertNotIn("Знеструмлено або резерв", [c["text"] for c in card["node"]["chips"]])
        i = 400 * 1000 / (SQRT3 * 380 * 0.95)
        kpis = card["kpis"]
        self.assertEqual(kpis["current"]["rating_a"], 1600)
        self.assertEqual((kpis["current"]["a"], kpis["current"]["pct"]), (round(i), round(i / 1600 * 100)))
        self.assertEqual((kpis["power"]["kw"], kpis["power"]["p_inst_kw"], kpis["power"]["cos_phi"]), (400, 800, 0.95))
        self.assertEqual(card["meter"]["code"], "TEDOM-1")  # облік — лічильник КГУ
        self.assertEqual(len(card["chart"]["a"]), 96)
        self.assertNotIn("taps", card)  # відгалужень немає
        self.assertNotIn("protection", card)
        self.fresh("infra/chp/state", 0.0, "stop")
        card = self.Dash.with_user(self.u_cost).get_node_card("QF-CHP")
        self.assertIn({"text": "Не генерує", "state": "off"}, card["node"]["chips"])

    # --- баланс секцій (D-47): ячейка генератора не задвоює й не губить потужність КГУ ------------------
    def test_section_balance_by_lines(self):
        self.fixture_grid()
        sections = lambda: self.Node._td_live_snapshot()["totals"]["sections"]  # noqa: E731
        base = sections()
        lines = {2: ("BW-1", "BW-4", "C2")}
        self.run_chp(700.0)
        with_chp = sections()
        self.assertEqual(with_chp[2]["p"], base[2]["p"])  # секція рахується за лініями, КГУ не додається вдруге
        self.assertEqual(with_chp[1]["p"], base[1]["p"])
        expected = sum(self.env["td.energy.node"].search([("code", "in", lines[2])]).mapped("p_now"))
        self.assertEqual(with_chp[2]["p"], expected)
        snap = self.Node._td_live_snapshot()
        self.assertEqual(snap["chp_kw"], 700.0)  # потужність КГУ в знімку — з вимірювання, не з ячейки
        self.assertEqual(snap["stale_feeders"], 1)  # лінія C2 без показань; ячейка QF-CHP не рахується фідером
        self.Node._td_live_write(snap, self.now)
        self.env["td.signal"].invalidate_model()
        p_s2 = self.env["td.signal"].search([("code", "=", "energy/sections/S2/p_kw")])
        self.assertEqual(p_s2.last_value, round(expected, 2))

    # --- міграція існуючих баз --------------------------------------------------------------------------
    def old_state(self):
        """База до 19.0.1.1.2: КГУ підключена прямо до секції 2, шафи QF-CHP немає, блок КГУ на старому місці."""
        sec2 = self.Node.search([("code", "=", "SEC-2")])
        self.chp.write({"parent_id": sec2.id, "sld_x": 1214, "sld_y": 192, "sld_w": 88, "sld_h": 64})
        self.cell.unlink()
        self.assertFalse(self.Node.search([("code", "=", "QF-CHP")]))

    def test_migration_from_old_database(self):
        self.old_state()
        report = hooks._migrate_chp_cell(self.env)
        self.assertEqual((report["cell_created"], report["chp_moved"], report["chp_sld_moved"]), (True, True, True))
        cell = self.Node.search([("code", "=", "QF-CHP")])
        self.assertEqual(
            (cell.kind, cell.cell_type, cell.parent_id.code, cell.cabinet_id.code),
            ("cell", "generator", "SEC-2", "SWB-1"),
        )
        self.assertEqual((cell.section, cell.sequence, cell.rating_a, cell.cos_phi_nominal), (2, 105, 1600, 0.95))
        self.assertEqual(self.chp.parent_id, cell)
        self.assertEqual((self.chp.sld_x, self.chp.sld_y), (1214, 84))
        self.assertEqual((cell.sld_show, cell.sld_shape, cell.sld_x, cell.sld_y), (True, "box", 1214, 192))
        again = hooks._migrate_chp_cell(self.env)  # ідемпотентно
        self.assertEqual((again["cell_created"], again["chp_moved"], again["chp_sld_moved"]), (False, False, False))
        self.assertEqual(self.Node.search_count([("code", "=", "QF-CHP")]), 1)

    def test_migration_keeps_user_changes(self):
        self.old_state()
        bess = self.Node.search([("code", "=", "BESS")])
        self.chp.write({"parent_id": bess.id, "sld_y": 500, "name": "Моя КГУ"})  # користувач уже змінив вузол
        report = hooks._migrate_chp_cell(self.env)
        self.assertEqual((report["cell_created"], report["chp_moved"], report["chp_sld_moved"]), (True, False, False))
        self.assertEqual((self.chp.parent_id, self.chp.sld_y, self.chp.name), (bess, 500, "Моя КГУ"))

    def test_rebind_idempotent_with_cell(self):  # повторна прив'язка даних (CSV) не дублює шафу
        before = self.Node.search_count([])
        hooks.run_bind(self.env)
        self.assertEqual(self.Node.search_count([]), before)
        self.assertEqual(self.chp.parent_id.code, "QF-CHP")
