#!/usr/bin/env python3
"""Автоперевірки D-02 (BT-*). Лише stdlib. Вихід — JSON `checks` для звіту, код виходу 1 при FAIL.

backlog_check.py --phase draft|post-sign --backlog package/backlog.md [--base old_backlog.md]
                 [--sources extracted.json] [--src-old DIR --src-new DIR]
  --sources  вихід extract_d02.py обов'язкових джерел режиму (для BT-coverage, BT-id-format, BT-refusals)
  --src-old/--src-new  (post-sign) каталоги з файлами-джерелами до/після з однаковими відносними шляхами (BT-src-diff)
"""
import argparse, json, os, re, sys

HEADERS = ["Заголовний блок", "Запити", "Групи", "Причини відмов (агреговано)", "Без ID джерела",
           "Рішення Власника продукту", "Журнал запусків"]
REQ_RE = re.compile(r"^REQ-([A-Z]\d{2}[a-z]?)-([a-z0-9_]+)-([A-Z]{2,4}(?:-D02)?-\d+)$")
PII = [re.compile(p) for p in (r"[\w.+-]+@[\w-]+\.[\w.]+", r"\+?\d[\d\s()-]{8,}\d", r"\b\d{8}\b",
                               r"\b[А-ЯІЇЄҐ][а-яіїєґ']+\s+[А-ЯІЇЄҐ][а-яіїєґ']+(?:ович|івна|ович|евич|ївна|івич)\b")]
THRESH = re.compile(r"поріг|≥\s*\d+\s*клієнт|\d+\s*бал|балів|автоматично\s+у\s+продукт", re.I)


def sections(text):
    out, cur = {}, None
    for line in text.splitlines():
        if line.startswith("## "):
            cur = line[3:].strip(); out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return out


def table(lines):
    rows, header = [], None
    for l in lines:
        if not l.lstrip().startswith("|"):
            continue
        c = [x.strip() for x in l.strip().strip("|").split("|")]
        if all(re.fullmatch(r":?-{2,}:?", x) for x in c if x):
            continue
        if header is None:
            header = c
        else:
            rows.append(dict(zip(header, c)))
    return rows


def col(row, key):
    return next((v for k, v in row.items() if key.lower() in k.lower()), "")


