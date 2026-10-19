import csv
import json
from unittest.mock import patch

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools import file_open

from .. import hooks
from ..hooks import migrate
from ..tools import params as P
from .flow import YardFlowCase, at

SIG_CODES = ("yard/gates/", "yard/scale/", "yard/lpr/")


@tagged("post_install", "-at_install", "f3d", "f3d_yard")
class TestYardMigration(YardFlowCase):
    def _csv(self):
        with file_open(migrate.CSV_PATH, "rb") as fh:
            return list(csv.DictReader(fh.read().decode("utf-8").splitlines()))

    def _synthetic(self):
        """Пакети TRUCK-T-1 (приймання) і TRUCK-T-2 (відвантаження) з доками й перевізником."""
        product = self.env["product.product"].create({"name": "T Доставка", "type": "service"})
        carrier = self.env["delivery.carrier"].create(
            {"name": "Власний транспорт", "delivery_type": "fixed", "product_id": product.id}
        )
        partner = self.env["res.partner"].create({"name": "Контрагент Т", "is_company": True})
        b_in = self._batch("incoming", partner=partner, dock=self.dock_t1, start=at(9, 30), end=at(10, 30))
        b_out = self._batch("outgoing", partner=partner, dock=self.dock_t3, start=at(12, 0), end=at(13, 0))
        b_out.picking_ids.carrier_id = carrier
        b_in.td_code, b_out.td_code = "TRUCK-T-1", "TRUCK-T-2"
        return b_in | b_out, carrier

    # ------------------------------------------------------------------ AC-48
    def test_signals_loaded(self):  # AC-48
        Signal = self.env["td.signal"].with_context(active_test=False)
        rows = self._csv()
        self.assertEqual(len(rows), 18)
        sigs = Signal.search([("code", "in", [r["code"] for r in rows])])
        self.assertEqual(len(sigs), 18)
        self.assertEqual(set(sigs.mapped("module")), {"yard"})
        for row in rows:
            sig = sigs.filtered(lambda s, row=row: s.code == row["code"])
            self.assertEqual(sig.address, json.loads(row["address"]), row["code"])
        self.assertEqual(sigs.filtered(lambda s: s.code.endswith("TRUCK-SCALE/stable")).address["field"], "stable")
        sources = self.env["td.source"].search([("code", "in", [s["code"] for s in migrate.SOURCES])])
        self.assertEqual(len(sources), 2)
        self.assertEqual(set(sources.mapped("module")), {"yard"})
        for spec in migrate.SOURCES:  # валідація telemetry виконана constrains при записі
            self.assertEqual(sources.filtered(lambda s, spec=spec: s.code == spec["code"]).params, spec["params"])
        lpr = sigs.filtered(lambda s: s.code.startswith("yard/lpr/"))
        push = self.env.ref("td_telemetry.source_http_push", raise_if_not_found=False)
        if push:
            self.assertEqual(lpr.source_id, push)
        linked = 0
        for xmlid in ("gate_w", "gate_e", "scale_truck"):
            rec = self.env.ref("td_yard." + xmlid)
            linked += sum(1 for f in rec._fields if f.endswith("_signal_id") and rec[f])
        self.assertEqual(linked, 16)

    def test_signals_step_idempotent(self):  # AC-48
        sig = self.env["td.signal"].search([("code", "=", "yard/scale/TRUCK-SCALE/weight_kg")])
        sig.sudo().write({"last_value": 12345.0})
        res = migrate.signals_and_sources(self.env)
        self.assertEqual((res["signals_created"], res["signals_updated"], res["linked"]), (0, 18, 16))
        self.assertEqual(sig.last_value, 12345.0)

    def test_ingest_foreign_codes_skip_hook(self):  # AC-48
        Signal = self.env["td.signal"]
        sig = Signal.create({"code": "other/x/y", "name": "T", "kind": "gauge", "create_request": False})
        readings = [{"code": sig.code, "ts": "2026-10-12T10:00:00Z", "value": float(i)} for i in range(3)]
        with patch.object(type(Signal), "_td_yard_safe") as safe:
            Signal._td_ingest(readings, src="module")
        safe.assert_not_called()

    # ------------------------------------------------------------------ AC-72 (крок 0)
    def test_params_step(self):  # AC-72
        icp = self.env["ir.config_parameter"].sudo()
        for environment, expected in (("test", "True"), ("prod", "False")):
            icp.set_param(migrate.KEY_ENV, environment)
            P.set_param(self.env, "migration_state", "pending")
            P.set_param(self.env, "read_enabled", "x")
            migrate.params(self.env)
            self.assertEqual(P.get_str(self.env, "read_enabled"), expected)
        P.set_param(self.env, "migration_state", "done")
        P.set_param(self.env, "read_enabled", "True")
        self.assertEqual(migrate.params(self.env), {"skipped": 1})
        self.assertEqual(P.get_str(self.env, "read_enabled"), "True")

    # ------------------------------------------------------------------ AC-76
    def test_run_all_synthetic(self):  # AC-76
        batches, carrier = self._synthetic()
        rep = hooks.run_all(self.env)
        self.assertEqual(rep["errors"], [])
        self.assertEqual(rep["visits_from_batches"]["visits"], 2)
        self.assertEqual(rep["bookings_from_batches"], {"bookings": 2, "conflicts": 0})
        visits = batches.td_visit_ids
        self.assertEqual(set(visits.mapped("state")), {"handling"})
        self.assertEqual(set(visits.booking_ids.mapped("source")), {"migration"})
        self.assertEqual(set(visits.booking_ids.mapped("state")), {"confirmed"})
        v_in, v_out = batches[0].td_visit_ids, batches[1].td_visit_ids
        self.assertEqual((v_in.visit_type, v_out.visit_type), ("incoming", "outgoing"))
        self.assertEqual(v_in.carrier_id, v_in.partner_id)
        self.assertEqual(v_out.carrier_id, self.env.company.partner_id)
        self.assertEqual(v_in.wait_min, 20.0)
        self.assertEqual(P.get_str(self.env, "migration_state"), "done")
        again = hooks.run_all(self.env)
        self.assertEqual(again["visits_from_batches"]["visits"], 0)
        self.assertEqual(again["bookings_from_batches"]["bookings"], 0)
        self.assertEqual(len(batches.td_visit_ids), 2)
        self.assertEqual(json.loads(P.get_str(self.env, "migration_report"))["visits_from_batches"]["visits"], 0)

    def test_run_all_empty_skipped(self):  # AC-76
        self.env["stock.picking.batch"].search([("td_code", "=like", "TRUCK-%")]).write({"td_code": False})
        rep = hooks.run_all(self.env)
        self.assertTrue(rep["visits_from_batches"]["skipped"])
        self.assertEqual(P.get_str(self.env, "migration_state"), "skipped")

    def test_step_error_isolated(self):  # R-24
        def carrier_partners(env):
            raise ValueError("boom")

        with (
            patch.object(hooks, "STEPS", (carrier_partners, migrate.product_weights)),
            self.assertLogs("odoo.addons.td_yard.hooks", level="ERROR"),
        ):
            rep = hooks.run_all(self.env)
        self.assertEqual(len(rep["errors"]), 1)
        self.assertIn("product_weights", rep)
        self.assertEqual(P.get_str(self.env, "migration_state"), "partial")

    def test_run_migration_button(self):  # V-34
        Visit = self.env["td.yard.visit"]
        with self.assertRaises(AccessError):
            Visit.with_user(self.user_manager).f3d_yard_run_migration()
        action = Visit.f3d_yard_run_migration()
        self.assertEqual(action["tag"], "display_notification")

    # ------------------------------------------------------------------ AC-77
    def test_product_weights(self):  # AC-77
        Product = self.env["product.product"]
        a = Product.create({"name": "T SON", "default_code": "DSP16-SON", "weight": 0})
        b = Product.create({"name": "T MDF", "default_code": "MDF18-RAW", "weight": 0})
        c = Product.create({"name": "T WHT", "default_code": "DSP16-WHT", "weight": 60})
        self.assertEqual(migrate.product_weights(self.env)["products_weighted"], 2)
        self.assertEqual((a.weight, b.weight, c.weight), (56.0, 70.0, 60.0))
        a.weight = 0
        P.set_param(self.env, "seed_product_weights", "False")
        self.assertEqual(migrate.product_weights(self.env)["products_weighted"], 0)
        self.assertEqual(a.weight, 0)

    def test_carrier_partners(self):  # R-24 крок 4
        product = self.env["product.product"].create({"name": "T Дост", "type": "service"})
        own = self.env["delivery.carrier"].create(
            {"name": "Власний транспорт", "delivery_type": "fixed", "product_id": product.id}
        )
        partner = self.env["res.partner"].create({"name": "НП Т", "is_company": True})
        other = self.env["delivery.carrier"].create(
            {"name": "НП Т", "delivery_type": "fixed", "product_id": product.id}
        )
        res = migrate.carrier_partners(self.env)
        self.assertGreaterEqual(res["carriers_linked"], 2)
        self.assertEqual(own.td_partner_id, self.env.company.partner_id)
        self.assertEqual(other.td_partner_id, partner)
        self.assertTrue(partner.td_is_carrier)

    # ------------------------------------------------------------------ AC-79
    def test_manual_cycle_without_signals(self):  # AC-79
        batch = self._batch("incoming", dock=self.dock_t1, start=at(9, 30), end=at(10, 30))
        visit = self._visit(plate="АА7777КТ", batch_id=batch.id)
        booking = self._booking(visit, self.dock_t1, at(9, 30), at(10, 30), confirm=True)
        self.assertTrue(booking)
        guard = self.env(user=self.user_guard)
        v = guard["td.yard.visit"].browse(visit.id)
        self.env["ir.config_parameter"].sudo().set_param("td.yard.write_enabled", "False")
        v.action_arrive()
        res = v.action_admit()
        self.assertIn("пульта", res["params"]["message"])
        gate = self.env.ref("td_yard.gate_w")
        self.assertEqual(gate.admitted_today, 1)
        self.assertEqual(gate.state, "unknown")
        data = guard["td.yard.visit"].kpp_data()
        self.assertFalse(data["can"]["command"])
        v.action_call_to_dock()
        scale = self.env.ref("td_yard.scale_truck")
        W = self.env["td.yard.weighing"]
        W.create({"scale_id": scale.id, "visit_id": visit.id, "kind": "in", "weight_kg": 25200, "source": "manual"})
        W.create({"scale_id": scale.id, "visit_id": visit.id, "kind": "out", "weight_kg": 14000, "source": "manual"})
        self.assertAlmostEqual(visit.net_kg, 11200.0)
        v.action_leave()
        self.assertEqual(visit.state, "left")
