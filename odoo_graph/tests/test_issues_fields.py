"""Проверки find_issues, которые говорят о кастомных полях:

orphan_field, odoo_mechanism, invisible_result, unreachable_gate,
unreachable_state.
"""

import unittest

from odoo_graph_fixtures import (AnalyzerCase, snapshot, field, view,
                                 automation, action)


class OrphanFieldTest(AnalyzerCase, unittest.TestCase):

    def test_field_without_any_reference(self):
        issues = self.run_issues(snapshot(
            fields=[field("sale.order", "x_note", label="Примітка")]))
        found = self.assertKind(issues, "orphan_field", count=1,
                                severity="высокая")
        self.assertEqual(len(issues), 1)
        self.assertIn("sale.order.x_note", found[0]["title"])
        self.assertEqual(found[0]["where"], "sale.order")

    def test_silent_when_field_is_shown_in_a_view(self):
        issues = self.run_issues(snapshot(
            fields=[field("sale.order", "x_note", label="Примітка")],
            views=[view(7, "sale.order", '<data><field name="x_note"/></data>',
                        name="Замовлення: примітка", inherit_id=500,
                        inherit_name="sale.order.form")]))
        self.assertQuiet(issues)

    def test_silent_when_field_is_written_by_an_action(self):
        issues = self.run_issues(snapshot(
            fields=[field("sale.order", "x_note", label="Примітка")],
            actions=[action(11, "sale.order", name="Заповнити примітку",
                            writes_path="x_note", writes_value="ok")]))
        self.assertNoKind(issues, "orphan_field")

    def test_silent_when_field_gates_an_automation(self):
        issues = self.run_issues(snapshot(
            fields=[field("sale.order", "x_visa", ttype="boolean",
                          label="Віза")],
            automations=[automation(4, "sale.order", "[('x_visa','!=',False)]",
                                    name="Знижка узгоджена")]))
        self.assertNoKind(issues, "orphan_field")

    def test_field_shown_only_in_a_view_of_another_model_is_an_orphan(self):
        issues = self.run_issues(snapshot(
            fields=[field("sale.order", "x_note", label="Примітка")],
            views=[view(7, "purchase.order",
                        '<data><field name="x_note"/></data>',
                        name="Закупівля", inherit_id=500,
                        inherit_name="purchase.order.form")]))
        self.assertKind(issues, "orphan_field", count=1)


class OdooMechanismTest(AnalyzerCase, unittest.TestCase):

    def test_analytic_plan_field_is_a_mechanism_not_an_orphan(self):
        issues = self.run_issues(snapshot(
            fields=[field("account.move.line", "x_plan2_id", ttype="many2one",
                          label="Напрям", relation="account.analytic.account")]))
        found = self.assertKind(issues, "odoo_mechanism", count=1,
                                severity="низкая")
        self.assertNoKind(issues, "orphan_field")
        self.assertIn("служебное поле Odoo", found[0]["title"])
        self.assertIn("аналитический план", found[0]["detail"])

    def test_any_plan_number_matches(self):
        issues = self.run_issues(snapshot(fields=[
            field("account.move.line", "x_plan2_id", label="Напрям"),
            field("account.move.line", "x_plan17_id", label="Проєкт")]))
        self.assertKind(issues, "odoo_mechanism", count=2)
        self.assertNoKind(issues, "orphan_field")

    def test_silent_when_the_mechanism_field_is_shown(self):
        issues = self.run_issues(snapshot(
            fields=[field("account.move.line", "x_plan2_id", label="Напрям")],
            views=[view(7, "account.move.line",
                        '<data><field name="x_plan2_id"/></data>',
                        name="Рядок проводки", inherit_id=500,
                        inherit_name="account.move.line.form")]))
        self.assertQuiet(issues)

    def test_similar_name_is_not_whitelisted(self):
        # x_plan_id (без номера) под шаблон механизма не подходит.
        issues = self.run_issues(snapshot(
            fields=[field("account.move.line", "x_plan_id", label="Напрям")]))
        self.assertNoKind(issues, "odoo_mechanism")
        self.assertKind(issues, "orphan_field", count=1)


