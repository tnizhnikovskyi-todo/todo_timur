#!/usr/bin/env python3
"""Граф кастомного слоя базы Odoo: извлечение, анализ влияния, поиск проблем.

Два режима:
  --live   читает метаданные напрямую из Odoo по XML-RPC (нужен API-ключ)
  --dump   работает по снимку метаданных (JSON), снятому заранее

Пишет только на диск, в Odoo ничего не изменяет.
"""

import argparse
import html
import json
import os
import re
import sys
from collections import Counter, defaultdict

# Слои метаданных, которые составляют кастомный слой базы.
LAYERS = ("models_manual", "fields_manual", "views_custom",
          "automations", "server_actions", "record_rules")

# Маркеры незачищенных тестовых артефактов в названиях.
LEFTOVER_RE = re.compile(
    r"перевірк|перевирк|порожн|спорожн|прибиран|залишок|чернетк|копія|"
    r"\btest\b|\btmp\b|\btodo:|черновик|проверк",
    re.IGNORECASE)

# Поля, которые Odoo создает сама и рендерит динамическими виджетами:
# статических ссылок в представлениях у них нет, сиротами они не являются.
KNOWN_MECHANISMS = (
    (re.compile(r"^x_plan\d+_id$"),
     "аналитический план Odoo: поле создается автоматически при добавлении "
     "плана и выводится виджетом аналитического распределения"),
)

FIELD_IN_ARCH_RE = re.compile(r"""<field\s[^>]*name=["']([^"']+)["']""")
FIELD_IN_DOMAIN_RE = re.compile(r"""['"]([a-zA-Z_][\w.]*)['"]\s*,\s*['"]""")
DOMAIN_TRIPLE_RE = re.compile(
    r"""\(\s*['"]([\w.]+)['"]\s*,\s*['"]([^'"]+)['"]\s*,\s*([^)]+?)\s*\)""")


def norm_value(raw):
    """Привести значение из домена или действия к сравнимому виду."""
    return str(raw).strip().strip("'\"").lower()


def domain_requirements(domain):
    """{имя поля: {значения, которых требует условие}} для операторов = и !=."""
    req = {}
    for field, op, value in DOMAIN_TRIPLE_RE.findall(domain or ""):
        if op not in ("=", "=="):
            continue
        req.setdefault(field.split(".")[0], set()).add(norm_value(value))
    return req


# --------------------------------------------------------------------------
# Извлечение
# --------------------------------------------------------------------------

def fetch_live(url, db, user, api_key):
    """Снять снимок метаданных из живой базы по XML-RPC."""
    import xmlrpc.client

    common = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/common")
    uid = common.authenticate(db, user, api_key, {})
    if not uid:
        sys.exit("Аутентификация не прошла: проверьте db / user / api-key")
    models = xmlrpc.client.ServerProxy(f"{url}/xmlrpc/2/object")

    def call(model, method, *args, **kw):
        return models.execute_kw(db, uid, api_key, model, method, list(args), kw)

    def search_read(model, domain, fields, limit=0):
        return call(model, "search_read", domain, fields, limit=limit or 0)

    version = call("ir.module.module", "search_read",
                   [("name", "=", "base")], ["latest_version"])
    snap = {
        "meta": {
            "db": db, "url": url,
            "odoo_version": (version[0]["latest_version"] if version else "?"),
            "modules_installed": call("ir.module.module", "search_count",
                                      [("state", "=", "installed")]),
            "extracted_via": "xmlrpc",
        }
    }

    snap["models_manual"] = [
        {"model": r["model"], "name": r["name"]}
        for r in search_read("ir.model", [("state", "=", "manual")],
                             ["model", "name"])
    ]
    snap["fields_manual"] = [
        {"id": r["id"], "model": r["model"], "name": r["name"],
         "label": r["field_description"], "ttype": r["ttype"],
         "relation": r["relation"] or None, "related": r["related"] or None}
        for r in search_read("ir.model.fields", [("state", "=", "manual")],
                             ["model", "name", "field_description", "ttype",
                              "relation", "related"])
    ]
    # Кастомные представления: правленые стандартные + все, что ссылаются на x_-поля.
    view_domain = ["|", ("arch_updated", "=", True), ("arch_db", "ilike", 'name="x_')]
    snap["views_custom"] = [
        {"id": r["id"], "name": r["name"], "model": r["model"] or None,
         "type": r["type"], "mode": r["mode"],
         "inherit_id": (r["inherit_id"][0] if r["inherit_id"] else None),
         "inherit_name": (r["inherit_id"][1] if r["inherit_id"] else None),
         "arch": r["arch_db"]}
        for r in search_read("ir.ui.view", view_domain,
                             ["name", "model", "type", "mode", "inherit_id",
                              "arch_db"])
    ]
    snap["automations"] = [
        {"id": r["id"], "name": r["name"], "model": r["model_name"],
         "trigger": r["trigger"], "active": r["active"],
         "filter_domain": r["filter_domain"] or ""}
        for r in search_read("base.automation", [],
                             ["name", "model_name", "trigger", "active",
                              "filter_domain"])
    ]
    snap["server_actions"] = [
        {"id": r["id"], "name": r["name"], "model": r["model_name"],
         "state": r["state"], "usage": r["usage"],
         "automation_id": (r["base_automation_id"][0]
                           if r.get("base_automation_id") else None),
         "writes_path": r.get("update_path") or None,
         "writes_value": r.get("value")}
        for r in search_read("ir.actions.server",
                             [("usage", "!=", "ir_cron")],
                             ["name", "model_name", "state", "usage",
                              "base_automation_id", "update_path", "value"])
    ]
    snap["record_rules"] = [
        {"id": r["id"], "name": r["name"], "model": r["model_id"][1],
         "domain": r["domain_force"], "global": r["global"],
         "groups": r["groups"], "standard": None}
        for r in search_read("ir.rule", [], ["name", "model_id",
                                             "domain_force", "global", "groups"])
    ]
    return snap


