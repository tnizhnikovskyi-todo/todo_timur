"""AC-81…AC-85: міграція демо (R-27, §5.3). Синтетичні дані; повна копія демо — `TestMigrationDemo` (skip без неї)."""

import json
from datetime import timedelta
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import tagged

from .. import hooks
from .common import F3DMachineCase

CSV = "odoo.addons.td_machine_connect.hooks._csv_rows"
LOGGER = "odoo.addons.td_machine_connect"
REAL_CSV_ROWS = hooks._csv_rows


def machines_csv(rows):
    """Підміна `_csv_rows`: `mc_machines` — задані рядки, `mc_signals` — справжній файл."""

    def fake(env, name):
        return rows if name == "mc_machines" else REAL_CSV_ROWS(env, name)

    return patch(CSV, side_effect=fake)


def row(code, protocol, source, io_unit="", io_slot="", operator=""):
    return {
        "code": code,
        "protocol": protocol,
        "source": source,
        "io_unit": io_unit,
        "io_slot": io_slot,
        "auto_start_mode": "job_or_single",
        "operator_code": operator,
    }


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestMigrationClean(F3DMachineCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        WC = cls.env["mrp.workcenter"]
        cls.wc_m1 = WC.create({"name": "Мігр. UA", "td_code": "MIG-1", "resource_calendar_id": cls.cal.id})
        cls.wc_m2 = WC.create({"name": "Мігр. IO", "td_code": "MIG-2", "resource_calendar_id": cls.cal.id})
        cls.eq_m1 = cls.env["maintenance.equipment"].create({"name": "Мігр. UA", "td_code": "MIG-1"})
        cls.rows = [
            row("MIG-1", "opcua", "UA-SAW-T", operator="OP-SAW-T"),
            row("MIG-2", "io", "MB-U80-T", 80, 3),
            row("NOPE-1", "opcua", "UA-SAW-T"),
        ]

    def run_mig(self):
        with machines_csv(self.rows):
            return hooks.run_migration(self.env)

    def test_clean_db_zero(self):
        """Чиста база: кроки 0–6 без демо-даних нічого не створюють, окрім сигналів; `done`."""
        Machine = self.env["td.machine"].with_context(active_test=False)
        before = Machine.search_count([])
        with machines_csv([]):
            rep = hooks.run_migration(self.env)
        self.assertEqual(Machine.search_count([]), before)
        for key in ("machines", "with_operator", "machines_wired", "timelog_marked", "downtimes_created"):
            self.assertEqual(rep[key], 0, key)
        self.assertEqual(rep["timelog_created"], 0)
        self.assertEqual(rep["signals_created"], 0)  # хук установки вже створив 207 сигналів
        self.assertEqual(rep["state"], "done")
        stored = json.loads(self._icp().get_param(hooks.REPORT_KEY))
        self.assertEqual(stored["state"], "done")
        self.assertEqual(self.env["td.machine"]._td_run_migration()["params"]["type"], "info")

    def test_installed_signals(self):
        """Сигнали модуля (207), створені хуком установки: `origin='module'`, xml-id, `machine_state` не видно в 3D."""
        Sig = self.env["td.signal"].with_context(active_test=False)
        rows = hooks._signal_rows("SAW-1", "opcua", None, None)
        sig = Sig.search([("code", "=", "workcenters/SAW-1/state")])
        self.assertEqual(sig.origin, "module")
        self.assertEqual(sig.source_id.code, "UA-SAW-1")
        self.assertTrue(self.env.ref("td_machine_connect.sig_workcenters_saw_1_state"))
        self.assertFalse(Sig.search([("code", "=", "workcenters/SAW-1/machine_state")]).viewer_visible)
        self.assertEqual(Sig.search([("code", "=", "workcenters/SAW-1/machine_state")]).source_id.code, "MC-DERIVED")
        self.assertTrue(Sig.search([("code", "=", "equipment/CUTOPT/cmd")]))
        self.assertFalse(Sig.search([("code", "=", "mc/cutopt/cmd")]))
        self.assertEqual(len(rows), 8)  # 7 OPC UA + обчислений стан

    def test_machines_signals(self):
        with self.assertLogs(LOGGER, "WARNING") as logs:
            rep = self.run_mig()
        self.assertTrue(any("NOPE-1" in line for line in logs.output))
        self.assertEqual((rep["machines"], rep["with_operator"], rep["with_equipment"]), (2, 1, 1))
        self.assertEqual(rep["signals_created"], 20)  # MIG-1: 7 + 1, MIG-2: 3 + 1, NOPE-1 (без РЦ): 7 + 1
        self.assertEqual(rep["machines_wired"], 2)
        m1 = self.env["td.machine"].search([("workcenter_id", "=", self.wc_m1.id)])
        m2 = self.env["td.machine"].search([("workcenter_id", "=", self.wc_m2.id)])
        self.assertEqual((m1.protocol, m2.protocol, m2.io_slot), ("opcua", "io", 3))
        self.assertEqual(m1.employee_id, self.emp_saw)
        self.assertEqual(m1.equipment_id, self.eq_m1)
        self.assertEqual(m1.source_id, self.src_saw)
        self.assertEqual(m1.sig_state_id.code, "workcenters/MIG-1/state")
        self.assertEqual(m1.sig_state_id.origin, "module")
        self.assertEqual(m1.sig_state_id.workcenter_id, self.wc_m1)
        self.assertEqual(m1.sig_machine_state_id.source_id, self.src_der)
        self.assertFalse(m1.sig_machine_state_id.viewer_visible)
        self.assertTrue(
            all(
                m1[f]
                for f in (
                    "sig_mode_id",
                    "sig_alarm_id",
                    "sig_pieces_id",
                    "sig_job_id",
                    "sig_event_id",
                    "sig_job_cmd_id",
                )
            )
        )
        self.assertEqual(m2.sig_state_id.address["addr"], 6)  # DI_RUN = 2·3
        self.assertEqual(m2.sig_alarm_id.address["addr"], 7)
        self.assertEqual(m2.sig_pieces_id.address["addr"], 12)  # HR = 4·3
        self.assertEqual(m2.sig_state_id.source_id, self.src_io)
        self.assertTrue(self.env.ref("td_machine_connect.sig_workcenters_mig_1_state"))
        self.assertEqual(self.env["td.machine"]._td_code_map().get("workcenters/MIG-1/state"), (m1.id, "state"))

    def test_bind_existing(self):
        """Наявний сигнал чужого модуля: лише `source_id`, `address`, `period_s`…; `module`/`origin` без змін."""
        Sig = self.env["td.signal"]
        sig = Sig.create(
            {
                "code": "workcenters/MIG-1/pieces_out",
                "name": "Лічильник (каталог)",
                "kind": "counter",
                "module": "telemetry",
                "origin": "catalog",
                "address": {"nodeid": "ns=2;s=old", "mode": "subscribe"},
                "period_s": 5,
            }
        )
        rep = self.run_mig()
        sig.invalidate_recordset()
        self.assertEqual(rep["signals_created"], 19)
        self.assertEqual(rep["signals_bound"], 1)
        self.assertEqual((sig.module, sig.origin), ("telemetry", "catalog"))
        self.assertEqual(sig.source_id, self.src_saw)
        self.assertIn("RelativePiecesOut", sig.address["nodeid"])
        self.assertEqual(sig.period_s, 60)
        self.assertEqual(sig.name, "Лічильник (каталог)")
        self.assertEqual(self.run_mig()["signals_bound"], 0)

    def test_params(self):
        icp = self._icp()
        for env_name, read, mode in (("test", "True", "collector"), ("prod", "False", "manual")):
            icp.set_param("td.base.environment", env_name)
            icp.search([("key", "in", [hooks.P + "read_enabled", hooks.P + "cutting_mode"])]).unlink()
            hooks.params(self.env)
            self.assertEqual(icp.get_param(hooks.P + "read_enabled"), read)
            self.assertEqual(icp.get_param(hooks.P + "cutting_mode"), mode)
        icp.set_param(hooks.P + "read_enabled", "True")  # наявні не перезаписуються
        hooks.params(self.env)
        self.assertEqual(icp.get_param(hooks.P + "read_enabled"), "True")

    def test_losses(self):
        cat = self.env.ref("mrp.category_availability")
        brk = self.env["mrp.workcenter.productivity.loss"].create({"name": "Перерва (тест)", "loss_id": cat.id})
        self.env["ir.model.data"].create(
            {"module": "factory3d", "name": "loss_break", "model": brk._name, "res_id": brk.id}
        )
        self.assertFalse(brk.td_planned)
        res = hooks.losses(self.env)
        self.assertEqual(res["loss_planned"], 1)
        self.assertTrue(brk.td_planned)
        self.assertEqual(hooks.losses(self.env)["loss_planned"], 0)
        if not self.env["res.lang"]._lang_get("uk_UA"):
            self.assertEqual(res["loss_translated"], 0)

    def test_sheets(self):
        Cat, Tmpl = self.env["product.category"], self.env["product.template"]
        cat = Cat.create({"name": "Плитні матеріали"})
        child = Cat.create({"name": "ДСП", "parent_id": cat.id})
        names = (
            ("ДСП 16 мм Дуб Сонома 2800×2070", child),
            ("ЛДСП 18,5 мм Білий 2750x1830", child),
            ("ХДФ 3 мм білий 2800×2070", cat),
            ("Плита без розмірів", cat),
        )
        tmpls = [Tmpl.create({"name": n, "categ_id": c.id}) for n, c in names]
        with self.assertLogs(LOGGER, "WARNING"):
            res = hooks.sheets(self.env)
        self.assertEqual(res["sheets_sized"], 3)
        dims = [(t.td_sheet_length_mm, t.td_sheet_width_mm, t.td_thickness_mm) for t in tmpls]
        self.assertEqual(dims, [(2800, 2070, 16), (2750, 1830, 18), (2800, 2070, 3), (0, 0, 0)])
        with self.assertLogs(LOGGER, "WARNING"):
            self.assertEqual(hooks.sheets(self.env)["sheets_sized"], 0)

    def test_stacks(self):
        loc = self.env["stock.location"].create(
            {
                "name": "PLT-M1",
                "location_id": self.loc_t1.location_id.id,
                "td_code": "PLT-M1",
                "td_loc_kind": "stack",
                "td_capacity": 60,
            }
        )
        op = self.env["stock.warehouse.orderpoint"].create(
            {"product_id": self.board.id, "location_id": loc.id, "product_min_qty": 5, "product_max_qty": 20}
        )
        res = hooks.stacks(self.env)
        stack = self.env["td.gantry.stack"].search([("location_id", "=", loc.id)])
        self.assertEqual(stack.orderpoint_id, op)
        self.assertEqual(stack.state, "unknown")
        self.assertGreaterEqual(res["stacks"], 3)
        self.assertGreaterEqual(res["orderpoints_linked"], 1)
        count = self.env["td.gantry.stack"].search_count([])
        self.assertEqual(hooks.stacks(self.env)["stacks"], res["stacks"])
        self.assertEqual(self.env["td.gantry.stack"].search_count([]), count)

    def _demo_log(self, wc, loss_xmlid, start, end):
        rec = self.env["mrp.workcenter.productivity"].create(
            {
                "workcenter_id": wc.id,
                "loss_id": self.env.ref(loss_xmlid).id,
                "date_start": self.kt(start),
                "date_end": self.kt(end) if end else False,
            }
        )
        # Записи до установки модуля мали б умовчання колонки: ставимо його явно.
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE mrp_workcenter_productivity SET td_source='operator', td_auto=false, td_downtime_id=NULL "
            "WHERE id=%s",
            (rec.id,),
        )
        rec.invalidate_recordset()
        return rec

    def test_demo_journal(self):
        eq = self.env["maintenance.equipment"].search_f3d("UA-T")
        req = self.env["maintenance.request"].create(
            {"name": "Аварія UA-T", "equipment_id": eq.id, "maintenance_type": "corrective"}
        )
        logs = [
            self._demo_log(self.wc_cnc, "mrp.block_reason1", "08:00", "08:30"),
            self._demo_log(self.wc_cnc, "mrp.block_reason2", "09:00", "09:20"),
            self._demo_log(self.wc_cnc, "mrp.block_reason0", "09:30", "09:40"),
            self._demo_log(self.wc_ua, "mrp.block_reason1", "09:42", None),
            self._demo_log(self.wc_ua, "mrp.block_reason7", "09:00", "09:40"),
        ]
        Log = self.env["mrp.workcenter.productivity"]
        count = Log.search_count([])
        # create_date ставить SQL (реальний час транзакції), не freezegun
        now = self.env.cr.now().replace(tzinfo=None)
        install_ts = now + timedelta(hours=1)
        res = hooks.demo_journal(self.env, install_ts)
        self.assertEqual(res, {"timelog_marked": 5, "downtimes_created": 4, "downtimes_open": 1, "requests_linked": 1})
        self.assertEqual(Log.search_count([]), count)
        self.assertEqual({r.td_source for r in logs}, {"demo"})
        kinds = [r.td_downtime_id.state_kind for r in logs[:4]]
        self.assertEqual(kinds, ["fault", "setup", "idle", "fault"])
        closed = logs[0].td_downtime_id
        self.assertEqual((closed.reason_source, closed.reason_state, closed.ppt_min), ("demo", "confirmed", 30.0))
        self.assertFalse(logs[4].td_downtime_id)
        open_dt = logs[3].td_downtime_id
        self.assertTrue(open_dt.is_open)
        self.assertEqual(open_dt.maintenance_request_id, req)
        self.assertEqual((self.m_ua.state, self.m_ua.state_since), ("fault", self.kt("09:42")))
        self.assertEqual(self.m_ua.current_downtime_id, open_dt)
        self.assertEqual(
            hooks.demo_journal(self.env, install_ts),
            {"timelog_marked": 0, "downtimes_created": 0, "downtimes_open": 0, "requests_linked": 0},
        )
        # записи після моменту установки не стають demo
        late = self._demo_log(self.wc_cnc, "mrp.block_reason1", "10:00", "10:10")
        hooks.demo_journal(self.env, now - timedelta(hours=1))
        self.assertEqual(late.td_source, "operator")

    def test_idempotent(self):
        rep1 = self.run_mig()
        counts = {
            m: self.env[m].with_context(active_test=False).search_count([])
            for m in ("td.signal", "td.machine", "td.downtime", "td.gantry.stack")
        }
        with self.assertLogs(LOGGER, "WARNING"):
            rep2 = self.run_mig()
        self.assertEqual((rep2["signals_created"], rep2["downtimes_created"], rep2["machines_wired"]), (0, 0, 0))
        self.assertEqual(rep2["state"], "done")
        self.assertEqual(rep2["install_ts"], rep1["install_ts"])
        for model, n in counts.items():
            self.assertEqual(self.env[model].with_context(active_test=False).search_count([]), n, model)

    def test_admin_only(self):
        with self.assertRaises(AccessError):
            hooks.run_migration(self.env(user=self.user_f3d_manager))
        with self.assertRaises(AccessError):
            self.env["td.machine"].with_user(self.user_f3d_manager)._td_run_migration()
        with machines_csv([]):
            self.env["td.machine"].with_user(self.user_f3d_admin)._td_run_migration()


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestMigrationDemo(F3DMachineCase):
    """Лише на копії демо (`-u td_machine_connect`): AC-81…85 за даними Додатка C."""

    def setUp(self):
        super().setUp()
        codes = [r["code"] for r in hooks._csv_rows(self.env, "mc_machines")]
        found = self.env["mrp.workcenter"].search([("td_code", "in", codes)])
        if len(found) < 35 or not self.env["maintenance.equipment"].search_f3d("CNC-2"):
            self.skipTest("потрібна копія демо-бази (35 РЦ з кодами Додатка A)")

    def test_demo(self):
        Machine = self.env["td.machine"]
        self.assertEqual(Machine.search_count([("protocol", "=", "opcua"), ("code", "!=", "")]) >= 15, True)
        self.assertEqual(Machine.search_count([("employee_id", "!=", False)]), 28)
        self.assertEqual(self.env["td.gantry.stack"].search_count([]), 27)
        self.assertEqual(self.env["td.gantry.stack"].search_count([("orderpoint_id", "!=", False)]), 23)
        cnc2 = Machine.search([("code", "=", "CNC-2")])
        self.assertEqual(cnc2.state, "fault")
        self.assertEqual(cnc2.current_downtime_id.maintenance_request_id.name, "MR/00031")
        self.assertEqual(self.env["td.downtime"].search_count([("reason_source", "=", "demo")]), 74)
        self.assertEqual(self.env["mrp.workcenter.productivity"].search_count([("td_source", "=", "demo")]), 184)
        before = self.env["mrp.workcenter.productivity"].search_count([])
        rep = hooks.run_migration(self.env)
        self.assertEqual((rep["signals_created"], rep["downtimes_created"]), (0, 0))
        self.assertEqual(self.env["mrp.workcenter.productivity"].search_count([]), before)
