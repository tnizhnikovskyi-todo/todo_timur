"""domain_requirements: какие значения полей требует условие автоматизации."""

import unittest

from odoo_graph_fixtures import og


class DomainRequirementsTest(unittest.TestCase):

    def test_simple_equality(self):
        self.assertEqual(og.domain_requirements("[('x_state', '=', 'done')]"),
                         {"x_state": {"done"}})

    def test_double_equals_operator(self):
        self.assertEqual(og.domain_requirements("[('x_state', '==', 'done')]"),
                         {"x_state": {"done"}})

    def test_double_quoted_domain(self):
        self.assertEqual(og.domain_requirements('[("x_state", "=", "done")]'),
                         {"x_state": {"done"}})

    def test_value_is_normalized(self):
        self.assertEqual(og.domain_requirements("[('x_state','=','DONE')]"),
                         {"x_state": {"done"}})

    def test_boolean_value(self):
        self.assertEqual(og.domain_requirements("[('x_visa','=',False)]"),
                         {"x_visa": {"false"}})
        self.assertEqual(og.domain_requirements("[('x_visa','=',True)]"),
                         {"x_visa": {"true"}})

    def test_numeric_value(self):
        self.assertEqual(og.domain_requirements("[('stage_id', '=', 3)]"),
                         {"stage_id": {"3"}})

    def test_dotted_path_collapses_to_base_field(self):
        self.assertEqual(
            og.domain_requirements("[('partner_id.name', '=', 'ТОВ')]"),
            {"partner_id": {"тов"}})

    def test_several_values_of_one_field(self):
        self.assertEqual(
            og.domain_requirements("[('x_a','=','one'),('x_a','=','two')]"),
            {"x_a": {"one", "two"}})

    def test_several_fields(self):
        self.assertEqual(
            og.domain_requirements("[('x_a','=','1'),('x_b','=','2')]"),
            {"x_a": {"1"}, "x_b": {"2"}})

    def test_other_operators_are_ignored(self):
        for domain in ("[('amount','>',20000)]",
                       "[('amount','<=',100000)]",
                       "[('state','in',('draft','sent'))]",
                       "[('x_a','!=',False)]",
                       "[('name','ilike','x')]",
                       "[('partner_id','child_of',[1])]"):
            self.assertEqual(og.domain_requirements(domain), {}, domain)

    def test_mixed_domain_keeps_only_equalities(self):
        domain = ("[('order_line.discount','>',10),"
                  "('state','in',('draft','sent')),"
                  "('x_discount_visa','=',False)]")
        self.assertEqual(og.domain_requirements(domain),
                         {"x_discount_visa": {"false"}})

    def test_logical_operators_are_not_fields(self):
        domain = "['|',('x_a','=','1'),('x_b','=','2')]"
        self.assertEqual(og.domain_requirements(domain),
                         {"x_a": {"1"}, "x_b": {"2"}})

    def test_empty_and_missing_domain(self):
        self.assertEqual(og.domain_requirements(""), {})
        self.assertEqual(og.domain_requirements(None), {})
        self.assertEqual(og.domain_requirements("[]"), {})

    def test_garbage_does_not_raise(self):
        self.assertEqual(og.domain_requirements("не домен вовсе"), {})

    @unittest.expectedFailure
    def test_list_style_domain(self):
        # НАЙДЕННЫЕ-БАГИ.md, находка 1: домен в виде списков (так его
        # сериализует веб-клиент Odoo) не разбирается вообще.
        self.assertEqual(og.domain_requirements('[["x_state","=","done"]]'),
                         {"x_state": {"done"}})


if __name__ == "__main__":
    unittest.main()