def load_dump(path):
    with open(path, encoding="utf-8") as fh:
        snap = json.load(fh)
    for layer in LAYERS:
        snap.setdefault(layer, [])
    return snap


# --------------------------------------------------------------------------
# Граф
# --------------------------------------------------------------------------

class Graph:
    def __init__(self):
        self.nodes = {}          # id -> {kind, label, model, ...}
        self.edges = []          # (src, dst, kind)
        self._out = defaultdict(list)
        self._in = defaultdict(list)

    def add_node(self, nid, **attrs):
        self.nodes.setdefault(nid, {}).update(attrs)

    def add_edge(self, src, dst, kind):
        if src not in self.nodes or dst not in self.nodes:
            return
        self.edges.append((src, dst, kind))
        self._out[src].append((dst, kind))
        self._in[dst].append((src, kind))

    def out(self, nid, kind=None):
        return [d for d, k in self._out[nid] if kind is None or k == kind]

    def inc(self, nid, kind=None):
        return [s for s, k in self._in[nid] if kind is None or k == kind]


def arch_fields(arch):
    return set(FIELD_IN_ARCH_RE.findall(arch or ""))


def domain_fields(domain):
    """Имена полей, упомянутые в домене (левые части троек)."""
    found = set()
    for token in FIELD_IN_DOMAIN_RE.findall(domain or ""):
        found.add(token.split(".")[0])
    return found


def build_graph(snap):
    g = Graph()
    custom_fields = defaultdict(dict)   # model -> {field_name: node_id}

    def model_node(model):
        if not model:
            return None
        nid = f"model:{model}"
        if nid not in g.nodes:
            g.add_node(nid, kind="model", label=model, model=model,
                       custom=any(m["model"] == model
                                  for m in snap["models_manual"]))
        return nid

    for rec in snap["models_manual"]:
        model_node(rec["model"])
        g.nodes[f"model:{rec['model']}"]["title"] = rec.get("name")

    for f in snap["fields_manual"]:
        nid = f"field:{f['model']}.{f['name']}"
        g.add_node(nid, kind="field", label=f["name"], model=f["model"],
                   ttype=f["ttype"], flabel=f.get("label"),
                   relation=f.get("relation"), related=f.get("related"))
        custom_fields[f["model"]][f["name"]] = nid
        g.add_edge(nid, model_node(f["model"]), "field_of")
        if f.get("relation"):
            g.add_edge(nid, model_node(f["relation"]), "relates_to")

    for v in snap["views_custom"]:
        nid = f"view:{v['id']}"
        g.add_node(nid, kind="view", label=v["name"], model=v.get("model"),
                   vtype=v.get("type"), mode=v.get("mode"),
                   inherit_id=v.get("inherit_id"),
                   inherit_name=v.get("inherit_name"),
                   arch=v.get("arch") or "",
                   fields=sorted(arch_fields(v.get("arch"))))
        if v.get("model"):
            g.add_edge(nid, model_node(v["model"]), "view_of")

    by_view_id = {v["id"]: f"view:{v['id']}" for v in snap["views_custom"]}
    for v in snap["views_custom"]:
        base = v.get("inherit_id")
        if base and base in by_view_id:
            g.add_edge(f"view:{v['id']}", by_view_id[base], "inherits")

    # представление -> кастомное поле, которое оно выводит
    for v in snap["views_custom"]:
        for fname in arch_fields(v.get("arch")):
            target = custom_fields.get(v.get("model"), {}).get(fname)
            if target:
                g.add_edge(f"view:{v['id']}", target, "shows")

    for a in snap["automations"]:
        nid = f"auto:{a['id']}"
        g.add_node(nid, kind="automation", label=a["name"], model=a["model"],
                   trigger=a.get("trigger"), active=a.get("active", True),
                   domain=a.get("filter_domain") or "")
        g.add_edge(nid, model_node(a["model"]), "automates")
        for fname in domain_fields(a.get("filter_domain")):
            target = custom_fields.get(a["model"], {}).get(fname)
            if target:
                g.add_edge(nid, target, "triggers_on")

    for s in snap["server_actions"]:
        nid = f"action:{s['id']}"
        g.add_node(nid, kind="action", label=s["name"], model=s["model"],
                   state=s.get("state"), usage=s.get("usage"),
                   automation_id=s.get("automation_id"),
                   writes_path=s.get("writes_path"),
                   writes_value=s.get("writes_value"))
        g.add_edge(nid, model_node(s["model"]), "acts_on")
        wpath = (s.get("writes_path") or "").split(".")[0]
        target = custom_fields.get(s["model"], {}).get(wpath)
        if target:
            g.add_edge(nid, target, "writes")
        if s.get("automation_id"):
            g.add_edge(nid, f"auto:{s['automation_id']}", "runs_in")

    for r in snap["record_rules"]:
        nid = f"rule:{r['id']}"
        g.add_node(nid, kind="rule", label=r["name"], model=r["model"],
                   domain=r.get("domain"), is_global=r.get("global"),
                   groups=r.get("groups") or [], standard=r.get("standard"))
        g.add_edge(nid, model_node(r["model"]), "restricts")

    return g


