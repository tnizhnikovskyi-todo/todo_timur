import unittest
from datetime import timedelta

from odoo import fields

from odoo.tests import tagged

from .test_rules import GensetCase

PFX = "infra/genset/GENSET/"


@tagged("post_install", "-at_install")
class TestProvider(GensetCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "td.viewer.event" not in cls.env:
            raise unittest.SkipTest("td_viewer3d не встановлено")

    def collect(self):
        payload = {}
        self.env["td.viewer.provider.genset"]._td_viewer_collect(payload, {})
        return payload["infra"]

    def test_card_rows(self):  # AC-22, AC-30
        self.link._cron_publish()
        infra = self.collect()
        card = infra["cards"]["GENSET"]
        self.assertEqual(len(card["rows"]), 14)
        rows = dict(card["rows"])
        self.assertEqual(rows["Потужність"], "634 кВА / 507 кВт (основна)")
        self.assertEqual(rows["Стан"], "під навантаженням · 348 кВт (68,6 %)")
        self.assertEqual(rows["Паливо"], "82 % · 500 л")
        self.assertEqual(rows["Автономність"], "≈ 5,2 год при 69 %")
        self.assertEqual(rows["Мотогодини"], "1 213 · до ТО 37")
        self.assertIn("острів", rows["Мережа"])
        self.assertTrue(card["note"])
        node = infra["genset"]["GENSET"]
        self.assertEqual((node["p_kw"], node["fuel_pct"], node["state"]), (348.0, 0.82, 7))
        self.assertEqual(node["state_label"], "під навантаженням")
        totals = infra["totals"]
        self.assertEqual(totals["genset_kw"], 348.0)
        self.assertEqual(totals["genset_kva"], 634)
        self.assertIsInstance(totals["genset_kva"], int)
        self.assertIs(totals["island"], True)
        self.assertIs(totals["grid_ok"], False)
        self.assertNotIn("critical_kw", totals)

    def test_order_and_bus_models(self):  # AC-23
        prov = self.env["td.viewer.provider.genset"]
        self.assertEqual(prov._td_sequence, 155)
        self.assertEqual(prov._td_viewer_bus_models(), ["maintenance.equipment", "td.signal"])
        self.assertNotIn("td.viewer.provider", type(prov)._inherit if isinstance(type(prov)._inherit, list) else [])

    def test_no_link_static(self):  # AC-24
        self.link.unlink()
        payload = {}
        self.env["td.viewer.provider.genset"]._td_viewer_collect(payload, {})
        self.assertNotIn("infra", payload)

    def test_delta_condition(self):  # AC-26
        prov = self.env["td.viewer.provider.genset"]
        self.link._cron_publish()
        patch = {}
        prov._td_viewer_delta(patch, {"changes": {"td.signal": {"energy/other/x"}}})
        self.assertEqual(patch, {})
        prov._td_viewer_delta(patch, {"changes": {"td.signal": {PFX + "state"}}})
        self.assertIn("GENSET", patch["infra"]["cards"])
        patch = {}
        prov._td_viewer_delta(patch, {"changes": {"maintenance.equipment": {"GENSET"}}})
        self.assertIn("genset", patch["infra"])

    def test_delta_deep_merge(self):  # AC-72
        self.link._cron_publish()
        patch = {"infra": {"cards": {"PV-INV": {"rows": []}}, "totals": {"pv_now": 468, "chp_kw": 400}}}
        self.env["td.viewer.provider.genset"]._td_viewer_delta(patch, {"changes": {"td.signal": {PFX + "state"}}})
        infra = patch["infra"]
        self.assertIn("PV-INV", infra["cards"])
        self.assertIn("GENSET", infra["cards"])
        self.assertEqual((infra["totals"]["pv_now"], infra["totals"]["chp_kw"]), (468, 400))
        self.assertEqual(infra["totals"]["genset_kw"], 348.0)

    def test_amf_row_and_rounding(self):  # AC-31, AC-45
        self.link.amf_master = "ats"
        self.link._cron_publish()
        self.assertEqual(dict(self.collect()["cards"]["GENSET"]["rows"])["Логіка AMF"], "ATyS p (головний)")
        self.snap(
            ts=fields.Datetime.now().replace(microsecond=0) + timedelta(seconds=5),
            p_kw=348.04,
            oil_bar=4.456,
            hours=1213.2,
        )
        self.link._cron_publish()
        node = self.collect()["genset"]["GENSET"]
        self.assertEqual((node["p_kw"], node["oil_bar"], node["hours"]), (348.0, 4.46, 1213.2))
