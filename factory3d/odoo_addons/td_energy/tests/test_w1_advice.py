"""W1-A: AC-116, AC-117 — слот рекомендацій (M-26, R-32)."""

from datetime import timedelta

from unittest.mock import patch

from odoo.tests import tagged

from .common import NOW, TAGS, TestW1Common


def rule_test(self, now):
    """Тестове правило-спадкоємець реєстру `_td_advice_rule_*` (C-32)."""
    return [
        {
            "code": "RULE-T",
            "dedup_key": "RULE-T:T2",
            "title": "Правило W1",
            "text": "Текст правила",
            "level": "info",
            "node_code": "T2",
            "actions": [],
            "expires_in_min": 30,
        }
    ]


@tagged(*TAGS)
class TestW1Advice(TestW1Common):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Advice = cls.env["td.energy.advice"]

    def seed(self):
        self.Advice.search([]).write({"state": "dismissed"})
        return self.Advice._td_demo_seed()

    def pult_advice(self, user=None):
        dash = self.env["td.energy.dashboard"].with_user(user or self.u_view)
        return dash.get_pult(parts=["advice"])["advice"]

    def test_slot_and_snooze(self):  # AC-116
        advice = self.seed()
        self.assertEqual(advice.code, "EXPORT-T2")
        data = self.pult_advice()
        self.assertEqual([a["kind"] for a in data["actions"]], ["link", "control", "control"])
        self.assertEqual([a["enabled"] for a in data["actions"]], [True, False, False])
        self.assertEqual(data["node_code"], "T2")
        advice.with_user(self.u_eng).action_snooze()
        self.assertEqual((advice.state, advice.snooze_until), ("snoozed", NOW + timedelta(minutes=30)))
        self.assertFalse(self.pult_advice())
        later = self.env["td.energy.dashboard"].with_user(self.u_view).with_context(f3d_now=NOW + timedelta(minutes=31))
        self.assertEqual(later.get_pult(parts=["advice"])["advice"]["code"], "EXPORT-T2")
        advice.with_user(self.u_eng).action_dismiss()
        self.assertFalse(self.pult_advice())
        self.assertFalse(self.Advice.get_open())

    def test_rules_registry(self):  # AC-117
        self.Advice.search([]).write({"state": "dismissed"})
        with patch.object(self.registry["td.energy.advice"], "_td_advice_rule_test", rule_test, create=True):
            self.Advice._cron_advice()
            self.Advice._cron_advice()
        found = self.Advice.search([("dedup_key", "=", "RULE-T:T2")])
        self.assertEqual(len(found), 1)
        self.assertEqual((found.kind, found.state, found.node_id.code), ("rule", "open", "T2"))
        self.assertEqual(found.expires_at, NOW + timedelta(minutes=30))
        self.Advice._cron_advice()  # правило більше не повертає елемент
        self.assertEqual(found.state, "expired")
