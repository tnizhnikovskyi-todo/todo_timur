"""W1-A: AC-103…AC-105, AC-140 — геометрія схеми, стани вузлів (R-26), ступені PFC (R-35)."""

import logging
from unittest.mock import patch

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .. import hooks
from ..tools import live, sld
from .common import TAGS, TestW1Common


@tagged(*TAGS)
class TestW1NodeSld(TestW1Common):
    def state(self, code):
        snap = sld.Snap(self.env(su=True), self.now)
        return snap.state(snap.by_code[code])

    def test_layout_load(self):  # AC-103
        shown = self.Node.search([("sld_show", "=", True)])
        self.assertEqual(len(shown), 22)
        by = {n.code: n for n in shown}
        self.assertEqual(
            (by["GRID-10KV"].sld_x, by["GRID-10KV"].sld_y, by["GRID-10KV"].sld_w, by["GRID-10KV"].sld_h),
            (580, 24, 160, 44),
        )
        self.assertEqual((by["T1"].sld_x, by["T1"].sld_y, by["T1"].sld_w, by["T1"].sld_h), (230, 192, 200, 64))
        sec = by["SEC-1"]
        self.assertEqual((sec.sld_shape, sec.sld_x, sec.sld_y, sec.sld_w, sec.sld_h), ("bar", 40, 298, 590, 6))
        self.assertEqual(sec.sld_label, "Секція шин 1 · 0,4 кВ")
        self.assertEqual(by["ATS-1"].sld_anchor_id.code, "SEC-2")
        self.assertFalse(self.Node.search([("code", "=", "SWB-1")]).sld_show)
        by["BW-2"].write({"sld_x": 999})
        stats = hooks._load_sld_layout(self.env)
        self.assertEqual(by["BW-2"].sld_x, 999)
        self.assertEqual((stats["loaded"], stats["missing"]), (0, 0))
        row = {"code": "NOPE", "shape": "box", "x": "1", "y": "1", "w": "10", "h": "10", "label": "", "anchor": ""}
        with (
            patch.object(hooks, "_rows", return_value=[row]),
            self.assertLogs("odoo.addons.td_energy.hooks", logging.WARNING),
        ):
            self.assertEqual(hooks._load_sld_layout(self.env)["missing"], 1)

    def test_sld_constraints(self):
        node = self.Node.search([("code", "=", "BW-3")])
        with self.assertRaises(ValidationError):
            node.write({"sld_w": 0})  # блок на схемі без розмірів
        with self.assertRaises(ValidationError):
            node.write({"sld_x": -1})
        with self.assertRaises(ValidationError):
            node.write({"sld_anchor_id": node.id})

    def test_states_table(self):  # AC-104
        self.fixture_grid()
        fresh = self.fresh
        fresh("energy/cells/QS/state", 1.0, "closed")
        self.assertEqual(self.state("QS"), "ok")
        fresh("energy/cells/QS/state", 0.0, "open")
        self.assertEqual(self.state("QS"), "off")
        fresh("infra/totals/pv_now", 309.0)
        self.assertEqual(self.state("PV-INV"), "gen")
        fresh("infra/totals/pv_now", 0.0)
        self.assertEqual(self.state("PV-INV"), "off")
        self.assertEqual(self.state("CHP"), "off")
        fresh("infra/chp/state", 2.0, "running")
        self.assertEqual(self.state("CHP"), "gen")
        fresh("infra/chp/state", 3.0, "fault")
        self.assertEqual(self.state("CHP"), "alarm")
        fresh("infra/ats/position", 2.0, "pos_I")
        self.assertEqual(self.state("ATS-1"), "off")
        fresh("infra/ats/position", 3.0, "pos_II")
        self.assertEqual(self.state("ATS-1"), "gen")
        self.Meter.search([("code", "=", "PM-QF-C2")]).write({"data_state": "stale"})
        self.assertEqual(self.state("C2"), "alarm")
        self.Meter.search([("code", "=", "PM-QF-C2")]).write({"data_state": "gap"})
        self.assertEqual(self.state("C2"), "warn")
        for load, expected in ((850.0, "warn"), (1010.0, "alarm"), (500.0, "ok")):
            fresh("energy/transformers/T1/s_kva", load)
            self.assertEqual(self.state("T1"), expected, load)
        self.assertEqual(self.state("RM6-1"), "ok")
        self.assertEqual(self.state("GRID-10KV"), "ok")

    def test_pfc_states(self):  # AC-104
        self.fixture_grid()
        fresh = self.fresh
        fresh("energy/cells/PFC-2/fault_step", 3.0)
        fresh("energy/sections/S2/cos_phi", 0.88)
        self.assertEqual(self.state("PFC-2"), "warn")  # fault_step > 0
        fresh("energy/sections/S2/cos_phi", 0.86)
        self.assertEqual(self.state("PFC-2"), "warn")
        fresh("energy/cells/PFC-2/fault_step", 0.0)
        self.assertEqual(self.state("PFC-2"), "alarm")  # cos < 0,90
        fresh("energy/sections/S2/cos_phi", 0.91)
        self.assertEqual(self.state("PFC-2"), "warn")  # cos < 0,92
        fresh("energy/sections/S2/cos_phi", 0.95)
        self.assertEqual(self.state("PFC-2"), "ok")

    def test_bess_states(self):  # AC-105
        for kw, expected in ((50.0, "gen"), (-50.0, "gen"), (0.0, "ok"), (0.5, "ok")):
            self.fresh("infra/totals/bess_kw", kw)
            self.fresh("infra/bess/state", 2.0, "running")
            self.assertEqual(self.state("BESS"), expected, kw)
        self.fresh("infra/bess/state", 3.0, "fault")
        self.assertEqual(self.state("BESS"), "alarm")

    def test_open_events_priority(self):
        self.fixture_grid()
        node = self.Node.search([("code", "=", "BW-2")])
        ev = self.Event._td_log("warn", "meter", "PM-QF-2", "Лічильник. Тест.", ts=self.now, node=node)
        self.assertEqual(self.state("BW-2"), "warn")
        bad = self.Event._td_log("bad", "threshold", "QF-2", "Струм. Аварія.", ts=self.now, node=node)
        self.assertEqual(self.state("BW-2"), "alarm")
        (ev | bad).write({"state": "resolved"})
        self.assertEqual(self.state("BW-2"), "ok")
        self.assertEqual(node.with_context(f3d_now=self.now).sld_state, "ok")

    def test_pfc_steps(self):  # AC-140
        lines = {"BW-2": {"section": 2, "p": 300.0, "cos": 0.88, "i": 500.0, "rating_a": 630}}
        res = live.site_totals(lines, {2: None}, {2: 350}, pfc_meas={2: 120.0}, pfc_step={2: 35})
        self.assertEqual(res["sections"][2]["pfc_q_now"], 105)  # round(120/35)·35
        self.assertEqual(res["sections"][2]["q_pfc"], 120.0)
        theory = live.site_totals(lines, {2: None}, {2: 350}, pfc_step={2: 35})
        self.assertEqual(theory["sections"][2]["pfc_q_now"] % 35, 0)
        self.assertLessEqual(theory["sections"][2]["pfc_q_now"], 350)
        old = live.site_totals(lines, {2: None}, {2: 350})
        self.assertEqual(old["sections"][2]["pfc_q_now"] % 50, 0)  # без параметра — старий крок 50
        pfc = self.Node.search([("code", "=", "PFC-2")])
        self.assertEqual((pfc.pfc_step_kvar, pfc.pfc_steps_total, pfc.rating_kvar), (35, 10, 350))
        with self.assertRaises(ValidationError):
            pfc.write({"pfc_steps_total": 9})
        self.fixture_grid()
        self.fresh("energy/cells/PFC-2/q_kvar", 120.0)
        snap = self.Node._td_live_snapshot()
        self.assertEqual(snap["totals"]["sections"][2]["pfc_q_now"], 105)

    def test_cron_live_writes_sections(self):  # R-35 п. 1
        self.fixture_grid()
        self.fresh("energy/lines/C2/p_now", 158.0)
        self.fresh("energy/lines/C2/i_now", 250.0)
        self.fresh("energy/cells/PFC-1/q_kvar", 70.0)
        self.fresh("energy/cells/PFC-2/q_kvar", 105.0)
        snap = self.Node._td_live_snapshot()
        self.assertTrue(self.Node._td_live_write(snap, fields.Datetime.now()))
        for s in (1, 2):
            for suffix in ("cos_phi", "p_kw", "q_kvar"):
                sig = self.env["td.signal"].search([("code", "=", "energy/sections/S%d/%s" % (s, suffix))])
                self.assertTrue(sig.last_ts, sig.code)
        self.assertEqual(self.Node.search([("code", "=", "PFC-2")]).pfc_q_now, 105)
