#!/usr/bin/env python3
"""Автоперевірки D-02 (BT-*). Лише stdlib. Вихід — JSON `checks` для звіту, код виходу 1 при FAIL.

backlog_check.py --phase draft|post-sign --backlog package/backlog.md [--base old_backlog.md]
                 [--sources extracted.json] [--mode a|b|c|d --trigger-ref <шлях>] [--rerun]
                 [--src-old DIR --src-new DIR]
backlog_check.py --selftest
  --sources     вихід extract_d02.py (обов'язкові джерела режиму; воронка допускається): BT-coverage, BT-id-format, BT-refusals
  --rerun       повторний запуск на тих самих входах: множина REQ має дорівнювати base (BT-rerun)
  --mode/--trigger-ref  режими б/в/г: нові REQ лише з файлу trigger_ref (BT-mode-scope)
  --src-old/--src-new  (post-sign) каталоги з файлами-джерелами до/після з однаковими відносними шляхами (BT-src-diff)
  --selftest    прогін на еталоні references/backlog-format.md і на фікстурах src-diff
ПІІ: шаблони з flow-core/references/pii-patterns.md (змінювати разом); перевіряються лише клітинки описових колонок.
"""
import argparse, json, os, re, sys, tempfile

HEADERS = ["Заголовний блок", "Запити", "Групи", "Причини відмов (агреговано)", "Без ID джерела",
           "Відкинуто", "Рішення Власника продукту", "Журнал запусків"]
REQ_RE = re.compile(r"^REQ-([A-D]\d{2}[a-d]?)-([a-z0-9_]+)-([A-Za-z0-9][A-Za-z0-9-]*)$")
DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
SHA_RE = re.compile(r"@[0-9a-fA-F]{7,40}\b")
TEXT_COLS = ("опис", "зміст", "аргумент", "переказ", "що перевірити", "обґрунтування", "примітка", "що виправити")
RECO_COLS = ("рекомендація", "аргумент")
PHONE_CAND = re.compile(r"\+?\d[\d\s()-]{8,}\d")
PHONE_OK = re.compile(r"^(\+?380\d{9}|0\d{9})$")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
EDRPOU = re.compile(r"(?:ЄДРПОУ\D{0,5}\d{8}\b)|\bUA\d{2}[\s\d]{20,}")
BARE8 = re.compile(r"(?<![\w.-])\d{8}(?![\w-])")
SECRET = re.compile(r"(password|passwd|pwd|api[_-]?key|token|secret)\s*[:=]\s*\S+", re.I)
FIO3 = re.compile(r"\b[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\b")
FIO_PAT = re.compile(r"\b[А-ЯІЇЄҐ][а-яіїєґ'’]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’]+(?:ович|евич|івич|йович|івна|ївна|евна)\b")
THRESH = re.compile(r"поріг|≥\s*\d+\s*клієнт|\d+\s*бал|балів|автоматично\s+у\s+продукт|N\s*клієнт\w*\s*->\s*у продукт", re.I)


def sections(text):
    out, cur = {}, None
    for line in text.splitlines():
        if line.startswith("## "):
            cur = line[3:].strip(); out[cur] = []
        elif cur is not None:
            out[cur].append(line)
    return out


def split_cells(l):
    return [x.strip() for x in l.strip().strip("|").split("|")]


def table(lines):
    rows, header = [], None
    for l in lines:
        if not l.lstrip().startswith("|"):
            continue
        c = split_cells(l)
        if all(re.fullmatch(r":?-{2,}:?", x) for x in c if x):
            continue
        if header is None:
            header = c
        else:
            rows.append(dict(zip(header, c)))
    return rows


def col(row, key):
    k = key.lower()
    return next((v for h, v in row.items() if h.lower().startswith(k)), None) or \
        next((v for h, v in row.items() if k in h.lower()), "")


def clean(s):
    return SHA_RE.sub("", DATE_RE.sub(" ", s))


