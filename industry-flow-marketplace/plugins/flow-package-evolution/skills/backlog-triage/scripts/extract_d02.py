#!/usr/bin/env python3
"""Витяг розділу «Запити в D-02» (або іншого, `section`) з файлів-джерел у JSON. Лише stdlib.

Використання: extract_d02.py manifest.json > extracted.json
manifest: [{"step":"B-09","client":"kl07","path":"clients/kl07/hypercare.md","sha":"a1b2c3d","section":"Запити в D-02"}]
Читає лише потрібний розділ (від заголовка `## <section>` до наступного `##`). Файл цілком у вихід не потрапляє.
"""
import json, re, sys

ID_RE = re.compile(r"\b([A-Z]{2,4}(?:-D02)?-\d+)\b")
EXCLUDE = ("баг конфіг", "баг код", "навчання")  # маршрути B-13 / B-07, не запити D-02 (лише B-09, B-10)


def cells(line):
    return [c.strip() for c in line.strip().strip("|").split("|")]


def extract(entry):
    text = open(entry["path"], encoding="utf-8").read()
    want = entry.get("section", "Запити в D-02").lower()
    out, inside, header = [], False, None
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip().lower().startswith(want)
            header = None
            continue
        if not inside or not line.lstrip().startswith("|"):
            continue
        c = cells(line)
        if all(re.fullmatch(r":?-{2,}:?", x) for x in c if x):
            continue
        if header is None:
            header = c
            continue
        row = dict(zip(header, c))
        m = next((ID_RE.search(x) for x in c if ID_RE.search(x)), None)
        low = line.lower()
        relevant = not (entry["step"] in ("B-09", "B-10") and any(e in low for e in EXCLUDE))
        out.append({"id": m.group(1) if m else None, "relevant": relevant, "cells": row})
    return {**{k: entry.get(k) for k in ("step", "client", "path", "sha")}, "section": want,
            "section_found": header is not None, "rows": out}


if __name__ == "__main__":
    manifest = json.load(open(sys.argv[1], encoding="utf-8"))
    json.dump({"sources": [extract(e) for e in manifest]}, sys.stdout, ensure_ascii=False, indent=1)
