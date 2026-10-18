#!/usr/bin/env python3
"""Одноразова міграція імен factory3d -> стандарт td_* (див. factory3d/build/RENAME.md).

Крок 1 (git mv каталогів і файлів) уже виконано окремим комітом. Цей скрипт — крок 2: заміна ідентифікаторів
у вмісті файлів. Жодного сліпого `s/f3d/td/g`: кожна категорія має власний явний регекс і лічильник,
а множини імен (моделі, поля, xml-id, файли) збираються з коду ДО заміни.

    python3 factory3d/build/rename_td.py            # сухий прогін: лічильники й залишки, нічого не пише
    python3 factory3d/build/rename_td.py --apply    # записати зміни

Скрипт ідемпотентний (повторний запуск після --apply нічого не змінює) і лишається в репозиторії як журнал
перейменування: у ньому за призначенням згадуються старі імена.
"""
from __future__ import annotations

import ast
import collections
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
ADDONS = REPO / "factory3d" / "odoo_addons"
RENAME_COMMIT = "95bf195"   # крок 1: git mv каталогів модулів і файлів f3d_* -> td_*

MODMAP = {
    "factory3d_base": "td_factory3d",
    "factory3d_viewer": "td_viewer3d",
    "factory3d_constructor": "td_constructor",
    "factory3d_constructor_viewer": "td_constructor_viewer3d",
    "factory3d_telemetry": "td_telemetry",
    "factory3d_iot_sim": "td_iot_sim",
    "factory3d_machine_connect": "td_machine_connect",
    "factory3d_energy": "td_energy",
    "factory3d_yard": "td_yard",
    "factory3d_access": "td_access",
    "factory3d_bms": "td_bms",
    "factory3d_fire_safety": "td_fire_safety",
    "factory3d_genset": "td_genset_factory3d",
    "factory3d_viewer_sale": "td_viewer3d_sale",
    "factory3d_yard_gantt": "td_yard_gantt",
    "factory3d_telemetry_viewer": "td_telemetry_viewer3d",
    "factory3d_fire_safety_viewer": "td_fire_safety_viewer3d",
    "factory3d_access_telemetry": "td_access_telemetry",
    "factory3d_base_mrp_maintenance": "td_factory3d_mrp_maintenance",
    "factory3d_machine_connect_mrp_workorder": "td_machine_connect_mrp_workorder",
    "test_factory3d_viewer": "test_td_viewer3d",
    "test_factory3d_fire_safety": "test_td_fire_safety",
}
# модулі, згадані лише в документації (заплановані мости, які не збиралися): імена за тією ж схемою
DOC_ONLY_MODULES = {
    "factory3d_energy_mrp_workorder": "td_energy_mrp_workorder",
    "factory3d_genset_viewer": "td_genset_viewer3d",
}
# простори імен ir.config_parameter: factory3d.<ns>.<param> -> td.<ns>.<param>
PARAM_NS = ("base", "telemetry", "yard", "access", "machine_connect", "viewer", "energy", "bms", "iot_sim",
            "genset", "fire_safety", "constructor")
# «віртуальні» ключі змін шини переглядача (не моделі), що живуть у тому самому просторі імен, що й моделі
VIRTUAL_MODEL_KEYS = ("energy", "bms")

# Файли, які не чіпаємо: артефакти, сторонні бібліотеки, окремі проєкти, макет-прототип
SKIP_PREFIXES = ("luxsite/", "odoo_graph/", "factory3d/dist/", "factory3d/viewer/index.html",
                 "factory3d/build/constructor/proto/", "factory3d/build/rename_td.py", "factory3d/build/RENAME.md")
SKIP_PARTS = ("/static/lib/", "/static/src/lib/", "/static/data/", ".min.js")
TEXT_EXT = {".py", ".xml", ".csv", ".js", ".mjs", ".scss", ".css", ".md", ".sh", ".toml", ".yml", ".yaml", ".txt",
            ".ini", ".sql", ".html", ".json", ".cfg", ".example", ".gitignore"}

