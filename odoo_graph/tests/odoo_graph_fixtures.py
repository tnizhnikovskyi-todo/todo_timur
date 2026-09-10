"""Общие помощники тестов: импорт анализатора и сборка синтетических снимков.

Модуль лежит рядом с тестами; `unittest discover -s odoo_graph/tests`
кладет этот каталог в sys.path, поэтому тесты импортируют его по имени.
"""

import itertools
import os
import sys

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TOOL_DIR = os.path.dirname(TESTS_DIR)                 # .../odoo_graph
DUMP_PATH = os.path.join(TOOL_DIR, "dumps", "edu-online-todo.json")

if TOOL_DIR not in sys.path:
    sys.path.insert(0, TOOL_DIR)

import odoo_graph as og                                # noqa: E402

# Все виды проблем, описанные в README (раздел «Проверки»).
DOCUMENTED_KINDS = frozenset((
    "unreachable_state", "unreachable_gate", "competing_writer",
    "duplicate_placement", "orphan_field", "invisible_result",
    "xpath_collision_risk", "leftover_artifact", "cross_model_field",
    "dangling_action", "empty_view", "odoo_mechanism",
))

SEVERITIES = ("высокая", "средняя", "низкая")


# --------------------------------------------------------------------------
# Фабрики записей снимка
# --------------------------------------------------------------------------

_ids = itertools.count(1)


def model(name, title=None):
    return {"model": name, "name": title or name}


def field(fmodel, name, label=None, ttype="char", relation=None, related=None,
          fid=None):
    return {"id": fid if fid is not None else next(_ids),
            "model": fmodel, "name": name, "label": label or name,
            "ttype": ttype, "relation": relation, "related": related}


def view(vid, vmodel, arch, name=None, vtype="form", mode="extension",
         inherit_id=None, inherit_name=None):
    return {"id": vid, "name": name or f"view.{vid}", "model": vmodel,
            "type": vtype, "mode": mode, "inherit_id": inherit_id,
            "inherit_name": inherit_name, "arch": arch}


def automation(aid, amodel, domain="", name=None, trigger="on_create_or_write",
               active=True):
    return {"id": aid, "name": name or f"Автоматизація {aid}", "model": amodel,
            "trigger": trigger, "active": active, "filter_domain": domain}


def action(sid, amodel, name=None, state="object_write", usage="base_automation",
           automation_id=None, writes_path=None, writes_value=None):
    return {"id": sid, "name": name or f"Дія {sid}", "model": amodel,
            "state": state, "usage": usage, "automation_id": automation_id,
            "writes_path": writes_path, "writes_value": writes_value}


def rule(rid, rmodel, name=None, domain="[]", is_global=True, groups=None,
         standard=None):
    return {"id": rid, "name": name or f"Правило {rid}", "model": rmodel,
            "domain": domain, "global": is_global, "groups": groups or [],
            "standard": standard}


def snapshot(models=(), fields=(), views=(), automations=(), actions=(),
             rules=(), meta=None):
    """Снимок метаданных той же формы, что и файлы в dumps/."""
    snap_meta = {"db": "synthetic", "url": "https://example.odoo.com",
                 "odoo_version": "19.0", "extracted_at": "2026-01-01",
                 "extracted_via": "tests"}
    snap_meta.update(meta or {})
    return {"meta": snap_meta,
            "models_manual": list(models),
            "fields_manual": list(fields),
            "views_custom": list(views),
            "automations": list(automations),
            "server_actions": list(actions),
            "record_rules": list(rules)}


# --------------------------------------------------------------------------
# Прогон анализа
# --------------------------------------------------------------------------

def analyze(snap):
    """(граф, список проблем) по снимку."""
    graph = og.build_graph(snap)
    return graph, og.find_issues(graph, snap)


def issues_of(issues, kind):
    return [i for i in issues if i["kind"] == kind]


def kinds_of(issues):
    return sorted({i["kind"] for i in issues})


class AnalyzerCase:
    """Утверждения о наборе проблем. Подмешивается к unittest.TestCase."""

    def run_issues(self, snap):
        _, issues = analyze(snap)
        for issue in issues:
            self.assertIn(issue["severity"], SEVERITIES)
            self.assertIn(issue["kind"], DOCUMENTED_KINDS)
        return issues

    def assertKind(self, issues, kind, count=None, severity=None):
        found = issues_of(issues, kind)
        self.assertTrue(found,
                        f"проверка {kind} не сработала; вместо неё: "
                        f"{kinds_of(issues)}")
        if count is not None:
            self.assertEqual(len(found), count,
                             f"{kind}: ожидалось {count}, получено "
                             f"{[i['title'] for i in found]}")
        if severity is not None:
            self.assertEqual([i["severity"] for i in found],
                             [severity] * len(found))
        return found

    def assertNoKind(self, issues, kind):
        found = issues_of(issues, kind)
        self.assertEqual(found, [],
                         f"ложное срабатывание {kind}: "
                         f"{[i['title'] for i in found]}")

    def assertQuiet(self, issues):
        self.assertEqual(issues, [],
                         f"ожидалась тишина, получено: "
                         f"{[(i['kind'], i['title']) for i in issues]}")
