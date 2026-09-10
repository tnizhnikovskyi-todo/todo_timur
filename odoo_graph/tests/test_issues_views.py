"""Проверки find_issues, которые говорят о представлениях:

duplicate_placement, xpath_collision_risk, empty_view.
"""

import unittest

from odoo_graph_fixtures import AnalyzerCase, snapshot, field, view


def ext(vid, arch, base=500, base_name="sale.order.form", name=None,
        vmodel="sale.order"):
    return view(vid, vmodel, arch, name=name or f"Розширення {vid}",
                mode="extension", inherit_id=base, inherit_name=base_name)


class DuplicatePlacementTest(AnalyzerCase, unittest.TestCase):

    def test_one_field_added_twice_into_the_same_base_view(self):
        issues = self.run_issues(snapshot(
            fields=[field("sale.order", "x_visa", label="Віза")],
            views=[ext(7, '<data><field name="x_visa"/></data>'),
                   ext(8, '<data><field name="x_visa"/></data>')]))
        found = self.assertKind(issues, "duplicate_placement", count=1,
                                severity="высокая")
        self.assertIn("sale.order.x_visa", found[0]["title"])
        self.assertIn("id 7", found[0]["detail"])
        self.assertIn("id 8", found[0]["detail"])
        # Два наследника одного представления — это ещё и риск xpath.
        self.assertKind(issues, "xpath_collision_risk", count=1)

    def test_silent_when_extensions_touch_different_base_views(self):
        issues = self.run_issues(snapshot(
            fields=[field("sale.order", "x_visa", label="Віза")],
            views=[ext(7, '<data><field name="x_visa"/></data>', base=500),
                   ext(8, '<data><field name="x_visa"/></data>', base=501,
                       base_name="sale.order.form.inherit")]))
        self.assertQuiet(issues)

    def test_silent_when_extensions_add_different_fields(self):
        issues = self.run_issues(snapshot(
            fields=[field("sale.order", "x_visa", label="Віза"),
                    field("sale.order", "x_step", label="Крок")],
            views=[ext(7, '<data><field name="x_visa"/></data>'),
                   ext(8, '<data><field name="x_step"/></data>')]))
        self.assertNoKind(issues, "duplicate_placement")

    def test_silent_when_the_field_is_repeated_inside_one_extension(self):
        # Дубль внутри одного представления эта проверка не ловит:
        # она сравнивает разные расширения одной формы.
        issues = self.run_issues(snapshot(
            fields=[field("sale.order", "x_visa", label="Віза")],
            views=[ext(7, '<data><field name="x_visa"/>'
                          '<field name="x_visa"/></data>')]))
        self.assertNoKind(issues, "duplicate_placement")

    def test_silent_for_primary_views(self):
        issues = self.run_issues(snapshot(
            fields=[field("sale.order", "x_visa", label="Віза")],
            views=[view(7, "sale.order", '<data><field name="x_visa"/></data>',
                        name="Форма 1", mode="primary", inherit_id=500,
                        inherit_name="sale.order.form"),
                   view(8, "sale.order", '<data><field name="x_visa"/></data>',
                        name="Форма 2", mode="primary", inherit_id=500,
                        inherit_name="sale.order.form")]))
        self.assertNoKind(issues, "duplicate_placement")

    def test_silent_when_the_duplicated_field_is_not_custom(self):
        issues = self.run_issues(snapshot(
            views=[ext(7, '<data><field name="partner_id"/></data>'),
                   ext(8, '<data><field name="partner_id"/></data>')]))
        self.assertNoKind(issues, "duplicate_placement")


