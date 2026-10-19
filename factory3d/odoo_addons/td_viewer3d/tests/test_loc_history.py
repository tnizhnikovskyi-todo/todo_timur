from datetime import timedelta
from unittest.mock import patch

from odoo import Command
from odoo.tests import HttpCase, tagged

from odoo.addons.td_viewer3d.tools import dates
from odoo.addons.td_viewer3d.tools import docs as docs_tools
from odoo.addons.td_viewer3d.tools import loc_history

from .common import F3dViewerBase


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestLocHistory(HttpCase, F3dViewerBase):
    """API-12 `GET /f3d/viewer/loc/<code>` (R-24): як товар потрапив у комірку і куди він іде."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for user in (cls.user_f3d, cls.user_nobody):
            user.password = user.login
        cls.user_no_stock = cls._make_user("f3d_nostock", ["base.group_user", "td_factory3d.group_td_user"])
        cls.user_no_stock.password = "f3d_nostock"
        env = cls.env
        cls.wh = env["stock.warehouse"].search([], limit=1)
        cls.supplier = env.ref("stock.stock_location_suppliers")
        cls.customer = env.ref("stock.stock_location_customers")
        cls.cell = env["stock.location"].create(
            {"name": "ZZ-H-CELL", "location_id": cls.wh.lot_stock_id.id, "td_code": "ZZ-H-CELL"}
        )
        cls.dest = env["stock.location"].create(
            {"name": "ZZ-H-DEST", "location_id": cls.wh.lot_stock_id.id, "td_code": "ZZ-H-DEST"}
        )
        make = env["product.product"].create
        cls.plate = make(
            {"name": "ZZ Плита", "default_code": "ZZ-PLATE", "is_storable": True, "type": "consu", "tracking": "lot"}
        )
        cls.fitting = make({"name": "ZZ Фурнітура", "default_code": "ZZ-FIT", "is_storable": True, "type": "consu"})
        cls.lot = env["stock.lot"].create(
            {"name": "ZZ-LOT-1", "product_id": cls.plate.id, "company_id": cls.wh.company_id.id}
        )

    # --- фікстури ---------------------------------------------------------
    def _picking(self, ptype, src, dest, product, qty, confirm=True):
        pick = self.env["stock.picking"].create(
            {
                "picking_type_id": ptype.id,
                "location_id": src.id,
                "location_dest_id": dest.id,
                "move_ids": [
                    Command.create(
                        {
                            "product_id": product.id,
                            "product_uom_qty": qty,
                            "location_id": src.id,
                            "location_dest_id": dest.id,
                        }
                    )
                ],
            }
        )
        if confirm:
            pick.action_confirm()
            pick.action_assign()
        return pick

    def _receive(self, qty, lot=None):
        """Виконане приймання партії `lot` (за замовчуванням ZZ-LOT-1) у комірку."""
        pick = self._picking(self.wh.in_type_id, self.supplier, self.cell, self.plate, qty)
        pick.move_ids.move_line_ids.write({"lot_id": (lot or self.lot).id, "quantity": qty})
        pick.move_ids.picked = True
        pick.with_context(skip_backorder=True).button_validate()
        self.assertEqual(pick.state, "done")
        return pick

    def _ship(self, qty):
        """Виконане відвантаження `qty` арк. плити з комірки клієнту (резервує те, що є в комірці)."""
        pick = self._picking(self.wh.out_type_id, self.cell, self.customer, self.plate, qty)
        pick.move_ids.picked = True
        pick.with_context(skip_backorder=True).button_validate()
        self.assertEqual(pick.state, "done")
        return pick

    def _fixture(self):
        """20 арк. партії ZZ-LOT-1 (5 прийманнями), резерв 5 + частковий резерв 15 (з 30), фурнітура без залишку
        з відвантаженням 3, очікуване приймання 7 арк., інвентаризація 4 шт. фурнітури."""
        recs = {"receipts": [self._receive(q) for q in (1, 2, 3, 4, 10)]}
        recs["res"] = self._picking(self.wh.out_type_id, self.cell, self.customer, self.plate, 5)
        recs["part"] = self._picking(self.wh.out_type_id, self.cell, self.customer, self.plate, 30)
        recs["out"] = self._picking(self.wh.int_type_id, self.cell, self.dest, self.fitting, 3)
        recs["incoming"] = self._picking(self.wh.in_type_id, self.supplier, self.cell, self.plate, 7)
        return recs

    def _get(self, url, user="f3d_user"):
        if user:
            self.authenticate(user, user)
        return self.url_open(url, allow_redirects=False)

    # --- доступ і валідація (V-2) -----------------------------------------
    def test_auth_and_acl(self):
        self.assertEqual(self._get("/f3d/viewer/loc/ZZ-H-CELL").status_code, 200)
        self.assertEqual(self._get("/f3d/viewer/loc/ZZ-H-CELL", user="f3d_nobody").status_code, 403)
        res = self._get("/f3d/viewer/loc/ZZ-H-CELL", user="f3d_nostock")  # група viewer без складу
        self.assertEqual((res.status_code, res.json()["error"]["code"]), (403, "forbidden"))
        self.logout()
        res = self.url_open("/f3d/viewer/loc/ZZ-H-CELL", allow_redirects=False)
        self.assertIn(res.status_code, (303, 401))

    def test_bad_code_400_unknown_404(self):
        for code in ("bad%20code", "a%27b", "x" * 65, "..%2Fx", ".hidden"):
            with self.subTest(code=code):
                res = self._get("/f3d/viewer/loc/" + code)
                self.assertEqual(res.status_code, 400)
                self.assertEqual(res.json()["error"]["code"], "bad_request")
        res = self._get("/f3d/viewer/loc/ZZ-NO-SUCH-CELL")
        self.assertEqual((res.status_code, res.json()["error"]["code"]), (404, "not_found"))

    def test_headers(self):
        res = self._get("/f3d/viewer/loc/ZZ-H-CELL")
        self.assertIn("application/json", res.headers["Content-Type"])
        self.assertEqual(res.headers["Cache-Control"], "no-store")

    # --- вміст ---------------------------------------------------------------
    def test_content(self):
        recs = self._fixture()
        data = self._get("/f3d/viewer/loc/ZZ-H-CELL").json()
        self.assertEqual((data["code"], data["truncated"]), ("ZZ-H-CELL", False))
        self.assertEqual(data["left"], [])  # усе, що приймали, ще в комірці
        by = {p["product"]: p for p in data["products"]}
        self.assertEqual(list(by), ["ZZ-FIT", "ZZ-PLATE"])
        plate = by["ZZ-PLATE"]
        self.assertEqual((plate["name"], plate["qty"], plate["reserved"]), ("ZZ Плита", 20, 20))
        lot = plate["lots"][0]
        self.assertEqual((lot["lot"], lot["qty"], lot["reserved"]), ("ZZ-LOT-1", 20, 20))

        # «Надійшло»: останні виконані приймання цієї партії, ≤ 3, новіші першими
        self.assertEqual([a["qty"] for a in lot["arrived"]], [10, 4, 3])
        first = lot["arrived"][0]
        self.assertEqual(
            first["doc"],
            {
                "name": recs["receipts"][-1].name,
                "model": "stock.picking",
                "id": recs["receipts"][-1].id,
                "kind": "picking",
                "state": "done",
            },
        )
        self.assertEqual(first["from"]["name"], "Постачальники")  # віртуальна локація — українською
        self.assertRegex(first["date"], r"^\d{4}-\d\d-\d\d \d\d:\d\d$")

        # «Резерв» і злиття з «Іде з комірки»: частково зарезервований документ — один запис з pending
        reserve = {r["doc"]["name"]: r for r in lot["reserve"]}
        self.assertEqual(set(reserve), {recs["res"].name, recs["part"].name})
        self.assertEqual((reserve[recs["res"].name]["qty"], reserve[recs["res"].name]["pending"]), (5, 0))
        part = reserve[recs["part"].name]
        self.assertEqual((part["qty"], part["pending"], part["doc"]["state"]), (15, 15, "assigned"))
        self.assertEqual(part["to"]["name"], "Клієнти")
        self.assertEqual(plate["out"], [])

        # «Очікується»: відкрите приймання в комірку
        self.assertEqual(len(plate["incoming"]), 1)
        inc = plate["incoming"][0]
        self.assertEqual((inc["doc"]["name"], inc["qty"], inc["doc"]["state"]), (recs["incoming"].name, 7, "assigned"))

        # «Іде з комірки»: підтверджене (не зарезервоване) переміщення з комірки на іншу локацію
        fit = by["ZZ-FIT"]
        self.assertEqual((fit["qty"], fit["lots"]), (0, []))
        self.assertEqual(len(fit["out"]), 1)
        out = fit["out"][0]
        self.assertEqual((out["doc"]["name"], out["qty"], out["doc"]["state"]), (recs["out"].name, 3, "waiting"))
        self.assertEqual((out["to"]["code"], out["to"]["name"]), ("ZZ-H-DEST", self.dest.complete_name))

    def test_inventory_document(self):
        """Інвентаризація (без документа-переміщення) — запис без посилання."""
        quant = (
            self.env["stock.quant"]
            .with_context(inventory_mode=True)
            .create({"product_id": self.fitting.id, "location_id": self.cell.id, "inventory_quantity": 4})
        )
        quant.action_apply_inventory()
        data = self._get("/f3d/viewer/loc/ZZ-H-CELL").json()
        fit = next(p for p in data["products"] if p["product"] == "ZZ-FIT")
        self.assertEqual((fit["qty"], len(fit["lots"])), (4, 1))
        doc = fit["lots"][0]["arrived"][0]["doc"]
        self.assertEqual(doc, {"name": "Інвентаризація", "model": None, "id": None, "kind": "inventory", "state": None})
        self.assertIsNone(fit["lots"][0]["arrived"][0]["from"])  # не «з Inventory adjustment»

    def test_virtual_places_ukrainian(self):
        """Віртуальні локації Odoo (англійські назви з даних) — українською за usage."""
        from odoo.addons.td_viewer3d.tools.loc_history import _place

        Loc = self.env["stock.location"]
        self.assertEqual(_place(Loc.search([("usage", "=", "customer")], limit=1))["name"], "Клієнти")
        self.assertEqual(_place(Loc.search([("usage", "=", "supplier")], limit=1))["name"], "Постачальники")
        self.assertIsNone(_place(Loc.search([("usage", "=", "inventory")], limit=1)))

    # --- «Раніше в комірці» (left) ----------------------------------------------
    def test_left_lot(self):
        """Партія, яка зайшла й повністю вийшла, — у `left` з документом виходу й надходженням; зі списку
        поточних товарів вона зникає."""
        arrival = self._receive(5)
        shipped = self._ship(5)
        data = self._get("/f3d/viewer/loc/ZZ-H-CELL").json()
        self.assertEqual(data["products"], [])
        self.assertEqual((data["left_days"], data["truncated"]), (30, False))
        self.assertEqual(len(data["left"]), 1)
        row = data["left"][0]
        self.assertEqual((row["product"], row["name"], row["lot"]), ("ZZ-PLATE", "ZZ Плита", "ZZ-LOT-1"))
        self.assertEqual(
            row["out"]["doc"],
            {"name": shipped.name, "model": "stock.picking", "id": shipped.id, "kind": "picking", "state": "done"},
        )
        self.assertEqual((row["out"]["qty"], row["out"]["to"]), (5, {"code": None, "name": "Клієнти"}))
        self.assertRegex(row["out"]["date"], r"^\d{4}-\d\d-\d\d \d\d:\d\d$")
        self.assertEqual(len(row["arrived"]), 1)
        self.assertEqual(
            (row["arrived"][0]["doc"]["name"], row["arrived"][0]["qty"], row["arrived"][0]["from"]["name"]),
            (arrival.name, 5, "Постачальники"),
        )

    def test_left_not_listed_while_in_cell(self):
        """Партія, що частково вийшла (залишок у комірці), лишається в `products`, а не в `left`."""
        self._receive(10)
        self._ship(4)
        data = self._get("/f3d/viewer/loc/ZZ-H-CELL").json()
        self.assertEqual(data["left"], [])
        self.assertEqual(data["products"][0]["lots"][0]["qty"], 6)

    def test_left_window_and_limit(self):
        """Вихід старший за вікно не потрапляє в `left`; понад KEEP_LEFT товарів/партій — найсвіжіші й `truncated`."""
        lots = [
            self.env["stock.lot"].create(
                {"name": "ZZ-LOT-W%d" % i, "product_id": self.plate.id, "company_id": self.wh.company_id.id}
            )
            for i in range(1, 5)
        ]
        ships = []
        for lot in lots:
            self._receive(2, lot)
            ships.append(self._ship(2))
        old = ships[0].move_line_ids
        old.date = dates.now(self.env) - timedelta(days=loc_history.LEFT_DAYS + 5)  # вікно рахується від demo_clock
        data = self._get("/f3d/viewer/loc/ZZ-H-CELL").json()
        self.assertEqual([r["lot"] for r in data["left"]], ["ZZ-LOT-W4", "ZZ-LOT-W3", "ZZ-LOT-W2"])
        self.assertFalse(data["truncated"])
        with patch.object(loc_history, "KEEP_LEFT", 2):
            data = self._get("/f3d/viewer/loc/ZZ-H-CELL").json()
        self.assertEqual([r["lot"] for r in data["left"]], ["ZZ-LOT-W4", "ZZ-LOT-W3"])
        self.assertTrue(data["truncated"])

    def test_empty_cell(self):
        data = self._get("/f3d/viewer/loc/ZZ-H-DEST").json()
        self.assertEqual(data["products"], [])

    def test_query_count_is_flat(self):
        """Пакетні вибірки: кількість запитів не росте з кількістю рядків руху."""
        self._fixture()
        env = self.env(user=self.user_f3d)

        def count():
            env.invalidate_all()
            before = env.cr.sql_log_count
            loc_history.build(env, env["stock.location"].browse(self.cell.id))
            return env.cr.sql_log_count - before

        base = count()
        for q in (1, 2, 3, 4):
            self._picking(self.wh.in_type_id, self.supplier, self.cell, self.plate, q)
            self._picking(self.wh.out_type_id, self.cell, self.customer, self.fitting, q)
        self.assertLessEqual(count(), base + 4)

    # --- R-23: стани документів, названих у кроках шляху ---------------------
    def test_doc_states_lookup(self):
        pick = self._picking(self.wh.in_type_id, self.supplier, self.cell, self.fitting, 1, confirm=False)
        done = self._receive(2)
        found = docs_tools.lookup_states(self.env, {pick.name, done.name, "NO/SUCH/00001"})
        self.assertEqual(
            found, {pick.name: {"kind": "picking", "state": "draft"}, done.name: {"kind": "picking", "state": "done"}}
        )
        pick.action_confirm()
        self.assertEqual(docs_tools.lookup_states(self.env, {pick.name})[pick.name]["state"], "assigned")
        pick.action_cancel()
        self.assertEqual(docs_tools.lookup_states(self.env, {pick.name})[pick.name]["state"], "cancel")
        self.assertEqual(docs_tools.lookup_states(self.env, set()), {})

    def test_chains_supply_docs(self):
        """Назва з нотатки кроку, якої немає в `pickings` payload, дістає стан у `supply.docs`."""
        pick = self._receive(2)
        known = self._picking(self.wh.in_type_id, self.supplier, self.cell, self.fitting, 1)
        payload = {
            "pickings": [{"name": known.name}],
            "quality_checks": [{"name": "QC/00001"}],
            "productions": [
                {
                    "name": "WH/MO/00001",
                    "supply": {
                        "note": None,
                        "steps": [
                            {"code": "A", "doc": known.name, "note": "у стелаж (%s), контроль QC/00001." % pick.name}
                        ],
                    },
                }
            ],
        }
        self.env["td.viewer.provider.chains"]._td_doc_states(payload)
        # known і QC/00001 є в payload — клієнт бере стан звідти; fallback лише для відсутніх
        self.assertEqual(payload["productions"][0]["supply"]["docs"], {pick.name: {"kind": "picking", "state": "done"}})

    def test_names_in(self):
        self.assertEqual(
            docs_tools.names_in(
                "WH/IN/00128 — фура", None, "у стелаж (WH/INT/00061), QC/00413.", "WH/Сировина/Плити/RCK-R1-3B", "10:30"
            ),
            {"WH/IN/00128", "WH/INT/00061", "QC/00413"},
        )
