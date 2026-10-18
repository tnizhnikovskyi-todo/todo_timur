"""W2-D: AC-282…AC-285 — payload `energy.layer` (R-57, M-41)."""

import json
import logging
import time

from odoo.tests import tagged

from ..tools import layer as layer_tools
from .common import TAGS, LayerCase

_logger = logging.getLogger(__name__)


@tagged(*TAGS)
class TestLayerPayload(LayerCase):
    def test_collect_structure(self):  # AC-282
        layer = self.layer()
        self.assertEqual(layer["schema"], 1)
        self.assertEqual(layer["thresholds"], {"warn_pct": 80, "alarm_pct": 100})
        shown = self.Node.search([("sld_show", "=", True), ("kind", "in", list(layer_tools.LAYER_KINDS))])
        self.assertEqual(len(layer["nodes"]), len(shown))
        self.assertIn(len(layer["nodes"]), range(18, 23))  # ≈ 21 вузол макета (без вводу 10 кВ і RM6)
        self.assertEqual(
            list(self.node(layer, "BW-2")),
            "code scene kind name state load i_a p_kw rating_a card alarms worst title".split(),
        )
        self.assertEqual(set(layer), {"schema", "thresholds", "show_markers", "nodes", "alarms", "summary"})
        self.assertEqual(set(layer["summary"]), {"alarm", "warn", "gen", "off"})
        self.assertEqual(sum(layer["summary"].values()), sum(n["state"] != "ok" for n in layer["nodes"]))
        self.assertLess(len(json.dumps(layer)), 12 * 1024)  # ≤ 12 КБ
        bw2 = self.node(layer, "BW-2")
        self.assertEqual(
            (bw2["name"], bw2["kind"], bw2["i_a"], bw2["p_kw"], bw2["rating_a"], bw2["load"]),
            ("ШР-2", "line", 192, 124.0, 630, 0.305),
        )

    def test_provider_contract_and_denied(self):  # AC-282
        provider = self.env["td.viewer.provider.energy_layer"]
        self.assertEqual(provider._f3d_sequence, 101)
        self.assertEqual(provider._f3d_sections, ("energy",))
        self.assertEqual(provider._f3d_group, "td_factory3d.group_td_user")
        self.assertEqual(provider._f3d_viewer_bus_models(), ["td.signal", "td.energy"])
        res = self.payload(self.u_viewer, full=True)
        self.assertEqual(res["meta"]["schema"], "1.1")  # схема не змінилась: ключ аддитивний
        self.assertEqual(res["meta"]["sections"]["energy"], "live")
        self.assertIn("layer", res["energy"])
        self.assertIn("transformers", res["energy"])  # розділ провайдера `energy` не втрачено
        nobody = self.payload(self.u_plain, full=True)
        self.assertEqual(nobody["meta"]["sections"]["energy"], "denied")
        self.assertNotIn("layer", nobody["energy"])

    def test_scene_rules(self):  # AC-283
        layer = self.layer()
        self.assertEqual(self.node(layer, "BW-2")["scene"], "BW-2")
        self.assertEqual(self.node(layer, "T1")["scene"], "T1")
        self.assertEqual(self.node(layer, "C1")["scene"], layer_tools.CABLES)
        self.assertEqual(self.node(layer, "C2")["scene"], "CABLES")
        # обладнання з `td_code` перекриває код вузла; код, якого немає в сцені, → scene=null (вузол лишається в списку)
        eq = self.env["maintenance.equipment"].create({"name": "Тест FL", "td_code": "FL-1"})
        self.Node.search([("code", "=", "BW-3")]).equipment_id = eq
        self.Node.search([("code", "=", "BW-4")]).equipment_id = self.env["maintenance.equipment"].create(
            {"name": "Нема в сцені", "td_code": "ZZ-NOT-IN-SCENE"}
        )
        layer = self.layer()
        self.assertEqual(self.node(layer, "BW-3")["scene"], "FL-1")
        self.assertIsNone(self.node(layer, "BW-4")["scene"])
        self.assertTrue(self.node(layer, "BW-4")["card"])  # картка доступна й без об'єкта сцени
        # найгірший стан об'єкта сцени: CABLES = C1 (ok) + C2 (alarm)
        self.assertEqual(self.node(layer, "C1")["state"], "ok")
        self.assertEqual(layer_tools.scene_states(layer)["CABLES"], "alarm")
        self.assertNotIn(None, layer_tools.scene_states(layer))
        self.assertEqual(layer_tools.worst_state(["ok", "warn", "gen", "off"]), "warn")
        self.assertEqual(layer_tools.worst_state([]), "ok")

    def test_scene_without_static(self):  # A-53: статику отримати неможливо — scene без перевірки
        self.assertEqual(layer_tools.scene_of("ZZ-1", "cell", None, None, None), "ZZ-1")
        self.assertEqual(layer_tools.scene_of("ZZ-1", "cell", None, "EQ-1", {"EQ-1"}), "EQ-1")
        self.assertIsNone(layer_tools.scene_of("ZZ-1", "cell", None, None, {"EQ-1"}))
        known = layer_tools.scene_codes({"static": {"energy": {"lines": {"A": 1}}, "equipment": {"B": 1}}})
        self.assertTrue({"A", "B", "CABLES", "PV-INV"} <= known)

    def test_states_match_pult(self):  # AC-284
        layer = self.layer()
        expected = {
            "C2": "alarm",
            "PFC-2": "warn",
            "PV-INV": "gen",
            "CHP": "off",
            "ATS-1": "off",
            "QS": "off",
            "T2": "ok",
        }
        for code, state in expected.items():
            self.assertEqual(self.node(layer, code)["state"], state, code)
        for node in self.Node.search([("sld_show", "=", True)]):  # той самий стан, що `td.energy.node.sld_state`
            if node.code in {n["code"] for n in layer["nodes"]}:
                self.assertEqual(self.node(layer, node.code)["state"], node.sld_state, node.code)
        c2 = self.node(layer, "C2")
        self.assertEqual((c2["alarms"], c2["worst"], c2["title"]), (1, "bad", "Лічильник PM-QF-C2 не на зв'язку"))
        self.assertIsNone(c2["load"])
        # пороги змінюються разом із `td.energy.load_*_pct`: BW-2 (30 %) → увага при порозі 25 %
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("td.energy.load_warn_pct", "25")
        icp.set_param("td.energy.load_alarm_pct", "90")
        layer = self.layer()
        self.assertEqual(layer["thresholds"], {"warn_pct": 25, "alarm_pct": 90})
        self.assertEqual(self.node(layer, "BW-2")["state"], "warn")
        self.env.invalidate_all()
        self.assertEqual(self.node(layer, "BW-2")["state"], self.Node.search([("code", "=", "BW-2")]).sld_state)

    def test_alarms(self):  # AC-285
        pfc2 = self.Node.search([("code", "=", "PFC-2")])
        self.event(pfc2, "warn", "pfc", "PFC-2: ступінь 3 у несправності", state="acked", ts="2026-10-17 10:55:00")
        self.event(pfc2, "info", "pfc", "Інфо", state="na")  # не маркер
        self.event(pfc2, "bad", "pfc", "Закрита", state="resolved")  # не відкрита
        self.event(pfc2, "warn", "manual", "x" * 150, ts="2026-10-17 10:56:00")
        layer = self.layer()
        alarms = layer["alarms"]
        self.assertEqual([a["level"] for a in alarms], ["bad", "warn", "warn"])  # bad першими, далі за часом
        self.assertEqual(alarms[0]["node"], "C2")
        self.assertEqual(alarms[0]["scene"], "CABLES")
        self.assertEqual(alarms[0]["time"], "13:47")
        self.assertEqual(alarms[0]["state"], "active")
        self.assertEqual(alarms[1]["time"], "13:56")  # нові першими
        self.assertEqual(alarms[2]["state"], "acked")
        self.assertTrue(all(len(a["title"]) <= 80 for a in alarms))
        self.assertEqual(len(alarms[1]["title"]), 80)
        text = json.dumps(layer)
        for forbidden in ("acked_by", "assigned_user", "cost", "modbus: timeout"):
            self.assertNotIn(forbidden, text)
        pfc = self.node(layer, "PFC-2")
        self.assertEqual((pfc["alarms"], pfc["worst"]), (2, "warn"))
        # ≤ marker_limit
        self.env["ir.config_parameter"].sudo().set_param("td.energy_viewer3d.marker_limit", "2")
        self.assertEqual(len(self.layer()["alarms"]), 2)
        self.assertEqual(self.layer()["alarms"][0]["level"], "bad")

    def test_params_defaults(self):
        prm = layer_tools.params(self.env)
        self.assertEqual(prm, {"layers": layer_tools.DEFAULT_LAYERS, "marker_limit": 40, "show_markers": True})
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("td.energy_viewer3d.layers", "не json")
        icp.set_param("td.energy_viewer3d.marker_limit", "abc")
        icp.set_param("td.energy_viewer3d.show_markers", "False")
        prm = layer_tools.params(self.env)
        self.assertEqual(
            (prm["layers"], prm["marker_limit"], prm["show_markers"]), (layer_tools.DEFAULT_LAYERS, 40, False)
        )
        self.assertFalse(self.layer()["show_markers"])
        icp.set_param("td.energy_viewer3d.layers", '["energy", "backup"]')
        icp.set_param("td.energy_viewer3d.marker_limit", "9999")
        prm = layer_tools.params(self.env)
        self.assertEqual((prm["layers"], prm["marker_limit"]), (["energy", "backup"], layer_tools.MAX_MARKER_LIMIT))

    def test_build_perf(self):  # ТП-11: ≤ 12 КБ і ≤ 150 мс (кращий із трьох прогонів)
        best = min(self._timed_build() for _ in range(3))
        _logger.info("energy.layer: побудова %.0f мс", best * 1000)
        self.assertLess(best, 0.15)
        self.assertLess(len(json.dumps(self.layer())), 12 * 1024)

    def _timed_build(self):
        start = time.perf_counter()
        self.layer()
        return time.perf_counter() - start