# --------------------------------------------------------------------------
# Проверки
# --------------------------------------------------------------------------

def find_issues(g, snap):
    issues = []

    def add(sev, kind, title, detail, where=""):
        issues.append({"severity": sev, "kind": kind, "title": title,
                       "detail": detail, "where": where})

    # Значения, которых поле никогда не получает: считаем заранее, потому что
    # этот вывод более конкретен и вытесняет общие выводы о том же поле.
    unreachable = {}
    for nid, n in g.nodes.items():
        if n["kind"] != "field" or g.inc(nid, "shows"):
            continue
        required = {}
        for a in g.inc(nid, "triggers_on"):
            for value in domain_requirements(
                    g.nodes[a].get("domain")).get(n["label"], ()):
                required.setdefault(value, []).append(a)
        produced = {norm_value(g.nodes[w].get("writes_value"))
                    for w in g.inc(nid, "writes")}
        produced.add("false")   # значение по умолчанию достижимо само собой
        missing = {v: autos for v, autos in required.items()
                   if v not in produced}
        if missing:
            unreachable[nid] = missing

    # 1. Поля без единой ссылки: ни представления, ни автоматизации
    for nid, n in g.nodes.items():
        if n["kind"] != "field":
            continue
        shown = g.inc(nid, "shows")
        triggered = g.inc(nid, "triggers_on")
        written = g.inc(nid, "writes")
        mechanism = next((why for rx, why in KNOWN_MECHANISMS
                          if rx.match(n["label"])), None)
        if mechanism and not shown:
            add("низкая", "odoo_mechanism",
                f"{n['model']}.{n['label']} — служебное поле Odoo",
                f"Статических ссылок в представлениях нет, и это нормально: "
                f"{mechanism}. Проверять как доработку не нужно.",
                n["model"])
        elif not shown and not triggered and not written:
            add("высокая", "orphan_field",
                f"{n['model']}.{n['label']} — поле ни на что не влияет",
                "Не выводится ни в одном представлении и не используется "
                "ни в одной автоматизации. Либо доработка не доведена, "
                "либо поле — мусор после экспериментов.",
                n["model"])
        elif nid in unreachable:
            pass        # об этом поле скажет проверка недостижимых значений
        elif not shown and (triggered or written):
            writers = ", ".join(f"«{g.nodes[a]['label']}»" for a in written)
            gates = ", ".join(f"«{g.nodes[a]['label']}»" for a in triggered)
            if written:
                # Значение ставит система — пользователь не видит результата.
                add("средняя", "invisible_result",
                    f"{n['model']}.{n['label']} — система пишет в поле, "
                    "которого не видно",
                    f"В поле пишут: {writers}. Ни в одном представлении оно "
                    "не выведено, поэтому пользователь не видит результат и "
                    "не понимает, почему система так себя ведет.",
                    n["model"])
            else:
                # Значение должен ставить человек, а поля в интерфейсе нет.
                add("высокая", "unreachable_gate",
                    f"{n['model']}.{n['label']} — условие автоматизации, "
                    "которое негде заполнить",
                    f"От значения этого поля зависит: {gates}. Никто в него "
                    "не пишет автоматически, а в интерфейс оно не выведено — "
                    "значит заполнить его штатным способом нельзя и "
                    "автоматизация не сработает никогда.",
                    n["model"])

    # 2. Одно поле дважды вставлено в одно и то же базовое представление
    placement = defaultdict(list)
    for nid, n in g.nodes.items():
        if n["kind"] != "view" or n.get("mode") != "extension":
            continue
        for fld in g.out(nid, "shows"):
            placement[(n.get("inherit_id"), fld)].append(nid)
    for (base, fld), views in placement.items():
        if len(views) > 1:
            names = ", ".join(f"{g.nodes[v]['label']} (id {v.split(':')[1]})"
                              for v in views)
            add("высокая", "duplicate_placement",
                f"{g.nodes[fld]['model']}.{g.nodes[fld]['label']} "
                f"вставлено в одну форму {len(views)} раза",
                f"Наследуют одно базовое представление (id {base}) и оба "
                f"добавляют это поле: {names}. В форме поле дублируется.",
                g.nodes[fld]["model"])

    # 3. Несколько кастомных расширений одного базового представления
    by_base = defaultdict(list)
    for nid, n in g.nodes.items():
        if n["kind"] == "view" and n.get("mode") == "extension" and n.get("inherit_id"):
            by_base[(n["inherit_id"], n.get("inherit_name"))].append(nid)
    for (base_id, base_name), views in sorted(by_base.items()):
        if len(views) > 1:
            add("средняя", "xpath_collision_risk",
                f"{base_name or base_id}: {len(views)} кастомных расширения",
                "Несколько наследников одного представления — типовая "
                "причина поломки при обновлении версии: xpath одного "
                "перестаёт находить узел после правки другого. "
                + "; ".join(f"id {v.split(':')[1]} «{g.nodes[v]['label']}»"
                            for v in views),
                g.nodes[views[0]].get("model") or "")

    # 4. Пустые расширения
    for nid, n in g.nodes.items():
        if n["kind"] == "view" and re.fullmatch(r"\s*<data\s*/>\s*", n.get("arch", "")):
            add("низкая", "empty_view",
                f"Пустое представление: «{n['label']}» (id {nid.split(':')[1]})",
                "Наследует базовое представление, но ничего не меняет. "
                "Занимает место в цепочке наследования и сбивает с толку.",
                n.get("model") or "")

    # 5. Незачищенные тестовые артефакты
    for nid, n in g.nodes.items():
        text = " ".join(str(x) for x in (n.get("label"), n.get("flabel")) if x)
        if LEFTOVER_RE.search(text):
            add("средняя", "leftover_artifact",
                f"{n['kind']}: «{n.get('label')}» помечено как тестовое",
                "Название говорит о проверке/черновике/уборке. "
                "В рабочей базе таких объектов быть не должно: они "
                "выполняются и влияют на данные наравне с рабочими.",
                n.get("model") or "")

    # 6. Одинаковое имя поля в разных моделях
    by_name = defaultdict(list)
    for f in snap["fields_manual"]:
        by_name[f["name"]].append(f)
    for name, recs in sorted(by_name.items()):
        if len(recs) > 1:
            models = ", ".join(sorted(r["model"] for r in recs))
            same_label = len({r.get("label") for r in recs}) == 1
            add("низкая" if same_label else "средняя", "cross_model_field",
                f"Поле {name} создано в {len(recs)} моделях",
                f"Модели: {models}. "
                + ("Подписи совпадают — похоже на осознанный сквозной "
                   "признак; проверьте, не нужен ли related вместо копии."
                   if same_label else
                   "Подписи отличаются — одно имя означает разные вещи, "
                   "это ломает отчётность и переносы."),
                "")

    # 7. Действия сервера без привязки к автоматизации, дублирующие привязанные
    linked = defaultdict(set)
    for s in snap["server_actions"]:
        if s.get("automation_id"):
            linked[s["model"]].add(s["state"])
    for s in snap["server_actions"]:
        if s.get("automation_id") or s.get("usage") == "ir_cron":
            continue
        if s["state"] in linked.get(s["model"], ()):
            add("средняя", "dangling_action",
                f"Действие «{s['name']}» не привязано к автоматизации",
                f"На модели {s['model']} уже есть действие того же типа "
                f"({s['state']}), привязанное к автоматизации. Это, скорее "
                "всего, дубль ручной сборки: срабатывает только вручную "
                "из меню и легко расходится с рабочей логикой.",
                s["model"])

    # 8. Ручное действие переписывает поле, которым управляет автоматизация
    for nid, n in g.nodes.items():
        if n["kind"] != "field":
            continue
        writers = g.inc(nid, "writes")
        manual = [a for a in writers if not g.nodes[a].get("automation_id")]
        auto = [a for a in writers if g.nodes[a].get("automation_id")]
        if manual and auto:
            auto_vals = {str(g.nodes[a].get("writes_value")) for a in auto}
            for a in manual:
                val = str(g.nodes[a].get("writes_value"))
                conflict = val not in auto_vals
                add("высокая" if conflict else "средняя",
                    "competing_writer",
                    f"«{g.nodes[a]['label']}» пишет в "
                    f"{n['model']}.{n['label']} в обход автоматизации",
                    f"Это действие запускается вручную и ставит значение "
                    f"`{val}`, тогда как полем управляют автоматизации "
                    f"(значения: {', '.join(sorted(auto_vals))}). "
                    + ("Значение не входит в набор автоматизаций — ручной "
                       "запуск выводит запись из согласованного состояния, "
                       "и автоматизация это уже не исправит."
                       if conflict else
                       "Значение совпадает с автоматическим, но логика "
                       "продублирована в двух местах и разойдется при "
                       "первой же правке."),
                    n["model"])

    # 9. Автоматизация ждет значения, которого никто не выставляет
    for nid, missing in unreachable.items():
        n = g.nodes[nid]
        for value, autos in sorted(missing.items()):
            waiting = ", ".join(f"«{g.nodes[a]['label']}»" for a in autos)
            written = g.inc(nid, "writes")
            how = ("Ни одно действие сервера его не выставляет"
                   if not written else
                   "Действия сервера пишут в это поле только другие значения")
            add("высокая", "unreachable_state",
                f"{n['model']}.{n['label']} никогда не получает "
                f"значение `{value}`",
                f"Ждут этого значения: {waiting}. {how}, а в интерфейсе поля "
                "нет — значит эта ветка процесса не запускается вообще "
                "никогда.",
                n["model"])

    order = {"высокая": 0, "средняя": 1, "низкая": 2}
    issues.sort(key=lambda i: (order[i["severity"]], i["kind"], i["title"]))
    return issues