class InvisibleResultTest(AnalyzerCase, unittest.TestCase):

    def _snap(self, extra_views=()):
        return snapshot(
            fields=[field("hr.expense", "x_over_limit", ttype="boolean",
                          label="Понад ліміт")],
            automations=[automation(7, "hr.expense",
                                    "[('total_amount','>',800)]",
                                    name="Витрата понад ліміт")],
            actions=[action(1321, "hr.expense", name="Позначити витрату",
                            automation_id=7, writes_path="x_over_limit",
                            writes_value="True")],
            views=list(extra_views))

    def test_system_writes_into_a_field_nobody_can_see(self):
        issues = self.run_issues(self._snap())
        found = self.assertKind(issues, "invisible_result", count=1,
                                severity="средняя")
        self.assertEqual(len(issues), 1)
        self.assertIn("hr.expense.x_over_limit", found[0]["title"])
        self.assertIn("Позначити витрату", found[0]["detail"])

    def test_silent_when_the_field_is_shown(self):
        issues = self.run_issues(self._snap(extra_views=[
            view(7, "hr.expense", '<data><field name="x_over_limit"/></data>',
                 name="Витрата", inherit_id=500,
                 inherit_name="hr.expense.form")]))
        self.assertQuiet(issues)

    def test_silent_when_nobody_writes(self):
        issues = self.run_issues(snapshot(
            fields=[field("hr.expense", "x_over_limit", ttype="boolean",
                          label="Понад ліміт")]))
        self.assertNoKind(issues, "invisible_result")


class UnreachableGateTest(AnalyzerCase, unittest.TestCase):

    def test_gate_field_has_no_way_to_be_filled(self):
        issues = self.run_issues(snapshot(
            fields=[field("sale.order", "x_visa", ttype="boolean",
                          label="Віза керівника")],
            automations=[automation(4, "sale.order", "[('x_visa','!=',False)]",
                                    name="Знижка узгоджена")]))
        found = self.assertKind(issues, "unreachable_gate", count=1,
                                severity="высокая")
        self.assertEqual(len(issues), 1)
        self.assertIn("sale.order.x_visa", found[0]["title"])
        self.assertIn("Знижка узгоджена", found[0]["detail"])

    def test_silent_when_the_gate_is_shown_in_a_form(self):
        issues = self.run_issues(snapshot(
            fields=[field("sale.order", "x_visa", ttype="boolean",
                          label="Віза керівника")],
            automations=[automation(4, "sale.order", "[('x_visa','!=',False)]",
                                    name="Знижка узгоджена")],
            views=[view(7, "sale.order", '<data><field name="x_visa"/></data>',
                        name="Замовлення: віза", inherit_id=500,
                        inherit_name="sale.order.form")]))
        self.assertQuiet(issues)

    def test_silent_when_an_action_fills_the_gate(self):
        issues = self.run_issues(snapshot(
            fields=[field("sale.order", "x_visa", ttype="boolean",
                          label="Віза керівника")],
            automations=[automation(4, "sale.order", "[('x_visa','!=',False)]",
                                    name="Знижка узгоджена")],
            actions=[action(11, "sale.order", name="Поставити візу",
                            automation_id=4, writes_path="x_visa",
                            writes_value="True")]))
        self.assertNoKind(issues, "unreachable_gate")
        self.assertKind(issues, "invisible_result", count=1)


