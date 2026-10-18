"""AC-26…AC-29, AC-35: живі показники (R-06), асиметрія (R-12 п. 3)."""

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from ..tools import live
from .common import TAGS, F3DEnergyCase

# R-06: P (кВт) і cos φ ліній, макет 12.10 10:30
LINES = {
    "BW-3": (1, 70.1, 0.92), "BW-2": (1, 80.5, 0.88), "C1": (1, 184.1, 0.90),
    "BW-1": (2, 106.9, 0.89), "BW-4": (2, 26.4, 0.92), "C2": (2, 158.0, 0.95),
}  # fmt: skip


@tagged(*TAGS)
class TestLivePure(F3DEnergyCase):
    def test_site_totals(self):  # AC-26
        lines = {c: {"section": s, "p": p, "cos": cos, "i": None, "rating_a": 630} for c, (s, p, cos) in LINES.items()}
        res = live.site_totals(lines, rating_kvar={1: 350, 2: 350})
        s1, s2 = res["sections"][1], res["sections"][2]
        self.assertAlmostEqual(s1["p"], 334.7, places=1)
        self.assertAlmostEqual(s1["cos_before"], 0.90, places=2)
        self.assertEqual(s1["pfc_q_now"], 100)
        self.assertAlmostEqual(s1["cos_after"], 0.97, places=2)
        self.assertAlmostEqual(s1["s"], 345.1, places=1)
        self.assertEqual(s2["pfc_q_now"], 50)
        self.assertAlmostEqual(s2["cos_before"], 0.93, places=2)
        self.assertAlmostEqual(res["p_now"], 626.0, places=1)
        self.assertAlmostEqual(res["s_now"], 645.0, delta=1.0)
        self.assertAlmostEqual(res["cos_before"], 0.91, places=2)
        self.assertAlmostEqual(res["cos_after"], 0.97, places=2)

    def test_measured_q_kvar_and_cos(self):
        lines = {"BW-3": {"section": 1, "p": 100.0, "cos": None, "rating_a": 630, "cos_nominal": 0.9}}
        res = live.site_totals(lines, q_kvar={1: 20.0}, rating_kvar={1: 350})
        q = 100.0 * 0.4843
        self.assertAlmostEqual(res["sections"][1]["q_pfc"], q - 20.0, places=1)
        self.assertEqual(live.pf_to_cos(-0.95), 0.95)
        self.assertAlmostEqual(live.pf_to_cos(1.9), 0.1, places=6)
        self.assertEqual(live.pf_to_cos(3.0), 0.0)

    def test_grid_split(self):  # AC-27
        self.assertEqual(live.grid_split(334.7, -376.7)[0], 0.0)
        self.assertAlmostEqual(live.grid_split(334.7, -376.7)[1], 42.0, places=6)
        self.assertEqual(live.grid_split(400.0, -100.0), (300.0, 0.0))
        self.assertEqual(live.grid_split(400.0, -100.0, island=True), (0.0, 0.0))
        self.assertEqual(
            (live.bess_mode(200), live.bess_mode(-200), live.bess_mode(0.5)), ("charge", "discharge", "idle")
        )

    def test_unbalance(self):  # AC-35 (чиста частина)
        self.assertAlmostEqual(live.unbalance_pct(171, 180, 168, 630), 4.05, places=2)
        self.assertAlmostEqual(live.unbalance_pct(140, 180, 150, 630), 14.89, places=2)
        self.assertIsNone(live.unbalance_pct(2, 3, 4, 630))