# --------------------------------------------------------------------------
# Отчеты
# --------------------------------------------------------------------------

def impact_report(g, snap, model):
    """Отчет влияния по одной модели — заготовка для раздела ТР."""
    mid = f"model:{model}"
    if mid not in g.nodes:
        return None

    fields = [n for n in g.inc(mid, "field_of")]
    views = [n for n in g.inc(mid, "view_of")]
    autos = [n for n in g.inc(mid, "automates")]
    actions = [n for n in g.inc(mid, "acts_on")]
    rules = [n for n in g.inc(mid, "restricts")]

    out = [f"# Анализ влияния: `{model}`", ""]
    out.append(f"База `{snap['meta'].get('db')}`, Odoo "
               f"{snap['meta'].get('odoo_version', '?')}. "
               f"Снимок метаданных: {snap['meta'].get('extracted_at', '—')}.")
    out.append("")
    out.append(f"**Затронуто объектов:** {len(fields)} кастомных полей, "
               f"{len(views)} представлений, {len(autos)} автоматизаций, "
               f"{len(actions)} действий сервера, {len(rules)} правил доступа.")
    out.append("")

    out.append("## Кастомные поля")
    out.append("")
    if fields:
        out.append("| Поле | Подпись | Тип | Связь | Где выводится "
                   "| Кто пишет | Условие автоматизации |")
        out.append("|---|---|---|---|---|---|---|")
        for f in sorted(fields, key=lambda n: g.nodes[n]["label"]):
            n = g.nodes[f]
            shown = g.inc(f, "shows")
            trig = g.inc(f, "triggers_on")
            written = g.inc(f, "writes")
            out.append("| `{}` | {} | {} | {} | {} | {} | {} |".format(
                n["label"], n.get("flabel") or "—", n.get("ttype"),
                f"`{n['relation']}`" if n.get("relation") else "—",
                (", ".join(f"id {v.split(':')[1]}" for v in shown)
                 or "**нигде**"),
                (", ".join(f"«{g.nodes[a]['label']}»" for a in written)
                 or "только вручную"),
                (", ".join(f"id {a.split(':')[1]}" for a in trig) or "—")))
    else:
        out.append("_Кастомных полей нет._")
    out.append("")

    out.append("## Представления")
    out.append("")
    if views:
        out.append("| id | Название | Тип | Режим | Наследует |")
        out.append("|---|---|---|---|---|")
        for v in sorted(views, key=lambda n: g.nodes[n]["label"]):
            n = g.nodes[v]
            out.append("| {} | {} | {} | {} | {} |".format(
                v.split(":")[1], n["label"], n.get("vtype"), n.get("mode"),
                f"{n.get('inherit_name')} (id {n.get('inherit_id')})"
                if n.get("inherit_id") else "—"))
    else:
        out.append("_Кастомных представлений нет._")
    out.append("")

    out.append("## Автоматизации и действия")
    out.append("")
    if autos:
        for a in sorted(autos, key=lambda n: g.nodes[n]["label"]):
            n = g.nodes[a]
            acts = g.inc(a, "runs_in")
            out.append(f"- **{n['label']}** (id {a.split(':')[1]}, "
                       f"триггер `{n.get('trigger')}`"
                       f"{'' if n.get('active', True) else ', ВЫКЛЮЧЕНА'})")
            out.append(f"  - условие: `{n.get('domain') or '—'}`")
            if acts:
                out.append("  - действия: " + ", ".join(
                    f"«{g.nodes[x]['label']}» ({g.nodes[x].get('state')})"
                    for x in acts))
    else:
        out.append("_Автоматизаций нет._")
    unlinked = [a for a in actions if not g.nodes[a].get("automation_id")]
    if unlinked:
        out.append("")
        out.append("Действия сервера без привязки к автоматизации "
                   "(запускаются вручную):")
        for a in sorted(unlinked, key=lambda n: g.nodes[n]["label"]):
            n = g.nodes[a]
            out.append(f"- «{n['label']}» (id {a.split(':')[1]}, "
                       f"{n.get('state')})")
    out.append("")

    out.append("## Правила доступа")
    out.append("")
    if rules:
        out.append("| id | Название | Глобальное | Группы | Домен |")
        out.append("|---|---|---|---|---|")
        for r in sorted(rules, key=lambda n: g.nodes[n]["label"]):
            n = g.nodes[r]
            out.append("| {} | {} | {} | {} | `{}` |".format(
                r.split(":")[1], n["label"],
                "да" if n.get("is_global") else "нет",
                ", ".join(str(x) for x in n.get("groups") or []) or "—",
                n.get("domain")))
    else:
        out.append("_Правил доступа нет._")
    out.append("")

    related = sorted({g.nodes[m]["label"]
                      for f in fields for m in g.out(f, "relates_to")})
    if related:
        out.append("## Связанные модели")
        out.append("")
        out.append("Кастомные поля этой модели ссылаются на: "
                   + ", ".join(f"`{m}`" for m in related)
                   + ". Изменения в этих справочниках отражаются здесь.")
        out.append("")

    return "\n".join(out)


