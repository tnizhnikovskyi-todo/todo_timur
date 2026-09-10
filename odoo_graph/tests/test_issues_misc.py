"""Проверки find_issues по названиям объектов и по именам полей:

leftover_artifact, cross_model_field.
"""

import unittest

from odoo_graph_fixtures import (AnalyzerCase, snapshot, field, view,
                                 automation, action, rule)

# Маркеры из LEFTOVER_RE, каждый — в живом названии.
LEFTOVER_NAMES = (
    "Погодити знижку (перевірка)",
    "Перевирка вiзи",
    "Порожня автоматизація",
    "Спорожнити поле",
    "Прибирання після міграції",
    "Залишок від першої версії",
    "Чернетка автоматизації",
    "Копія автоматизації візи",
    "Sandbox test flow",
    "Sync tmp state",
    "todo: прибрати перед здачею",
    "Черновик автоматизации",
    "Проверка визы",
)

CLEAN_NAMES = (
    "Знижка понад 10 % — віза керівника",
    "Закупка: віза керівника — узгоджено",
    "Latest sync",                    # «test» внутри слова — не маркер
    "Protest handling",
    "Контроль ліміту витрат",
)


class LeftoverArtifactTest(AnalyzerCase, unittest.TestCase):

    def test_every_marker_is_recognised(self):
        for name in LEFTOVER_NAMES:
            with self.subTest(name=name):
                issues = self.run_issues(snapshot(
                    automations=[automation(1, "sale.order", name=name)]))
                found = self.assertKind(issues, "leftover_artifact", count=1,
                                        severity="средняя")
                self.assertIn(name, found[0]["title"])
                self.assertEqual(found[0]["where"], "sale.order")

    def test_clean_names_are_silent(self):
        for name in CLEAN_NAMES:
            with self.subTest(name=name):
                issues = self.run_issues(snapshot(
                    automations=[automation(1, "sale.order", name=name)]))
                self.assertNoKind(issues, "leftover_artifact")

    def test_company_suffix_in_view_names_is_not_a_marker(self):
        # Реальные представления базы называются ...todo — это суффикс
        # компании, а не маркер «todo:».
        issues = self.run_issues(snapshot(views=[
            view(7, "budget.analytic", "<data><group/></data>",
                 name="budget.analytic.form.stattya.todo", mode="extension",
                 inherit_id=500, inherit_name="budget.analytic.view.form")]))
        self.assertNoKind(issues, "leftover_artifact")

    def test_marker_in_a_field_label(self):
        issues = self.run_issues(snapshot(fields=[
            field("sale.order", "x_flag", label="TEST ознака")]))
        self.assertKind(issues, "leftover_artifact", count=1)

    def test_marker_is_found_in_any_kind_of_object(self):
        issues = self.run_issues(snapshot(
            fields=[field("sale.order", "x_flag", label="Чернетка ознаки")],
            views=[view(7, "sale.order", "<data><group/></data>",
                        name="Копія форми", mode="extension", inherit_id=500,
                        inherit_name="sale.order.form")],
            automations=[automation(1, "sale.order", name="Перевірка візи")],
            actions=[action(11, "sale.order", name="Тимчасовий залишок",
                            state="code")],
            rules=[rule(5, "sale.order", name="Правило (проверка)")]))
        found = self.assertKind(issues, "leftover_artifact", count=5)
        self.assertEqual(
            sorted(i["title"].split(":")[0] for i in found),
            ["action", "automation", "field", "rule", "view"])

    def test_case_is_ignored(self):
        issues = self.run_issues(snapshot(
            automations=[automation(1, "sale.order", name="ПЕРЕВІРКА ВІЗИ")]))
        self.assertKind(issues, "leftover_artifact", count=1)


class CrossModelFieldTest(AnalyzerCase, unittest.TestCase):

    def test_same_name_and_same_label_is_a_low_severity_note(self):
        issues = self.run_issues(snapshot(fields=[
            field("sale.order", "x_visa", label="Віза керівника"),
            field("purchase.order", "x_visa", label="Віза керівника")]))
        found = self.assertKind(issues, "cross_model_field", count=1,
                                severity="низкая")
        self.assertIn("x_visa", found[0]["title"])
        self.assertIn("2 моделях", found[0]["title"])
        self.assertIn("purchase.order, sale.order", found[0]["detail"])
        self.assertIn("Подписи совпадают", found[0]["detail"])

    def test_same_name_but_different_labels_is_worse(self):
        issues = self.run_issues(snapshot(fields=[
            field("sale.order", "x_visa", label="Віза керівника"),
            field("purchase.order", "x_visa", label="Погоджено")]))
        found = self.assertKind(issues, "cross_model_field", count=1,
                                severity="средняя")
        self.assertIn("Подписи отличаются", found[0]["detail"])

    def test_three_models(self):
        issues = self.run_issues(snapshot(fields=[
            field("sale.order", "x_visa", label="Віза"),
            field("purchase.order", "x_visa", label="Віза"),
            field("hr.expense", "x_visa", label="Віза")]))
        found = self.assertKind(issues, "cross_model_field", count=1)
        self.assertIn("3 моделях", found[0]["title"])

    def test_silent_for_distinct_field_names(self):
        issues = self.run_issues(snapshot(fields=[
            field("sale.order", "x_visa", label="Віза"),
            field("purchase.order", "x_visa_head", label="Віза")]))
        self.assertNoKind(issues, "cross_model_field")

    def test_silent_for_a_single_field(self):
        issues = self.run_issues(snapshot(fields=[
            field("sale.order", "x_visa", label="Віза")]))
        self.assertNoKind(issues, "cross_model_field")

    def test_each_repeated_name_is_reported_once(self):
        issues = self.run_issues(snapshot(fields=[
            field("sale.order", "x_visa", label="Віза"),
            field("purchase.order", "x_visa", label="Віза"),
            field("sale.order", "x_step", label="Крок"),
            field("hr.expense", "x_step", label="Крок")]))
        found = self.assertKind(issues, "cross_model_field", count=2)
        self.assertEqual(sorted(i["title"] for i in found),
                         ["Поле x_step создано в 2 моделях",
                          "Поле x_visa создано в 2 моделях"])


if __name__ == "__main__":
    unittest.main()