class XpathCollisionTest(AnalyzerCase, unittest.TestCase):

    def test_two_extensions_of_one_base_view(self):
        issues = self.run_issues(snapshot(
            fields=[field("sale.order", "x_visa", label="Віза"),
                    field("sale.order", "x_step", label="Крок")],
            views=[ext(7, '<data><field name="x_visa"/></data>',
                       name="Віза на знижку"),
                   ext(8, '<data><field name="x_step"/></data>',
                       name="Крок узгодження")]))
        found = self.assertKind(issues, "xpath_collision_risk", count=1,
                                severity="средняя")
        self.assertEqual(len(issues), 1)
        self.assertIn("sale.order.form", found[0]["title"])
        self.assertIn("2 кастомных расширения", found[0]["title"])
        self.assertIn("Віза на знижку", found[0]["detail"])
        self.assertIn("Крок узгодження", found[0]["detail"])
        self.assertEqual(found[0]["where"], "sale.order")

    def test_silent_for_a_single_extension(self):
        issues = self.run_issues(snapshot(
            fields=[field("sale.order", "x_visa", label="Віза")],
            views=[ext(7, '<data><field name="x_visa"/></data>')]))
        self.assertQuiet(issues)

    def test_silent_for_extensions_of_different_base_views(self):
        issues = self.run_issues(snapshot(views=[
            ext(7, '<data><group/></data>', base=500),
            ext(8, '<data><group/></data>', base=501,
                base_name="purchase.order.form")]))
        self.assertNoKind(issues, "xpath_collision_risk")

    def test_silent_for_views_without_a_base(self):
        issues = self.run_issues(snapshot(views=[
            view(7, "sale.order", "<form><group/></form>", name="Форма 1",
                 mode="primary"),
            view(8, "sale.order", "<form><group/></form>", name="Форма 2",
                 mode="primary")]))
        self.assertNoKind(issues, "xpath_collision_risk")

    def test_three_extensions_are_reported_once(self):
        issues = self.run_issues(snapshot(views=[
            ext(7, "<data><group/></data>"),
            ext(8, "<data><group/></data>"),
            ext(9, "<data><group/></data>")]))
        found = self.assertKind(issues, "xpath_collision_risk", count=1)
        self.assertIn("3 кастомных расширения", found[0]["title"])

    @unittest.expectedFailure
    def test_mixed_inherit_name_does_not_crash(self):
        # НАЙДЕННЫЕ-БАГИ.md, находка 2: если у двух расширений одного и того
        # же базового представления inherit_name заполнен не везде,
        # find_issues падает на сортировке ключей.
        issues = self.run_issues(snapshot(views=[
            ext(7, "<data><group/></data>", base_name=None),
            ext(8, "<data><group/></data>", base_name="sale.order.form")]))
        self.assertKind(issues, "xpath_collision_risk")


class EmptyViewTest(AnalyzerCase, unittest.TestCase):

    def test_self_closing_data_tag(self):
        issues = self.run_issues(snapshot(views=[ext(7, "<data/>")]))
        found = self.assertKind(issues, "empty_view", count=1,
                                severity="низкая")
        self.assertEqual(len(issues), 1)
        self.assertIn("id 7", found[0]["title"])
        self.assertEqual(found[0]["where"], "sale.order")

    def test_whitespace_around_the_tag(self):
        issues = self.run_issues(snapshot(views=[
            ext(7, "  <data />\n"),
            ext(8, "\n<data/>  ", base=501, base_name="purchase.order.form")]))
        self.assertKind(issues, "empty_view", count=2)

    def test_silent_for_a_view_that_changes_something(self):
        issues = self.run_issues(snapshot(
            fields=[field("sale.order", "x_visa", label="Віза")],
            views=[ext(7, '<data><xpath expr="//sheet" position="inside">'
                          '<field name="x_visa"/></xpath></data>')]))
        self.assertNoKind(issues, "empty_view")

    def test_silent_for_a_full_form_arch(self):
        issues = self.run_issues(snapshot(views=[
            view(7, "sale.order", "<form><sheet><group/></sheet></form>",
                 name="Форма", mode="primary")]))
        self.assertNoKind(issues, "empty_view")

    @unittest.expectedFailure
    def test_paired_empty_data_tag(self):
        # НАЙДЕННЫЕ-БАГИ.md, находка 3: пустое расширение, записанное как
        # <data></data>, не распознается.
        issues = self.run_issues(snapshot(views=[ext(7, "<data></data>")]))
        self.assertKind(issues, "empty_view", count=1)


if __name__ == "__main__":
    unittest.main()