L = r"(?<![A-Za-z0-9_])"          # лівий кордон токена
R = r"(?![A-Za-z0-9_])"           # правий кордон токена


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "-C", str(REPO), "ls-files"], capture_output=True, text=True, check=True).stdout
    files = []
    for rel in out.splitlines():
        if rel.startswith(SKIP_PREFIXES) or any(p in "/" + rel for p in SKIP_PARTS):
            continue
        p = Path(rel)
        if p.suffix in TEXT_EXT or p.name in TEXT_EXT:
            files.append(rel)
    return files


def _lit(node: ast.AST) -> list[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    if isinstance(node, (ast.List, ast.Tuple)):
        return [s for e in node.elts for s in _lit(e)]
    return []


def collect_inventory(files: list[str]) -> dict:
    """Множини імен із коду: моделі `f3d.*` (_name), поля `f3d_*` (fields.X), xml-id, стеми файлів."""
    models: set[str] = set()
    fields: set[str] = set()
    xmlids: set[str] = set()
    for rel in files:
        path = REPO / rel
        text = path.read_text(encoding="utf-8")
        if rel.startswith("factory3d/odoo_addons/") and rel.endswith(".py"):
            try:
                tree = ast.parse(text)
            except SyntaxError:
                continue
            for cls in (n for n in ast.walk(tree) if isinstance(n, ast.ClassDef)):
                for st in cls.body:
                    if not (isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name)):
                        continue
                    tgt = st.targets[0].id
                    if tgt == "_name":
                        models.update(n for n in _lit(st.value) if n.startswith("f3d."))
                    elif (isinstance(st.value, ast.Call) and isinstance(st.value.func, ast.Attribute)
                          and isinstance(st.value.func.value, ast.Name) and st.value.func.value.id == "fields"
                          and tgt.startswith("f3d_")):
                        fields.add(tgt)
        if rel.startswith("factory3d/odoo_addons/") and rel.endswith(".xml"):
            for m in re.finditer(r"<(?:record|menuitem|template|report|act_window|asset|function)\b[^>]*?\bid=\"([^\"]+)\"",
                                 text, re.S):
                xmlids.add(m.group(1))
        if rel.startswith("factory3d/odoo_addons/") and rel.endswith(".csv"):
            first = text.splitlines()[:1]
            if first and first[0].startswith("id,"):
                for line in text.splitlines()[1:]:
                    if line and not line.startswith("#"):
                        xmlids.add(line.split(",", 1)[0].strip('"'))
    seg = re.compile(r"(?<![A-Za-z0-9])f3d(?![A-Za-z0-9])")
    xml_f3d = {x for x in xmlids if "." not in x and seg.search(x) and "x_f3d" not in x}
    return {"models": models, "fields": fields, "xmlids": xml_f3d}


def renamed_file_stems() -> set[str]:
    """Стеми файлів f3d_<x>.{py,xml,csv}, перейменованих на td_<x> у коміті кроку 1 (RENAME_COMMIT)."""
    out = subprocess.run(["git", "-C", str(REPO), "show", "--name-status", "-M", "--format=", RENAME_COMMIT],
                         capture_output=True, text=True, check=True).stdout
    stems = set()
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[0].startswith("R"):
            old, new = Path(parts[1]), Path(parts[2])
            if old.name.startswith("f3d_") and new.name.startswith("td_") and old.suffix == new.suffix:
                stems.add(old.stem[len("f3d_"):])
    return stems


def alt(items) -> str:
    """Альтернація з довших імен до коротших; порожня множина не збігається ні з чим (ідемпотентність)."""
    return "|".join(re.escape(i) for i in sorted(items, key=lambda s: (-len(s), s))) or "(?!)"


