#!/usr/bin/env python3
"""Автоперевірка B-02 (package-fit-gap). Запуск: python3 -I check_fit_gap.py --client <к> --tag package/vX.Y
[--base <sha>] [--repo .] [--forbidden <файл>] [--business-case <шлях>]. Лише stdlib. Вихід: JSON [{id,status,msg}], код 1 при FAIL.
Значення збігів PII у вихід не пишуться (тип:файл:рядок). Перевірки, які неможливо автоматизувати, = MANUAL."""
import argparse, json, re, subprocess, sys

HEAD = ["Джерела", "Вимоги", "Суперечності й відкриті питання", "Рішення з сесій",
        "Запити в D-02", "Відповідність пакету", "Факти для пілоту"]
CLASSES = {"з пакета", "доналаштування", "доробка"}
PII = {  # дзеркало flow-core/references/pii-patterns.md (strict)
    "email": r"[\w.+-]+@[\w-]+\.[\w.-]+",
    "phone": r"(?<![\w:])(\+?380\d{9}|0\d{9})(?!\w)",
    "iban": r"\bUA\d{2}[\s\d]{20,}",
    "edrpou": r"ЄДРПОУ\D{0,5}\d{8}\b",
    "ipn": r"(?i)\bІПН\D{0,5}\d{10}\b",
    "fio": r"\b[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\b",
    "secret": r"(?i)(password|passwd|pwd|api[_-]?key|token|secret)\s*[:=]\s*\S+",
}
SRC = re.compile(r"^(fathom:[\w-]+@\d{1,2}:\d{2}:\d{2}|анкета:(VP-\d+|р\.\d+))$")


def sh(args, cwd):
    if args and args[0] == "git":  # кириличні шляхи без octal-екранування
        args = ["git", "-c", "core.quotePath=false"] + args[1:]
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    return r.returncode, r.stdout


def show(repo, ref, path):
    rc, out = sh(["git", "show", f"{ref}:{path}"], repo)
    return out if rc == 0 else None


def section(text, name):
    m = re.search(rf"^##\s+{re.escape(name)}\s*$(.*?)(?=^##\s|\Z)", text, re.M | re.S)
    return m.group(1) if m else None


