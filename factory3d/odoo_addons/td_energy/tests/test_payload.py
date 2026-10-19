"""AC-52, AC-59, AC-61, AC-63…AC-69: провайдери переглядача `energy` і `infra` (R-16…R-18, A-04).
Без `td_viewer3d`: методи провайдера викликаються напряму."""

from datetime import timedelta

from odoo import fields
from odoo.tests import new_test_user, tagged

from .common import TAGS, F3DEnergyCase
from .test_alloc import AllocMixin
from .test_costing import SPEC

# макет 12.10 10:30 (R-06): (лінія, P, cos φ)
LINES = [
    ("BW-3", 70.1, 0.92), ("BW-2", 80.5, 0.88), ("C1", 184.1, 0.90),
    ("BW-1", 106.9, 0.89), ("BW-4", 26.4, 0.92), ("C2", 158.0, 0.95),
]  # fmt: skip
TOTAL_KEYS = {
    "p_inst", "p_now", "s_now", "cos_before", "cos_after", "kwh_today", "peak_kw", "peak_time", "cost_today",
    "capacity_kva", "pv_kw", "grid_kw", "pv_today", "chp_kw", "export_kw", "bess_kw", "contract_kw",
}  # fmt: skip


@tagged(*TAGS)
class TestPayload(AllocMixin, F3DEnergyCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.alloc_setup()
        cls.u_mrpm = new_test_user(cls.env, login="en_mrpm2", groups="base.group_user,mrp.group_mrp_manager")

    # --- фікстури -----------------------------------------------------------------------------------------
    def sig(self, code, value=None, text=None):
        self.env.cr.execute(
            "UPDATE td_signal SET last_value=%s, last_text=%s, last_ts=%s, status='ok', last_quality='good'"
            " WHERE code=%s",
            (value, text, fields.Datetime.now(), code),
        )
        self.assertEqual(self.env.cr.rowcount, 1, code)
        self.env["td.signal"].invalidate_model()

    def set_grid(self, lines=LINES, q1=334.7, q2=-376.7):
        for code, p, cos in lines:
            self.sig("energy/lines/%s/p_now" % code, p)
            self.sig("energy/lines/%s/cos_phi" % code, cos)
            self.sig("energy/lines/%s/i_now" % code, round(p * 1000 / (1.7320508 * 400 * cos)))
        self.sig("energy/cells/Q1/p_now", q1)
        self.sig("energy/cells/Q2/p_now", q2)
        self.sig("energy/cells/Q1/state", 1, "closed")
        self.sig("energy/cells/Q1/i_now", 530)

    def set_infra(self, soc=76.1, bess=200.0, chp=400.0):
        for k in range(1, 9):
            self.sig("infra/pv/PV-INV-%d/p_kw" % k, 58.5)
            self.sig("infra/pv/PV-INV-%d/kwh_today" % k, 250.0)
            self.sig("infra/pv/PV-INV-%d/status" % k, 512, "on_grid")
        self.sig("infra/totals/chp_kw", chp)
        self.sig("infra/chp/heat_kw", 421.0)
        self.sig("infra/chp/gas_m3h", 99.5)
        self.sig("infra/chp/hours", 12345.0)
        self.sig("infra/chp/state", 2, "running")
        self.sig("infra/totals/bess_kw", bess)
        self.sig("infra/totals/bess_soc", soc)
        self.sig("infra/ats/position", 2, "pos_I")
        self.sig("infra/ats/mode", 16, "auto")

    def set_critical(self, total=347.8):
        """Критичні вузли дають Σ `total` (BW-1 — 106.9 з макета, решта поділена порівну)."""
        nodes = self.env["td.energy.node"].search([("is_critical", "=", True), ("kind", "in", ("consumer", "line"))])
        rest = nodes.filtered(lambda n: n.code != "BW-1")
        for n in rest:
            kind = "consumers" if n.kind == "consumer" else "lines"
            self.sig("energy/%s/%s/p_now" % (kind, n.code), round((total - 106.9) / len(rest), 6))

    def provider(self, name, user=None):
        return self.env["td.viewer.provider.%s" % name].with_user(user or self.u_energy)

    def energy(self, ctx=None, user=None, payload=None):
        payload = (
            payload if payload is not None else {"energy": {"totals": {"peak_time": "09:15"}, "typical": [0] * 24}}
        )
        self.provider("energy", user)._td_viewer_collect(payload, ctx or {})
        return payload

    def make_mo(self):
        nodes = [self.mk_direct(c, p, lf, meter=False) for c, p, lf, _m in SPEC]
        mo = self.mk_mo(self.env["mrp.workcenter"].concat(*[n.workcenter_id for n in nodes]))
        for wo, (_c, _p, _lf, minutes) in zip(mo.workorder_ids.sorted("id"), SPEC, strict=True):
            self.log(wo, self.at(1), self.at(1, minutes))
        self.run_day()
        return mo

    # --- energy -------------------------------------------------------------------------------------------
    def test_energy_section_keys_and_numbers(self):  # AC-63
        self.set_grid()
        self.set_infra()
        energy = self.energy()["energy"]
        self.assertEqual(set(energy["meta"]), {"source", "u_kv", "tariff_uah", "note"})
        self.assertEqual(set(energy["totals"]), TOTAL_KEYS)
        totals = energy["totals"]
        self.assertEqual((totals["p_now"], totals["capacity_kva"], totals["p_inst"]), (626, 2000, 1201))
        self.assertEqual(totals["cos_after"], 0.97)
        self.assertEqual(set(energy["transformers"]), {"T1", "T2"})
        for item in energy["transformers"].values():
            self.assertTrue({"name", "rating_kva", "section", "incomer"} <= set(item))
        self.assertEqual(
            list(energy["cells"]),
            ["PFC-1", "Q1", "QF-3", "QF-2", "QF-C1", "QS", "QF-1", "QF-4", "QF-C2", "Q2", "PFC-2"],
        )
        self.assertEqual(len(energy["lines"]), 6)
        self.assertEqual(len(energy["consumers"]), 49)
        self.assertEqual(len(energy["profile"]), 24)
        self.assertEqual(len(energy["typical"]), 24)
        self.assertLessEqual(len(energy["events"]), 6)
        self.assertEqual((totals["grid_kw"], totals["export_kw"]), (0.0, 42.0))
        self.assertTrue(energy["lines"]["BW-1"]["consumers"])

    def test_cells_states_consumers(self):  # AC-64
        self.set_grid()
        energy = self.energy()["energy"]
        qs = energy["cells"]["QS"]
        self.assertEqual((qs["type"], qs["section"], qs["state"], qs["rating_a"]), ("coupler", None, "off", 1600))
        self.assertIn("Розімкнений", qs["note"])
        self.assertEqual(energy["cells"]["PFC-2"]["q_now"], 35)  # W1 D-09: крок 35 квар
        self.assertEqual(energy["cells"]["Q1"]["state"], "on")
        self.sig("energy/cells/Q1/state", 2, "tripped")
        self.assertEqual(self.energy()["energy"]["cells"]["Q1"]["state"], "tripped")
        node = self.env["td.energy.node"].search([("code", "=", "SAW-1")])
        node.workcenter_id = self.mk_wc("SAW-1")
        energy = self.energy(user=self.u_mrpm)["energy"]
        self.assertEqual(energy["consumers"]["SAW-1"].get("status"), "idle")
        self.sig("energy/consumers/SAW-1/p_now", 12.18)
        saw = self.energy(user=self.u_mrpm)["energy"]["consumers"]["SAW-1"]
        self.assertEqual(
            (saw["i_now"], saw["p_now"], saw["status"]), (22, 12.18, "idle")
        )  # без machine_connect і без завдань — простій (R-16 п. 6)
        self.ensure_signal("workcenters/SAW-1/machine_state", "state", "")
        self.sig("workcenters/SAW-1/machine_state", 1, "working")
        self.assertEqual(self.energy(user=self.u_mrpm)["energy"]["consumers"]["SAW-1"]["status"], "work")
        wc = self.mk_wc("CNC-T")
        self.env["td.energy.node"].create(
            {
                "code": "CNC-T", "name": "CNC-T", "kind": "consumer", "workcenter_id": wc.id, "section": 1,
                "parent_id": self.env["td.energy.node"].search([("code", "=", "SEC-1")]).id, "p_inst_kw": 22.0,
            }
        )  # fmt: skip
        self.ensure_signal("workcenters/CNC-T/machine_state", "state", "")
        self.sig("workcenters/CNC-T/machine_state", 3, "fault")
        self.assertEqual(self.energy(user=self.u_mrpm)["energy"]["consumers"]["CNC-T"]["status"], "stop")

    def test_cost_hidden_kiosk(self):  # AC-65
        mo = self.make_mo()
        for ctx, user in (({"kiosk": True}, self.u_mrpm), ({}, self.u_master)):
            payload = {"productions": [{"name": mo.name, "energy_cost": 1}]}
            self.energy(ctx, user, payload)
            self.assertNotIn("cost_today", payload["energy"]["totals"])
            self.assertNotIn("energy_cost", payload["productions"][0])
            self.assertAlmostEqual(payload["productions"][0]["energy_kwh"], 86.2, places=1)
        payload = {"productions": [{"name": mo.name}]}
        self.energy({}, self.u_mrpm, payload)
        self.assertIn("cost_today", payload["energy"]["totals"])
        self.assertIn("energy_cost", payload["productions"][0])

    def test_viewer_numbers(self):  # AC-52
        mo = self.make_mo()
        payload = {"productions": [{"name": mo.name}]}
        self.energy({}, self.u_mrpm, payload)
        item = payload["productions"][0]
        self.assertEqual((item["energy_kwh"], item["energy_cost"], item["energy_quality"]), (86.2, 724, "estimate"))

    def test_workcenter_energy(self):  # AC-66
        self.set_grid()
        self.env["td.energy.node"].search([("code", "=", "SAW-1")]).workcenter_id = self.mk_wc("SAW-1")
        self.sig("energy/consumers/SAW-1/p_now", 12.18)
        payload = self.energy(user=self.u_mrpm, payload={"workcenters": {"SAW-1": {}, "NOPE": {}}})
        self.assertEqual(payload["workcenters"]["SAW-1"]["energy"], {"p_now": 12.18, "line": "BW-1"})
        self.assertNotIn("energy", payload["workcenters"]["NOPE"])

    # --- infra --------------------------------------------------------------------------------------------
    def infra(self, payload=None, ctx=None):
        payload = payload if payload is not None else {}
        self.provider("infra")._td_viewer_collect(payload, ctx or {})
        return payload["infra"]

    def test_infra_cards_totals(self):  # AC-67, AC-61
        self.set_grid()
        self.set_infra()
        self.set_critical()
        static = {"cards": {"WATER": {"rows": [["a", "b"]]}, "SERVER": {"rows": []}, "GENSET": {"rows": [["Г", "1"]]}},
                  "totals": {"genset_kva": 634}}  # fmt: skip
        infra = self.infra({"infra": {"cards": dict(static["cards"]), "totals": {"genset_kva": 634}}})
        totals, cards = infra["totals"], infra["cards"]
        self.assertEqual((totals["export_kw"], totals["grid_kw"], totals["critical_kw"]), (42, 0, 348))
        self.assertEqual((totals["bess_mode"], totals["n_modules"], totals["pv_now"]), ("charge", 1552, 468.0))
        self.assertIn(["Зараз", "заряджається 200 кВт (надлишок СЕС і КГУ)"], cards["BESS"]["rows"])
        self.assertIn(["Тримає критичні", "≈ 51 хв"], cards["BESS"]["rows"])
        self.assertIn(["Стан", "усі в мережі"], cards["PV-INV"]["rows"])
        self.assertIn(["Модулів", "1 552 × 580 Вт"], cards["PV-ROOF"]["rows"])
        self.assertEqual(cards["WATER"], static["cards"]["WATER"])
        self.assertEqual(cards["SERVER"], static["cards"]["SERVER"])
        self.assertEqual((cards["GENSET"], totals["genset_kva"]), (static["cards"]["GENSET"], 634))
        self.assertEqual(set(cards), {"WATER", "SERVER", "GENSET", "PV-ROOF", "PV-INV", "CHP", "ATS-1", "BESS"})
        self.assertIn(["Положення", "Мережа (T1/T2)"], cards["ATS-1"]["rows"])
        self.sig("infra/pv/PV-INV-3/status", 768, "fault")
        cards = self.infra()["cards"]
        self.assertIn(["Стан", "в мережі 7 з 8; PV-INV-3: аварія"], cards["PV-INV"]["rows"])
        self.assertIn("warn", cards["PV-INV"])

    def test_island_totals(self):  # AC-59
        self.set_grid(lines=[("BW-1", 348.0, 0.9)] + [(c, 0.0, 0.9) for c, _p, _k in LINES if c != "BW-1"])
        self.set_infra(bess=-200.0)
        self.sig("infra/ats/position", 3, "pos_II")
        now = fields.Datetime.now()
        self.env["td.energy.outage"].search([]).unlink()
        self.env["td.energy.outage"].create(
            {"ts_start": now - timedelta(minutes=2), "source": "ats", "state": "open", "load_before_kw": 626.0}
        )
        totals = self.infra()["totals"]
        self.assertEqual((totals["grid_kw"], totals["export_kw"], totals["load_kw"]), (0, 0, 348))
        self.assertEqual((totals["shed_kw"], totals["bess_mode"]), (278, "discharge"))
        for key in totals:
            self.assertFalse(key in ("island", "grid_ok") or key.startswith("genset_") and key != "genset_kva", key)

    def test_delta_deep_merge(self):  # AC-68
        self.set_grid()
        self.set_infra()
        patch = {"infra": {"totals": {"genset_kw": 348}}}
        ctx = {"changes": {"td.signal": {"infra/pv/PV-INV-1/p_kw"}}}
        self.provider("infra")._td_viewer_delta(patch, ctx)
        self.assertEqual(patch["infra"]["totals"]["genset_kw"], 348)
        self.assertEqual(patch["infra"]["totals"]["export_kw"], 42)
        patch = {}
        self.provider("infra")._td_viewer_delta(patch, {"changes": {"td.signal": {"infra/genset/x"}}})
        self.assertEqual(patch, {})
        self.provider("energy")._td_viewer_delta(patch, {"changes": {"mrp.production": {1}}})
        self.assertIn("energy", patch)

    def test_providers_registered(self):  # AC-69
        for name, seq, sections in (("energy", 100, ("energy",)), ("infra", 150, ("infra",))):
            model = "td.viewer.provider.%s" % name
            self.assertIn(model, self.env.registry)
            prov = self.env[model]
            self.assertEqual((prov._td_sequence, tuple(prov._td_sections)), (seq, sections))
            self.assertFalse(set(prov._inherit) - {"base"})
            self.assertEqual(prov._td_group, "td_factory3d.group_td_user")
            prov._td_viewer_collect({}, {})
            prov._td_viewer_delta({}, {})
        self.assertIn("mrp.production", self.env["td.viewer.provider.energy"]._td_viewer_bus_models())
