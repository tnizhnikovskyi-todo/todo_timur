import unittest
from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import F3dViewerBase


@tagged("post_install", "-at_install", "f3d", "f3d_viewer")
class TestBus(F3dViewerBase):
    """M-03, M-07, R-15: AC-18, AC-20, AC-49."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.Event = env["f3d.viewer.event"]
        cls.wh = env["stock.warehouse"].search([], limit=1)
        cls.loc_a = env["stock.location"].create(
            {"name": "TST-A", "location_id": cls.wh.lot_stock_id.id, "f3d_code": "TST-LOC-A"})
        cls.loc_b = env["stock.location"].create(
            {"name": "TST-B", "location_id": cls.wh.lot_stock_id.id, "f3d_code": "TST-LOC-B"})
        cls.product = env["product.product"].create({"name": "TST bus", "default_code": "TST-BUS", "is_storable": True})
        env["stock.quant"]._update_available_quantity(cls.product, cls.loc_a, 100)

    def _flush(self):
        self.env.flush_all()
        self.env.cr.precommit.run()
        self.env.flush_all()

    def _reset(self):
        """Скидає накопичене під час фікстур: події й повідомлення починаються з нуля."""
        self._flush()
        self.Event.sudo().search([]).unlink()
        return self.bus_messages()

    def _events(self):
        return self.Event.sudo().search([])

    def test_coalesce_action_assign(self):
        """AC-18: 12 переміщень в одній транзакції -> не більше 3 подій і 3 повідомлень."""
        sent = self._reset()
        picking_type = self.wh.int_type_id
        pickings = self.env["stock.picking"]
        for _i in range(12):
            pickings |= self.env["stock.picking"].create({
                "picking_type_id": picking_type.id, "location_id": self.loc_a.id,
                "location_dest_id": self.loc_b.id,
                "move_ids": [(0, 0, {"product_id": self.product.id, "product_uom_qty": 1,
                                     "location_id": self.loc_a.id, "location_dest_id": self.loc_b.id})]})
        pickings.action_confirm()
        pickings.action_assign()
        self._flush()
        events = self._events()
        self.assertTrue(0 < len(events) <= 3, events.mapped("model"))
        self.assertTrue(set(events.mapped("model")) <= {"stock.picking", "stock.move.line", "stock.quant"})
        self.assertTrue(0 < len(sent) <= 3)
        for target, ntype, msg in sent:
            self.assertEqual((target, ntype), ("f3d_viewer", "f3d_viewer"))
            self.assertEqual(set(msg), {"model", "codes", "kind", "ts"})
            self.assertRegex(msg["ts"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
        by_model = {e.model: e for e in events}
        self.assertTrue({"TST-LOC-A", "TST-LOC-B"} & set(by_model["stock.move.line"].codes))
        self.assertTrue(set(pickings.mapped("name")) <= set(by_model["stock.picking"].codes))
        self.assertEqual(by_model["stock.picking"].kind, "doc")
        self.assertEqual(by_model["stock.move.line"].kind, "stock")

    def test_workorder_finish_codes(self):
        wc = self.env["mrp.workcenter"].create({"name": "TST WC", "code": "TSTWC", "f3d_code": "TST-WC-BUS"})
        fin = self.env["product.product"].create({"name": "TST fin", "default_code": "TST-FIN-B", "is_storable": True})
        bom = self.env["mrp.bom"].create({
            "product_tmpl_id": fin.product_tmpl_id.id, "product_id": fin.id, "product_qty": 1, "code": "TB",
            "operation_ids": [(0, 0, {"name": "Op", "workcenter_id": wc.id, "time_cycle_manual": 10})]})
        mo = self.env["mrp.production"].create({"product_id": fin.id, "bom_id": bom.id, "product_qty": 1})
        mo.action_confirm()
        wo = mo.workorder_ids[:1]
        self._reset()
        wo.button_start()
        wo.button_finish()
        self._flush()
        ev = self._events().filtered(lambda e: e.model == "mrp.workorder")
        self.assertTrue(ev)
        codes = set().union(*[set(e.codes) for e in ev])
        self.assertTrue({"WO%05d" % wo.id, mo.name, "TST-WC-BUS"} <= codes, codes)
        self.assertEqual(set(ev.mapped("kind")), {"state"})

    def test_maintenance_event_snapshot(self):
        """AC-49."""
        eq = self.env["maintenance.equipment"].create({"name": "TST CNC", "f3d_code": "TST-CNC-2"})
        stage_new = self.env.ref("maintenance.stage_0")
        stage_work = self.env.ref("maintenance.stage_1")
        req = self.env["maintenance.request"].create(
            {"name": "TST/MR/00031", "equipment_id": eq.id, "stage_id": stage_new.id})
        self._reset()
        self.env["f3d.viewer.snapshot"].sudo().search([]).unlink()
        req.write({"stage_id": stage_work.id})
        self._flush()
        ev = self._events().filtered(lambda e: e.model == "maintenance.request")
        self.assertEqual(ev.kind, "maintenance")
        self.assertTrue({"TST/MR/00031", "TST-CNC-2"} <= set(ev.codes))
        snap = self.env["f3d.viewer.snapshot"].sudo().search([("kind", "=", "event")])
        self.assertEqual(len(snap), 1)
        self.assertEqual(snap.note, "Зупинка TST-CNC-2 · TST/MR/00031")

    def test_bus_disabled_param(self):
        sent = self._reset()
        self.set_param("bus_enabled", "False")
        self.Event._notify("stock.quant", ["TST-LOC-A"], "stock")
        self._flush()
        self.assertEqual(len(self._events()), 1)
        self.assertEqual(sent, [])
        self.set_param("bus_enabled", "True")
        self.Event._notify("stock.quant", ["TST-LOC-A"], "stock")
        self._flush()
        self.assertEqual(len(sent), 1)

    def test_empty_codes_ignored(self):
        self._reset()
        self.Event._notify("stock.quant", ["", None, False], "stock")
        self._flush()
        self.assertFalse(self._events())

    def test_codes_cap_500(self):
        sent = self._reset()
        self.Event._notify("stock.quant", ["C%04d" % i for i in range(600)], "stock")
        self._flush()
        ev = self._events()
        self.assertEqual((len(ev), len(ev.codes), ev.n), (1, 500, 500))
        self.assertEqual(len(sent[0][2]["codes"]), 500)

    def test_since(self):
        self._reset()
        t0 = fields.Datetime.now() - timedelta(seconds=5)
        self.Event._notify("stock.quant", ["A"], "stock")
        self.Event._notify("mrp.workorder", ["WO00001"], "state")
        self._flush()
        self.assertEqual(self.Event._since(t0), {"stock.quant": {"A"}, "mrp.workorder": {"WO00001"}})
        self.assertEqual(self.Event._since(fields.Datetime.now() + timedelta(seconds=30)), {})
        self.assertIsNone(self.Event._since(fields.Datetime.now() - timedelta(days=3)))
        self.assertIsNone(self.Event._since(t0, limit=1))

    def test_signal_cron(self):
        """AC-20."""
        if "x_f3d_signal" not in self.env:
            raise unittest.SkipTest("немає x_f3d_signal (factory3d_iot_sim)")
        Signal = self.env["x_f3d_signal"].sudo()
        sigs = Signal.search([("x_active", "=", True), ("x_code", "!=", False)], limit=3)
        if len(sigs) < 3:
            raise unittest.SkipTest("менше трьох сигналів")
        self.set_param("signal_bus_ts", "")
        self.Event._cron_signal_bus()
        self._reset()
        sigs.write({"x_updated": fields.Datetime.now() + timedelta(minutes=5)})
        self.Event._cron_signal_bus()
        self._flush()
        ev = self._events()
        self.assertEqual((len(ev), ev.kind, ev.model), (1, "signal", "x_f3d_signal"))
        self.assertEqual(set(ev.codes), set(sigs.mapped("x_code")))
        self.Event._cron_signal_bus()
        self._flush()
        self.assertEqual(len(self._events()), 1)
