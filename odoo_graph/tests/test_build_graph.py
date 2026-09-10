"""build_graph: узлы и связи, которые строятся из снимка метаданных."""

import json
import os
import tempfile
import unittest

from odoo_graph_fixtures import (og, snapshot, model, field, view, automation,
                                 action, rule)


class GraphPrimitivesTest(unittest.TestCase):
    """Поведение самого контейнера Graph."""

    def setUp(self):
        self.g = og.Graph()
        self.g.add_node("a", kind="model", label="a")
        self.g.add_node("b", kind="model", label="b")

    def test_add_node_merges_attributes(self):
        self.g.add_node("a", extra=1)
        self.assertEqual(self.g.nodes["a"]["label"], "a")
        self.assertEqual(self.g.nodes["a"]["extra"], 1)

    def test_edge_between_known_nodes(self):
        self.g.add_edge("a", "b", "field_of")
        self.assertEqual(self.g.edges, [("a", "b", "field_of")])
        self.assertEqual(self.g.out("a"), ["b"])
        self.assertEqual(self.g.inc("b"), ["a"])

    def test_edge_to_unknown_node_is_dropped(self):
        self.g.add_edge("a", "нет-такого", "field_of")
        self.g.add_edge("нет-такого", "a", "field_of")
        self.assertEqual(self.g.edges, [])

    def test_kind_filter(self):
        self.g.add_node("c", kind="model", label="c")
        self.g.add_edge("a", "b", "shows")
        self.g.add_edge("a", "c", "writes")
        self.assertEqual(self.g.out("a", "shows"), ["b"])
        self.assertEqual(self.g.out("a", "writes"), ["c"])
        self.assertEqual(sorted(self.g.out("a")), ["b", "c"])
        self.assertEqual(self.g.out("a", "inherits"), [])


