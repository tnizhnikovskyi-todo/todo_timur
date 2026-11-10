#!/usr/bin/env python3
"""Пошук незамаскованих персональних даних у файлах/теках. Значень не друкує.
Запуск: python3 -I check_pii.py --path P [--path P2] [--extra-rules rules.json]
Правила (узгоджені з references/anonymization-check.md і flow-core/references/pii-patterns.md):
- CSV/TSV: колонки за заголовком (телефон/ІПН/ЄДРПОУ/рахунок/паспорт/ПІБ/контакт) мають містити ЛИШЕ маску
  (PHONE_MASKED_01, NAME_MASKED_01 …, sha1:<hex>); email/iban/passport/телефон — і в будь-якій клітинці.
- Інші файли (md/yaml/json/txt): телефон (+380…/0…), email, iban, паспорт; ІПН/ЄДРПОУ — лише поряд із ключовим словом.
- Числа з десятковою частиною (суми) і довгі кількості поза такими колонками не вважаються ПД.
--allow-columns: перелік колонок-кодів (артикул, штрихкод, кількість), де passport/phone-збіги ігноруються; BA фіксує його в плані.
--extra-rules: JSON {"<клас>": "<regex>"} — додаткові класи з DATA_POLICY, застосовуються до кожного рядка/клітинки."""
import argparse, csv, io, json, os, re, sys

PHONE = re.compile(r"(?<![\d.,])(?:\+?380|0)[\s()-]*\d{2}[\s()-]*\d{3}[\s()-]*\d{2}[\s()-]*\d{2}(?![\d]|[.,]\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
IBAN = re.compile(r"\bUA\d{2}[0-9A-Z]{25}\b")
PASSPORT = re.compile(r"\b[А-ЯІЇЄҐA-Z]{2}\s?\d{6}\b")
TAX_CTX = re.compile(r"(ІПН|РНОКПП|ЄДРПОУ|ІНН|VAT|рахун\w*|IBAN)\D{0,15}(?<![\d.,])\d{8,14}(?![\d]|[.,]\d)", re.I)
FOP = re.compile(r"ФОП\s+[А-ЯІЇЄҐ]")
PASSPORT_CTX = re.compile(r"паспорт\w*\D{0,15}[А-ЯІЇЄҐA-Z]{2}\s?\d{6}\b", re.I)
MASKED = re.compile(r"^(?:[A-Z]+_MASKED_\d+|sha1:[0-9a-f]{8,40})$")
COLS = [  # (клас, регексп заголовка)
    ("phone", re.compile(r"телефон|phone|\bтел\b|мобіл", re.I)),
    ("tax_id", re.compile(r"іпн|рнокпп|єдрпоу|\bінн\b|\bvat\b|edrpou", re.I)),
    ("iban", re.compile(r"рахун|iban", re.I)),
    ("passport", re.compile(r"паспорт|passport", re.I)),
    ("name", re.compile(r"піб|прізвищ|контакт|співробітник|full.?name", re.I)),
    ("email", re.compile(r"e-?mail|пошта", re.I)),
]
TEXT_EXT = {".csv", ".md", ".yaml", ".yml", ".txt", ".json", ".tsv"}


def files(path):
    if os.path.isfile(path):
        yield path
        return
    for root, _, names in os.walk(path):
        for n in sorted(names):
            if os.path.splitext(n)[1].lower() in TEXT_EXT:
                yield os.path.join(root, n)


def text_classes(s, extra, cell=False):
    # у клітинці CSV passport шукається лише в колонці «паспорт» (артикули виду AB123456 — не ПД); у тексті — біля ключового слова
    c = [k for k, rx in (("phone", PHONE), ("email", EMAIL), ("iban", IBAN), ("passport", PASSPORT_CTX), ("tax_id", TAX_CTX))
         if rx.search(s) and not (cell and k == "passport")]
    if cell and FOP.search(s):
        c.append("name")
    c += [k for k, rx in extra.items() if rx.search(s)]
    return c


def scan_csv(f, raw, extra, hits, allow=()):
    delim = "\t" if f.lower().endswith(".tsv") else (";" if raw.count(";") > raw.count(",") else ",")
    rows = list(csv.reader(io.StringIO(raw), delimiter=delim))
    if not rows:
        return
    head = rows[0]
    kinds = [[k for k, rx in COLS if rx.search(h)] for h in head]
    for ln, row in enumerate(rows[1:], 2):
        for i, v in enumerate(row):
            v = v.strip()
            if not v or MASKED.match(v):
                continue
            col = head[i] if i < len(head) else "?"
            cls = set(kinds[i]) if i < len(kinds) else set()
            cls |= set(text_classes(v, extra, cell=True)) - {"tax_id"}
            if col.strip().lower() in allow:
                cls -= {"phone", "passport"}
            for k in sorted(cls):
                hits.append({"file": f, "line": ln, "column": col, "class": k})


def scan(path, extra, allow=()):
    hits = []
    for f in files(path):
        try:
            raw = open(f, encoding="utf-8-sig", errors="ignore").read()
        except OSError as e:
            hits.append({"file": f, "line": 0, "class": "unreadable:" + e.__class__.__name__})
            continue
        if f.lower().endswith((".csv", ".tsv")):
            scan_csv(f, raw, extra, hits, allow)
        else:
            for i, line in enumerate(raw.splitlines(), 1):
                for k in text_classes(line, extra):
                    hits.append({"file": f, "line": i, "class": k})
    return hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", action="append", required=True)
    ap.add_argument("--allow-columns", help="колонки-коди через кому (ігнорують passport/phone)")
    ap.add_argument("--extra-rules", help="JSON {клас: regex} з DATA_POLICY")
    a = ap.parse_args()
    extra = {}
    if a.extra_rules:
        extra = {k: re.compile(v) for k, v in json.load(open(a.extra_rules, encoding="utf-8")).items()}
    allow = {c.strip().lower() for c in (a.allow_columns or "").split(",") if c.strip()}
    hits = [h for p in a.path if os.path.exists(p) for h in scan(p, extra, allow)]
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
