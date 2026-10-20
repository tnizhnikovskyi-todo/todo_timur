"""AC-86…AC-88: провайдер переглядача `td.viewer.provider.machines` (R-25, M-22). Без td_viewer3d."""

from unittest.mock import patch

from odoo.tests import tagged

from ..tools import payload as payload_tools
from .common import F3DMachineCase


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestViewerProvider(F3DMachineCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.provider = cls.env["td.viewer.provider.machines"]

    def _shift(self, machine, oee=0.84):
        shift = self.env["td.oee.shift"].create(
            {
                "machine_id": machine.id,
                "date": self.D0,
                "date_start": self.kt("07:00"),
                "date_end": self.kt("15:30"),
                "source": "machine",
                "has_data": True,
                "oee": oee,
                "availability": 0.844,
                "performance": 1.0,
                "quality": 1.0,
            }
        )
        machine.oee_shift_id = shift
        return shift

    def _payload(self):
        return {
            "workcenters": {
                "SAW-T": {"code": "SAW-T", "status": "idle", "oee": 0.1, "losses": [1], "queue": ["q"],
                          "current_workorder": "WO1", "productive_minutes": 5},
                "CNC-T": {"code": "CNC-T", "status": "idle", "oee": 0.2, "losses": [], "queue": []},
                "NONE-1": {"code": "NONE-1", "status": "idle"},
            },
            "equipment": {"GANTRY-1": {"state": "idle"}, "FL-1": {"state": "busy"}},
            "locations": {"PLT-T1": {"kind": "stack"}, "PLT-T2": {"kind": "stack"}, "WH-1": {}},
            "productions": [],
            "sheet_chain": {"steps": [{} for _ in range(5)]},
        }  # fmt: skip

    def _setup_live(self):
        mo = self.make_mo(self.wc_saw, qty=14)
        wo = mo.workorder_ids[:1]
        self.m_saw.write({"state": "working", "state_since": self.kt("09:55"), "active_workorder_id": wo.id})
        wo.td_qty_counted = 14
        self._shift(self.m_saw)
        self.make_log(self.m_saw, "working", "09:55", "10:25", wo=wo, pieces=80)
        loss = self.env.ref("mrp.block_reason1")
        down = self.env["td.downtime"].create(
            {
                "machine_id": self.m_cnc.id,
                "date_start": self.kt("09:42"),
                "state_kind": "fault",
                "loss_id": loss.id,
                "reason_state": "to_confirm",
                "hint_text": "E0421 Помилка шпинделя осі Z",
            }
        )
        self.m_cnc.write({"state": "fault", "state_since": self.kt("09:42"), "current_downtime_id": down.id})
        job_model = self.env["td.gantry.job"]
        job_model._td_set_gantry_status({"state": "moving", "aisles_open": [2], "alarms": ["Вакуум"], "vacuum_kpa": 71})
        self.stack_t1.write({"ws_qty": 40, "ws_seen": self.kt("10:29")})
        self.stack_t1._td_refresh()
        self.job = job_model.create(
            {
                "state": "active",
                "ws_id": "J-7",
                "sheets": 10,
                "done": 4,
                "product_id": self.board.id,
                "target_workcenter_id": self.wc_saw.id,
                "external_ref": mo.name,
                "production_id": mo.id,
                "stack_id": self.stack_t1.id,
            }
        )
        self.map = self.env["td.cut.map"].create(
            {
                "production_id": mo.id,
                "workorder_id": wo.id,
                "qty": 14,
                "material_product_id": self.board.id,
                "sheet_length_mm": 2800,
                "sheet_width_mm": 2070,
                "thickness_mm": 16,
                "state": "planned",
                "plan_sheets": 12,
                "plan_waste_pct": 7.25,
            }
        )
        return mo

    def test_collect_payload(self):
        mo = self._setup_live()
        payload = self._payload()
        payload["productions"] = [{"name": mo.name, "supply": {"x": 1}}, {"name": "WH/MO/NO-SUPPLY"}]
        self.provider._td_viewer_collect(payload, {})
        saw = payload["workcenters"]["SAW-T"]
        self.assertEqual(
            {k: saw[k] for k in ("machine_state", "state_since", "link", "online", "oee", "availability", "performance",
                                 "quality", "pieces_shift", "counted", "status")},
            {"machine_state": "working", "state_since": "2026-10-12 09:55", "link": "opcua", "online": True,
             "oee": 0.84, "availability": 0.84, "performance": 1.0, "quality": 1.0, "pieces_shift": 80,
             "counted": 14, "status": "work"},
        )  # fmt: skip
        self.assertEqual((saw["losses"], saw["queue"], saw["current_workorder"]), ([1], ["q"], "WO1"))
        self.assertNotIn("downtime", saw)
        cnc = payload["workcenters"]["CNC-T"]
        self.assertEqual(cnc["status"], "stop")
        self.assertEqual(cnc["link"], "manual")
        self.assertEqual(cnc["oee"], 0.2)  # немає запису OEE — вхідне значення
        self.assertEqual(
            cnc["downtime"],
            {"reason": self.env.ref("mrp.block_reason1").name, "since": "09:42", "minutes": 48, "kind": "fault",
             "state": "to_confirm", "hint": "E0421 Помилка шпинделя осі Z"},
        )  # fmt: skip
        self.assertEqual(
            payload["equipment"]["GANTRY-1"]["gantry"],
            {"state": "moving", "job": {"id": "J-7", "target": "SAW-T", "sheets": 10, "done": 4, "ref": mo.name},
             "stacks": 1, "aisles_open": [2], "alarms": ["Вакуум"]},
        )  # fmt: skip
        self.assertNotIn("gantry", payload["equipment"]["FL-1"])
        t1 = payload["locations"]["PLT-T1"]["gantry"]
        self.assertEqual((t1["qty"], t1["state"]), (40, self.stack_t1.state))
        self.assertEqual(t1["diff"], self.stack_t1.diff)
        self.assertNotIn("gantry", payload["locations"]["PLT-T2"])
        prod = payload["productions"][0]
        self.assertEqual(prod["cut_map"], {"name": self.map.name, "state": "planned", "sheets": 12, "waste_pct": 7.3})
        self.assertEqual(prod["supply"]["gantry"], {"job": self.job.name, "sheets": 10, "done": 4, "state": "active"})
        self.assertNotIn("cut_map", payload["productions"][1])
        self.assertEqual(payload["sheet_chain"]["steps"][4]["stock"], "портал: 1 завд. · 6 арк.")
        self.assertNotIn("stock", payload["sheet_chain"]["steps"][0])
        self.assertEqual(payload["workcenters"]["NONE-1"], {"code": "NONE-1", "status": "idle"})
        # build_machines повертає ті самі ключі, що collect дописує
        frag = payload_tools.build_machines(self.env, {}, self._payload())
        self.assertEqual(set(frag), {"workcenters", "equipment", "locations", "sheet_chain"})
        self.assertEqual(set(frag["workcenters"]), {"SAW-T", "CNC-T"})

    def test_no_oee_keeps_input(self):
        payload = self._payload()
        self.provider._td_viewer_collect(payload, {})
        saw, cnc = payload["workcenters"]["SAW-T"], payload["workcenters"]["CNC-T"]
        self.assertEqual((saw["oee"], cnc["oee"]), (0.1, 0.2))
        self.assertEqual(saw["status"], "idle")  # nodata: статус провайдера production
        self.assertFalse(saw["online"])
        self.assertEqual(saw["pieces_shift"], 0)
        self.m_cnc.state = "fault"
        self.provider._td_viewer_collect(payload, {})
        self.assertEqual(payload["workcenters"]["CNC-T"]["status"], "stop")
        self.assertNotIn("downtime", payload["workcenters"]["CNC-T"])
        for empty in ({}, {"workcenters": None}, {"productions": "x", "locations": []}):
            self.provider._td_viewer_collect(empty, {})
        self.assertEqual(self.provider._td_viewer_collect({}, {}), None)

    def test_as_user(self):
        """Провайдер працює від користувача запиту (`group_td_user`)."""
        self._setup_live()
        payload = self._payload()
        self.env["td.viewer.provider.machines"].with_user(self.user_f3d)._td_viewer_collect(payload, {})
        self.assertEqual(payload["workcenters"]["SAW-T"]["machine_state"], "working")
        self.assertEqual(payload["equipment"]["GANTRY-1"]["gantry"]["state"], "moving")

    def test_bus_and_delta(self):
        self.assertEqual(self.provider._td_sequence, 75)
        self.assertEqual(self.provider._td_group, "td_factory3d.group_td_user")
        self.assertEqual(self.provider._td_sections, ())
        self.assertEqual(
            self.provider._td_viewer_bus_models(),
            ["mrp.workcenter", "stock.location", "maintenance.equipment", "mrp.production"],
        )
        self.assertFalse(self.provider._inherit and "td.viewer.provider" in str(self.provider._inherit))
        self._setup_live()
        patch_ = {"workcenters": {"SAW-T": {"code": "SAW-T", "status": "idle"}}}
        self.provider._td_viewer_delta(patch_, {})
        self.assertEqual(set(patch_), {"workcenters"})
        self.assertEqual(patch_["workcenters"]["SAW-T"]["machine_state"], "working")
        # R-30 п. 6: решта верстатів у дельті — лише зведення `flow` (живі поля R-25 — тільки вузлам патча)
        others = {code: node for code, node in patch_["workcenters"].items() if code != "SAW-T"}
        self.assertTrue(others)
        self.assertTrue(all(set(node) == {"flow"} for node in others.values()))
        empty = {}
        self.provider._td_viewer_delta(empty, {})
        self.assertEqual(set(empty), {"workcenters"})
        self.assertTrue(all(set(node) == {"flow"} for node in empty["workcenters"].values()))

    def test_notify(self):
        if "td.viewer.event" not in self.env:
            self.skipTest("td_viewer3d не встановлено")
        Event = type(self.env["td.viewer.event"])
        with patch.object(Event, "_notify") as notify:
            self.m_saw._td_notify()
        notify.assert_called_once_with("mrp.workcenter", ["SAW-T"], "state")
