"""AC-47…AC-51: звірка стосу порталу, статус і стоси woodStore, дії, поповнення."""

import hashlib
import json
import uuid
from datetime import datetime
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import HttpCase, tagged

from .common import P, F3DMachineCase

SRC = "REST-WOODSTORE-T"


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestGantryStack(F3DMachineCase):
    def setUp(self):
        super().setUp()
        # telemetry `_td_handler_models` чекає класи від `registry.descendants`, а в 19.0 це імена: 0 обробників
        patcher = patch.object(
            type(self.env["td.push.handler"]),
            "_td_handler_models",
            lambda _self, route: ["td.push.handler.machine_connect"] if route.startswith("mc_") else [],
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.env["stock.quant"]._update_available_quantity(self.board, self.loc_t1, 45, lot_id=self.lot_l1)
        self.mo = self.make_mo(self.wc_saw, name="WH/MO/T0001", qty=4, comps=((self.board, 1),))
        self.job = self.env["td.gantry.job"].create(
            {
                "type": "feed",
                "state": "active",
                "stack_id": self.stack_t1.id,
                "product_id": self.board.id,
                "target_workcenter_id": self.wc_saw.id,
                "production_id": self.mo.id,
                "sheets": 10,
                "done": 7,
            }
        )
        self.stack_t1.write({"ws_qty": 38, "ws_product": "BOARD-T", "ws_lot": "L1", "ws_seen": self.kt("10:30")})

    def _make_diff(self):
        """ws_qty=36 -> `pending` о 10:30, `diff` о 10:41."""
        self.stack_t1.write({"ws_qty": 36})
        self.stack_t1._td_refresh()
        self.assertEqual(self.stack_t1.state, "pending")
        self.stack_t1.ws_seen = self.kt("10:36")
        with self.at("10:41"):
            self.stack_t1._td_refresh()

    def test_fed_unconsumed(self):
        self.stack_t1._td_refresh()
        s = self.stack_t1
        self.assertEqual((s.odoo_qty, s.fed_unconsumed, s.expected_qty, s.diff), (45, 7, 38, 0))
        self.assertEqual((s.state, s.odoo_product_id, s.odoo_lot_id), ("ok", self.board, self.lot_l1))
        self.mo.state = "done"  # МО закрито: подані листи вже списані з квантів
        s._td_refresh()
        self.assertEqual(s.fed_unconsumed, 0)

    def test_pending_then_diff(self):
        self._make_diff()
        s = self.stack_t1
        self.assertEqual((s.state, s.diff), ("diff", -2))
        self.assertTrue(s.diff_since)
        acts = self.acts(s)
        self.assertEqual(len(acts), 1)
        self.assertTrue(acts.user_id.has_group("stock.group_stock_manager"))
        for t in ("10:42", "10:43", "10:44"):
            s.ws_seen = self.kt("10:40")
            self.gantry_tick(t)
        self.assertEqual(len(self.acts(s)), 1)
        # самоусунення: діяльність закривається
        s.ws_qty = 38
        s.ws_seen = self.kt("10:44")
        with self.at("10:45"):
            s._td_refresh()
        self.assertEqual((s.state, s.diff_since), ("ok", False))
        self.assertFalse(self.acts(s))

    def test_product_mismatch(self):
        s = self.stack_t1
        s.ws_product = "DSP16-SON"
        s._td_refresh()
        self.assertEqual(s.state, "diff")
        self.assertEqual(len(self.acts(s)), 1)
        self.assertIn("DSP16-SON", self.acts(s).summary)

    def test_unknown_when_stale(self):
        s = self.stack_t1
        with self.at("10:50"):
            s._td_refresh()
        self.assertEqual(s.state, "unknown")

    def test_status_event(self):
        status = {
            "state": "idle",
            "position": {"x": 1.0, "y": 2.0, "z": 3.0},
            "vacuum_kpa": -70.0,
            "cycles_today": 5,
            "current_job": None,
            "aisles": [{"no": 1, "gate_open": False}, {"no": 2, "gate_open": True}],
            "alarms": ["Вакуум"],
            "ts": "2026-10-12T07:30:00Z",
        }
        self.push_event("mc_woodstore", {"kind": "status", "source": SRC, "status": status}, SRC)
        gs = json.loads(self.env["ir.config_parameter"].sudo().get_param(P + "gantry_status"))
        self.assertEqual((gs["aisles_open"], gs["alarms"], gs["state"]), ([2], ["Вакуум"], "idle"))
        msgs = self.env["mail.message"].search(
            [("model", "=", "maintenance.equipment"), ("res_id", "=", self.eq_gantry.id)]
        )
        self.assertEqual(len(msgs.filtered(lambda m: "Тривога порталу: Вакуум" in (m.body or ""))), 1)
        # той самий статус (інший ts) -> без повторної тривоги
        self.push_event("mc_woodstore", {"kind": "status", "source": SRC, "status": {**status, "ts": "x"}}, SRC)
        msgs = self.env["mail.message"].search(
            [("model", "=", "maintenance.equipment"), ("res_id", "=", self.eq_gantry.id)]
        )
        self.assertEqual(len(msgs.filtered(lambda m: "Тривога порталу" in (m.body or ""))), 1)

        # стоси: 23 стоси з qty > 0
        Stack = self.env["td.gantry.stack"]
        Stack.search([]).write({"ws_qty": 0})
        items = [{"id": "PLT-T1", "qty": 38, "product": "BOARD-T", "lot": "L1", "reserved": 10}]
        items.append({"id": "PLT-T2", "qty": 5, "product": "BOARD-T", "lot": None, "reserved": 0})
        for i in range(21):
            loc = self.env["stock.location"].create(
                {
                    "name": "PLT-Z%02d" % i,
                    "location_id": self.loc_t1.location_id.id,
                    "td_code": "PLT-Z%02d" % i,
                    "td_loc_kind": "stack",
                    "td_capacity": 60,
                }
            )
            Stack.create({"location_id": loc.id})
            items.append({"id": "PLT-Z%02d" % i, "qty": 10, "product": "BOARD-T", "lot": None, "reserved": 0})
        items.append({"id": "PLT-NOPE", "qty": 1, "product": "X", "lot": None, "reserved": 0})
        with self.assertLogs("odoo.addons.td_machine_connect", "WARNING"):
            self.push_event("mc_woodstore", {"kind": "stacks", "source": SRC, "hash": "h", "items": items}, SRC)
        self.assertEqual(self.stack_t1.ws_qty, 38)
        self.assertEqual(self.stack_t1.ws_reserved, 10)
        self.assertTrue(self.stack_t1.ws_seen)
        self.assertEqual(self.sig_g_stacks.last_value, 23)

    def test_accept_portal(self):
        self._make_diff()
        s = self.stack_t1
        with self.assertRaises(AccessError):
            s.with_user(self.user_f3d).action_accept_portal()
        with self.at("10:41"):
            s.with_user(self.user_stock_manager).action_accept_portal()
        quants = self.env["stock.quant"].search([("location_id", "=", self.loc_t1.id)])
        self.assertEqual(sum(quants.mapped("quantity")), 43)
        self.assertEqual((s.expected_qty, s.state), (36, "ok"))
        moves = self.env["stock.move"].search([("product_id", "=", self.board.id), ("is_inventory", "=", True)])
        self.assertTrue(moves and all(m.state == "done" for m in moves))

    def test_fix_portal_needs_write(self):
        self._make_diff()
        s = self.stack_t1
        with self.assertRaises(AccessError):
            s.with_user(self.user_f3d).action_fix_portal()
        with self.assertRaises(UserError):
            s.with_user(self.user_stock_manager).action_fix_portal()
        self.enable_write()
        s.with_user(self.user_stock_manager).action_fix_portal()
        cmd = self.env["td.command"].search([("signal_id", "=", self.sig_g_cmd.id)])
        self.assertEqual(len(cmd), 1)
        self.assertEqual(cmd.payload, {"op": "stack", "stack": "PLT-T1", "qty": 38, "product": "BOARD-T", "lot": "L1"})
        self.assertEqual(cmd.text, "stack;PLT-T1;38;BOARD-T;L1")

    def test_below_min_filter(self):
        """Фільтр «Нижче мінімуму»: `below_min` (не порівняння поля з полем у домені)."""
        wh = self.env["stock.warehouse"].search([("company_id", "=", self.env.company.id)], limit=1)
        op = self.env["stock.warehouse.orderpoint"].create(
            {
                "product_id": self.board.id,
                "location_id": self.loc_t1.id,
                "warehouse_id": wh.id,
                "product_min_qty": 10,
                "product_max_qty": 60,
            }
        )
        s = self.stack_t1
        Stack = self.env["td.gantry.stack"]
        below = [("id", "=", s.id), ("below_min", "=", True)]
        s.write({"ws_qty": 9})
        self.assertFalse(s.below_min, "без правила поповнення стос не «нижче мінімуму»")
        s.orderpoint_id = op
        self.assertTrue(s.below_min)
        self.assertEqual(Stack.search(below), s)
        s.ws_qty = 10
        self.assertFalse(s.below_min)
        self.assertFalse(Stack.search(below))
        op.product_min_qty = 11
        self.assertTrue(s.below_min)
        arch = self.env.ref("td_machine_connect.view_td_gantry_stack_search").arch
        self.assertIn("below_min", arch)
        self.assertNotIn("'min_qty'", arch)

    def test_replenish_once_per_hour(self):
        wh = self.env["stock.warehouse"].search([("company_id", "=", self.env.company.id)], limit=1)
        op = self.env["stock.warehouse.orderpoint"].create(
            {
                "product_id": self.board.id,
                "location_id": self.loc_t1.id,
                "warehouse_id": wh.id,
                "product_min_qty": 10,
                "product_max_qty": 60,
            }
        )
        s = self.stack_t1
        s.write({"orderpoint_id": op.id, "ws_qty": 9})
        self._icp().set_param(P + "gantry_auto_replenish", "True")
        with patch.object(type(op), "action_replenish", return_value=True) as m:
            self.gantry_tick("10:30")
            self.assertEqual(m.call_count, 1)
            self.gantry_tick("10:40")
            self.assertEqual(m.call_count, 1)
            self._icp().set_param(P + "gantry_auto_replenish", "False")
            s.replenish_at = False
            self.gantry_tick("10:41")
            self.assertEqual(m.call_count, 1)
            s.action_replenish()  # кнопка — без умови параметра
            self.assertEqual(m.call_count, 2)
        s.orderpoint_id = False
        with self.assertRaises(UserError):
            s.action_replenish()

        # переміщення в стос виконано, запис вимкнено -> діяльність
        src = self.env["stock.location"].create(
            {"name": "RCK-T", "location_id": wh.view_location_id.id, "usage": "internal"}
        )
        self.env["stock.quant"]._update_available_quantity(self.board, src, 20, lot_id=self.lot_l1)
        pick = self.env["stock.picking"].create(
            {
                "picking_type_id": wh.int_type_id.id,
                "location_id": src.id,
                "location_dest_id": self.loc_t1.id,
                "move_ids": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.board.id,
                            "product_uom_qty": 5,
                            "location_id": src.id,
                            "location_dest_id": self.loc_t1.id,
                        },
                    )
                ],
            }
        )
        pick.action_confirm()
        pick.action_assign()
        pick.move_ids.picked = True
        pick._action_done()
        self.assertEqual(pick.state, "done")
        self.assertEqual(s.odoo_qty, 50)
        acts = self.acts(s).filtered(lambda a: a.summary.startswith("Оновіть стос PLT-T1 у woodStore"))
        self.assertEqual(len(acts), 1)

    def test_ev02_stacks_27_like_adapter(self):
        """ТП-04: EV-02 `stacks` на 27 стосів, payload як від адаптера woodstore (kind/hash/items)."""
        wh = self.env["stock.warehouse"].search([("company_id", "=", self.env.company.id)], limit=1)
        stacks = self.stack_t1 | self.stack_t2
        for i in range(25):
            loc = self.env["stock.location"].create(
                {
                    "name": "PLT-W%02d" % i,
                    "location_id": wh.lot_stock_id.id,
                    "td_code": "PLT-W%02d" % i,
                    "td_loc_kind": "stack",
                    "td_capacity": 60,
                }
            )
            stacks |= self.env["td.gantry.stack"].create({"location_id": loc.id})
        items = [
            {
                "id": s.code,
                "row": 1 + i // 6,
                "col": 1 + i % 6,
                "product": "DSP16-SON",
                "lot": "DSP16-SON-2610-%03d" % i,
                "qty": 20 + i,
                "max": 60,
                "reserved": 0,
                "locked": False,
                "updated": "2026-10-15T10:30:00+03:00",
            }
            for i, s in enumerate(stacks)
        ]
        self.assertEqual(len(items), 27)
        res = self.push_event("mc_woodstore", {"kind": "stacks", "source": SRC, "hash": "ab" * 32, "items": items}, SRC)
        self.assertEqual(res["accepted"], 1)
        ev = self.env["td.push.event"].sudo().search([("route", "=", "mc_woodstore")], limit=1)
        self.assertFalse(ev.error)
        self.assertEqual(self.stack_t2.ws_qty, 21)
        self.assertEqual(self.stack_t1.ws_qty, 20)


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestGantryStackHttp(HttpCase):
    def test_ev02_stacks_27_http(self):
        """ТП-04: POST /f3d/telemetry/event з EV-02 `stacks` (27 стосів) → 200, 27 стосів оновлено."""
        env = self.env
        env["ir.config_parameter"].sudo().set_param("td.telemetry.read_enabled", "True")
        token = "tp04-" + uuid.uuid4().hex
        env["td.collector"].create(
            {"code": "COL-TP04", "name": "ТП-04", "token_hash": hashlib.sha256(token.encode()).hexdigest()}
        )
        wh = env["stock.warehouse"].search([("company_id", "=", env.company.id)], limit=1)
        stacks = env["td.gantry.stack"]
        items = []
        for i in range(27):
            code = "PLT-H%02d" % i
            loc = env["stock.location"].create(
                {
                    "name": code,
                    "location_id": wh.lot_stock_id.id,
                    "td_code": code,
                    "td_loc_kind": "stack",
                    "td_capacity": 60,
                }
            )
            stacks |= env["td.gantry.stack"].create({"location_id": loc.id})
            items.append(
                {
                    "id": code,
                    "row": 1 + i // 6,
                    "col": 1 + i % 6,
                    "product": "DSP16-SON",
                    "lot": "DSP16-SON-2610-%03d" % i,
                    "qty": 20 + i,
                    "max": 60,
                    "reserved": 0,
                    "locked": False,
                    "updated": datetime.now().astimezone().isoformat(),
                }
            )
        body = {
            "events": [
                {
                    "event_id": hashlib.sha256(uuid.uuid4().bytes).hexdigest(),
                    "route": "mc_woodstore",
                    "ts": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.000Z"),
                    "remote": "REST-WOODSTORE",
                    "headers": {},
                    "payload": {"kind": "stacks", "source": "REST-WOODSTORE", "hash": "ab" * 32, "items": items},
                }
            ]
        }
        resp = self.url_open(
            "/f3d/telemetry/event",
            data=json.dumps(body),
            headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        )
        self.assertEqual(resp.status_code, 200, resp.text[:300])
        self.assertEqual(resp.json()["accepted"], 1)
        ev = env["td.push.event"].sudo().search([("route", "=", "mc_woodstore")], limit=1)
        self.assertFalse(ev.error)
        stacks.invalidate_recordset()
        self.assertEqual(sorted(stacks.mapped("ws_qty")), list(range(20, 47)))