def table(sec):
    rows = [l.strip() for l in sec.splitlines() if l.strip().startswith("|")]
    if len(rows) < 2:
        return [], []
    cells = lambda l: [c.strip() for c in l.strip("|").split("|")]
    hdr = cells(rows[0])
    return hdr, [cells(r) for r in rows[2:]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--client", required=True)
    ap.add_argument("--tag", required=True)
    ap.add_argument("--base", required=True, help="git.base з наряду (SHA)")
    ap.add_argument("--business-case", help="шлях до business-case.md (від кореня репо) для FG-threshold")
    ap.add_argument("--repo", default=".")
    ap.add_argument("--forbidden", help="файл зі забороненими рядками (назва юрособи, ЄДРПОУ), по одному в рядку")
    a = ap.parse_args()
    res = []
    add = lambda i, s, m="": res.append({"id": i, "status": s, "msg": m})
    base = f"clients/{a.client}"
    files = {n: open(f"{a.repo}/{base}/{n}", encoding="utf-8").read() if __import__("os").path.exists(f"{a.repo}/{base}/{n}") else None
             for n in ("fit-gap.md", "questionnaire.md", "answers.yaml")}
    fg = files["fit-gap.md"] or ""
    # FG-headings
    miss = [h for h in HEAD if section(fg, h) is None]
    add("FG-headings", "FAIL" if miss else "PASS", "немає: " + ", ".join(miss) if miss else "")
    # FG-agreement
    ag = open(f"{a.repo}/{base}/discovery-agreement.md", encoding="utf-8").read() if __import__("os").path.exists(f"{a.repo}/{base}/discovery-agreement.md") else None
    if ag is None:
        add("FG-agreement", "FAIL", "угоди немає")
    else:
        sig = re.findall(r"(?im)^\s*підпис[^\n]*?\b(20\d{2}-\d{2}-\d{2}|\d{2}\.\d{2}\.20\d{2})", ag)
        add("FG-agreement", "FAIL" if len(sig) < 2 else "MANUAL",
            "менше двох позначок підпису з датами" if len(sig) < 2 else "дві позначки з датами є; стадія угоди в CRM (q10, ключ наряду preconditions_confirmed.crm_deal_stage) і пункт про AI — вручну за references/agreement-check.md")
    # таблиця Вимоги
    hdr, rows = table(section(fg, "Вимоги") or "")
    col = lambda n: next((i for i, h in enumerate(hdr) if h.lower().startswith(n)), None)
    ic, ih, ip, is_, iw = col("рішення"), col("год"), col("місце"), col("джерело"), col("хто")
    reqs = [r for r in rows if r and r[0].startswith("FG-") and not any("знято" in c.lower() for c in r)]
    bad = []
    for r in reqs:
        v = r[ic].lower() if ic is not None and ic < len(r) else ""
        if v not in CLASSES:
            bad.append(r[0])
    add("FG-class", "FAIL" if bad or not reqs else "PASS", ("рядки: " + ", ".join(bad)) if bad else ("немає вимог" if not reqs else ""))
    bad = []
    for r in reqs:
        cls = r[ic].lower() if ic is not None else ""
        h = r[ih].replace("–", "-").replace("—", "-") if ih is not None and ih < len(r) else ""
        m = re.fullmatch(r"(\d+(?:[.,]\d+)?)(?:-(\d+(?:[.,]\d+)?))?", h.strip())
        if not m:
            bad.append(r[0]); continue
        lo = float(m.group(1).replace(",", ".")); hi = float((m.group(2) or m.group(1)).replace(",", "."))
        if lo > hi or (cls != "з пакета" and lo <= 0):
            bad.append(r[0])
        if iw is not None and cls != "з пакета" and "AI-чернетка" not in r[iw] and "BA" not in r[iw]:
            bad.append(r[0])
    add("FG-hours", "FAIL" if bad else "PASS", ("рядки: " + ", ".join(sorted(set(bad)))) if bad else "")
    # карта пакета на тегу
    rc, ls = sh(["git", "ls-tree", "-r", "--name-only", a.tag, "--", "package/"], a.repo)
    pkg = {}
    for p in ("package/templates/answers.yaml", "package/ALLOCATION.md", "package/config/CONFIG.md", "package/demo/scenarios.md"):
        pkg[p] = show(a.repo, a.tag, p) or ""
    if rc != 0:
        add("FG-anchor", "FAIL", f"тег {a.tag} не читається")
    else:
        schema = pkg["package/templates/answers.yaml"]
        vps = set(re.findall(r"\bVP-\d+\b", schema)); mods = set(re.findall(r"\btd_\w+", pkg["package/ALLOCATION.md"]))
        sc = set(re.findall(r"\bS-\d+\b", pkg["package/demo/scenarios.md"]))
        heads = [h.strip().lower() for h in re.findall(r"^#{2,}\s+(.+)$", pkg["package/config/CONFIG.md"], re.M)]  # H1 не якір
        bad = []
        for r in reqs:
            place = r[ip].strip() if ip is not None and ip < len(r) else ""
            cls = r[ic].lower() if ic is not None else ""
            if place.lower() == "немає в пакеті":
                if cls == "з пакета": bad.append(r[0])
                continue
            toks = re.findall(r"VP-\d+|td_\w+|S-\d+", place)
            cm = re.search(r"CONFIG\.md\s*§\s*(.+)", place)
            tok_ok = all(t in vps | mods | sc for t in toks)
            if cm:
                title = re.split(r"[;,]|\s+(?=VP-|td_|S-)", cm.group(1))[0].strip(" «»\"'`").lower()
                ok = title in heads and tok_ok
            else:
                ok = bool(toks) and tok_ok
            if not ok: bad.append(r[0])
        add("FG-anchor", "FAIL" if bad else "PASS", ("якір не знайдено на тегу: " + ", ".join(bad)) if bad else "")
    # FG-source
    srcs = section(fg, "Джерела") or ""
    ids = set(re.findall(r"fathom:([\w-]+)", srcs)); bad = []
    for r in reqs:
        parts = [p.strip() for p in (r[is_] if is_ is not None and is_ < len(r) else "").split(";") if p.strip()]
        for p in parts:
            m = SRC.match(p)
            if not m or (p.startswith("fathom:") and p[7:].split("@")[0] not in ids):
                bad.append(r[0])
        if not parts: bad.append(r[0])
    add("FG-source", "FAIL" if bad else "PASS", ("рядки: " + ", ".join(sorted(set(bad)))) if bad else "")
    add("FG-coverage", "MANUAL", "N/N оброблених частин у «Джерела»; Q-N з тегом вимоги — вручну")
    # FG-schema
    ans = files["answers.yaml"]
    if ans is None or rc != 0:
        add("FG-schema", "FAIL", "answers.yaml або тег відсутні")
    else:
        schema = pkg["package/templates/answers.yaml"]
        want = set(); allowed = {}
        for l in schema.splitlines():
            m = re.match(r"^(VP-\d+)\s*:", l)
            if m and "deprecated" not in l.lower():
                want.add(m.group(1))
                am = re.search(r"(?:allowed|допустим\w*)\s*:\s*([^#]+?)\s*$", l, re.I)
                if am: allowed[m.group(1)] = {x.strip().lower() for x in re.split(r"[|,/]", am.group(1)) if x.strip()}
        got = {}
        for l in ans.splitlines():
            m = re.match(r"^(VP-\d+)\s*:\s*([^#]*?)\s*(#.*)?$", l)
            if m: got[m.group(1)] = m.group(2).strip().strip("'\"")
        errs = [f"немає {k}" for k in sorted(want - set(got))] + [f"зайвий {k}" for k in sorted(set(got) - want)]
        errs += [f"{k}: порожньо" for k, v in got.items() if not v]
        errs += [f"{k}: значення поза схемою" for k, v in got.items() if k in allowed and v and v.lower() != "уточнити" and v.lower() not in allowed[k]]
        add("FG-schema", "FAIL" if errs else ("PASS" if allowed else "MANUAL"),
            "; ".join(errs) if errs else ("" if allowed else "ключі збігаються; допустимі значення схеми не розпізнано — звірити вручну"))
    # FG-d02
    d02 = section(fg, "Запити в D-02") or ""
    h2, r2 = table(d02)
    prev = show(a.repo, a.base, f"{base}/fit-gap.md")
    msg = []
    if r2 and h2:
        last = len(h2) - 1
        old = {}
        if prev:
            ph, pr = table(section(prev, "Запити в D-02") or "")
            old = {r[0]: r[-1] for r in pr if r}
        for r in r2:
            if r and r[0] in old and old[r[0]] != r[-1]: msg.append(f"{r[0]}: колонку D-02 змінено")
            if r and r[0] not in old and r[-1].strip(): msg.append(f"{r[0]}: колонка D-02 не порожня")
    if not msg:
        yv = [l for l in (files["answers.yaml"] or "").splitlines() if re.search(r"уточнити", l, re.I) and "дефект" in l.lower()]
        if yv and len(r2) < len(yv):
            msg.append(f"«уточнити» з коментарем «дефект»: {len(yv)}, рядків у «Запити в D-02»: {len(r2)}")
    add("FG-d02", "FAIL" if msg else "MANUAL", "; ".join(msg) if msg else "зіставлення «уточнити» без коментаря «дефект» з FG-D02 — вручну")
    # FG-threshold
    cnt = {c: sum(1 for r in reqs if r[ic].lower() == c) for c in CLASSES} if ic is not None else {}
    sec_m = section(fg, "Відповідність пакету") or ""
    sm = re.search(r"(?i)SHA[:\s]*([0-9a-f]{7,40})", sec_m)
    if not sm:
        add("FG-threshold", "FAIL", "немає SHA business-case")
    elif not a.business_case:
        add("FG-threshold", "MANUAL", f"SHA є; --business-case не задано; перерахунок: {cnt}")
    else:
        rcb, sha = sh(["git", "log", "-1", "--format=%H", "--", a.business_case], a.repo)
        sha = sha.strip()
        bc = ""
        try: bc = open(f"{a.repo}/{a.business_case}", encoding="utf-8").read()
        except OSError: pass
        thr = re.findall(r"\d+(?:[.,]\d+)?\s*%", section(bc, "Поріг відповідності пакету") or "")
        errs = []
        if not sha or not sha.startswith(sm.group(1).lower()): errs.append("SHA не збігається з git log business-case")
        if not thr: errs.append("у business-case немає числа порогу")
        elif not any(t.replace(" ", "") in sec_m.replace(" ", "") for t in thr): errs.append("число порогу з business-case не знайдено в розділі")
        add("FG-threshold", "FAIL" if errs else "MANUAL", "; ".join(errs) if errs else f"SHA і поріг збігаються; частки з таблиці ({cnt}) — звірити вручну")
    # FG-pii
    forb = []
    if a.forbidden:
        forb = [l.strip() for l in open(a.forbidden, encoding="utf-8") if l.strip()]
    hits = []
    for n, t in files.items():
        for i, l in enumerate((t or "").splitlines(), 1):
            for k, p in PII.items():
                if re.search(p, l): hits.append(f"{k}:{n}:{i}")
            if any(f.lower() in l.lower() for f in forb): hits.append(f"forbidden:{n}:{i}")
    add("FG-pii", "FAIL" if hits else "PASS", ", ".join(hits[:20]))
    # FG-ignore: _input поза git
    rc2, _ = sh(["git", "check-ignore", "-q", f"{base}/_input/x"], a.repo)
    import os
    if os.path.isdir(f"{a.repo}/{base}/_input"):
        add("FG-ignore", "FAIL", "_input/ існує — видалити перед здачею")
    else:
        add("FG-ignore", "PASS" if rc2 == 0 else "FAIL", "" if rc2 == 0 else f"{base}/_input/ не в .gitignore")
    # FG-scope
    rc3, out = sh(["git", "status", "--porcelain", "--untracked-files=all"], a.repo)
    rc4, d = sh(["git", "diff", "--name-only", f"{a.base}..HEAD", "--", "."], a.repo)
    if rc4 != 0:
        add("FG-scope", "FAIL", f"base {a.base} не читається")
        print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    changed = set()
    for l in out.splitlines():
        for x in l[3:].split(" -> "):  # перейменування «R old -> new»
            changed.add(x.strip().strip('"'))
    changed |= {l.strip() for l in d.splitlines()}
    ok = {f"{base}/{n}" for n in ("fit-gap.md", "questionnaire.md", "answers.yaml")} | {f"{base}/sales/{n}" for n in (f"журнал_продажу_{a.client}.md", f"повнота_даних_{a.client}.md")}
    extra = sorted(changed - ok)
    add("FG-scope", "FAIL" if extra else "PASS", ("зайве: " + ", ".join(extra[:10])) if extra else "")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)


main()
