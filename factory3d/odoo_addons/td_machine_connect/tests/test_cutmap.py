"""AC-59…AC-65: деталі виробів, карти розкрою, CSV, оптимізатор, план, випуск."""

import base64
import hashlib
import json
from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import new_test_user, tagged
from odoo.tools import mute_logger

from ..tools import cutcsv
from .common import F3DMachineCase, kt

SRC = "REST-CUTOPT-T"
CSV_E = (
    "part_code;name;length_mm;width_mm;qty;material_role;material;grain;edge_top;edge_bottom;edge_left;edge_right;"
    "program;note\n"
    "P001;Боковина;720;560;2;main;;1;EB-T;;EB-T;;;\n"
    "P002;Дно;764;{w};1;main;;0;EB-T;;;;;\n"
    "P003;Задня стінка;780;716;1;back;;0;;;;;;\n"
)
EXPECTED_CSV = (
    "PartId;Description;Material;Length;Width;Quantity;Grain;EdgeTop;EdgeBottom;EdgeLeft;EdgeRight;Program\r\n"
    "P001;Боковина;BOARD-T;720;560;28;1;EB-T;;EB-T;;\r\n"
)


def plan_json(parts=28, total=7):
    return {
        "total_sheets": total,
        "waste_pct": 11.4,
        "cut_length_m": 182.6,
        "est_min": 31,
        "sheets": [
            {
                "no": 1,
                "product": "BOARD-T",
                "parts": [{"id": "P001", "x": 0, "y": 0, "w": 720, "h": 560, "rot": 0} for _i in range(parts)],
            }
        ],
    }


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestCutMap(F3DMachineCase):
    def setUp(self):
        super().setUp()
        patcher = patch.object(
            type(self.env["td.push.handler"]),
            "_td_handler_models",
            lambda _self, route: ["td.push.handler.machine_connect"] if route.startswith("mc_") else [],
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.Part = self.env["td.cut.part"]
        self.Map = self.env["td.cut.map"]
        self.mo = self.make_mo(self.wc_saw, qty=14, comps=((self.board, 8 / 14),), name="WH/MO/T0233")
        self.part1 = self._part(self.mo.bom_id, "P001", "Боковина", 720, 560, qty=2, grain="1", edge_top="EB-T",
                                edge_left="EB-T")  # fmt: skip

    def _part(self, bom, code, name, length, width, **kw):
        return self.Part.create(
            {"bom_id": bom.id, "part_code": code, "name": name, "length_mm": length, "width_mm": width, **kw}
        )

    def _import(self, text, replace=False):
        wiz = self.env["td.cut.part.import.wizard"].create(
            {"bom_id": self.mo.bom_id.id, "file": base64.b64encode(text.encode()), "replace": replace}
        )
        return wiz.action_import()

    def _map(self, mode="collector"):
        rec = self.Map._td_create_for(self.mo, "main")
        rec.mode = mode
        return rec

    def _cmds(self, rec, op=None):
        cmds = rec.command_ids.sorted("id")
        return cmds.filtered(lambda c: c.payload.get("op") == op) if op else cmds

    def _exported_map(self):
        self.enable_write()
        rec = self._map()
        rec.action_export()
        return rec

    def test_part_constraints_and_import(self):
        bom = self.mo.bom_id
        for vals in ({"length_mm": 0}, {"qty": 0}):
            with self.subTest(vals=vals), mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
                with self.cr.savepoint():
                    self._part(bom, "PX", "Х", vals.get("length_mm", 100), 100, **{"qty": vals.get("qty", 1)})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            self._part(bom, "PY", "Y", 100, 100, material_role="product")
        before = self.Part.search_count([("bom_id", "=", bom.id)])
        with self.assertRaises(UserError) as ctx:
            self._import(CSV_E.format(w=2300))
        self.assertIn("рядок 3: width_mm", str(ctx.exception))
        self.assertEqual(self.Part.search_count([("bom_id", "=", bom.id)]), before)
        self._import(CSV_E.format(w=500))
        self.assertEqual(self.Part.search_count([("bom_id", "=", bom.id)]), 3)
        self._import(CSV_E.format(w=500))  # upsert
        self.assertEqual(self.Part.search_count([("bom_id", "=", bom.id)]), 3)
        self._import(CSV_E.format(w=500), replace=True)
        self.assertEqual(self.Part.search_count([("bom_id", "=", bom.id)]), 3)

    def test_create_lines_and_fit(self):
        rec = self._map()
        self.assertEqual(rec.state, "draft")
        self.assertEqual((rec.sheet_length_mm, rec.sheet_width_mm, rec.thickness_mm), (2800, 2070, 16))
        self.assertEqual(rec.workorder_id, self.mo.workorder_ids[:1])
        self.assertEqual(rec.line_ids.mapped("qty"), [28])
        self.assertEqual(rec.parts_count, 28)
        self._part(self.mo.bom_id, "P002", "Велика", 2100, 1500, grain="1")  # вміщується без повороту
        rec.action_build_lines()
        self.assertEqual(len(rec.line_ids), 2)
        self._part(self.mo.bom_id, "P003", "Квадрат", 2100, 2100)
        with self.assertRaises(ValidationError), self.cr.savepoint():
            rec.action_build_lines()
        with self.assertRaises(UserError):  # ролі back немає деталей
            self.Map._td_create_for(self.make_mo(self.wc_saw, comps=((self.board, 1), (self.hdf, 1))), "back")

    def test_export_csv(self):
        rec = self._exported_map()
        self.assertEqual(rec.state, "optimizing")
        att = rec.csv_attachment_id
        self.assertEqual(att.name, "%s_parts.csv" % rec.name)
        self.assertEqual(att.raw, EXPECTED_CSV.encode())
        self.assertEqual(rec.csv_attachment_id.mimetype, "text/csv")
        with self.assertRaises(UserError):
            rec.action_export()
        self.assertEqual(
            cutcsv.build_parts_csv(
                [{"part_code": "A", "name": "a;b\nc", "length_mm": 1, "width_mm": 2, "qty": 3}], "M"
            ),
            cutcsv.CSV_HEADER_LINE + "A;a,b c;M;1;2;3;0;;;;;\r\n",
        )

    def test_send_optimizer_token(self):
        rec = self._exported_map()
        cmd = self._cmds(rec, "upload")
        self.assertEqual(len(cmd), 1)
        token = cmd.payload["token"]
        self.assertRegex(token, r"^[0-9a-f]{16}$")
        self.assertEqual(cmd.payload, {"op": "upload", "map": rec.id, "token": token})
        self.assertEqual(rec.export_token_hash, hashlib.sha256(token.encode()).hexdigest())
        self.assertEqual(rec.export_token_expires, kt("10:40"))
        with self.assertRaises(AccessError):
            rec.with_user(self.user_f3d_manager).read(["export_token_hash"])

    def test_apply_job_plan_mpr(self):
        rec = self._exported_map()
        self.cmd_done(self._cmds(rec, "upload"), data={"job_id": "cj-00077", "state": "optimizing", "eta_s": 5})
        self.assertEqual(rec.ext_job_id, "cj-00077")
        # події після рестарту колектора: map порожній — карта за job_id
        self.assertEqual(self.Map._td_find_for_event(False, "cj-00077"), rec)
        self.push_event("mc_cutopt", {"kind": "plan", "source": SRC, "map": rec.name, "job_id": "cj-00077",
                                      "plan": plan_json()}, SRC)  # fmt: skip
        self.push_event("mc_cutopt", {"kind": "mpr", "source": SRC, "map": rec.name, "job_id": "cj-00077",
                                      "part": "P001", "text": "[H\nBSX=720"}, SRC)  # fmt: skip
        self.env.invalidate_all()
        self.assertEqual((rec.state, rec.plan_sheets, rec.plan_waste_pct), ("planned", 7, 11.4))
        self.assertEqual(rec.plan_attachment_id.name, "%s_plan.json" % rec.name)
        self.assertEqual(rec.line_ids.mpr_attachment_id.name, "P001.mpr")
        self.assertEqual(rec.mpr_attachment_ids, rec.line_ids.mpr_attachment_id)
        self.assertFalse(rec.message_ids.filtered(lambda m: "не відповідає" in (m.body or "")))
        bad = plan_json(total=0)
        with self.assertRaises(ValueError):
            rec._td_apply_plan(bad)
        rec._td_apply_plan(plan_json(parts=27))
        self.assertTrue(rec.message_ids.filtered(lambda m: "P001 28 → 27" in (m.body or "")))
        # job: planned -> підсумок; error
        rec._td_apply_job({"job_id": "cj-00077", "state": "error", "error": "збій"})
        self.assertEqual((rec.state, rec.error), ("error", "збій"))

    def test_optimizing_timeout_and_status_poll(self):
        rec = self._exported_map()
        self.cmd_done(self._cmds(rec, "upload"), data={"job_id": "cj-00077", "state": "optimizing", "eta_s": 5})
        self.cutmap_tick("10:32:00")
        self.assertEqual(len(self._cmds(rec, "status")), 1)
        self.cutmap_tick("10:40:00")
        self.assertEqual(rec.state, "optimizing")
        self.cutmap_tick("11:10:00")
        self.assertEqual(rec.state, "error")
        self.assertIn("30 хв", rec.error)
        rec.action_reset_draft()
        self.assertEqual((rec.state, rec.ext_job_id), ("draft", False))

    def test_sheets_warning_and_update_need(self):
        rec = self._map()
        self.mo.move_raw_ids.filtered(lambda m: m.product_id == self.board).product_uom_qty = 8  # 8/14 × 14 = 7.98
        rec.plan_sheets = 9
        self.assertEqual(rec.sheets_need, 8)
        self.assertTrue(rec.sheets_warning)
        with self.assertRaises(AccessError):
            rec.with_user(self.user_f3d_manager).action_update_mo_need()
        boss = new_test_user(
            self.env,
            login="mc_cut_boss",
            groups="base.group_user,td_factory3d.group_td_manager,mrp.group_mrp_manager",
        )
        rec.with_user(boss).action_update_mo_need()
        self.assertEqual(sum(self.mo.move_raw_ids.filtered(lambda m: m.product_id == self.board).mapped(
            "product_uom_qty")), 9)  # fmt: skip
        self.assertFalse(rec.sheets_warning)
        self.assertTrue(self.mo.message_ids.filtered(lambda m: "8 → 9" in (m.body or "")))

    def test_release_and_manual_plan(self):
        rec = self._exported_map()
        self.cmd_done(self._cmds(rec, "upload"), data={"job_id": "cj-00077", "state": "optimizing", "eta_s": 5})
        rec._td_apply_plan(plan_json())
        rec.action_release()
        cmd = self._cmds(rec, "release")
        self.assertEqual(cmd.payload, {"op": "release", "job": "cj-00077", "machine": "SAW-T", "priority": 5})
        self.assertEqual(rec.state, "planned")
        self.cmd_done(cmd, data={"job_id": "cj-00077", "state": "released", "job_order_id": "cj-00077"})
        self.assertEqual((rec.state, rec.job_order_id), ("released", "cj-00077"))
        # крон: завдання розкрою стартувало -> running -> done
        self.mo.workorder_ids[:1].sudo().state = "progress"
        self.cutmap_tick("10:35:00")
        self.assertEqual(rec.state, "running")
        self.mo.workorder_ids[:1].sudo().state = "done"
        self.cutmap_tick("10:36:00")
        self.assertEqual(rec.state, "done")
        # ручний режим
        man = self._map(mode="manual")
        man.action_export()
        self.assertEqual(man.state, "exported")
        wiz = self.env["td.cut.plan.import.wizard"].create(
            {"map_id": man.id, "file": base64.b64encode(json.dumps(plan_json()).encode())}
        )
        wiz.action_import()
        self.assertEqual((man.state, man.plan_sheets), ("planned", 7))
        man.action_release()
        self.assertEqual(man.state, "released")
        self.assertFalse(man.command_ids)
        with self.assertRaises(UserError):
            self.env["td.cut.plan.import.wizard"].create(
                {"map_id": man.id, "file": base64.b64encode(b"{}")}
            ).action_import()

    def test_csv_formula_prefix_stripped(self):
        self.part1.name = "=SUM(A1)"
        rec = self._map(mode="manual")
        rec.action_export()
        self.assertIn("P001;SUM(A1);BOARD-T;720;560;28;", rec.csv_attachment_id.raw.decode())
        self.assertFalse(rec.csv_attachment_id.raw.startswith(b"\xef\xbb\xbf"))