def pii_scan(sec):
    """Лише клітинки описових колонок таблиць + абзаци поза таблицями; повертає (fail, manual) як 'тип:розділ:рядок'."""
    fail, manual = [], []
    for name, lines in sec.items():
        hdr = None
        for n, l in enumerate(lines, 1):
            if l.lstrip().startswith("|"):
                c = split_cells(l)
                if all(re.fullmatch(r":?-{2,}:?", x) for x in c if x):
                    continue
                if hdr is None:
                    hdr = c
                    continue
                cells = [v for h, v in zip(hdr, c) if any(t in h.lower() for t in TEXT_COLS)]
            else:
                hdr = None
                cells = [l] if not l.startswith("```") else []
            for cell in cells:
                t = clean(cell)
                where = f"{name}:{n}"
                if EMAIL.search(cell): fail.append(f"email:{where}")
                if SECRET.search(cell): fail.append(f"secret:{where}")
                if EDRPOU.search(t) or BARE8.search(t): fail.append(f"edrpou/iban:{where}")
                if FIO_PAT.search(t): fail.append(f"піб:{where}")
                elif FIO3.search(t): manual.append(f"піб?:{where}")
                for m in PHONE_CAND.finditer(t):
                    if PHONE_OK.match(re.sub(r"[\s()-]", "", m.group(0))):
                        fail.append(f"phone:{where}")
    return sorted(set(fail)), sorted(set(manual))


def signature(sec):
    s = "\n".join(sec.get("Рішення Власника продукту", []))
    name = re.search(r"Ім'я:\s*([^\s_][^\n]*?)(?:\s{2,}|\s+Роль:|$)", s)
    date = re.search(r"Дата:\s*(\d{4}-\d{2}-\d{2})", s)
    return (name.group(1) if name else None), (date.group(1) if date else None)