def issues_report(g, snap, issues):
    out = ["# Проблемы кастомного слоя", ""]
    out.append(f"База `{snap['meta'].get('db')}`, Odoo "
               f"{snap['meta'].get('odoo_version','?')}. "
               f"Найдено {len(issues)} проблем.")
    out.append("")
    counts = Counter(i["severity"] for i in issues)
    out.append("| Критичность | Кол-во |")
    out.append("|---|---|")
    for sev in ("высокая", "средняя", "низкая"):
        out.append(f"| {sev} | {counts.get(sev, 0)} |")
    out.append("")
    current = None
    for i in issues:
        if i["severity"] != current:
            current = i["severity"]
            out.append(f"## Критичность: {current}")
            out.append("")
        where = f" — `{i['where']}`" if i["where"] else ""
        out.append(f"### {i['title']}{where}")
        out.append("")
        out.append(i["detail"])
        out.append("")
    return "\n".join(out)


def stats_report(g, snap):
    kinds = Counter(n["kind"] for n in g.nodes.values())
    per_model = Counter()
    for nid, n in g.nodes.items():
        if n["kind"] != "model" and n.get("model"):
            per_model[n["model"]] += 1
    out = ["# Кастомный слой: сводка", ""]
    out.append(f"База `{snap['meta'].get('db')}`, Odoo "
               f"{snap['meta'].get('odoo_version','?')}, "
               f"модулей установлено: {snap['meta'].get('modules_installed','?')}.")
    out.append("")
    out.append(f"Узлов в графе: {len(g.nodes)}, связей: {len(g.edges)}.")
    out.append("")
    out.append("| Тип узла | Кол-во |")
    out.append("|---|---|")
    for k, c in kinds.most_common():
        out.append(f"| {k} | {c} |")
    out.append("")
    out.append("## Модели по объему кастомизации")
    out.append("")
    out.append("| Модель | Объектов кастомного слоя |")
    out.append("|---|---|")
    for m, c in per_model.most_common():
        out.append(f"| `{m}` | {c} |")
    return "\n".join(out)


