"""AC-06 (R-02 KPI), AC-07 (R-03 циліндри)."""

from odoo.tests import tagged

from ..tools import kpi
from .common import TAGS, ChpCase

DEV = [-6, 4, -2, 9, 28, -7, 3, -5, 2, -8, 5, -3, -12, 6, 1, -4]
CYL = [f"{row}{n}" for row in "AB" for n in range(1, 9)]


@tagged(*TAGS)
class TestKpi(ChpCase):
    def test_efficiency_and_co2(self):  # AC-06
        v = {"gas/flow": 109.0, "gen/p_kw": 400.0, "ht/q_total": 497.0, "eng/rpm": 1500.0, "gas/day": 1000.0,
             "ht/t_sup": 88.0, "ht/t_ret": 58.0}  # fmt: skip
        k = kpi.compute(v, 9.5, 1.98)
        self.assertEqual((k["fuel_kw"], k["eta_e"], k["eta_h"], k["eta_t"]), (1035.5, 38.6, 48.0, 86.6))
        self.assertEqual((k["co2_kgh"], k["co2_day_t"], k["dT"]), (215.8, 1.98, 30.0))
        k2 = kpi.compute({**v, "gas/flow": 199.0, "gen/p_kw": 800.0, "ht/q_total": 856.0}, 9.5, 1.98)
        self.assertEqual((k2["eta_e"], k2["eta_h"], k2["eta_t"], k2["co2_kgh"]), (42.3, 45.3, 87.6, 394.0))
        k3 = kpi.compute({**v, "eng/rpm": 900.0}, 9.5, 1.98)  # rpm < 1200 → η = 0
        self.assertEqual((k3["eta_e"], k3["eta_h"], k3["eta_t"]), (0.0, 0.0, 0.0))
        self.assertEqual(k3["fuel_kw"], 1035.5)
        k4 = kpi.compute({}, 9.5, 1.98)  # немає даних
        self.assertTrue(all(val is None for val in k4.values()))

    def test_kpi_from_state(self):
        self.idle()
        self.put({"gas/flow": 199.0, "gen/p_kw": 800.0, "ht/q_total": 856.0, "eng/rpm": 1500.0})
        k = self.pult(self.u_user).get_state()["k"]
        self.assertEqual((k["eta_e"], k["eta_h"], k["eta_t"]), (42.3, 45.3, 87.6))
        self.unit.write({"lhv_kwh_m3": 10.0})
        self.assertEqual(self.pult(self.u_user).get_state()["k"]["fuel_kw"], 1990.0)

    def test_cylinders(self):  # AC-07
        v = {f"cyl/{cid}/t": 470.0 + DEV[i] for i, cid in enumerate(CYL)}
        v["cyl/A5/plug_h"] = 3560.0
        v["eng/rpm"] = 1500.0
        th = self.unit._td_th()
        rows = {r["id"]: r for r in kpi.cylinders(CYL, v, th)}
        self.assertEqual(rows["A5"]["dev"], 27.3)
        self.assertEqual(kpi.cylinder_level(rows["A5"]["dev"], th), "warn")
        self.assertEqual(kpi.cylinder_level(rows["A1"]["dev"], th), "ok")
        self.assertEqual(kpi.cylinder_level(45.0, th), "alarm")
        self.assertEqual(kpi.plug_state(3560.0, th["plug_interval_h"]), (89, "Зношується"))
        self.assertEqual(kpi.plug_state(3900.0, 4000.0)[1], "Замінити")
        self.assertEqual(kpi.plug_state(1000.0, 4000.0)[1], "Норма")
        v["eng/rpm"] = 900.0
        rows = {r["id"]: r for r in kpi.cylinders(CYL, v, th)}
        self.assertIsNone(rows["A5"]["dev"])
        self.assertEqual(rows["A5"]["t"], 498.0)