class UnreachableStateTest(AnalyzerCase, unittest.TestCase):

    def _snap(self, writes_value="head", domain="[('x_approval','=','approved')]",
              extra_views=(), automation_id=4):
        return snapshot(
            fields=[field("sale.order", "x_approval", ttype="selection",
                          label="Узгодження знижки")],
            automations=[automation(4, "sale.order", domain,
                                    name="Знижка узгоджена")],
            actions=[action(11, "sale.order", name="Поставити крок",
                            automation_id=automation_id,
                            writes_path="x_approval",
                            writes_value=writes_value)],
            views=list(extra_views))

    def test_automation_waits_for_a_value_nobody_writes(self):
        issues = self.run_issues(self._snap())
        found = self.assertKind(issues, "unreachable_state", count=1,
                                severity="высокая")
        self.assertEqual(len(issues), 1)
        self.assertIn("sale.order.x_approval", found[0]["title"])
        self.assertIn("`approved`", found[0]["title"])
        self.assertIn("Знижка узгоджена", found[0]["detail"])
        self.assertIn("только другие значения", found[0]["detail"])

    def test_wording_when_nothing_writes_into_the_field_at_all(self):
        snap = self._snap()
        snap["server_actions"] = []
        issues = self.run_issues(snap)
        found = self.assertKind(issues, "unreachable_state", count=1)
        self.assertIn("Ни одно действие сервера его не выставляет",
                      found[0]["detail"])

    def test_silent_when_an_action_writes_that_value(self):
        issues = self.run_issues(self._snap(writes_value="approved"))
        self.assertNoKind(issues, "unreachable_state")
        self.assertKind(issues, "invisible_result", count=1)

    def test_value_written_by_a_manual_action_also_counts(self):
        issues = self.run_issues(self._snap(writes_value="approved",
                                            automation_id=None))
        self.assertNoKind(issues, "unreachable_state")

    def test_written_value_is_compared_normalized(self):
        # Значение действия приводится norm_value, поэтому регистр и кавычки
        # не создают ложную недостижимость.
        issues = self.run_issues(self._snap(writes_value="'APPROVED'"))
        self.assertNoKind(issues, "unreachable_state")

    def test_silent_when_the_field_is_shown_in_a_view(self):
        issues = self.run_issues(self._snap(extra_views=[
            view(7, "sale.order", '<data><field name="x_approval"/></data>',
                 name="Замовлення: узгодження", inherit_id=500,
                 inherit_name="sale.order.form")]))
        self.assertNoKind(issues, "unreachable_state")
        self.assertQuiet(issues)

    def test_false_is_reachable_by_default(self):
        # Пустое значение поле получает само собой — это не тупик.
        issues = self.run_issues(snapshot(
            fields=[field("sale.order", "x_approval", ttype="selection",
                          label="Узгодження знижки")],
            automations=[automation(4, "sale.order",
                                    "[('x_approval','=',False)]",
                                    name="Знижка не узгоджена")]))
        self.assertNoKind(issues, "unreachable_state")
        self.assertKind(issues, "unreachable_gate", count=1)

    def test_non_equality_operator_is_not_a_requirement(self):
        issues = self.run_issues(self._snap(
            domain="[('x_approval','!=','approved')]"))
        self.assertNoKind(issues, "unreachable_state")

    def test_several_automations_waiting_for_one_value_are_grouped(self):
        snap = self._snap()
        snap["automations"].append(
            automation(5, "sale.order", "[('x_approval','=','approved')]",
                       name="Лист про узгодження"))
        issues = self.run_issues(snap)
        found = self.assertKind(issues, "unreachable_state", count=1)
        self.assertIn("Знижка узгоджена", found[0]["detail"])
        self.assertIn("Лист про узгодження", found[0]["detail"])

    def test_each_missing_value_is_reported_separately(self):
        snap = self._snap()
        snap["automations"].append(
            automation(5, "sale.order", "[('x_approval','=','director')]",
                       name="Віза директора"))
        issues = self.run_issues(snap)
        found = self.assertKind(issues, "unreachable_state", count=2)
        self.assertEqual(sorted("`approved`" in i["title"] for i in found),
                         [False, True])


if __name__ == "__main__":
    unittest.main()