# --------------------------------------------------------------------------
# HTML-визуализация
# --------------------------------------------------------------------------

HTML_TMPL = """<!doctype html>
<html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
 background:#161426;color:#e8e6f2;display:flex;height:100vh;overflow:hidden}
#stage{flex:1;position:relative;min-width:0}
svg{width:100%;height:100%;display:block;cursor:grab}
aside{width:300px;flex:0 0 300px;border-left:1px solid #2c2a44;padding:18px;
 overflow-y:auto;background:#1b1930}
h1{font-size:13px;letter-spacing:.12em;text-transform:uppercase;color:#9b98b8;margin:0 0 14px}
.row{display:flex;align-items:center;gap:9px;padding:5px 0;font-size:13px}
.row .dot{width:11px;height:11px;border-radius:50%;flex:0 0 11px}
.row .nm{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.row .ct{color:#77749a;font-variant-numeric:tabular-nums}
.legend{margin-top:22px;padding-top:16px;border-top:1px solid #2c2a44;font-size:12px;color:#9b98b8}
.legend div{padding:3px 0}
#tip{position:absolute;pointer-events:none;background:#0f0e1c;border:1px solid #3a3760;
 border-radius:6px;padding:8px 10px;font-size:12px;max-width:320px;opacity:0;transition:opacity .1s}
@media(max-width:760px){body{flex-direction:column;height:auto}
 aside{width:100%;flex:none;border-left:none;border-top:1px solid #2c2a44}
 #stage{height:60vh}}
</style></head><body>
<div id="stage"><svg id="g"></svg><div id="tip"></div></div>
<aside><h1>Модели</h1><div id="list"></div>
<div class="legend"><div><b>Форма узла</b></div>
<div>● модель &nbsp; ● поле &nbsp; ● представление</div>
<div>● автоматизация &nbsp; ● действие &nbsp; ● правило</div>
<div style="margin-top:10px">Размер — число связей. Тяните узлы мышью.</div>
</div></aside>
<script>
const DATA = __DATA__;
const svg = document.getElementById('g'), tip = document.getElementById('tip');
const W = () => svg.clientWidth, H = () => svg.clientHeight;
const palette = ['#6f9ee8','#e8a34f','#e0555f','#5fc2b0','#63c05c','#e6cf52',
                 '#d081c4','#e87fa0','#a98467','#9b98b8','#8fb5ef','#f0b877'];
const models = [...new Set(DATA.nodes.map(n => n.model).filter(Boolean))];
const counts = {};
DATA.nodes.forEach(n => { if (n.model) counts[n.model] = (counts[n.model]||0)+1; });
models.sort((a,b) => counts[b]-counts[a]);
const color = {};
models.forEach((m,i) => color[m] = palette[i % palette.length]);
const KIND_R = {model:9, field:5, view:5.5, automation:6, action:4.5, rule:4.5};

const idx = {}; DATA.nodes.forEach((n,i) => idx[n.id] = i);
const N = DATA.nodes.map(n => ({...n,
  x: W()/2 + (Math.random()-0.5)*380, y: H()/2 + (Math.random()-0.5)*380,
  vx:0, vy:0, deg:0}));
const L = DATA.edges.map(e => ({s: idx[e[0]], t: idx[e[1]], k: e[2]}))
                    .filter(e => e.s !== undefined && e.t !== undefined);
L.forEach(e => { N[e.s].deg++; N[e.t].deg++; });

const ns = 'http://www.w3.org/2000/svg';
const root = document.createElementNS(ns,'g'); svg.appendChild(root);
const gl = document.createElementNS(ns,'g'); root.appendChild(gl);
const gn = document.createElementNS(ns,'g'); root.appendChild(gn);

const lines = L.map(e => {
  const el = document.createElementNS(ns,'line');
  el.setAttribute('stroke', e.k === 'inherits' ? '#5a5580' : '#332f52');
  el.setAttribute('stroke-width', e.k === 'inherits' ? 1.4 : 0.9);
  gl.appendChild(el); return el;
});
const circles = N.map(n => {
  const el = document.createElementNS(ns,'circle');
  el.setAttribute('r', (KIND_R[n.kind]||5) + Math.min(n.deg*0.55, 6));
  el.setAttribute('fill', n.model ? color[n.model] : '#6b6890');
  el.setAttribute('stroke', n.kind === 'model' ? '#f2f0ff' : 'none');
  el.setAttribute('stroke-width', n.kind === 'model' ? 1.4 : 0);
  el.style.cursor = 'pointer';
  el.addEventListener('mousemove', ev => {
    tip.innerHTML = '<b>' + esc(n.label) + '</b><br>' + esc(n.kind)
      + (n.model ? ' · ' + esc(n.model) : '')
      + (n.detail ? '<br>' + esc(n.detail) : '');
    tip.style.opacity = 1;
    tip.style.left = Math.min(ev.offsetX + 14, W() - 340) + 'px';
    tip.style.top = (ev.offsetY + 14) + 'px';
  });
  el.addEventListener('mouseleave', () => tip.style.opacity = 0);
  el.addEventListener('mousedown', ev => { drag = n; ev.preventDefault(); });
  gn.appendChild(el); return el;
});
function esc(s){ const d = document.createElement('div'); d.textContent = s == null ? '' : s; return d.innerHTML; }

const gt = document.createElementNS(ns,'g'); root.appendChild(gt);
const labels = N.map(n => {
  if (n.kind !== 'model') return null;
  const el = document.createElementNS(ns,'text');
  el.textContent = n.label;
  el.setAttribute('font-size', 10.5);
  el.setAttribute('fill', '#cfcce6');
  el.setAttribute('paint-order', 'stroke');
  el.setAttribute('stroke', '#161426');
  el.setAttribute('stroke-width', 3);
  gt.appendChild(el); return el;
});

let drag = null, pan = null, tx = 0, ty = 0, sc = 1;
svg.addEventListener('mousemove', ev => {
  if (drag) { drag.x = (ev.offsetX - tx)/sc; drag.y = (ev.offsetY - ty)/sc; drag.vx = drag.vy = 0; }
  else if (pan) { tx += ev.offsetX - pan[0]; ty += ev.offsetY - pan[1]; pan = [ev.offsetX, ev.offsetY]; apply(); }
});
svg.addEventListener('mousedown', ev => { if (!drag) pan = [ev.offsetX, ev.offsetY]; });
window.addEventListener('mouseup', () => { drag = null; pan = null; });
svg.addEventListener('wheel', ev => {
  ev.preventDefault();
  const f = ev.deltaY < 0 ? 1.12 : 0.89;
  tx = ev.offsetX - (ev.offsetX - tx)*f; ty = ev.offsetY - (ev.offsetY - ty)*f;
  sc *= f; apply();
}, {passive:false});
function apply(){ root.setAttribute('transform', `translate(${tx},${ty}) scale(${sc})`); }

// Связи внутри модели держим короткими, между моделями — длинными,
// чтобы кластеры расходились и граф не превращался в клубок.
const REST = {inherits:34, field_of:52, view_of:52, automates:56, acts_on:56,
              restricts:58, shows:64, writes:64, triggers_on:64, relates_to:150};

function physics(){
  const cx = W()/2, cy = H()/2;
  for (let i = 0; i < N.length; i++) {
    for (let j = i+1; j < N.length; j++) {
      const dx = N[j].x - N[i].x, dy = N[j].y - N[i].y;
      const d2 = dx*dx + dy*dy || 0.01;
      if (d2 > 250000) continue;
      const same = N[i].model && N[i].model === N[j].model;
      const f = (same ? 700 : 2100)/d2, d = Math.sqrt(d2);
      const fx = f*dx/d, fy = f*dy/d;
      N[i].vx -= fx; N[i].vy -= fy; N[j].vx += fx; N[j].vy += fy;
    }
  }
  L.forEach(e => {
    const a = N[e.s], b = N[e.t];
    const dx = b.x - a.x, dy = b.y - a.y, d = Math.hypot(dx, dy) || 0.01;
    const f = (d - (REST[e.k] || 60)) * 0.014;
    a.vx += f*dx/d; a.vy += f*dy/d; b.vx -= f*dx/d; b.vy -= f*dy/d;
  });
  N.forEach(n => {
    n.vx += (cx - n.x)*0.0026; n.vy += (cy - n.y)*0.0026;
    if (n !== drag) { n.x += n.vx *= 0.85; n.y += n.vy *= 0.85; }
  });
}

function paint(){
  N.forEach((n, i) => {
    circles[i].setAttribute('cx', n.x); circles[i].setAttribute('cy', n.y);
    if (labels[i]) { labels[i].setAttribute('x', n.x + 12);
                     labels[i].setAttribute('y', n.y + 4); }
  });
  L.forEach((e, i) => {
    lines[i].setAttribute('x1', N[e.s].x); lines[i].setAttribute('y1', N[e.s].y);
    lines[i].setAttribute('x2', N[e.t].x); lines[i].setAttribute('y2', N[e.t].y);
  });
}

for (let i = 0; i < 400; i++) physics();   // прогрев до первой отрисовки

function fit(){                            // вписать граф в окно
  const xs = N.map(n => n.x), ys = N.map(n => n.y);
  const x0 = Math.min(...xs), x1 = Math.max(...xs);
  const y0 = Math.min(...ys), y1 = Math.max(...ys);
  const pad = 90;
  sc = Math.min(W()/(x1 - x0 + pad), H()/(y1 - y0 + pad), 1.6);
  tx = (W() - (x1 + x0)*sc)/2; ty = (H() - (y1 + y0)*sc)/2;
  apply();
}
fit();
window.addEventListener('resize', fit);
(function loop(){ physics(); paint(); requestAnimationFrame(loop); })();

const list = document.getElementById('list');
models.forEach(m => {
  const row = document.createElement('div'); row.className = 'row';
  row.innerHTML = `<span class="dot" style="background:${color[m]}"></span>`
    + `<span class="nm" title="${esc(m)}">${esc(m)}</span>`
    + `<span class="ct">${counts[m]}</span>`;
  list.appendChild(row);
});
</script></body></html>
"""