def rejected_check(a, req, sec=None):
    """BT-rejected: реєстр відкинутого — розділ `## Відкинуто` у самому беклозі (узгоджено з D-02.yaml); кожне «відхилити» має
    рядок `REJ-NNN` з посиланням на REQ; формат і do_not_reject перевіряє flow-core check_rejected.py над беклогом (--intake)."""
    import subprocess
    rej = [r.get("ID запиту", "") for r in req if "відхил" in (col(r, "Рішення") + col(r, "Рекомендація")).lower()]
    if not rej:
        return {"id": "BT-rejected", "status": "SKIP", "msg": "рішень/рекомендацій «відхилити» немає"}
    reg_txt = "\n".join((sec or {}).get("Відкинуто", []))
    miss = [i for i in rej if i and not re.search(r"(?<![A-Za-z0-9-])" + re.escape(i) + r"(?![A-Za-z0-9-])", reg_txt)]
    scr = getattr(a, "check_rejected", None) or os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "..", "flow-core", "skills", "flow-autocheck", "scripts", "check_rejected.py"))
    if not os.path.exists(scr):
        return {"id": "BT-rejected", "status": "SKIP", "msg": "check_rejected.py не знайдено (--check-rejected); формат реєстру не перевірено"}
    cmd = [sys.executable, "-I", scr, a.backlog]
    if getattr(a, "intake", None):
        cmd += ["--intake", a.intake]
    p = subprocess.run(cmd, capture_output=True, text=True)
    try:
        bad = [f"{c['id']}: {c.get('msg', '')}" for c in json.loads(p.stdout) if c["status"] == "FAIL"]
    except ValueError:
        bad = ["вивід check_rejected.py не JSON"]
    if miss:
        bad.append("REQ без посилання в розділі «Відкинуто»: " + ", ".join(miss))
    return {"id": "BT-rejected", "status": "FAIL" if bad else "PASS", **({"msg": "; ".join(bad)} if bad else {})}


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
    data = []
    if a.sources:
        data = json.load(open(a.sources, encoding="utf-8"))["sources"]
        d02 = [s for s in data if not s["section"].startswith("причини відмов")]
        src_ids = {(s["client"], r["id"]) for s in d02 for r in s["rows"] if r["id"]}
        for i in ids:
            m = REQ_RE.match(i)
            if m and (m.group(2), m.group(3)) not in src_ids:
                bad.append(i + " (ID не знайдено в джерелі)")
    add("BT-id-format", not bad, "; ".join(bad))
    base_rows, base_sec = [], {}
    if a.base and os.path.exists(a.base):
        base_sec = sections(open(a.base, encoding="utf-8").read())
        base_rows = table(base_sec.get("Запити", []))
    base_map = {r.get("ID запиту"): r for r in base_rows}
    if base_rows:
        lost = sorted(set(base_map) - set(ids))
        extra = sorted(set(ids) - set(base_map)) if a.rerun else []
        add("BT-rerun", not lost and not extra,
            "зникли REQ з попереднього: " + ", ".join(lost) + ("; зайві при повторі: " + ", ".join(extra) if extra else ""))
    if a.mode in ("b", "c", "d") and a.trigger_ref:
        out = [r.get("ID запиту") for r in req if r.get("ID запиту") not in base_map
               and a.trigger_ref not in col(r, "Крок і файл")]
        add("BT-mode-scope", not out, "нові REQ не з trigger_ref: " + ", ".join(map(str, out)))
    jr = "\n".join(sec.get("Журнал запусків", []))
    drafts = [c for c in (split_cells(l) for l in sec.get("Журнал запусків", []) if l.lstrip().startswith("|"))
              if len(c) > 2 and "draft" in c[2].lower() and DATE_RE.fullmatch(c[0])]
    if a.phase == "draft":
        viol = []
        for r in req:
            old = base_map.get(r.get("ID запиту"))
            for k in ("Рішення", "Версія", "Обґрунтування"):
                v = col(r, k)
                if (old is None and v) or (old is not None and v != col(old, k)):
                    viol.append(f"{r.get('ID запиту')}: {k}")
        nm, dt = signature(sec)
        if nm or dt:
            viol.append("підпис заповнено (попередній підпис переноситься в «Журнал запусків», блок порожній)")
        if base_sec:
            bn, bd = signature(base_sec)
            if bd and bd not in jr:
                viol.append(f"підпис попереднього циклу {bd} не перенесено в «Журнал запусків»")
        add("BT-draft-only", not viol, "; ".join(viol))
        rb = []
        for row in table(sec.get("Групи", [])):
            if "у продукт" in col(row, "Рекомендація").lower():
                arg = col(row, "Аргумент") + " " + col(row, "Використання")
                if not re.search(r"метрик немає|жива|не жива", arg, re.I) or not re.search(r"\d", col(row, "Клієнтів") + col(row, "Лідів")):
                    rb.append(row.get("GRP", "?"))
        reco_cells = [v for rows in (req, table(sec.get("Групи", []))) for r in rows for h, v in r.items()
                      if any(h.lower().startswith(t) for t in RECO_COLS)]
        if any(THRESH.search(v) for v in reco_cells):
            rb.append("є числовий поріг/бали")
        add("BT-reco", not rb, "; ".join(map(str, rb)))
        if a.sources:
            noid = "\n".join(sec.get("Без ID джерела", []))
            lost = []
            for s in data:
                if s["section"].startswith("причини відмов"):
                    continue
                if not s["section_found"]:
                    lost.append(f"{s['path']}: розділ не знайдено")
                for r in s["rows"]:
                    if not r["relevant"]:
                        continue
                    if r["id"]:
                        if not any(i.endswith(f"-{s['client']}-{r['id']}") for i in ids):
                            lost.append(f"{s['path']}:{r['id']}")
                    elif s["path"] not in noid:
                        lost.append(f"{s['path']}: рядок без ID")
            add("BT-coverage", not lost, "загублено: " + "; ".join(lost))
            ref = []
            noid_ok = sec.get("Без ID джерела", [])
            for s in data:
                if not s["section"].startswith("причини відмов"):
                    continue
                for r in s["rows"]:
                    if "немає функції" not in r.get("type", ""):
                        continue
                    if r["id"]:
                        in_noid = any(s["path"] in ln and re.search(rf"(?<![\w-]){re.escape(r['id'])}(?![\w-])", ln) for ln in noid_ok)
                        if not in_noid and not any(re.search(rf"-[a-z0-9_]+-{re.escape(r['id'])}$", i) for i in ids):
                            ref.append(f"{s['path']}:{r['id']}")
                    elif not any(s["path"] in ln for ln in noid_ok):
                        ref.append(f"{s['path']}: «немає функції» без посилання")
            add("BT-refusals", not ref, "немає REQ або запису в «Без ID джерела»: " + "; ".join(ref))
    lead = [r.get("ID запиту") for r in req if "(лід)" in col(r, "Клієнт") and
            ("у кастом" in col(r, "Рішення").lower() or "у кастом" in col(r, "Рекомендація").lower())]
    add("BT-lead", not lead, "лід з «у кастом»: " + ", ".join(map(str, lead)))
    fail, manual = pii_scan(sec)
    res.append({"id": "BT-pii", "status": "FAIL" if fail else ("MANUAL" if manual else "PASS"),
                **({"msg": "; ".join(fail + manual)} if fail or manual else {})})
    if a.phase == "post-sign":
        errs = []
        nm, dt = signature(sec)
        if not (nm and dt):
            errs.append("підпис не заповнено")
        elif drafts and dt < max(c[0] for c in drafts):
            errs.append(f"підпис {dt} старіший за останній draft {max(c[0] for c in drafts)}")
        for r in req:
            if "рознесено" in col(r, "Статус").lower():
                continue
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
    res.append(rejected_check(a, req, sec))
    return res


