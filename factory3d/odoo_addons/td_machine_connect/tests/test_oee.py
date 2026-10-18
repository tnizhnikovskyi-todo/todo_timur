"""AC-39…AC-44: OEE за фактом (R-13), записи за зміну й крон (R-14)."""

from datetime import timedelta

from odoo.tests import tagged

from ..tools import oee
from .common import D0, F3DMachineCase, kt


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestOee(F3DMachineCase):
    def loss(self, name, planned=False):
        return self.env["mrp.workcenter.productivity.loss"].create(
            {"name": name, "loss_id": self.env.ref("mrp.category_availability").id, "td_planned": planned}
        )

    def scenario(self, m, work, pieces, cycle, downs, bad=0):
        """Зміна 07:00–10:30: `work` хв `working` із завданням, далі прості `downs=[(state, хв, причина)]`."""
        wo = self.make_mo(m.workcenter_id, qty=max(int(pieces), 1), cycle=cycle).workorder_ids[:1]
        Log, Downtime = self.env["td.machine.state.log"].sudo(), self.env["td.downtime"].sudo()
        t = kt("07:00")
        Log.create(
            {
                "machine_id": m.id,
                "state": "working",
                "date_start": t,
                "date_end": t + timedelta(minutes=work),
                "workorder_id": wo.id,
                "pieces": pieces,
            }
        )
        t += timedelta(minutes=work)
        for state, minutes, name in downs:
            end = t + timedelta(minutes=minutes)
            Log.create({"machine_id": m.id, "state": state, "date_start": t, "date_end": end})
            Downtime.create(
                {
                    "machine_id": m.id,
                    "state_kind": state,
                    "date_start": t,
                    "date_end": end,
                    "loss_id": name.id,
                }
            )
            t = end
        if bad:
            self.env["stock.scrap"].sudo().create(
                {
                    "product_id": self.fg.id,
                    "scrap_qty": bad,
                    "workorder_id": wo.id,
                    "production_id": wo.production_id.id,
                    "state": "done",
                    "date_done": kt("10:00"),
                }
            )
        return wo

    def oee_of(self, m):
        return m._f3d_oee(kt("07:00"), kt("10:30"))

    def test_saw1_macket(self):
        wait, tool, unknown = (
            self.loss("Очікування матеріалу"),
            self.loss("Заміна інструменту"),
            self.loss("Не вказано"),
        )
        self.scenario(self.m_saw, 176, 80, 2.2, [("idle", 16, wait), ("setup", 10, tool), ("idle", 8, unknown)])
        res = self.oee_of(self.m_saw)
        self.assertEqual(res["source"], "machine")
        self.assertAlmostEqual(res["ppt_min"], 210, 3)
        self.assertAlmostEqual(res["run_min"], 176, 3)
        self.assertAlmostEqual(res["availability"], 0.8381, 3)
        self.assertAlmostEqual(res["performance"], 1.0, 4)
        self.assertAlmostEqual(res["quality"], 1.0, 4)
        self.assertAlmostEqual(res["oee"], 0.838, 3)
        self.assertEqual([x["minutes"] for x in res["losses"]], [16.0, 10.0, 8.0])
        self.assertEqual(
            [x["name"] for x in res["losses"]], ["Очікування матеріалу", "Заміна інструменту", "Не вказано"]
        )
        # чиста функція дає той самий результат на тому самому вході
        iv = [(kt("07:00"), kt("07:00") + timedelta(minutes=176))]
        direct = oee.compute_oee(
            {
                "ppt": [(kt("07:00"), kt("10:30"))],
                "run": iv,
                "run_wo": iv,
                "idle": [(kt("09:56"), kt("10:30"))],
                "pieces": {1: 80},
                "cycles": {1: 2.2},
            }
        )
        self.assertAlmostEqual(direct["oee"], res["oee"], 4)

    def test_saw1_real(self):
        wait, tool, unknown = (
            self.loss("Очікування матеріалу"),
            self.loss("Заміна інструменту"),
            self.loss("Не вказано"),
        )
        self.scenario(self.m_saw, 176, 76, 2.2, [("idle", 16, wait), ("setup", 10, tool), ("idle", 8, unknown)], bad=1)
        res = self.oee_of(self.m_saw)
        self.assertAlmostEqual(res["performance"], 0.95, 4)
        self.assertAlmostEqual(res["quality"], 0.9868, 4)
        self.assertAlmostEqual(res["oee"], 0.7857, 3)
        self.assertEqual(res["qty_bad"], 1)

    def test_cnc2(self):
        down = [
            ("setup", 11, self.loss("Налагодження")),
            ("idle", 5, self.loss("Очікування матеріалу")),
            ("setup", 23, self.loss("Заміна інструменту")),
            ("fault", 48, self.loss("Поломка")),
            ("idle", 58, self.loss("Не вказано")),
        ]
        self.scenario(self.m_ua, 65, 32, 2.0, down)
        res = self.oee_of(self.m_ua)
        self.assertAlmostEqual(res["oee"], 0.305, 3)
        self.assertAlmostEqual(res["fault_min"], 48, 3)
        self.assertAlmostEqual(res["unexplained_min"], 0, 3)

    def test_saw3(self):
        down = [
            ("setup", 14, self.loss("Налагодження")),
            ("idle", 81, self.loss("Очікування матеріалу")),
            ("idle", 12, self.loss("Не вказано")),
        ]
        self.scenario(self.m_io, 103, 114, 0.9, down)
        res = self.oee_of(self.m_io)
        self.assertAlmostEqual(res["availability"], 0.4905, 3)
        self.assertAlmostEqual(res["performance"], 0.996, 3)
        self.assertAlmostEqual(res["oee"], 0.488, delta=0.001)

    def test_period_two_shifts(self):
        Shift = self.env["td.oee.shift"].sudo()
        base = {"machine_id": self.m_saw.id, "state": "closed", "source": "machine", "has_data": True, "ppt_min": 480}
        rows = Shift.create(
            [
                dict(base, date=D0, run_min=400, run_wo_min=400, ideal_min=396, qty_total=180, qty_bad=2),
                dict(base, date=D0 + timedelta(days=1), run_min=360, run_wo_min=360, ideal_min=350, qty_total=159),
            ]
        )
        msg = rows.action_oee_period()["params"]["message"]
        self.assertIn("A 0,79 · P 0,98 · Q 0,99 · OEE 0,77", msg)
        self.assertIn("SAW-T", msg)

    def test_nodata_coverage(self):
        Log = self.env["td.machine.state.log"].sudo()
        Log.create({"machine_id": self.m_saw.id, "state": "nodata", "date_start": kt("07:00"), "date_end": kt("07:30")})
        Log.create(
            {"machine_id": self.m_saw.id, "state": "working", "date_start": kt("07:30"), "date_end": kt("11:30")}
        )
        res = self.m_saw._f3d_oee(kt("07:00"), kt("15:30"))
        self.assertAlmostEqual(res["ppt_min"], 450, 3)
        self.assertAlmostEqual(res["nodata_min"], 30, 3)
        self.assertAlmostEqual(res["coverage"], 0.9375, 4)
        self.assertTrue(res["incomplete"])

    def test_planned_stop(self):
        Log = self.env["td.machine.state.log"].sudo()
        Log.create({"machine_id": self.m_saw.id, "state": "idle", "date_start": kt("07:00"), "date_end": kt("07:20")})
        self.env["td.downtime"].sudo().create(
            {
                "machine_id": self.m_saw.id,
                "state_kind": "idle",
                "date_start": kt("07:00"),
                "date_end": kt("07:20"),
                "loss_id": self.loss("Перерва", planned=True).id,
            }
        )
        res = self.m_saw._f3d_oee(kt("07:00"), kt("10:30"))
        self.assertAlmostEqual(res["planned_stop_min"], 20, 3)
        self.assertAlmostEqual(res["ppt_min"], 190, 3)
        self.assertEqual(res["losses"], [])

    def test_timelog_source(self):
        Prod = self.env["mrp.workcenter.productivity"].sudo()
        wc = self.wc_cnc
        Prod.create(
            {
                "workcenter_id": wc.id,
                "loss_id": self.env.ref("mrp.block_reason7").id,
                "date_start": kt("07:00"),
                "date_end": kt("09:00"),
            }
        )
        Prod.create(
            {
                "workcenter_id": wc.id,
                "loss_id": self.env.ref("mrp.block_reason1").id,
                "date_start": kt("09:00"),
                "date_end": kt("09:30"),
            }
        )
        res = self.m_cnc._f3d_oee(kt("07:00"), kt("10:30"))
        self.assertEqual(res["source"], "timelog")
        self.assertAlmostEqual(res["run_min"], 120, 3)
        self.assertAlmostEqual(res["fault_min"], 30, 3)
        self.assertAlmostEqual(res["unexplained_min"], res["ppt_min"] - 150, 3)

    def test_timelog_stale_open_record(self):
        """M-2: відкритий запис журналу часу з минулих діб не дає роботи; закритий нічний обрізається вікном."""
        Prod = self.env["mrp.workcenter.productivity"].sudo()
        wc = self.wc_cnc
        productive = self.env.ref("mrp.block_reason7")
        old = Prod.create(
            {"workcenter_id": wc.id, "loss_id": productive.id, "date_start": kt("06:36", D0 - timedelta(days=3))}
        )
        self.assertFalse(old.date_end)
        res = self.m_cnc._f3d_oee(kt("07:00"), kt("10:30"))
        self.assertEqual(res["source"], "timelog")
        self.assertAlmostEqual(res["run_min"], 0, 3)
        self.assertAlmostEqual(res["availability"], 0, 3)
        # відкритий запис, що почався незадовго до початку вікна, рахується від початку вікна
        Prod.create({"workcenter_id": wc.id, "loss_id": productive.id, "date_start": kt("06:30")})
        res = self.m_cnc._f3d_oee(kt("07:00"), kt("10:30"))
        self.assertAlmostEqual(res["run_min"], res["ppt_min"], 3)
        self.assertGreater(res["run_min"], 0)
        # закритий запис, що почався до вікна, обрізається до вікна
        old.write({"date_end": kt("08:00")})
        res = self.m_cnc._f3d_oee(kt("07:00"), kt("08:00"))
        self.assertAlmostEqual(res["run_min"], 60, 3)

    def test_cron_open_close_rotate(self):
        Shift = self.env["td.oee.shift"]
        Log = self.env["td.machine.state.log"].sudo()
        Log.create(
            {"machine_id": self.m_saw.id, "state": "working", "date_start": kt("07:00"), "date_end": kt("10:00")}
        )
        self.oee_tick("10:30")
        rec = Shift.search([("machine_id", "=", self.m_saw.id), ("date", "=", D0)])
        self.assertEqual(len(rec), 1)
        self.assertEqual(rec.state, "open")
        self.assertEqual(self.m_saw.oee_shift_id, rec)
        self.assertAlmostEqual(rec.run_min, 180, 3)
        self.oee_tick("15:35")
        rec = Shift.search([("machine_id", "=", self.m_saw.id), ("date", "=", D0)])
        self.assertEqual(rec.state, "closed")
        before = (rec.computed_at, rec.run_min)
        Log.create(
            {"machine_id": self.m_saw.id, "state": "working", "date_start": kt("10:00"), "date_end": kt("11:00")}
        )
        self.oee_tick("15:40")
        rec = Shift.search([("machine_id", "=", self.m_saw.id), ("date", "=", D0)])
        self.assertEqual((rec.computed_at, rec.run_min), before)
        # кнопка перерахунку змінює закритий запис (права менеджера)
        rec.with_user(self.user_f3d_manager).action_recompute()
        self.assertAlmostEqual(rec.run_min, 240, 3)
        self.assertEqual(rec.state, "closed")
        # ротація: старий інтервал зникає, запис OEE лишається
        old_end = kt("10:30") - timedelta(days=401)
        Log.create(
            {
                "machine_id": self.m_saw.id,
                "state": "idle",
                "date_start": old_end - timedelta(hours=1),
                "date_end": old_end,
            }
        )
        old_shift = Shift.sudo().create(
            {"machine_id": self.m_saw.id, "date": D0 - timedelta(days=401), "source": "machine", "state": "closed"}
        )
        self.env["td.machine.state.log"]._cron_rotate()
        self.assertFalse(Log.search([("date_end", "=", old_end)]))
        self.assertTrue(old_shift.exists())
