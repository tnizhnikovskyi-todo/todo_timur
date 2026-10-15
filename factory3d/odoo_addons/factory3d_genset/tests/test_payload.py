"""Повний payload переглядача з мостом: AC-22, AC-25, AC-30, AC-66, AC-70, AC-72, ТП-01, ТП-02."""
import statistics
import time
import unittest
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from . import test_rules
from .test_rules import GensetCase

PFX = "infra/genset/GENSET/"


@tagged("post_install", "-at_install")
class TestPayload(GensetCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if "f3d.viewer.event" not in cls.env:
            raise unittest.SkipTest("factory3d_viewer не встановлено")

    def payload(self, user=None, **kw):
        from odoo.addons.factory3d_viewer.tools.payload import PayloadBuilder
        return PayloadBuilder(self.env(user=user or self.user_reader), **kw).build()

    def provider(self):
        return self.env["f3d.viewer.provider.genset"]

    def collect(self):
        data = {}
        self.provider()._f3d_viewer_collect(data, {})
        return data["infra"]

    def crit(self):
        test_rules.TestCritical._nodes(self)

    def test_critical_items(self):  # AC-32, AC-22
        self.crit()
        self.signals["CR-L"].active = False
        self.link._cron_publish()
        infra = self.collect()
        self.assertEqual(infra["genset"]["GENSET"]["critical_missing"], ["energy/lines/CR-L/p_now"])
        card = infra["cards"]["GENSET"]
        self.assertEqual(len(card["items"]), 2)
        rows = dict(card["rows"])
        self.assertEqual(rows["Критичні споживачі зараз"], "22 кВт з 507 кВт")

    def test_stale_card(self):  # AC-25, R-12
        self.snap(ts=fields.Datetime.now() - timedelta(minutes=7))
        self.link._cron_publish()
        infra = self.collect()
        card = infra["cards"]["GENSET"]
        self.assertRegex(dict(card["rows"])["Зв'язок"], r"^втрачено з \d\d:\d\d$")
        self.assertRegex(card["warn"], r"^Зв'язок із контролером втрачено \(\d+ хв\)$")
        self.assertEqual(infra["genset"]["GENSET"]["state_label"], "немає даних")

    def test_full_payload_critical_kw_untouched(self):  # AC-30, AC-70
        self.crit()
        self.link._cron_publish()
        with_link = self.payload(full=True)["infra"]["totals"]
        self.link.active = False
        without = self.payload(full=True)["infra"]["totals"]
        self.assertIn("critical_kw", without)
        self.assertEqual(with_link["critical_kw"], without["critical_kw"])
        for key in ("grid_kw", "chp_kw", "pv_now", "bess_kw"):
            self.assertEqual(with_link.get(key), without.get(key), key)
        self.assertEqual(with_link["genset_kw"], 348.0)
        self.assertIs(with_link["island"], True)
        # запасний шлях R-04 п. 2
        self.link.active = True
        self.env["f3d.energy.node"].search([("is_critical", "=", True)]).write({"is_critical": False})
        self.set_param("critical_codes", "energy/consumers/CR-B/p_now")
        self.assertEqual(self.link._critical_kw()[0], 10.0)
        again = self.payload(full=True)["infra"]["totals"]
        self.assertEqual(again.get("critical_kw"), without.get("critical_kw"))
        self.assertIn("GENSET", self.payload(full=True)["infra"]["cards"])

    def test_delta_ac72(self):  # AC-72
        self.link._cron_publish()
        prov = self.provider()
        base = {"infra": {"cards": {"PV-INV": {"rows": [["Стан", "усі в мережі"]]}},
                          "totals": {"pv_now": 468, "chp_kw": 400, "critical_kw": 348}}}
        for code in (PFX + "state", "infra/ats/position"):
            patch = {"infra": {"cards": dict(base["infra"]["cards"]), "totals": dict(base["infra"]["totals"])}}
            prov._f3d_viewer_delta(patch, {"changes": {"f3d.signal": {code}}})
            infra = patch["infra"]
            self.assertIn("PV-INV", infra["cards"])
            self.assertIn("GENSET", infra["cards"])
            t = infra["totals"]
            self.assertEqual((t["pv_now"], t["chp_kw"], t["critical_kw"]), (468, 400, 348))
            self.assertEqual((t["genset_kw"], t["genset_kva"]), (348.0, 634))
            self.assertIn("island", t)
            self.assertIn("grid_ok", t)
        patch = {"infra": {"totals": {"pv_now": 468}}}
        prov._f3d_viewer_delta(patch, {"changes": {"f3d.signal": {"energy/totals/p_now"}}})
        self.assertEqual(patch, {"infra": {"totals": {"pv_now": 468}}})

    def _queries(self, func):
        cr = self.env.cr
        before = cr.sql_log_count
        func()
        return cr.sql_log_count - before

    def test_perf(self):  # AC-66, ТП-01, ТП-02
        self.crit()
        self.make_ats_signals()
        self.link._cron_publish()
        self.payload()  # прогрів кешів
        with_link = self._queries(lambda: self.payload())
        self.link.active = False
        without = self._queries(lambda: self.payload())
        self.link.active = True
        self.assertLessEqual(with_link - without, 8, (with_link, without))
        samples = []
        for _i in range(5):
            t0 = time.perf_counter()
            self.collect()
            samples.append(time.perf_counter() - t0)
        self.assertLessEqual(statistics.median(samples), 0.05, samples)
        # _publish_one з моками
        self.snap(ts=fields.Datetime.now() + timedelta(seconds=1))
        t0 = time.perf_counter()
        queries = self._queries(self.link._publish_one)
        self.assertLessEqual(queries, 40)
        self.assertLessEqual(time.perf_counter() - t0, 0.5)

    def make_ats_signals(self):
        self.make_ats(3, 0)