def walk(d):
    return {os.path.relpath(os.path.join(r, f), d) for r, _, fs in os.walk(d) for f in fs}


def src_diff(old, new):
    bad = []
    for rel in sorted(walk(old) - walk(new)):
        bad.append(rel + ": файл видалено")
    for rel in sorted(walk(new)):
        po, pn = os.path.join(old, rel), os.path.join(new, rel)
        if not os.path.exists(po):
            bad.append(rel + ": файл новий"); continue
        lo = open(po, encoding="utf-8").read().splitlines()
        ln = open(pn, encoding="utf-8").read().splitlines()
        if len(lo) != len(ln):
            bad.append(rel + ": змінено кількість рядків"); continue
        in_sec, hdr = False, None
        for x, y in zip(lo, ln):
            if x.startswith("## "):
                in_sec, hdr = x[3:].strip().lower().startswith("запити в d-02"), None
            if in_sec and x.startswith("|") and hdr is None:
                hdr = split_cells(x)
            if x == y:
                continue
            if not (in_sec and hdr and x.startswith("|") and y.startswith("|")):
                bad.append(f"{rel}: зміна поза розділом «Запити в D-02» або не в рядку таблиці"); break
            cx, cy = split_cells(x), split_cells(y)
            if len(cx) != len(cy):
                bad.append(f"{rel}: змінено кількість колонок"); break
            diff = [i for i in range(len(cx)) if cx[i] != cy[i]]
            if not all(i < len(hdr) and "рішення d-02" in hdr[i].lower() for i in diff):
                bad.append(f"{rel}: змінено не колонку «рішення D-02»"); break
    return not bad, "; ".join(bad)