def build_rules(inv: dict) -> list[tuple[str, re.Pattern, object]]:
    """Явні регекси за категоріями; порядок має значення (спочатку модулі, потім xml-id, поля, таблиці, моделі)."""
    models = {m[len("f3d."):] for m in inv["models"]} | set(VIRTUAL_MODEL_KEYS)
    tables = {m.replace(".", "_") for m in models if m not in VIRTUAL_MODEL_KEYS}
    fields = {f[len("f3d_"):] for f in inv["fields"]}
    xmlids = inv["xmlids"]
    stems = renamed_file_stems()
    seg = re.compile(r"(?<![A-Za-z0-9])f3d(?![A-Za-z0-9])")

    def xmlid_new(m: re.Match) -> str:
        return seg.sub("td", m.group(0))

    return [
        # 1. технічні імена модулів: manifests depends, odoo.addons.<m>, <m>.xmlid, /<m>/static, @<m>/..., --test-tags
        ("module", re.compile(L + "(" + alt({**MODMAP, **DOC_ONLY_MODULES}) + ")" + R),
         lambda m: {**MODMAP, **DOC_ONLY_MODULES}[m.group(1)]),
        # 2. ключі ir.config_parameter: factory3d.<ns>.<param>, а також шаблони 'factory3d.%', "factory3d." + key
        ("config_param", re.compile(r"(?<![A-Za-z0-9_./-])factory3d\.(?=(?:" + "|".join(PARAM_NS) + r")(?![A-Za-z0-9])|[%'\"{<*])"),
         lambda m: "td."),
        # 3. моделі: f3d.<model>[.attr] (довші імена першими); localStorage-ключі f3d.ui/lite/layers/static не збігаються
        ("model", re.compile(r"(?:(?<![A-Za-z0-9_./-])|(?<=data/))f3d\.(" + alt(models) + ")" + R), lambda m: "td." + m.group(1)),
        # 4. xml-id моделей/полів: model_f3d_<m>, field_f3d_<m>__<f>, __f3d_<field>
        ("xmlid_model", re.compile(L + r"(model|field)_f3d_"), lambda m: m.group(1) + "_td_"),
        ("xmlid_field", re.compile(r"(?<=[A-Za-z0-9]__)f3d_(" + alt(fields) + ")" + R), lambda m: "td_" + m.group(1)),
        # 5. xml-id, оголошені в data/views/security (record/menuitem/template/report/csv id), точний токен
        ("xmlid", re.compile(L + "(" + alt(xmlids) + ")" + R), xmlid_new),
        # 5б. префікси xml-id групи/меню/привілею (динамічні складання: 'group_f3d_' + name; фільтри group_f3d_*)
        ("xmlid_prefix", re.compile(r"(?<![A-Za-z0-9])(group|menu|privilege)_f3d_"), lambda m: m.group(1) + "_td_"),
        # 6. поля: точний токен f3d_<field>, default_f3d_<field> (контекст)
        ("field", re.compile(L + r"f3d_(" + alt(fields) + ")" + R), lambda m: "td_" + m.group(1)),
        ("field_default", re.compile(r"(?<![A-Za-z0-9])default_f3d_(" + alt(fields) + ")" + R), lambda m: "default_td_" + m.group(1)),
        # 7. таблиці моделей у сирому SQL (f3d_access_server -> td_access_server) і стеми файлів
        ("table", re.compile(L + r"f3d_(" + alt(tables) + ")" + R), lambda m: "td_" + m.group(1)),
        ("file_stem", re.compile(L + r"f3d_(" + alt(stems) + ")" + R), lambda m: "td_" + m.group(1)) if stems else None,
        # 7б. динамічні префікси імен полів: n.startswith('f3d_fire_'); шаблони-«зірочки» поля/таблиці/файли f3d_<x>_*
        ("field_prefix", re.compile(r"(startswith\(\s*[\"'])f3d_"), lambda m: m.group(1) + "td_"),
        ("wildcard", re.compile(r"(?<![A-Za-z0-9_.])f3d_((?:[a-z0-9]+_)*)\*"), lambda m: "td_" + m.group(1) + "*"),
        ("wildcard_module", re.compile(L + r"factory3d_\*"), lambda m: "td_*"),
        # 8. DDL-імена: таблиці many2many (…_rel), індекси (…_idx, …_uniq), службова таблиця журналу пакетів колектора
        ("ddl_name", re.compile(L + r"f3d_([a-z0-9_]+_(?:rel|idx|uniq)|collector_push(?:_collector_ts_idx)?)" + R),
         lambda m: "td_" + m.group(1)),
        # 9. імена блоків налаштувань: <block name="factory3d_<area>_<x>"> (після правила модулів)
        ("settings_block", re.compile(r"(?<=name=\")factory3d_([a-z0-9]+_[a-z0-9_]+)(?=\")|(?<=@name=')factory3d_([a-z0-9]+_[a-z0-9_]+)(?=')"), lambda m: "td_" + (m.group(1) or m.group(2))),
        # 10. назви успадкованих представлень у <field name="name">: <model>.form.f3d.<x> (лише XML)
        ("view_name", re.compile(r"(?<=[a-z]\.)f3d(?=\.[a-z])"), lambda m: "td"),
    ]