class BuildGraphTest(unittest.TestCase):

    def test_empty_snapshot_gives_empty_graph(self):
        g = og.build_graph(snapshot())
        self.assertEqual(g.nodes, {})
        self.assertEqual(g.edges, [])

    def test_manual_model_node(self):
        g = og.build_graph(snapshot(models=[model("x_course", "Курс")]))
        node = g.nodes["model:x_course"]
        self.assertEqual(node["kind"], "model")
        self.assertEqual(node["label"], "x_course")
        self.assertEqual(node["title"], "Курс")
        self.assertTrue(node["custom"])

    def test_standard_model_node_is_not_custom(self):
        g = og.build_graph(snapshot(fields=[field("sale.order", "x_a")]))
        self.assertFalse(g.nodes["model:sale.order"]["custom"])

    def test_field_node_and_field_of_edge(self):
        g = og.build_graph(snapshot(fields=[
            field("sale.order", "x_a", label="Ознака", ttype="selection")]))
        nid = "field:sale.order.x_a"
        node = g.nodes[nid]
        self.assertEqual(node["kind"], "field")
        self.assertEqual(node["label"], "x_a")
        self.assertEqual(node["model"], "sale.order")
        self.assertEqual(node["flabel"], "Ознака")
        self.assertEqual(node["ttype"], "selection")
        self.assertEqual(g.out(nid, "field_of"), ["model:sale.order"])

    def test_relational_field_links_to_related_model(self):
        g = og.build_graph(snapshot(fields=[
            field("sale.order", "x_partner", ttype="many2one",
                  relation="res.partner")]))
        nid = "field:sale.order.x_partner"
        self.assertEqual(g.out(nid, "relates_to"), ["model:res.partner"])
        self.assertIn("model:res.partner", g.nodes)

    def test_non_relational_field_has_no_relates_to(self):
        g = og.build_graph(snapshot(fields=[field("sale.order", "x_a")]))
        self.assertEqual(g.out("field:sale.order.x_a", "relates_to"), [])

    def test_view_node_and_view_of_edge(self):
        arch = '<data><field name="x_b"/><field name="x_a"/></data>'
        g = og.build_graph(snapshot(views=[
            view(7, "sale.order", arch, name="форма", inherit_id=500,
                 inherit_name="sale.order.form")]))
        node = g.nodes["view:7"]
        self.assertEqual(node["kind"], "view")
        self.assertEqual(node["label"], "форма")
        self.assertEqual(node["mode"], "extension")
        self.assertEqual(node["inherit_id"], 500)
        self.assertEqual(node["inherit_name"], "sale.order.form")
        self.assertEqual(node["fields"], ["x_a", "x_b"])   # отсортированы
        self.assertEqual(g.out("view:7", "view_of"), ["model:sale.order"])

    def test_view_without_model_has_no_view_of_edge(self):
        g = og.build_graph(snapshot(views=[view(7, None, "<data/>")]))
        self.assertIn("view:7", g.nodes)
        self.assertEqual(g.out("view:7", "view_of"), [])

    def test_inherits_edge_only_when_base_view_is_in_snapshot(self):
        base = view(500, "sale.order", "<form/>", mode="primary")
        child = view(7, "sale.order", "<data/>", inherit_id=500)
        outside = view(8, "sale.order", "<data/>", inherit_id=999)
        g = og.build_graph(snapshot(views=[base, child, outside]))
        self.assertEqual(g.out("view:7", "inherits"), ["view:500"])
        self.assertEqual(g.out("view:8", "inherits"), [])

    def test_shows_edge_for_custom_field_of_the_same_model(self):
        g = og.build_graph(snapshot(
            fields=[field("sale.order", "x_a")],
            views=[view(7, "sale.order", '<data><field name="x_a"/></data>')]))
        self.assertEqual(g.out("view:7", "shows"), ["field:sale.order.x_a"])

    def test_no_shows_edge_for_standard_field(self):
        g = og.build_graph(snapshot(
            fields=[field("sale.order", "x_a")],
            views=[view(7, "sale.order",
                        '<data><field name="partner_id"/></data>')]))
        self.assertEqual(g.out("view:7", "shows"), [])

    def test_no_shows_edge_across_models(self):
        # Поле x_a кастомное, но на другой модели — представление его не выводит.
        g = og.build_graph(snapshot(
            fields=[field("purchase.order", "x_a")],
            views=[view(7, "sale.order", '<data><field name="x_a"/></data>')]))
        self.assertEqual(g.out("view:7", "shows"), [])

    def test_automation_node_and_edges(self):
        g = og.build_graph(snapshot(
            fields=[field("sale.order", "x_visa", ttype="boolean")],
            automations=[automation(3, "sale.order",
                                    "[('x_visa','=',True)]", name="Віза")]))
        node = g.nodes["auto:3"]
        self.assertEqual(node["kind"], "automation")
        self.assertEqual(node["label"], "Віза")
        self.assertEqual(node["domain"], "[('x_visa','=',True)]")
        self.assertEqual(g.out("auto:3", "automates"), ["model:sale.order"])
        self.assertEqual(g.out("auto:3", "triggers_on"),
                         ["field:sale.order.x_visa"])

    def test_automation_domain_on_standard_field_makes_no_edge(self):
        g = og.build_graph(snapshot(
            fields=[field("sale.order", "x_visa")],
            automations=[automation(3, "sale.order",
                                    "[('state','=','draft')]")]))
        self.assertEqual(g.out("auto:3", "triggers_on"), [])

    def test_action_node_and_edges(self):
        g = og.build_graph(snapshot(
            fields=[field("sale.order", "x_step", ttype="selection")],
            automations=[automation(3, "sale.order")],
            actions=[action(11, "sale.order", automation_id=3,
                            writes_path="x_step", writes_value="head")]))
        node = g.nodes["action:11"]
        self.assertEqual(node["kind"], "action")
        self.assertEqual(node["writes_value"], "head")
        self.assertEqual(g.out("action:11", "acts_on"), ["model:sale.order"])
        self.assertEqual(g.out("action:11", "writes"), ["field:sale.order.x_step"])
        self.assertEqual(g.out("action:11", "runs_in"), ["auto:3"])

    def test_action_write_path_uses_first_segment(self):
        g = og.build_graph(snapshot(
            fields=[field("sale.order", "x_partner", ttype="many2one",
                          relation="res.partner")],
            actions=[action(11, "sale.order", writes_path="x_partner.name",
                            writes_value="ТОВ")]))
        self.assertEqual(g.out("action:11", "writes"),
                         ["field:sale.order.x_partner"])

    def test_action_without_write_path(self):
        g = og.build_graph(snapshot(
            actions=[action(11, "sale.order", state="next_activity")]))
        self.assertEqual(g.out("action:11", "writes"), [])

    def test_action_pointing_at_missing_automation_is_not_linked(self):
        g = og.build_graph(snapshot(
            actions=[action(11, "sale.order", automation_id=42)]))
        self.assertEqual(g.out("action:11", "runs_in"), [])
        self.assertEqual(g.nodes["action:11"]["automation_id"], 42)

    def test_rule_node_and_edge(self):
        g = og.build_graph(snapshot(rules=[
            rule(5, "sale.order", name="Правило компанії",
                 domain="[('company_id','=',1)]", is_global=True, groups=[10])]))
        node = g.nodes["rule:5"]
        self.assertEqual(node["kind"], "rule")
        self.assertTrue(node["is_global"])
        self.assertEqual(node["groups"], [10])
        self.assertEqual(g.out("rule:5", "restricts"), ["model:sale.order"])

    def test_incoming_edges_are_symmetric(self):
        g = og.build_graph(snapshot(
            fields=[field("sale.order", "x_a")],
            views=[view(7, "sale.order", '<data><field name="x_a"/></data>')]))
        self.assertEqual(g.inc("field:sale.order.x_a", "shows"), ["view:7"])
        self.assertEqual(g.inc("model:sale.order", "field_of"),
                         ["field:sale.order.x_a"])
        self.assertEqual(g.inc("model:sale.order", "view_of"), ["view:7"])


class ArchAndDomainScanTest(unittest.TestCase):

    def test_arch_fields(self):
        arch = ('<data><xpath expr="//sheet" position="inside">'
                '<field name="x_a" optional="show"/>'
                "<field name='x_b'/></xpath></data>")
        self.assertEqual(og.arch_fields(arch), {"x_a", "x_b"})

    def test_arch_fields_on_empty_arch(self):
        self.assertEqual(og.arch_fields(""), set())
        self.assertEqual(og.arch_fields(None), set())

    def test_domain_fields(self):
        domain = "[('x_a','=',1),('partner_id.name','ilike','ТОВ')]"
        self.assertEqual(og.domain_fields(domain), {"x_a", "partner_id"})

    def test_domain_fields_on_empty_domain(self):
        self.assertEqual(og.domain_fields(""), set())
        self.assertEqual(og.domain_fields(None), set())


class LoadDumpTest(unittest.TestCase):

    def test_missing_layers_are_filled(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "dump.json")
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"meta": {"db": "empty"}}, fh)
            snap = og.load_dump(path)
        for layer in og.LAYERS:
            self.assertEqual(snap[layer], [], layer)
        g = og.build_graph(snap)
        self.assertEqual(g.nodes, {})
        self.assertEqual(og.find_issues(g, snap), [])


if __name__ == "__main__":
    unittest.main()
