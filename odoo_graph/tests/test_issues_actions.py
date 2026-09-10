"""Проверки find_issues, которые говорят о действиях сервера:

competing_writer, dangling_action.
"""

import unittest

from odoo_graph_fixtures import (AnalyzerCase, snapshot, field, view,
                                 automation, action, kinds_of)

VISIBLE_FORM = view(7, "hr.expense", '<data><field name="x_over_limit"/></data>',
                    name="Витрата: ознака", inherit_id=500,
                    inherit_name="hr.expense.form")


class CompetingWriterTest(AnalyzerCase, unittest.TestCase):

    def _snap(self, manual_value, auto_value="True", manual_state="object_write"):
        return snapshot(
            fields=[field("hr.expense", "x_over_limit", ttype="boolean",
                          label="Понад ліміт")],
            views=[VISIBLE_FORM],
            automations=[automation(7, "hr.expense",
                                    "[('total_amount','>',800)]",
                                    name="Витрата понад ліміт")],
            actions=[action(1321, "hr.expense", name="Автоматична позначка",
                            automation_id=7, writes_path="x_over_limit",
                            writes_value=auto_value),
                     action(1331, "hr.expense", name="Ручна позначка",
                            state=manual_state, usage="ir_actions_server",
                            automation_id=None, writes_path="x_over_limit",
                            writes_value=manual_value)])

    def test_manual_action_writes_a_value_outside_the_automatic_set(self):
        issues = self.run_issues(self._snap(manual_value=False))
        found = self.assertKind(issues, "competing_writer", count=1,
                                severity="высокая")
        self.assertIn("Ручна позначка", found[0]["title"])
        self.assertIn("hr.expense.x_over_limit", found[0]["title"])
        self.assertIn("выводит запись из согласованного состояния",
                      found[0]["detail"])

    def test_manual_action_duplicating_the_automatic_value_is_softer(self):
        issues = self.run_issues(self._snap(manual_value="True"))
        found = self.assertKind(issues, "competing_writer", count=1,
                                severity="средняя")
        self.assertIn("логика", found[0]["detail"])

    def test_silent_when_every_writer_belongs_to_an_automation(self):
        snap = self._snap(manual_value=False)
        snap["server_actions"][1]["automation_id"] = 7
        issues = self.run_issues(snap)
        self.assertNoKind(issues, "competing_writer")

    def test_silent_when_every_writer_is_manual(self):
        snap = self._snap(manual_value=False)
        snap["server_actions"][0]["automation_id"] = None
        issues = self.run_issues(snap)
        self.assertNoKind(issues, "competing_writer")

    def test_silent_when_writers_touch_different_fields(self):
        snap = self._snap(manual_value=False)
        snap["fields_manual"].append(
            field("hr.expense", "x_note", label="Примітка"))
        snap["server_actions"][1]["writes_path"] = "x_note"
        issues = self.run_issues(snap)
        self.assertNoKind(issues, "competing_writer")

    def test_reported_together_with_the_dangling_action(self):
        # Ручное действие того же типа, что и привязанное, — ещё и дубль.
        issues = self.run_issues(self._snap(manual_value=False))
        self.assertEqual(kinds_of(issues),
                         ["competing_writer", "dangling_action"])

    @unittest.expectedFailure
    def test_values_are_compared_normalized(self):
        # НАЙДЕННЫЕ-БАГИ.md, находка 4: значения сравниваются сырыми строками,
        # поэтому `approved` и ` approved` считаются разными и проблема
        # получает критичность «высокая» вместо «средняя».
        issues = self.run_issues(self._snap(manual_value=" approved",
                                            auto_value="approved"))
        self.assertKind(issues, "competing_writer", count=1,
                        severity="средняя")


class DanglingActionTest(AnalyzerCase, unittest.TestCase):

    def _snap(self, manual_state="next_activity", manual_model="sale.order",
              usage="ir_actions_server"):
        return snapshot(
            automations=[automation(1, "sale.order", name="Нагадування")],
            actions=[action(597, "sale.order", name="Створити активність",
                            state="next_activity", automation_id=1),
                     action(598, manual_model, name="Передзвонити клієнту",
                            state=manual_state, usage=usage,
                            automation_id=None)])

    def test_manual_copy_of_a_linked_action(self):
        issues = self.run_issues(self._snap())
        found = self.assertKind(issues, "dangling_action", count=1,
                                severity="средняя")
        self.assertEqual(len(issues), 1)
        self.assertIn("Передзвонити клієнту", found[0]["title"])
        self.assertIn("sale.order", found[0]["detail"])
        self.assertEqual(found[0]["where"], "sale.order")

    def test_silent_when_the_manual_action_is_of_another_type(self):
        issues = self.run_issues(self._snap(manual_state="code"))
        self.assertQuiet(issues)

    def test_silent_when_the_manual_action_is_on_another_model(self):
        issues = self.run_issues(self._snap(manual_model="purchase.order"))
        self.assertQuiet(issues)

    def test_silent_for_scheduled_actions(self):
        issues = self.run_issues(self._snap(usage="ir_cron"))
        self.assertQuiet(issues)

    def test_silent_when_no_action_of_that_type_is_linked(self):
        issues = self.run_issues(snapshot(actions=[
            action(598, "sale.order", name="Передзвонити клієнту",
                   state="next_activity", usage="ir_actions_server",
                   automation_id=None),
            action(599, "sale.order", name="Надіслати листа",
                   state="mail_post", usage="ir_actions_server",
                   automation_id=None)]))
        self.assertQuiet(issues)

    def test_silent_when_all_actions_are_linked(self):
        snap = self._snap()
        snap["server_actions"][1]["automation_id"] = 1
        issues = self.run_issues(snap)
        self.assertQuiet(issues)

    def test_every_unlinked_duplicate_is_reported(self):
        snap = self._snap()
        snap["server_actions"].append(
            action(599, "sale.order", name="Ще одне нагадування",
                   state="next_activity", usage="ir_actions_server",
                   automation_id=None))
        issues = self.run_issues(snap)
        self.assertKind(issues, "dangling_action", count=2)


if __name__ == "__main__":
    unittest.main()
