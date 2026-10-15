from datetime import datetime
from unittest.mock import patch

from odoo.tests import tagged

from odoo.addons.factory3d_viewer.tools import dates, payload as payload_tools

from .common import F3dViewerBase, F3dViewerCase

# 2026-10-12 10:30 за Києвом = 07:30 UTC (літній час діє до 25.10)
START_0700 = "2026-10-12 04:00:00"


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestProductionSynthetic(F3dViewerBase):
    """Провайдер production на власних записах: R-06, R-07; AC-14, AC-15, AC-43."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        att = [(5, 0, 0)] + [(0, 0, {"name": "d%d" % d, "dayofweek": str(d), "hour_from": 7.0, "hour_to": 15.0,
                                     "day_period": "morning"}) for d in range(7)]
        cls.calendar = env["resource.calendar"].create(
            {"name": "TST зміна 07-15", "tz": "Europe/Kyiv", "attendance_ids": att})
        cls.wc1 = env["mrp.workcenter"].create({"name": "TST WC1", "code": "TSTWC1", "f3d_code": "TST-WC-1",
                                                "resource_calendar_id": cls.calendar.id})
        cls.wc2 = env["mrp.workcenter"].create({"name": "TST WC2", "code": "TSTWC2", "f3d_code": "TST-WC-2",
                                                "resource_calendar_id": cls.calendar.id})
        cls.finished = env["product.product"].create({"name": "TST finished", "default_code": "TST-FIN",
                                                      "is_storable": True})
        cls.comp = env["product.product"].create({"name": "TST comp", "default_code": "TST-CMP",
                                                  "is_storable": True})
        cls.bom = env["mrp.bom"].create({
            "product_tmpl_id": cls.finished.product_tmpl_id.id, "product_id": cls.finished.id, "product_qty": 1,
            "code": "T",
            "bom_line_ids": [(0, 0, {"product_id": cls.comp.id, "product_qty": 2})],
            "operation_ids": [(0, 0, {"name": "Op1", "workcenter_id": cls.wc1.id, "time_cycle_manual": 30}),
                              (0, 0, {"name": "Op2", "workcenter_id": cls.wc2.id, "time_cycle_manual": 20})]})
        cls.mo = env["mrp.production"].create({"product_id": cls.finished.id, "bom_id": cls.bom.id,
                                               "product_qty": 1})
        cls.mo.action_confirm()
        Loss = env["mrp.workcenter.productivity.loss"]
        cls.l_prod = Loss.search([("loss_type", "=", "productive")], limit=1)
        cls.l_avail = Loss.search([("loss_type", "=", "availability")], limit=1)

    def setUp(self):
        super().setUp()
        self.demo_clock("2026-10-12 10:30")

    def _data(self, user=None, **kw):
        return self.payload(user or self.user_f3d, **kw)

    def _mo(self, data):
        return next(m for m in data["productions"] if m["name"] == self.mo.name)

    def test_denied_without_mrp_group(self):
        """AC-14."""
        data = self._data(self.user_stock_only)
        self.assertFalse(data.get("productions"))
        self.assertFalse(data.get("workorders"))
        self.assertEqual(data["meta"]["sections"]["productions"], "denied")

    def test_workorder_states_derivation(self):
        """AC-43: резервування не підтверджене -> перше завдання waiting, друге pending, progress 0."""
        self.mo.reservation_state = "confirmed"
        mo = self._mo(self._data())
        self.assertEqual(mo["state"], "confirmed")
        self.assertEqual(mo["reservation_state"], "waiting")
        self.assertEqual(mo["progress"], 0.0)
        self.assertEqual(len(mo["workorders"]), 2)
        data = self._data()
        states = [data["workorders"][w]["state"] for w in self._mo(data)["workorders"]]
        self.assertEqual(states, ["waiting", "pending"])
        self.assertEqual([data["workorders"][w]["sequence"] for w in mo["workorders"]], [1, 2])

    def test_progress_demo_clock(self):
        """AC-15: відкритий журнал від 09:58 -> duration 32 на демо-годиннику."""
        wo = self.mo.workorder_ids.sorted("sequence")[0]
        wo.write({"state": "progress", "date_start": "2026-10-12 06:58:00"})
        self.env["mrp.workcenter.productivity"].create({
            "workcenter_id": self.wc1.id, "workorder_id": wo.id, "loss_id": self.l_prod.id,
            "date_start": "2026-10-12 06:58:00"})
        data = self._data()
        self.assertEqual(data["meta"]["now"], "2026-10-12 10:30")
        rec = data["workorders"]["WO%05d" % wo.id]
        self.assertEqual(rec["duration"], 32)
        self.assertEqual(rec["state"], "progress")
        self.assertEqual(rec["date_start"], "2026-10-12 09:58")
        self.assertLess(rec["progress"], 1.0)
        self.assertEqual(data["workcenters"]["TST-WC-1"]["current_workorder"], "WO%05d" % wo.id)
        self.assertEqual(data["workcenters"]["TST-WC-1"]["status"], "work")

    def test_oee_and_losses(self):
        """R-06: 176 продуктивних хвилин при зміні з 07:00 і now 10:30 -> oee 0.84; простій у losses."""
        Log = self.env["mrp.workcenter.productivity"]
        Log.create({"workcenter_id": self.wc1.id, "loss_id": self.l_prod.id, "date_start": START_0700,
                    "date_end": "2026-10-12 06:56:00"})
        Log.create({"workcenter_id": self.wc2.id, "loss_id": self.l_avail.id, "date_start": "2026-10-12 06:40:00",
                    "date_end": "2026-10-12 06:55:00"})
        data = self._data()
        wc1, wc2 = data["workcenters"]["TST-WC-1"], data["workcenters"]["TST-WC-2"]
        self.assertEqual(wc1["productive_minutes"], 176)
        self.assertEqual(wc1["oee"], 0.84)
        self.assertEqual(wc1["status"], "idle")
        self.assertEqual(wc2["losses"], [{"reason": self.l_avail.name, "minutes": 15}])

    def test_blocked_workcenter_stops(self):
        """AC-42 (CNC-2): відкрита поломка -> working_state blocked, status stop."""
        self.env["mrp.workcenter.productivity"].create({
            "workcenter_id": self.wc2.id, "loss_id": self.l_avail.id, "date_start": "2026-10-12 06:42:00"})
        rec = self._data()["workcenters"]["TST-WC-2"]
        self.assertEqual(rec["working_state"], "blocked")
        self.assertEqual(rec["status"], "stop")
        self.assertEqual(rec["losses"][0]["minutes"], 48)

    def test_queue_max_8(self):
        data = self._data()
        self.assertLessEqual(len(data["workcenters"]["TST-WC-1"]["queue"]), 8)

    def test_components_and_energy_keys(self):
        mo = self._mo(self._data())
        self.assertEqual(mo["route"], "T")
        self.assertEqual([c["product"] for c in mo["components"]], ["TST-CMP"])
        self.assertEqual(mo["components"][0]["qty"], 2)
        self.assertIn("energy_kwh", mo)
        self.assertNotIn("energy_cost", mo)  # factory3d_energy немає / користувач без групи вартості

    def test_energy_cost_requires_group(self):
        """AC-60 (мок групи): із групою — ключ є, кіоск — немає."""
        orig = payload_tools.group_ok

        def fake(env, xmlid):
            return True if xmlid == payload_tools.ENERGY_COST_GROUP else orig(env, xmlid)
        with patch.object(payload_tools, "group_ok", side_effect=fake):
            self.assertIn("energy_cost", self._mo(self._data()))
            self.assertNotIn("energy_cost", self._mo(self._data(kiosk=True)))

    def test_delta_selects_mo(self):
        from odoo.addons.factory3d_viewer.tools.payload import DeltaBuilder
        res = DeltaBuilder(self.env(user=self.user_f3d), since=None, changes={"mrp.production": {self.mo.name}}).build()
        patch_ = res["patch"]
        self.assertEqual([m["name"] for m in patch_["productions"]], [self.mo.name])
        self.assertEqual(len(patch_["workorders"]), 2)
        self.assertEqual(set(patch_["workcenters"]), {"TST-WC-1", "TST-WC-2"})


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestProduction(F3dViewerCase):
    """Демо-база: рівність із dist/odoo_demo.json ± 0,01."""

    def _data(self, **kw):
        return self.payload(self.user_f3d, **kw)

    def test_workcenters_35(self):
        self.assertEqual(len(self._data()["workcenters"]), 35)

    def test_oee_saw1_084(self):
        """AC-42. Еталон 176 хв / 0,84 — для dist/odoo_demo.json; шаблон на CE має інші журнали часу
        (перекриття, інші тривалості), тому очікування рахуються з `mrp.workcenter.productivity` за R-06."""
        wc = self._data()["workcenters"]["SAW-1"]
        env = self.env
        now = dates.utc("2026-10-12 10:30")
        today_start = dates.utc("2026-10-12 00:00")
        logs = env["mrp.workcenter.productivity"].search([
            ("workcenter_id.f3d_code", "=", "SAW-1"), ("loss_id.loss_type", "=", "productive"),
            "|", ("date_end", "=", False), ("date_start", ">=", today_start)])
        expected = round(sum(
            (lg.duration or 0.0) if lg.date_end
            else max(0.0, (now - max(lg.date_start, today_start)).total_seconds() / 60) for lg in logs))
        self.assertTrue(expected)
        self.assertEqual(wc["productive_minutes"], expected)
        workcenter = env["mrp.workcenter"].search([("f3d_code", "=", "SAW-1")])
        now_local = datetime.strptime(dates.local(now), dates.FMT)
        start, end = env["f3d.viewer.provider.production"]._shift(workcenter, now_local, now_local.weekday())
        elapsed = max(1.0, (min(now_local, end) - start).total_seconds() / 60)
        self.assertAlmostEqual(wc["oee"], max(0.0, min(1.0, expected / elapsed)), delta=0.01)
        if expected == 176:  # еталонна демо-база
            self.assertAlmostEqual(wc["oee"], 0.84, delta=0.01)
        self.assertEqual(wc["status"], "work")

    def test_cnc2_stop_losses(self):
        wc = self._data()["workcenters"]["CNC-2"]
        self.assertEqual(wc["status"], "stop")
        # «Поломка» у еталонній демо; у шаблоні на CE — стандартна втрата Odoo «Equipment Failure»
        self.assertTrue(any(x["reason"] in ("Поломка", "Equipment Failure") for x in wc["losses"]), wc["losses"])

    def test_workorder_states_derivation(self):
        data = self._data()
        waiting = [m for m in data["productions"] if m.get("reservation_state") == "waiting"]
        self.assertEqual(len(waiting), 2)
        for mo in waiting:
            self.assertEqual(mo["progress"], 0.0)
            self.assertEqual(data["workorders"][mo["workorders"][0]]["state"], "waiting")

    def test_progress_demo_clock(self):
        data = self._data()
        self.assertEqual(data["meta"]["now"], "2026-10-12 10:30")
        prog = [w for w in data["workorders"].values() if w["state"] == "progress"]
        self.assertEqual(len(prog), 30)
        self.assertTrue(all(w["duration"] >= 0 and w["date_planned_finished"] for w in prog))

    def test_energy_kwh_mo231(self):
        mo = next(m for m in self._data()["productions"] if m["name"] == "WH/MO/00231")
        self.assertAlmostEqual(mo["energy_kwh"], 86.2, delta=0.1)
        self.assertNotIn("energy_cost", mo)

    def test_energy_cost_requires_group(self):
        """AC-60."""
        orig = payload_tools.group_ok

        def fake(env, xmlid):
            return True if xmlid == payload_tools.ENERGY_COST_GROUP else orig(env, xmlid)
        with patch.object(payload_tools, "group_ok", side_effect=fake):
            mo = next(m for m in self._data()["productions"] if m["name"] == "WH/MO/00231")
            self.assertAlmostEqual(mo["energy_cost"], 724, delta=2)
            mo = next(m for m in self._data(kiosk=True)["productions"] if m["name"] == "WH/MO/00231")
            self.assertNotIn("energy_cost", mo)

    def test_queue_max_8(self):
        for wc in self._data()["workcenters"].values():
            self.assertLessEqual(len(wc["queue"]), 8)