def render_html(g, snap, title):
    nodes, edges = [], []
    for nid, n in g.nodes.items():
        detail = ""
        if n["kind"] == "field":
            detail = f"{n.get('flabel') or ''} · {n.get('ttype') or ''}"
        elif n["kind"] == "view":
            detail = f"{n.get('vtype') or ''} · {n.get('mode') or ''}"
        elif n["kind"] == "automation":
            detail = n.get("trigger") or ""
        elif n["kind"] == "action":
            detail = n.get("state") or ""
        nodes.append({"id": nid, "kind": n["kind"], "label": n.get("label"),
                      "model": n.get("model"), "detail": detail.strip(" ·")})
    for s, d, k in g.edges:
        edges.append([s, d, k])
    payload = json.dumps({"nodes": nodes, "edges": edges}, ensure_ascii=False)
    return (HTML_TMPL.replace("__TITLE__", html.escape(title))
                     .replace("__DATA__", payload))


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--dump", help="снимок метаданных (JSON)")
    src.add_argument("--live", action="store_true",
                     help="читать из живой базы по XML-RPC")
    ap.add_argument("--url", default=os.environ.get("ODOO_URL"))
    ap.add_argument("--db", default=os.environ.get("ODOO_DB"))
    ap.add_argument("--user", default=os.environ.get("ODOO_USER"))
    ap.add_argument("--api-key", default=os.environ.get("ODOO_API_KEY"))
    ap.add_argument("--model", action="append", default=[],
                    help="модель для отчета влияния (можно несколько)")
    ap.add_argument("--out", default="out", help="каталог результатов")
    ap.add_argument("--save-dump", help="куда сохранить снимок при --live")
    args = ap.parse_args()

    if args.live:
        missing = [k for k in ("url", "db", "user", "api_key")
                   if not getattr(args, k)]
        if missing:
            sys.exit("Для --live нужны: " + ", ".join("--" + m.replace("_", "-")
                                                      for m in missing))
        snap = fetch_live(args.url, args.db, args.user, args.api_key)
        if args.save_dump:
            os.makedirs(os.path.dirname(args.save_dump) or ".", exist_ok=True)
            with open(args.save_dump, "w", encoding="utf-8") as fh:
                json.dump(snap, fh, ensure_ascii=False, indent=2)
            print(f"снимок  -> {args.save_dump}")
    else:
        snap = load_dump(args.dump)

    g = build_graph(snap)
    issues = find_issues(g, snap)
    os.makedirs(args.out, exist_ok=True)

    def write(name, text):
        path = os.path.join(args.out, name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text + "\n")
        print(f"{name:34s} -> {path}")

    write("00-сводка.md", stats_report(g, snap))
    write("01-проблеми.md", issues_report(g, snap, issues))

    targets = args.model or [m for m, _ in Counter(
        n.get("model") for nid, n in g.nodes.items()
        if n["kind"] != "model" and n.get("model")).most_common(3)]
    for model in targets:
        rep = impact_report(g, snap, model)
        if rep is None:
            print(f"нет данных по модели {model}", file=sys.stderr)
            continue
        write(f"impact-{model}.md", rep)

    write("graph.json", json.dumps(
        {"nodes": [dict(id=k, **{kk: vv for kk, vv in v.items() if kk != "arch"})
                   for k, v in g.nodes.items()],
         "edges": [{"src": s, "dst": d, "kind": k} for s, d, k in g.edges]},
        ensure_ascii=False, indent=2))
    write("graph.html", render_html(
        g, snap, f"Кастомный слой {snap['meta'].get('db', 'Odoo')}"))

    sev = Counter(i["severity"] for i in issues)
    print(f"\nузлов {len(g.nodes)}, связей {len(g.edges)}; проблем: "
          f"высокая {sev.get('высокая',0)}, средняя {sev.get('средняя',0)}, "
          f"низкая {sev.get('низкая',0)}")


if __name__ == "__main__":
    main()
