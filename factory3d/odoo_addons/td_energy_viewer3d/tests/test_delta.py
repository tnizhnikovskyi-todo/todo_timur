"""W2-D: AC-286 — дельта шару: повна заміна `energy.layer` (R-57, M-41)."""

from odoo.tests import tagged

from .common import TAGS, LayerCase


@tagged(*TAGS)
class TestDelta(LayerCase):
    def delta_layer(self, changes, user=None):
        patch = {}
        self.provider(user)._td_viewer_delta(patch, {"kiosk": False, "changes": changes})
        return patch.get("energy", {}).get("layer")

    def test_delta_on_energy_changes(self):  # AC-286
        self.assertIsNotNone(self.delta_layer({"td.energy": {"C2"}}))
        self.assertIsNotNone(self.delta_layer({"td.signal": {"energy/lines/BW-2/i_now"}}))
        self.assertIsNotNone(self.delta_layer({"td.signal": {"infra/bess/state"}}))
        self.assertIsNone(self.delta_layer({"td.signal": {"lighting/x"}}))
        self.assertIsNone(self.delta_layer({"stock.quant": {"A"}}))
        self.assertIsNone(self.delta_layer({}))
        self.assertEqual(self.delta_layer({"td.energy": {"C2"}}), self.layer())

    def test_delta_is_full_replacement(self):  # AC-286
        res = self.delta(self.u_viewer, {"td.energy": {"C2"}})
        patch = res["patch"]
        layer = patch["energy"]["layer"]
        self.assertEqual(len(layer["alarms"]), 1)
        self.assertIn("transformers", patch["energy"])  # розділ `energy` провайдера 100 збережено поруч
        # склеювання на клієнті (deep_merge): списки замінюються цілком
        from odoo.addons.td_viewer3d.tools.payload import deep_merge

        base = {"energy": {"layer": {"alarms": [{"id": 1}, {"id": 2}, {"id": 3}], "nodes": [{"code": "X"}]}}}
        deep_merge(base, patch)
        self.assertEqual([a["id"] for a in base["energy"]["layer"]["alarms"]], [layer["alarms"][0]["id"]])
        self.assertEqual(len(base["energy"]["layer"]["nodes"]), len(layer["nodes"]))
        # без енергетичних змін шару в патчі немає
        res = self.delta(self.u_viewer, {"stock.quant": {"A"}})
        self.assertNotIn("layer", res["patch"].get("energy", {}))
        # після закриття тривоги наступна дельта віддає порожній список (а не стару копію)
        self.c2_event.write({"state": "resolved"})
        self.assertEqual(self.delta_layer({"td.energy": {"C2"}})["alarms"], [])
