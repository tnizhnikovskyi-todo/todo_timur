#!/usr/bin/env python3
"""Технічний борг, етап 1: внутрішні Python-імена `_f3d_*` → `_td_*` у всьому factory3d.

Журнал перейменування (як і `rename_td.py`: у ньому за призначенням згадуються старі імена).

Правило: токен `(?<![A-Za-z0-9_])_f3d_<ідентифікатор>` → `_td_<ідентифікатор>` у всіх текстових файлах каталогу
factory3d (Python, XML-дані `ir.actions.server`, тести, JSON-фікстури, документи). Токен лишається без змін, якщо це:

* ім'я SQL-об'єкта моделі (`_f3d_x_uniq = models.Constraint(...)`, `models.Index`, `models.UniqueIndex`): з нього
  Odoo будує ім'я обмеження/індексу в БД (`<таблиця>_f3d_x_uniq`) і xml-id `constraint_<…>` — це ім'я БД, а не API;
* частина іншого імені (`_compute_f3d_x`, `action_f3d_x`, `o_f3d_x`, `x_f3d_signal`): слово має починатися на `_f3d_`.

Карта імен будується з дерева (AST + регекс). Перед заміною перевіряється колізія: якщо `_td_<x>` уже визначено на
тій самій моделі (або на моделі-предку/нащадку через `_inherit`), скрипт зупиняється, нічого не зливаючи мовчки.

    python3 factory3d/build/rename_private.py            # карта, колізії, звіт (нічого не змінює)
    python3 factory3d/build/rename_private.py --apply    # змінити файли
    python3 factory3d/build/rename_private.py --apply --group td_energy   # лише файли групи (каталог модуля / docs)
"""

from __future__ import annotations

import argparse
import ast
import collections
import json
import os
import re
import subprocess
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
TOKEN = re.compile(r"(?<![A-Za-z0-9_])_f3d_([A-Za-z0-9_]*)")
SQL_CALLS = {"Constraint", "Index", "UniqueIndex"}
# історичні журнали: старі імена там — призначення
SKIP = {"factory3d/build/RENAME.md", "factory3d/build/rename_td.py", "factory3d/build/rename_private.py"}
SKIP_PARTS = ("/static/lib/", "/dist/")
TEXT_EXT = {
    ".py", ".xml", ".json", ".js", ".mjs", ".md", ".csv", ".po", ".pot", ".sql", ".sh", ".toml", ".txt", ".yml", ".yaml",
    ".html", ".css", ".scss", ".cfg", ".ini", ".rst",
}  # fmt: skip


def tracked() -> list[str]:
    out = subprocess.check_output(["git", "ls-files", "-z", "--", "factory3d"], cwd=ROOT).decode()
    return [f for f in out.split("\0") if f and f not in SKIP and not any(p in "/" + f for p in SKIP_PARTS)]


def read(rel: str) -> str | None:
    if os.path.splitext(rel)[1] not in TEXT_EXT:
        return None
    try:
        with open(os.path.join(ROOT, rel), encoding="utf-8", newline="") as fh:
            return fh.read()
    except (OSError, UnicodeDecodeError):
        return None


def class_model(cls: ast.ClassDef) -> tuple[str | None, list[str]]:
    name, inherit = None, []
    for st in cls.body:
        if isinstance(st, ast.Assign) and len(st.targets) == 1 and isinstance(st.targets[0], ast.Name):
            if st.targets[0].id in ("_name", "_inherit"):
                try:
                    val = ast.literal_eval(st.value)
                except ValueError:
                    continue
                if st.targets[0].id == "_name":
                    name = val
                else:
                    inherit = [val] if isinstance(val, str) else list(val)
    return name, inherit


