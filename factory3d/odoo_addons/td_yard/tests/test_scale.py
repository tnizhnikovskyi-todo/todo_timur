from datetime import timedelta, timezone

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .flow import YardFlowCase

WCODE = "yard/scale/TRUCK-SCALE/weight_kg"
SCODE = "yard/scale/TRUCK-SCALE/stable"


@tagged("post_install", "-at_install", "f3d", "f3d_yard")
class TestYardScale(YardFlowCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Signal = env["td.signal"]

        def signal(code, name):
            return Signal.search([("code", "=", code)]) or Signal.create(
                {"code": code, "name": name, "kind": "gauge", "module": "yard", "create_request": False}
            )

        cls.scale = env.ref("td_yard.scale_truck")
        cls.scale.write(
            {"weight_signal_id": signal(WCODE, "Автоваги: вага").id, "stable_signal_id": signal(SCODE, "Стабільно").id}
        )
        cls.one_kg = cls._product("T Одиничний", 1.0, cls.categ_hdf)
        cls.guard_env = env(user=cls.user_guard)

    # ------------------------------------------------------------------ помічники
    def _weigh(self, visit, kind, kg, **vals):
        return self.env["td.yard.weighing"].create(
            dict(
                {"scale_id": self.scale.id, "visit_id": visit.id, "kind": kind, "weight_kg": kg, "source": "manual"},
                **vals,
            )
        )

    def _on_site(self, batch=None, state="handling", **vals):
        batch = batch or self._batch()
        batch.picking_ids.user_id = self.env.user
        outgoing = batch.picking_ids[:1].picking_type_code == "outgoing"
        visit_vals = {"batch_id": batch.id, "visit_type": "outgoing" if outgoing else "incoming"}
        visit = self._visit(**dict(visit_vals, **vals))
        return self._force(visit, state)

    def _ingest(self, base, specs):
        """specs: [(секунди від base, вага, 'S'|'D'|None, якість)] -> td.signal._td_ingest."""
        readings = []
        for spec in specs:
            off, weight, status = spec[:3]
            quality = spec[3] if len(spec) > 3 else "good"
            iso = (base + timedelta(seconds=off)).replace(tzinfo=timezone.utc).isoformat()
            readings.append({"code": WCODE, "ts": iso, "value": weight, "q": quality})
            if status:
                readings.append({"code": SCODE, "ts": iso, "value": 1.0 if status == "S" else 0.0})
        return self.env["td.signal"]._td_ingest(readings, src="module")

    def _autos(self):
        return self.env["td.yard.weighing"].search([("source", "=", "auto"), ("scale_id", "=", self.scale.id)])

    def _queued(self):
        visit = self._visit()
        return self._force(visit, "queued", admitted_at=fields.Datetime.now())

    # ------------------------------------------------------------------ нетто й звірка (R-12)
    def test_net_from_weighings(self):  # AC-17
        visit = self._on_site()
        picking = visit.batch_id.picking_ids
        self._weigh(visit, "in", 25200.0)
        self.assertTrue(visit.weighed_in_at)
        self.assertEqual((visit.net_kg, visit.weight_check, visit.state), (0.0, "none", "handling"))
        self._weigh(visit, "out", 14000.0)
        self.assertEqual((visit.gross_kg, visit.tare_kg, visit.net_kg), (25200.0, 14000.0, 11200.0))
        self.assertEqual((visit.weight_check, visit.deviation_pct), ("ok", 0.0))
        self.assertEqual((picking.td_net_weight_kg, picking.td_weight_check), (11200.0, "ok"))
        self.assertEqual(visit.state, "weighed")
        self.assertTrue(visit.weighed_out_at and visit.handling_end_at)
        self.assertEqual(sorted(visit.weighing_ids.mapped("role")), ["gross", "tare"])

    def test_deviation_and_activity(self):  # AC-18
        visit = self._on_site()
        picking = visit.batch_id.picking_ids
        self._weigh(visit, "out", 14000.0)
        w_in = self._weigh(visit, "in", 25520.0)
        self.assertEqual((visit.weight_check, visit.deviation_pct), ("deviation", 2.86))
        self.assertEqual(picking.td_weight_check, "deviation")
        summary = "Відхилення нетто"
        self.assertEqual(len(picking.activity_ids.filtered(lambda a: a.summary == summary)), 1)
        visit._td_yard_write_pickings()
        self.assertEqual(len(picking.activity_ids.filtered(lambda a: a.summary == summary)), 1)
        w_in.action_void()
        self._weigh(visit, "in", 25300.0)
        self.assertEqual((visit.weight_check, visit.deviation_pct), ("ok", 0.89))
        small = self._on_site(self._batch(lines=((6600, None),), product=self.one_kg))
        self._weigh(small, "out", 14000.0)
        self._weigh(small, "in", 20750.0)
        self.assertEqual((small.weight_check, small.deviation_pct), ("deviation", 2.27))

    def test_reference_outgoing_split_and_void(self):  # AC-19
        no_ref = self._on_site(self._batch(lines=((10, None),), product=self.product_nw))
        self._weigh(no_ref, "in", 20000.0)
        self._weigh(no_ref, "out", 14000.0)
        self.assertEqual(no_ref.weight_check, "no_reference")
        out = self._on_site(self._batch("outgoing", lines=((7000, None),), product=self.one_kg))
        self._weigh(out, "in", 14000.0)
        self._weigh(out, "out", 21380.0)
        self.assertEqual((out.tare_kg, out.gross_kg, out.net_kg), (14000.0, 21380.0, 7380.0))
        self.assertEqual(sorted(out.weighing_ids.mapped("role")), ["gross", "tare"])
        kgm = self.env.ref("uom.product_uom_kgm")
        weight_uom = self.env["product.template"]._get_weight_uom_id_from_ir_config_parameter()
        self.assertAlmostEqual(out.batch_id.picking_ids.shipping_weight, kgm._compute_quantity(7380.0, weight_uom), 3)
        first = self._batch(lines=((8000, None),), product=self.one_kg)
        second = self._batch(lines=((4000, None),), product=self.one_kg)
        first.picking_ids = [Command.link(second.picking_ids.id)]
        two = self._on_site(first)
        self._weigh(two, "in", 26300.0)
        w_out = self._weigh(two, "out", 14000.0)
        self.assertEqual(sorted(two.batch_id.picking_ids.mapped("td_net_weight_kg")), [4100.0, 8200.0])
        w_out.action_void()
        self.assertEqual((two.net_kg, two.weight_check, two.state), (0.0, "none", "weighed"))
        self.assertEqual(set(two.batch_id.picking_ids.mapped("td_net_weight_kg")), {0.0})
        self.assertEqual(set(two.batch_id.picking_ids.mapped("td_weight_check")), {"none"})

    # ------------------------------------------------------------------ перевірки (AC-41, AC-42)
    def test_manual_constraints(self):  # AC-41
        visit = self._on_site()
        for bad in (300.0, 61000.0):
            with self.assertRaises(ValidationError) as cm:
                self._weigh(visit, "in", bad)
            self.assertIn("поза межами", str(cm.exception))
        self._weigh(visit, "in", 25200.0)
        with self.assertRaises(ValidationError):
            self._weigh(visit, "in", 25100.0)
        with self.assertRaises(ValidationError) as cm:
            self._weigh(visit, "out", 14000.0, ts=fields.Datetime.now() + timedelta(minutes=5))
        self.assertIn("майбутньому", str(cm.exception))
        self._weigh(visit, "check", 14000.0)
        self._weigh(visit, "check", 14100.0)

    def test_stale_reading_and_offline(self):  # AC-42
        now = fields.Datetime.now()
        self._queued()
        self._ingest(now - timedelta(seconds=22), [(0, 25200.0, "S"), (1, 25200.0, "S")])
        self.assertFalse(self._autos())
        self.assertEqual(self.scale.last_weight_kg, 25200.0)
        with self.assertRaisesRegex(UserError, "введіть вагу вручну"):
            self.scale.action_capture()
        self.scale.weight_signal_id.status = "stale"
        self.scale._td_yard_refresh_offline()
        self.assertEqual(self.scale.capture_state, "offline")
        self.scale.weight_signal_id.status = "ok"
        self.scale._td_yard_refresh_offline()
        self.assertEqual(self.scale.capture_state, "idle")

    def test_capture_button_and_manual_form(self):
        visit = self._on_site(state="queued")
        action = visit._td_yard_do_weigh()  # немає показань -> ручна форма
        self.assertEqual((action["res_model"], action["context"]["default_kind"]), ("td.yard.weighing", "in"))
        now = fields.Datetime.now()
        self.scale.write({"last_weight_kg": 25200.0, "last_stable": True, "last_ts": now})
        weighing = self.scale.with_user(self.user_guard).action_capture(visit=visit)
        self.assertEqual(
            (weighing.source, weighing.kind, weighing.weight_kg, weighing.visit_id), ("auto", "in", 25200.0, visit)
        )

    def test_acl(self):
        visit = self._on_site()
        with self.assertRaises(AccessError):
            self.env["td.yard.weighing"].with_user(self.user_reader).create(
                {"scale_id": self.scale.id, "visit_id": visit.id, "kind": "in", "weight_kg": 25200.0}
            )
        weighing = self._weigh(visit, "in", 25200.0)
        weighing.with_user(self.user_guard).action_void()
        self.assertEqual(weighing.state, "void")
        with self.assertRaises(AccessError):
            weighing.with_user(self.user_reader).action_void()

    # ------------------------------------------------------------------ автозахоплення (AC-43…AC-45)
    def test_auto_capture_example(self):  # AC-43
        first = self._queued()
        base = fields.Datetime.now() - timedelta(seconds=10)
        self._ingest(base, [(0, 8400.0, "D"), (1, 17600.0, "D"), (2, 25200.0, "D"), (3, 25200.0, "S")])
        self.assertFalse(self._autos())
        self.assertEqual(self.scale.capture_state, "settling")
        self._ingest(base, [(4, 25180.0, "S")])
        weighing = self._autos()
        self.assertEqual((len(weighing), weighing.weight_kg, weighing.kind, weighing.role), (1, 25200.0, "in", "gross"))
        self.assertEqual((weighing.visit_id, weighing.state), (first, "assigned"))
        self.assertEqual(first.weighed_in_at, base + timedelta(seconds=4))
        self.assertEqual(self.scale.capture_state, "captured")
        self._ingest(base, [(5, 25200.0, "S"), (6, 25200.0, "S")])
        self.assertEqual(len(self._autos()), 1)
        self._ingest(base, [(7, 300.0, "S")])
        self.assertEqual(self.scale.capture_state, "idle")
        second = self._queued()
        self._ingest(base, [(8, 14000.0, "S"), (9, 14000.0, "S")])
        autos = self._autos()
        self.assertEqual((len(autos), autos[0].weight_kg, autos[0].visit_id), (2, 14000.0, second))

    def test_auto_capture_negatives(self):  # AC-44
        self._queued()
        base = fields.Datetime.now() - timedelta(seconds=10)
        self._ingest(base, [(0, 25200.0, "D"), (1, 25200.0, "D"), (2, 25200.0, "D")])
        self.assertFalse(self._autos())
        self._ingest(base, [(3, 25200.0, "S"), (4, 25260.0, "S")])
        self.assertFalse(self._autos())
        self.assertEqual(self.scale.candidate_kg, 25260.0)
        self._ingest(base, [(5, None, None, "bad")])
        self.assertEqual(self.scale.last_weight_kg, 25260.0)
        self.assertFalse(self._autos())

    def test_unassigned_and_out_capture(self):  # AC-45
        first, second = self._queued(), self._queued()
        base = fields.Datetime.now() - timedelta(seconds=10)
        self._ingest(base, [(0, 25200.0, "S"), (1, 25200.0, "S")])
        weighing = self._autos()
        self.assertEqual(
            (weighing.state, weighing.kind, weighing.visit_id), ("unassigned", "check", self.env["td.yard.visit"])
        )
        self.assertEqual(weighing.note, "Кандидатів: 2")
        weighing.with_user(self.user_guard).action_assign(first.id)
        self.assertEqual((weighing.state, weighing.kind, weighing.visit_id), ("assigned", "in", first))
        self.assertTrue(first.weighed_in_at)
        self._force(first, "handling", handling_end_at=fields.Datetime.now())
        self._force(second, "cancelled")
        self._ingest(base, [(2, 300.0, "S"), (3, 14000.0, "S"), (4, 14000.0, "S")])
        out = self._autos() - weighing
        self.assertEqual((out.kind, out.visit_id, out.weight_kg), ("out", first, 14000.0))
        self.assertEqual(first.state, "weighed")

    def test_read_disabled_skips_capture(self):
        from ..tools import params as P

        P.set_param(self.env, "read_enabled", "False")
        self._queued()
        base = fields.Datetime.now() - timedelta(seconds=10)
        self._ingest(base, [(0, 25200.0, "S"), (1, 25200.0, "S")])
        self.assertFalse(self._autos())
        self.assertEqual(self.scale.last_weight_kg, 0.0)

    def test_seed_scale(self):  # AC-46 (ваги)
        scale = self.env.ref("td_yard.scale_truck")
        self.assertEqual((scale.max_kg, scale.min_kg, scale.division_kg), (60000.0, 400.0, 20.0))
        self.assertEqual((scale.pos_x, scale.pos_y), (172.0, -14.0))
        self.assertEqual(self.env.ref("td_yard.gate_e").scale_id, scale)
