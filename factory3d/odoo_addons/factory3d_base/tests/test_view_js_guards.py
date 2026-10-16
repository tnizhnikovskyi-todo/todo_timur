"""Статичні вартові виглядів (QA меню 16.10.2026): клієнтські вирази не повинні містити Python-конструкцій.

* канбан `t-*`: Odoo 19 (OWL) компілює їх як JS — `x in ('a','b')` дає TypeError, `True/False/None`, `not`, `not in` не існують;
* домени/контексти фільтрів обчислює py.js: `datetime.time.min/max` він не знає (OwlError у «Відвідувачі»);
* домен не вміє порівнювати поле з полем: `('ws_qty', '<', 'min_qty')` порівнює з рядком (ValueError у search_count).
* віджет ace/code: CodeEditor Odoo 19 приймає лише режими з CodeEditor.MODES; `'json'` дає OwlError «Invalid props» (у debug).
Перевіряються усі встановлені factory3d_* і td_genset (у прогоні «Run A» — всі 18 модулів).
"""
import ast
import re

from lxml import etree

from odoo.tests import TransactionCase, tagged

_STR = re.compile(r"'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\"")
_JS_PYISMS = (
    (re.compile(r"\bin\s*[(\[]"), "Python `in (...)`/`in [...]` (у JS `x in 'рядок'` -> TypeError; є `[...].includes(x)`)"),
    (re.compile(r"\bnot\s+in\b"), "Python `not in`"),
    (re.compile(r"\b(?:True|False|None)\b"), "Python True/False/None (у JS: true/false/null)"),
    (re.compile(r"(?<![\w.$!])not\s"), "Python `not` (у JS: `!`)"),
)
_T_SKIP = {"t-name", "t-call", "t-set", "t-as", "t-key", "t-slot", "t-translation", "t-ref", "t-inherit", "t-inherit-mode"}
_ATTF = re.compile(r"(?:#|\$)\{(.*?)\}|\{\{(.*?)\}\}")
_TIME_MINMAX = re.compile(r"\btime\.(?:min|max)\b|\bdate(?:time)?\.(?:min|max)\b")
_ACE_MODES = {"javascript", "xml", "qweb", "scss", "python"}  # web/static/src/core/code_editor/code_editor.js
_ORDER_LEAF = re.compile(r"\(\s*'([\w.]+)'\s*,\s*'(<|>|<=|>=)'\s*,\s*'([a-z_][a-z_0-9]*)'\s*\)")


@tagged('post_install', '-at_install', 'f3d', 'f3d_base')
class TestViewJsGuards(TransactionCase):

    def _f3d_views(self):
        modules = self.env['ir.module.module'].search([('state', '=', 'installed')]).filtered(
            lambda m: m.name.startswith('factory3d_') or m.name == 'td_genset').mapped('name')
        data = self.env['ir.model.data'].search([('model', '=', 'ir.ui.view'), ('module', 'in', modules)])
        return self.env['ir.ui.view'].browse(data.mapped('res_id')).exists().filtered(lambda v: v.type != 'qweb')

    @staticmethod
    def _arch(view):
        return etree.fromstring((view.arch_db or '<data/>').encode())

    def test_kanban_template_expressions_are_js(self):
        problems = []
        views = self._f3d_views()
        self.assertTrue(views)
        for view in views:
            for el in self._arch(view).iter():
                if not isinstance(el.tag, str):
                    continue
                for attr, value in el.attrib.items():
                    if not attr.startswith('t-') or attr in _T_SKIP:
                        continue
                    if attr.startswith('t-attf-'):
                        exprs = [m.group(1) or m.group(2) for m in _ATTF.finditer(value)]
                    else:
                        exprs = [value]
                    for expr in exprs:
                        stripped = _STR.sub("''", expr)
                        for regex, message in _JS_PYISMS:
                            if regex.search(stripped):
                                problems.append("%s: <%s %s=%r>: %s" % (view.xml_id or view.name, el.tag, attr, expr, message))
        self.assertFalse(problems, "Python-конструкції у JS-виразах шаблонів:\n" + "\n".join(problems))

    def test_filter_domains_are_client_safe(self):
        problems = []
        for view in self._f3d_views():
            Model = self.env.get(view.model) if view.model else None
            for el in self._arch(view).iter():
                if not isinstance(el.tag, str) or el.tag not in ('filter', 'field'):
                    continue
                for attr in ('domain', 'filter_domain', 'context'):
                    value = el.get(attr)
                    if not value:
                        continue
                    label = "%s: <%s %s>" % (view.xml_id or view.name, el.tag, el.get('name') or el.get('string') or '')
                    if _TIME_MINMAX.search(value):
                        problems.append("%s: %s не підтримується JS-обчислювачем (datetime.time(0, 0, 0)/(23, 59, 59))" % (label, attr))
                    if Model is not None and el.tag == 'filter' and attr == 'domain':
                        for field, op, rhs in _ORDER_LEAF.findall(value):
                            if field.split('.')[0] in Model._fields and rhs in Model._fields:
                                problems.append("%s: домен порівнює поле з полем ('%s' %s '%s'); потрібне булеве поле з _search/store"
                                                % (label, field, op, rhs))
        self.assertFalse(problems, "Домени, які клієнт або ORM не обчислять:\n" + "\n".join(problems))

    def test_code_editor_modes(self):
        problems = []
        for view in self._f3d_views():
            for el in self._arch(view).iter('field'):
                if el.get('widget') not in ('ace', 'code') or not el.get('options'):
                    continue
                try:
                    mode = ast.literal_eval(el.get('options')).get('mode')
                except (ValueError, SyntaxError):
                    continue
                if mode and mode not in _ACE_MODES:
                    problems.append("%s: <field %s widget=%s> mode=%r" % (view.xml_id or view.name, el.get('name'), el.get('widget'), mode))
        self.assertFalse(problems, "Режим CodeEditor поза %s:\n%s" % (sorted(_ACE_MODES), "\n".join(problems)))