def scan(files: list[str]):
    """-> (імена SQL-об'єктів, {ім'я: [(файл, модель|None)]} визначень `_f3d_`/`_td_`, граф успадкування моделей)."""
    sql_names: set[str] = set()
    defs: dict[str, list[tuple[str, str | None]]] = collections.defaultdict(list)
    parents: dict[str, set[str]] = collections.defaultdict(set)
    for rel in files:
        if not rel.endswith(".py"):
            continue
        src = read(rel)
        if src is None:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue

        def own(st):
            if isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef)):
                return [(st.name, False)]
            if isinstance(st, ast.Assign):
                call = isinstance(st.value, ast.Call)
                fn = getattr(st.value.func, "attr", getattr(st.value.func, "id", "")) if call else ""
                return [(t.id, fn in SQL_CALLS) for t in st.targets if isinstance(t, ast.Name)]
            if isinstance(st, ast.AnnAssign) and isinstance(st.target, ast.Name):
                return [(st.target.id, False)]
            return []

        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                name, inherit = class_model(node)
                model = name or (inherit[0] if inherit else None)
                for p in inherit:
                    if p != model:
                        parents[model].add(p)
                for st in node.body:
                    for n, is_sql in own(st):
                        if n.startswith("_f3d_") and is_sql:
                            sql_names.add(n)
                        elif n.startswith(("_f3d_", "_td_")):
                            defs[n].append((rel, model))
            else:
                for n, is_sql in own(node):
                    if n.startswith(("_f3d_", "_td_")):
                        defs[n].append((rel, None))
    return sql_names, defs, parents


def closure(model: str, parents) -> set[str]:
    seen, todo = {model}, [model]
    while todo:
        for p in parents.get(todo.pop(), ()):
            if p not in seen:
                seen.add(p)
                todo.append(p)
    return seen


def collisions(defs, parents, sql_names) -> list[str]:
    bad = []
    for name, where in defs.items():
        if not name.startswith("_f3d_") or name in sql_names:
            continue
        new = "_td_" + name[5:]
        for rel_old, m_old in where:
            for rel_new, m_new in defs.get(new, ()):
                same_file_scope = m_old is None and m_new is None and rel_old == rel_new
                related = (
                    m_old is not None
                    and m_new is not None
                    and (m_new in closure(m_old, parents) or m_old in closure(m_new, parents))
                )
                if same_file_scope or related:
                    bad.append(f"{name} ({rel_old}, {m_old}) ↔ {new} ({rel_new}, {m_new})")
    return bad


def group_of(rel: str) -> str:
    parts = rel.split("/")
    if parts[:2] == ["factory3d", "odoo_addons"]:
        return parts[2]
    return "/".join(parts[:2]) if parts[:2] in (["factory3d", "docs"], ["factory3d", "build"]) else parts[1]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--group", action="append", help="обмежити заміну групою: модуль, docs, build, services, tools…")
    ap.add_argument("--map", help="записати карту імен у JSON")
    ap.add_argument(
        "--skip-check",
        action="store_true",
        help="не перевіряти колізії (для другої й далі груп: після першої групи `_td_x` уже є — це перевизначення)",
    )
    args = ap.parse_args()

    files = tracked()
    sql_names, defs, parents = scan(files)
    names: collections.Counter[str] = collections.Counter()
    per_group: collections.Counter[str] = collections.Counter()
    for rel in files:
        src = read(rel)
        if src:
            for m in TOKEN.finditer(src):
                if m.group(0) not in sql_names:
                    names[m.group(0)] += 1
                    per_group[group_of(rel)] += 1
    bad = [] if args.skip_check else collisions(defs, parents, sql_names)
    print(f"імен: {len(names)} (+{len(sql_names)} SQL-об'єктів лишаються), входжень: {sum(names.values())}")
    print("за групами:", dict(per_group.most_common()))
    if bad:
        print("КОЛІЗІЇ (нічого не змінено):", *bad, sep="\n  ")
        return 1
    if args.map:
        with open(args.map, "w", encoding="utf-8") as fh:
            json.dump({n: "_td_" + n[5:] for n in sorted(names)}, fh, ensure_ascii=False, indent=1)
    if not args.apply:
        return 0
    changed = 0
    for rel in files:
        if args.group and group_of(rel) not in args.group:
            continue
        src = read(rel)
        if not src:
            continue
        new = TOKEN.sub(lambda m: m.group(0) if m.group(0) in sql_names else "_td_" + m.group(1), src)
        if new != src:
            with open(os.path.join(ROOT, rel), "w", encoding="utf-8", newline="") as fh:
                fh.write(new)
            changed += 1
    print("змінено файлів:", changed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
