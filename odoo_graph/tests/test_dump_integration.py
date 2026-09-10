"""Интеграция: полный прогон по снимку реальной базы dumps/edu-online-todo.json."""

import json
import os
import re
import unittest

from odoo_graph_fixtures import og, DUMP_PATH, DOCUMENTED_KINDS, SEVERITIES, TOOL_DIR

NODE_KINDS = {"model", "field", "view", "automation", "action", "rule"}
EDGE_KINDS = {"field_of", "relates_to", "view_of", "inherits", "shows",
              "automates", "triggers_on", "acts_on", "writes", "runs_in",
              "restricts"}


class DumpIntegrationTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.snap = og.load_dump(DUMP_PATH)
        cls.graph = og.build_graph(cls.snap)
        cls.issues = og.find_issues(cls.graph, cls.snap)

    def test_dump_is_present_and_has_every_layer(self):
        for layer in og.LAYERS:
            self.assertTrue(self.snap[layer], f"слой {layer} пуст")

    def test_graph_is_not_empty(self):
        self.assertGreater(len(self.graph.nodes), 0)
        self.assertGreater(len(self.graph.edges), 0)

    def test_every_snapshot_record_became_a_node(self):
        expected = (len(self.snap["fields_manual"])
                    + len(self.snap["views_custom"])
                    + len(self.snap["automations"])
                    + len(self.snap["server_actions"])
                    + len(self.snap["record_rules"]))
        non_model = [n for n in self.graph.nodes.values()
                     if n["kind"] != "model"]
        self.assertEqual(len(non_model), expected)
        self.assertTrue(any(n["kind"] == "model"
                            for n in self.graph.nodes.values()))

    def test_node_and_edge_shape(self):
        for nid, node in self.graph.nodes.items():
            self.assertIn(node["kind"], NODE_KINDS, nid)
            self.assertTrue(node.get("label"), nid)
        for src, dst, kind in self.graph.edges:
            self.assertIn(src, self.graph.nodes)
            self.assertIn(dst, self.graph.nodes)
            self.assertIn(kind, EDGE_KINDS)

    def test_issues_are_well_formed(self):
        self.assertTrue(self.issues)
        for issue in self.issues:
            self.assertEqual(sorted(issue),
                             ["detail", "kind", "severity", "title", "where"])
            self.assertIn(issue["severity"], SEVERITIES)
            self.assertIn(issue["kind"], DOCUMENTED_KINDS)
            self.assertTrue(issue["title"])
            self.assertTrue(issue["detail"])

    def test_issues_are_sorted_by_severity(self):
        order = [SEVERITIES.index(i["severity"]) for i in self.issues]
        self.assertEqual(order, sorted(order))

    def test_analysis_is_deterministic(self):
        again = og.find_issues(og.build_graph(og.load_dump(DUMP_PATH)),
                               self.snap)
        self.assertEqual(again, self.issues)

    def test_reports_render(self):
        summary = og.stats_report(self.graph, self.snap)
        problems = og.issues_report(self.graph, self.snap, self.issues)
        self.assertIn("edu-online-todo", summary)
        self.assertTrue(problems.startswith("# Проблемы кастомного слоя"))

    def test_impact_report_for_a_customised_model(self):
        report = og.impact_report(self.graph, self.snap, "sale.order")
        self.assertIsNotNone(report)
        self.assertIn("# Анализ влияния: `sale.order`", report)
        self.assertIn("x_discount_approval", report)

    def test_impact_report_for_an_unknown_model(self):
        self.assertIsNone(og.impact_report(self.graph, self.snap, "нет.такой"))

    def test_html_is_a_single_file_without_external_sources(self):
        page = og.render_html(self.graph, self.snap, "Кастомный слой")
        self.assertIn("<!doctype html>", page.lower())
        self.assertNotIn("<script src", page)
        payload = re.search(r'"nodes":\s*\[', page)
        self.assertIsNotNone(payload)

    def test_graph_json_is_serialisable(self):
        dumped = json.dumps(
            {"nodes": [dict(id=k, **{kk: vv for kk, vv in v.items()
                                     if kk != "arch"})
                       for k, v in self.graph.nodes.items()],
             "edges": [{"src": s, "dst": d, "kind": k}
                       for s, d, k in self.graph.edges]},
            ensure_ascii=False)
        self.assertEqual(len(json.loads(dumped)["edges"]),
                         len(self.graph.edges))


class ReadmeContractTest(unittest.TestCase):
    """README — часть интерфейса инструмента: список проверок должен совпадать."""

    def test_readme_lists_exactly_the_documented_checks(self):
        with open(os.path.join(TOOL_DIR, "README.md"), encoding="utf-8") as fh:
            readme = fh.read()
        section = readme.split("## Проверки", 1)[1].split("\n## ", 1)[0]
        listed = set(re.findall(r"^\|\s*`(\w+)`\s*\|", section, re.M))
        self.assertEqual(listed, set(DOCUMENTED_KINDS))

    def test_every_documented_check_is_implemented(self):
        with open(os.path.join(TOOL_DIR, "odoo_graph.py"), encoding="utf-8") as fh:
            source = fh.read()
        body = source.split("def find_issues", 1)[1].split("\ndef ", 1)[0]
        mentioned = set(re.findall(r'"(\w+)"', body)) & set(DOCUMENTED_KINDS)
        self.assertEqual(mentioned, set(DOCUMENTED_KINDS))


if __name__ == "__main__":
    unittest.main()
