"""W1-A: AC-130…AC-135, AC-133 — планове відключення (R-31, M-25)."""

from datetime import datetime, timedelta

from odoo import Command
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import NOW, TAGS, TestW1Common

START = datetime(2026, 10, 18, 4, 0)  # 07:00 Київ (наступна доба)
END = datetime(2026, 10, 18, 6, 0)  # 09:00 Київ


@tagged(*TAGS)
class TestW1OutagePlan(TestW1Common):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Plan = cls.env["td.energy.outage.plan"]
        cls.bw2 = cls.Node.search([("code", "=", "BW-2")])
        cls.affected = cls.Node.search([("id", "child_of", cls.bw2.id), ("kind", "in", ("tapoff", "consumer"))])
        cls.consumer = cls.affected.filtered(lambda n: n.kind == "consumer")[:1]
        cls.wc = cls.env["mrp.workcenter"].create({"name": "W1-WC", "code": "W1-WC"})
        cls.consumer.write({"workcenter_id": cls.wc.id})
        cls.mos = cls.env["mrp.production"]
        for k in range(3):
            cls.mos |= cls._mk_mo(k)

    @classmethod
    def _mk_mo(cls, k):
        product = cls.env["product.product"].create(
            {
                "name": "W1-%d" % k,
                "is_storable": True,
                "type": "consu",
                "categ_id": cls.env.ref("product.product_category_goods").id,
            }  # fmt: skip
        )
        bom = cls.env["mrp.bom"].create(
            {
                "product_tmpl_id": product.product_tmpl_id.id,
                "product_qty": 1.0,
                "operation_ids": [Command.create({"name": "Op", "workcenter_id": cls.wc.id})],
            }
        )
        mo = cls.env["mrp.production"].create({"product_id": product.id, "bom_id": bom.id, "product_qty": 1.0})
        mo.action_confirm()
        mo.workorder_ids.write(
            {
                "date_start": START + timedelta(minutes=20 * k + 10),
                "date_finished": START + timedelta(minutes=20 * k + 25),
            }
        )
        return mo

    def mk_plan(self, user=None, **kw):
        vals = {"node_id": self.bw2.id, "start": START, "end": END, "reason": "busway"}
        vals.update(kw)
        return self.Plan.with_user(user or self.u_eng).create(vals)

    def test_submit(self):  # AC-130
        plan = self.mk_plan()
        self.assertEqual((plan.state, plan.name), ("draft", "ШР-2 · 18.10 07:00–09:00"))
        plan.action_submit()
        self.assertEqual(plan.state, "pending")
        self.assertEqual(plan.affected_count, len(self.affected))
        self.assertEqual(plan.production_count, 3)
        group = self.env.ref("mrp.group_mrp_manager")
        managers = group.all_user_ids.filtered(lambda u: u.active and not u.share)
        self.assertTrue(self.u_mrp in managers)
        activities = plan.sudo().activity_ids
        self.assertEqual(set(activities.mapped("user_id").ids), set(managers.ids))
        stock_partners = self.u_stock.partner_id
        self.assertIn(stock_partners, plan.sudo().message_partner_ids)
        late = self.mk_plan(start=NOW - timedelta(hours=1), end=NOW + timedelta(hours=1))
        with self.assertRaisesRegex(UserError, "Початок має бути в майбутньому."):
            late.action_submit()
        with self.assertRaises(AccessError):
            self.mk_plan().with_user(self.u_view).action_submit()

    def test_approve_reject(self):  # AC-131
        plan = self.mk_plan()
        plan.action_submit()
        with self.assertRaises(AccessError) as caught:
            plan.with_user(self.u_eng).action_approve()
        self.assertEqual(str(caught.exception), "Узгоджує керівник виробництва.")
        plan.with_user(self.u_mrp).action_approve()
        self.assertEqual((plan.state, plan.approver_id), ("approved", self.u_mrp))
        self.assertEqual(plan.approved_at, NOW)
        self.assertFalse(plan.sudo().activity_ids)
        second = self.mk_plan(start=START + timedelta(days=1), end=END + timedelta(days=1))
        second.action_submit()
        with self.assertRaisesRegex(UserError, "Вкажіть причину відхилення."):
            second.with_user(self.u_mrp).action_reject("")
        second.with_user(self.u_mrp).action_reject("Збігається з відвантаженням")
        self.assertEqual((second.state, second.reject_reason), ("rejected", "Збігається з відвантаженням"))

    def test_constraints(self):  # AC-132
        with self.assertRaises(ValidationError):
            self.mk_plan(start=END, end=START)
        first = self.mk_plan()
        first.action_submit()
        with self.assertRaisesRegex(ValidationError, "вже є відключення в цей час"):
            overlap = self.mk_plan(start=START + timedelta(minutes=30), end=END + timedelta(hours=1))
            overlap.action_submit()
        with self.assertRaises(ValidationError):
            self.mk_plan(
                reason="other", reason_text=False, start=START + timedelta(days=3), end=END + timedelta(days=3)
            )

    def test_node_card_and_pult(self):  # AC-133
        plan = self.mk_plan()
        plan.action_submit()
        plan.with_user(self.u_mrp).action_approve()
        dash = self.env["td.energy.dashboard"].with_user(self.u_view)
        outage = dash.get_node_card("BW-2")["outage"]
        self.assertEqual(
            outage,
            {
                "plan_id": plan.id,
                "when": "18.10 · 07:00–09:00",
                "reason": "протяжка з'єднань шинопроводу",
                "orders": 3,
                "state": "approved",
                "state_label": "узгоджено",
            },  # fmt: skip
        )
        maint = dash.get_pult(parts=["side"])["maint"]
        self.assertTrue(any(r["title"] == "ШР-2 · планове відключення" and r["kind"] == "outage" for r in maint))

    def test_cron_close(self):  # AC-134
        approved = self.mk_plan(start=NOW - timedelta(hours=3), end=NOW - timedelta(hours=1))
        approved.sudo().write({"state": "approved"})
        pending = self.mk_plan(start=NOW - timedelta(days=2), end=NOW - timedelta(days=1))
        pending.sudo().write({"state": "pending"})
        draft = self.mk_plan(start=NOW - timedelta(days=5), end=NOW - timedelta(days=4))
        future = self.mk_plan(start=NOW + timedelta(days=4), end=NOW + timedelta(days=5))
        self.Plan._cron_close()
        self.assertEqual(
            (approved.state, pending.state, draft.state, future.state), ("done", "cancelled", "cancelled", "draft")
        )

    def test_preview(self):  # AC-135
        before = self.Plan.search_count([])
        res = self.Plan.with_user(self.u_eng).preview("BW-2", START, END)
        taps = self.affected.filtered(lambda n: n.kind == "tapoff") or self.affected
        self.assertEqual(res["tap_count"], len(taps))
        self.assertEqual(sorted(res["tap_codes"]), sorted(taps.mapped("code")))
        self.assertEqual(res["order_count"], 3)
        self.assertEqual({o["name"] for o in res["orders"]}, set(self.mos.mapped("name")))
        self.assertEqual(self.Plan.search_count([]), before)
        with self.assertRaisesRegex(UserError, "Невідомий вузол: X."):
            self.Plan.preview("X", START, END)