# Імена, що згадуються лише в документації (заплановані або вилучені поля/файли/xml-id): лише для .md
DOC_EXTRA_EXACT = ("f3d_row", "f3d_bay", "f3d_level", "f3d_pos", "f3d_kind_loc", "f3d_bms_deviation_id",
                   "view_f3d_energy_dashboard", "report_f3d_fire_events", "report_f3d_fire_events_document",
                   "f3d_access_card_server_id_fkey", "stock_location_f3d_code_index", "f3d_slot_preset",
                   "f3d_putaway_rule", "f3d_replenish_rule", "f3d_comment", "f3d_zone_lock")
DOC_EXTRA_PREFIX = ("f3d_sheet_", "f3d_meter_", "f3d_fire_consent_")
DOC_EXTRA = re.compile(L + "(?:" + "|".join(re.escape(t) for t in DOC_EXTRA_EXACT) + ")" + R + "|"
                       + L + "(?:" + "|".join(re.escape(t) for t in DOC_EXTRA_PREFIX) + ")")

# Значення даних, які збігаються з іменами таблиць/полів, але лишаються без змін: ключі Selection типів «локальних»
# джерел телеметрії (f3d_machine; f3d_bms/f3d_energy не збігаються з жодним правилом і так лишаються)
# + назва pip-пакета колектора f3d_collector (services/collector), що збігається з таблицею f3d_collector
PROTECT = re.compile(
    r"(?:<field name=\"type\">|\.type != \"|selection_add=\[\(\"|ondelete=\{\"|\+ \[\"|type=')f3d_machine"
    r"|name = \"f3d_collector\"|\"f3d_collector>="
    r"|(?:пакет колектора|пакет|залежність) f3d_collector" + R)


def apply_rules(text: str, rules, counts: collections.Counter, rel: str = "") -> str:
    skip = set()
    if not rel.endswith(".xml"):
        skip.add("view_name")
    if rel.endswith("tools/odoo/ENV.md"):
        skip.add("wildcard")   # там f3d_* — імена баз даних, а не поля
    rules = [r for r in rules if r is None or r[0] not in skip]
    shields: list[str] = []

    def shield(m: re.Match) -> str:
        shields.append(m.group(0))
        return f"\x00{len(shields) - 1}\x00"

    text = PROTECT.sub(shield, text)
    text = _apply(text, rules, counts)
    if rel.endswith(".md"):
        text, n = DOC_EXTRA.subn(lambda m: re.sub(r"f3d", "td", m.group(0), count=1), text)
        counts["doc_extra"] += n
    return re.sub(r"\x00(\d+)\x00", lambda m: shields[int(m.group(1))], text)


def _apply(text: str, rules, counts: collections.Counter) -> str:
    for rule in rules:
        if rule is None:
            continue
        cat, pat, repl = rule
        text, n = pat.subn(repl, text)
        counts[cat] += n
    return text


def main() -> int:
    apply = "--apply" in sys.argv
    files = tracked_files()
    inv = collect_inventory(files)
    rules = build_rules(inv)
    print(f"файлів у обробці: {len(files)}; моделей {len(inv['models'])}, полів {len(inv['fields'])}, xml-id {len(inv['xmlids'])}")
    counts: collections.Counter = collections.Counter()
    per_file: dict[str, collections.Counter] = {}
    changed = 0
    for rel in files:
        path = REPO / rel
        try:
            old = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        c: collections.Counter = collections.Counter()
        new = apply_rules(old, rules, c, rel)
        if new != old:
            changed += 1
            per_file[rel] = c
            counts.update(c)
            if apply:
                path.write_text(new, encoding="utf-8")
    print(f"змінено файлів: {changed}")
    for cat, n in counts.most_common():
        print(f"  {cat}: {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