def run(a):
    text = open(a.backlog, encoding="utf-8").read()
    sec = sections(text)
    req = table(sec.get("Запити", []))
    res = []

    def add(i, ok, msg=""):
        res.append({"id": i, "status": "PASS" if ok else "FAIL", **({"msg": msg} if msg and not ok else {})})

    miss = [h for h in HEADERS if h not in sec]
    add("BT-headers", not miss, "немає: " + ", ".join(miss))
    ids = [r.get("ID запиту", "") for r in req]
    dup = {i for i in ids if ids.count(i) > 1}
    add("BT-id-unique", not dup, "дублі: " + ", ".join(sorted(dup)))
    bad = [i for i in ids if not REQ_RE.match(i)]
    src_ids = set()
    if a.sources:
        data = json.load(open(a.sources, encoding="utf-8"))["sources"]
        src_ids = {(s["client"], r["id"]) for s in data for r in s["rows"] if r["id"]}
        for i in ids:
            m = REQ_RE.match(i)
            if m and (m.group(2), m.group(3)) not in src_ids:
                bad.append(i + " (ID не знайдено в джерелі)")
    add("BT-id-format", not bad, "; ".join(bad))
    if a.base and os.path.exists(a.base):
        base = table(sections(open(a.base, encoding="utf-8").read()).get("Запити", []))
        base_ids = {r.get("ID запиту") for r in base}
        # повторний запуск на тих самих входах не додає рядків: нові REQ мають бути відсутні в base
        add("BT-rerun", len(ids) == len(set(ids)) and base_ids <= set(ids),
            "у новому беклозі зникли REQ з попереднього: " + ", ".join(sorted(base_ids - set(ids))))
    decision_cols = ("Рішення", "Версія", "Обґрунтування")
    if a.phase == "draft":
        base_map = {}
        if a.base and os.path.exists(a.base):
            base_map = {r.get("ID запиту"): r for r in table(sections(open(a.base, encoding="utf-8").read()).get("Запити", []))}
        viol = []
        for r in req:
            old = base_map.get(r.get("ID запиту"))
            for k in decision_cols:
                v = col(r, k)
                if (old is None and v) or (old is not None and v != col(old, k)):
                    viol.append(f"{r.get('ID запиту')}: {k}")
        sign = "\n".join(sec.get("Рішення Власника продукту", []))
        if not base_map and re.search(r"Ім'я:\s*[^\s_]", sign):
            viol.append("підпис заповнено")
        add("BT-draft-only", not viol, "; ".join(viol))
        rb = []
        grp = {g.get("GRP"): g for g in table(sec.get("Групи", []))}
        for g, row in grp.items():
            if "у продукт" in col(row, "Рекомендація").lower():
                arg = col(row, "Аргумент") + " " + col(row, "Використання")
                if not re.search(r"метрик немає|жива|не жива", arg, re.I) or not re.search(r"\d", col(row, "Клієнтів") + col(row, "Лідів")):
                    rb.append(g)
        if THRESH.search(text):
            rb.append("є числовий поріг/бали")
        add("BT-reco", not rb, "; ".join(map(str, rb)))
        if a.sources:
            noid = "\n".join(sec.get("Без ID джерела", []))
            lost = []
            for s in data:
                for r in s["rows"]:
                    if not r["relevant"]:
                        continue
                    if r["id"]:
                        if not any(i.endswith(f"-{s['client']}-{r['id']}") for i in ids):
                            lost.append(f"{s['path']}:{r['id']}")
                    elif s["path"] not in noid:
                        lost.append(f"{s['path']}: рядок без ID")
            add("BT-coverage", not lost, "загублено: " + "; ".join(lost))
    lead = [r.get("ID запиту") for r in req if "(лід)" in col(r, "Клієнт") and
            ("у кастом" in col(r, "Рішення").lower() or "у кастом" in col(r, "Рекомендація").lower())]
    add("BT-lead", not lead, "лід з «у кастом»: " + ", ".join(map(str, lead)))
    pii = sorted({p.pattern[:20] for p in PII if p.search(text)})
    add("BT-pii", not pii, "знайдено шаблони ПІІ")
    if a.phase == "post-sign":
        sign = "\n".join(sec.get("Рішення Власника продукту", []))
        errs = []
        if not (re.search(r"Ім'я:\s*[^\s_]", sign) and re.search(r"Дата:\s*\d{4}-\d{2}-\d{2}", sign)):
            errs.append("підпис не заповнено")
        for r in req:
            d, i = col(r, "Рішення").lower(), r.get("ID запиту")
            if not d:
                errs.append(f"{i}: немає рішення")
            elif "у продукт" in d and not re.search(r"\d+\.\d+", col(r, "Версія") + d):
                errs.append(f"{i}: немає версії")
            elif "відхил" in d and not (col(r, "Обґрунтування") or re.search(r"\(.+\)", d)):
                errs.append(f"{i}: немає причини")
        add("BT-signed", not errs, "; ".join(errs))
        if a.src_old and a.src_new:
            add("BT-src-diff", *src_diff(a.src_old, a.src_new))
    return res


def src_diff(old, new):
    bad = []
    for root, _, files in os.walk(new):
        for f in files:
            pn = os.path.join(root, f)
            rel = os.path.relpath(pn, new)
            po = os.path.join(old, rel)
            if not os.path.exists(po):
                bad.append(rel + ": файл новий"); continue
            lo, ln = open(po, encoding="utf-8").read().splitlines(), open(pn, encoding="utf-8").read().splitlines()
            if len(lo) != len(ln):
                bad.append(rel + ": змінено кількість рядків"); continue
            hdr = None
            for x, y in zip(lo, ln):
                if x.startswith("|") and hdr is None:
                    hdr = [c.strip() for c in x.strip("|").split("|")]
                if x == y:
                    continue
                cx, cy = [c.strip() for c in x.strip("|").split("|")], [c.strip() for c in y.strip("|").split("|")]
                diff = [i for i in range(max(len(cx), len(cy))) if (cx[i:i+1] or [""]) != (cy[i:i+1] or [""])]
                ok = x.startswith("|") and len(cx) == len(cy) and hdr and all("рішення d-02" in hdr[i].lower() for i in diff if i < len(hdr))
                if not ok:
                    bad.append(f"{rel}: змінено не колонку рішення D-02")
                    break
    return not bad, "; ".join(bad)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--phase", choices=["draft", "post-sign"], required=True)
    p.add_argument("--backlog", required=True)
    p.add_argument("--base"); p.add_argument("--sources"); p.add_argument("--src-old"); p.add_argument("--src-new")
    r = run(p.parse_args())
    print(json.dumps({"checks": r}, ensure_ascii=False, indent=1))
    sys.exit(1 if any(c["status"] == "FAIL" for c in r) else 0)
