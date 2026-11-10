#!/usr/bin/env python3
"""Витяг розділу «Запити в D-02» (або іншого, `section`) з файлів-джерел у JSON. Лише stdlib.

Використання: python3 -I extract_d02.py manifest.json > extracted.json
manifest: [{"step":"B-09","client":"kl07","path":"clients/kl07/hypercare.md","sha":"a1b2c3d","section":"Запити в D-02"}]
Читає лише потрібний розділ (від заголовка `## <section>` до наступного `##`). Файл цілком у вихід не потрапляє.
`section_found` — заголовок розділу є; `table_found` — у розділі є шапка таблиці (розділ без таблиці = 0 запитів, не помилка).
ID беруться лише з колонки «ID…» (воронка — «Посилання»); без такої колонки рядок без ID. Колонка типу: «Тип»; для воронки — «Причина».
Лічильники (рядків у розділі / релевантних / без ID / розділ знайдено) друкуються в stderr: ними звіряють джерело
з extracted.json без читання файлів цілком. `relevant` залежить лише від значення колонки «Тип» (B-09, B-10:
«баг конфіг», «баг код», «навчання» -> false); без колонки «Тип» усі рядки релевантні (`type_column: false`).
"""
import json, re, sys

ID_RE = re.compile(r"\b([A-Z]{2,4}(?:-D02)?-\d+)\b")
EXCLUDE = ("баг конфіг", "баг код", "навчання")  # маршрути B-13 / B-07, не запити D-02 (лише B-09, B-10)


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def extract(entry):
    try:
        text = open(entry["path"], encoding="utf-8").read()
    except OSError as e:
        print(f"WARN {entry.get('path')}: файл недоступний ({e.__class__.__name__}); file_found=false", file=sys.stderr)
        return {**{k: entry.get(k) for k in ("step", "client", "path", "sha")},
                "section": entry.get("section", "Запити в D-02").lower(), "file_found": False,
                "section_found": False, "table_found": False, "type_column": False, "rows": []}
    want = entry.get("section", "Запити в D-02").lower()
    out, inside, header, tcol, icol, seen = [], False, None, None, None, False
    for line in text.splitlines():
        if re.match(r"#{2,}\s", line):
            if line.startswith("## "):
                inside = line[3:].strip().lower().startswith(want)
                seen = seen or inside
                header = None
            continue
        if not inside or not line.lstrip().startswith("|"):
            continue
        c = cells(line)
        if all(re.fullmatch(r":?-{2,}:?", x) for x in c if x):
            continue
        if header is None:
            header = c
            funnel = want.startswith("причини відмов")
            tcol = None
            for k in (("причин", "тип") if funnel else ("тип",)):
                tcol = next((i for i, h in enumerate(c) if h.lower().startswith(k)), None)
                if tcol is not None:
                    break
            idkey = "посилання" if funnel else "id"
            icol = next((i for i, h in enumerate(c) if h.lower().startswith(idkey)), None)
            continue
        row = dict(zip(header, c))
        m = ID_RE.search(c[icol]) if icol is not None and icol < len(c) else None
        typ = c[tcol].lower() if tcol is not None and tcol < len(c) else ""
        relevant = not (entry["step"] in ("B-09", "B-10") and any(e in typ for e in EXCLUDE))
        out.append({"id": m.group(1) if m else None, "type": typ, "relevant": relevant, "cells": row})
    return {**{k: entry.get(k) for k in ("step", "client", "path", "sha")}, "section": want,
            "file_found": True, "section_found": seen, "table_found": header is not None, "type_column": tcol is not None, "rows": out}


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__.split("\n")[0] + "\nUsage: python3 -I extract_d02.py manifest.json > extracted.json", file=sys.stderr)
        sys.exit(2)
    try:
        manifest = json.load(open(sys.argv[1], encoding="utf-8"))
    except (OSError, ValueError) as e:
        print(f"ERROR manifest {sys.argv[1]}: {e}", file=sys.stderr)
        sys.exit(2)
    res = [extract(e) for e in manifest]
    json.dump({"sources": res}, sys.stdout, ensure_ascii=False, indent=1)
    for s in res:
        r = s["rows"]
        print(f"{s['path']}@{s['sha']}: file_found={s['file_found']} section_found={s['section_found']} table_found={s['table_found']} rows={len(r)} "
              f"relevant={sum(x['relevant'] for x in r)} no_id={sum(not x['id'] for x in r)} "
              f"type_column={s['type_column']}", file=sys.stderr)