def selftest():
    here = os.path.dirname(os.path.abspath(__file__))
    fmt = open(os.path.join(here, "..", "references", "backlog-format.md"), encoding="utf-8").read()
    ref = re.search(r"```markdown\n(.*?)\n```", fmt, re.S).group(1)
    ref = ref.replace("<YYYY-MM-DD>", "2026-11-09")
    ref = ref.replace("| Дата | Режим | Фаза | N одиниць | SHA входів |\n|---|---|---|---|---|",
                      "| Дата | Режим | Фаза | N одиниць | SHA входів |\n|---|---|---|---|---|\n| 2026-11-09 | а | draft | 3 | a1b2c3d, 20261109 |")
    fails = []
    with tempfile.TemporaryDirectory() as d:
        def check(name, content, expect, phase="draft", sources=None, **kw):
            p = os.path.join(d, "b.md"); open(p, "w", encoding="utf-8").write(content)
            ns = argparse.Namespace(phase=phase, backlog=p, base=None, sources=sources, mode=None, trigger_ref=None,
                                    rerun=False, src_old=None, src_new=None, **kw)
            got = {c["id"]: c["status"] for c in run(ns)}
            for k, v in expect.items():
                if got.get(k) != v:
                    fails.append(f"{name}: {k} очікувалось {v}, є {got.get(k)}")
        check("etalon+dates", ref, {"BT-headers": "PASS", "BT-pii": "PASS", "BT-draft-only": "PASS", "BT-reco": "PASS",
                                    "BT-id-format": "PASS", "BT-lead": "PASS"})
        check("phone", ref.replace("Колір кромки", "Тел. +380 50 111 22 33 колір кромки"), {"BT-pii": "FAIL"})
        check("threshold", ref.replace("<3-5 рядків за recommendation-guide.md>", "поріг 3 клієнти"), {"BT-reco": "FAIL"})
        # воронка посилається на ID, якого немає в журналі продажу -> «Без ID джерела», REQ не потрібен
        srcs = os.path.join(d, "s.json")
        json.dump({"sources": [{"step": "B-01", "client": "", "path": "funnel-2026-10.md", "sha": "a1b2c3d",
                                "section": "причини відмов", "section_found": True, "table_found": True, "type_column": True,
                                "rows": [{"id": "SAL-D02-02", "type": "немає функції", "relevant": True, "cells": {}}]}]},
                  open(srcs, "w", encoding="utf-8"))
        noid = ref.replace("## Без ID джерела\n", "## Без ID джерела\n\nfunnel-2026-10.md SAL-D02-02 (власник B-01)\n", 1)
        check("funnel-noid", noid, {"BT-refusals": "PASS"}, sources=srcs)
        check("funnel-lost", ref, {"BT-refusals": "FAIL"}, sources=srcs)
        # src-diff
        o, n = os.path.join(d, "o"), os.path.join(d, "n")
        for t in (o, n):
            os.makedirs(os.path.join(t, "c"))
        base = "## Інше\n| a | b |\n|---|---|\n| 1 | 2 |\n\n## Запити в D-02\n| ID | Тип | рішення D-02 і версія пакета |\n|---|---|---|\n| INC-1 | нова вимога | |\n"
        open(os.path.join(o, "c/h.md"), "w").write(base)
        open(os.path.join(n, "c/h.md"), "w").write(base.replace("нова вимога | |", "нова вимога | у продукт (версія 1.2) |"))
        if not src_diff(o, n)[0]: fails.append("src-diff: законна зміна дала FAIL")
        open(os.path.join(n, "c/h.md"), "w").write(base.replace("| 1 | 2 |", "| 1 | 3 |"))
        if src_diff(o, n)[0]: fails.append("src-diff: зміна поза розділом пройшла")
        open(os.path.join(n, "c/h.md"), "w").write(base.replace("INC-1 | нова", "INC-2 | нова"))
        if src_diff(o, n)[0]: fails.append("src-diff: зміна ID пройшла")
        os.remove(os.path.join(n, "c/h.md"))
        if src_diff(o, n)[0]: fails.append("src-diff: видалений файл пройшов")
    print(json.dumps({"selftest": "FAIL" if fails else "PASS", "fails": fails}, ensure_ascii=False, indent=1))
    return 1 if fails else 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--selftest", action="store_true")
    p.add_argument("--phase", choices=["draft", "post-sign"])
    p.add_argument("--backlog")
    p.add_argument("--base"); p.add_argument("--sources"); p.add_argument("--src-old"); p.add_argument("--src-new")
    p.add_argument("--intake"); p.add_argument("--check-rejected"); p.add_argument("--mode", choices=["a", "b", "c", "d"]); p.add_argument("--trigger-ref"); p.add_argument("--rerun", action="store_true")
    ns = p.parse_args()
    if ns.selftest:
        sys.exit(selftest())
    if not (ns.phase and ns.backlog):
        p.error("--phase і --backlog обов'язкові")
    r = run(ns)
    print(json.dumps({"checks": r}, ensure_ascii=False, indent=1))
    sys.exit(1 if any(c["status"] == "FAIL" for c in r) else 0)