@tagged(*TAGS)
class TestLiveCron(F3DEnergyCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Node = cls.env["td.energy.node"]
        cls.Signal = cls.env["td.signal"]

    def put(self, values, seconds_ago=5):
        ts = fields.Datetime.now() - timedelta(seconds=seconds_ago)
        self.Signal._f3d_ingest([{"code": c, "ts": ts, "value": v} for c, v in values.items()])

    def put_lines(self, names=None):
        values = {}
        for code, (_s, p, cos) in LINES.items():
            if names is None or code in names:
                values["energy/lines/%s/p_now" % code] = p
                values["energy/lines/%s/cos_phi" % code] = cos
        self.put(values)

    def sig(self, code):
        return self.Signal.search([("code", "=", code)])

    def test_critical_kw(self):  # AC-28
        values = {
            "energy/consumers/LP-1/p_now": 5.6, "energy/consumers/LP-2/p_now": 23.2,
            "energy/consumers/LP-3/p_now": 9.5, "energy/consumers/DUST-1/p_now": 127.5,
            "energy/consumers/COMPRESSOR/p_now": 46.6, "energy/consumers/BOILER/p_now": 10.0,
            "energy/consumers/OFFICE/p_now": 17.6, "energy/consumers/EF-ELEC/p_now": 0.84,
            "energy/consumers/EF-CHG/p_now": 0.107, "energy/lines/BW-1/p_now": 106.9,
        }  # fmt: skip
        self.put(values)
        snap = self.Node._f3d_live_snapshot()
        self.assertAlmostEqual(snap["critical_kw"], 347.847, places=3)
        self.assertEqual(round(snap["critical_kw"]), 348)

    def test_cron_live_writes_totals(self):  # AC-29
        self.put_lines()
        values = {"energy/cells/Q1/p_now": 334.7, "energy/cells/Q2/p_now": -376.7}
        values.update({"infra/pv/PV-INV-%d/p_kw" % k: 58.5 for k in range(1, 9)})
        self.put(values)
        self.Node._cron_live()
        p_now = self.sig("energy/totals/p_now")
        self.assertAlmostEqual(p_now.last_value, 626.0, delta=0.1)
        self.assertEqual(p_now.last_ts.second, 0)
        self.assertAlmostEqual(self.sig("energy/totals/cos_phi").last_value, 0.97, places=2)
        self.assertAlmostEqual(self.sig("infra/totals/pv_now").last_value, 468.0, places=1)
        self.assertEqual(self.sig("infra/totals/grid_kw").last_value, 0.0)
        self.assertAlmostEqual(self.sig("infra/totals/export_kw").last_value, 42.0, places=1)
        self.assertEqual(self.Node.search([("code", "=", "PFC-1")]).pfc_q_now, 70)  # W1 D-09: крок 35 квар
        self.assertEqual(self.Node.search([("code", "=", "PFC-2")]).pfc_q_now, 35)
        self.assertTrue(self.env["td.energy.event"].search([("kind", "=", "pfc"), ("code", "=", "PFC-1")]))
        self.assertEqual(self.env.ref("td_energy.source_en_derived").state, "online")

    def test_cron_live_stale_feeders(self):  # AC-29 (3 несвіжі фідери)
        self.put_lines(names=("BW-3", "BW-2", "C1"))
        self.put({"energy/cells/Q1/p_now": 334.7, "energy/cells/Q2/p_now": 100.0})
        self.Node._cron_live()
        self.assertFalse(self.sig("energy/totals/p_now").last_ts)

    def test_asymmetry(self):  # AC-35
        now = fields.Datetime.now().replace(second=0, microsecond=0)
        t0, t1, t2 = now - timedelta(minutes=30), now - timedelta(minutes=20), now - timedelta(minutes=5)

        def phases(ts, a, b, c):
            self.Signal._f3d_ingest(
                [
                    {"code": "energy/lines/BW-1/i_%s" % ph, "ts": ts, "value": v}
                    for ph, v in zip("abc", (a, b, c), strict=True)
                ]
            )

        phases(t0, 171, 180, 168)
        self.Node._f3d_asymmetry(t0)
        unbal = self.sig("energy/lines/BW-1/i_unbal_pct")
        self.assertAlmostEqual(unbal.last_value, 4.05, places=2)
        phases(t1, 140, 180, 150)
        self.Node._f3d_asymmetry(t1)
        self.assertAlmostEqual(unbal.last_value, 14.89, places=2)
        phases(t2, 140, 180, 150)
        self.Node._f3d_asymmetry(t2)
        self.assertAlmostEqual(unbal.last_value, 14.89, places=2)
        self.assertEqual(unbal.status, "warn")  # min_duration_s = 900: 15 хв від першого порушення
        phases(now, 2, 3, 4)
        self.Node._f3d_asymmetry(now)
        self.assertAlmostEqual(unbal.last_value, 14.89, places=2)
