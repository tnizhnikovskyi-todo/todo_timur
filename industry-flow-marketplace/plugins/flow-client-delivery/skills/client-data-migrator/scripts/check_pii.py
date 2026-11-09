#!/usr/bin/env python3
"""Пошук незамаскованих персональних даних у файлах/теках. Значень не друкує. Запуск: python3 -I check_pii.py --path P [--path P2]"""
import argparse, json, os, re, sys

RULES = {
    "phone": re.compile(r"(?<!\d)(\+?38)?0?\d{2}[\s\-()]*\d{3}[\s\-]*\d{2}[\s\-]*\d{2}(?!\d)"),
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "tax_id": re.compile(r"(?<!\d)\d{10}(?!\d)"),
    "iban": re.compile(r"\bUA\d{2}[0-9A-Z]{25}\b"),
    "passport": re.compile(r"\b[А-ЯІЇЄҐA-Z]{2}\s?\d{6}\b"),
}
TEXT_EXT = {".csv", ".md", ".yaml", ".yml", ".txt", ".json", ".tsv", ".py"}


def files(path):
    if os.path.isfile(path):
        yield path
        return
    for root, _, names in os.walk(path):
        for n in names:
            if os.path.splitext(n)[1].lower() in TEXT_EXT:
                yield os.path.join(root, n)


def scan(path):
    hits = []
    for f in files(path):
        try:
            with open(f, encoding="utf-8", errors="ignore") as fh:
                for i, line in enumerate(fh, 1):
                    for cls, rx in RULES.items():
                        if rx.search(line):
                            hits.append({"file": f, "line": i, "class": cls})
        except OSError as e:
            hits.append({"file": f, "line": 0, "class": "unreadable:" + e.__class__.__name__})
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", action="append", required=True)
    a = ap.parse_args()
    hits = [h for p in a.path if os.path.exists(p) for h in scan(p)]
    missing = [p for p in a.path if not os.path.exists(p)]
    if hits:
        res = {"id": "MIG-pii", "status": "FAIL", "msg": f"збігів {len(hits)} (значення не показано)", "hits": hits[:50]}
    elif missing:
        res = {"id": "MIG-pii", "status": "SKIP", "msg": "немає шляхів: " + ", ".join(missing)}
    else:
        res = {"id": "MIG-pii", "status": "PASS", "msg": "збігів немає"}
    print(json.dumps([res], ensure_ascii=False))
    sys.exit(1 if res["status"] == "FAIL" else 0)


if __name__ == "__main__":
    main()
