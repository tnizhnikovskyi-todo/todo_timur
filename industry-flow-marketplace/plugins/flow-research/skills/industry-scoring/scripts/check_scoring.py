#!/usr/bin/env python3
"""Автоперевірки A-01 (SC-*). stdlib. Вивід: JSON [{id,status,msg}]. Код виходу 1, якщо є FAIL.
Використання: check_scoring.py <scoring.md> [--param <файл з текстом параметра критерію>]
  [--metrics <json> | --metrics-csv <csv>] [--snapshot YYYY-MM] [--exclude 84,97,98,99] [--min-panel N]
--metrics: {"companies":{"31":120,...},"revenue":{...},"growth":{...},"panel":{...}} (значення з відповіді Q2, без округлення).
--metrics-csv: CSV з роздільником «;» і заголовком code;companies;revenue;growth[;panel] (growth — частка, r_last/r_base-1;
  panel — panel_n; колонку можна назвати panel або panel_n, код — code або sec). Його складає субагент із відповіді запиту (scoring-formula.md §3), вручну числа не переносять.
--min-panel: N для SC-panel (інакше N з тексту параметра: «мін. панель N», «мінімальна панель для growth = N», «min_panel=N»; інакше довідкове 30, лише WARN).
SC-coverage: коди «Повний рейтинг» ∪ виключені = коди references/kved-2010-sections.md; різниця в будь-який бік (відсутні й зайві коди) — WARN.
SC-panel: розділи топ-10 з панеллю зростання < N — WARN (бал не змінюється).
SC-order: MANUAL, якщо параметр задає дію (б) norm(growth)=0 чи (в) виключення для малої панелі; FAIL «CSV неповний», якщо в CSV немає кодів із «Повного рейтингу».
SC-repro виконується окремими запитами (MANUAL, фіксується в memo). Формат checks — flow-core/references/report-format.md."""
import argparse, csv, json, re, sys
from pathlib import Path

HEADERS = ["Знімок даних", "Критерій ранжування", "Топ-10", "Повний рейтинг", "Рішення на ринку: джерела",
           "Якість даних і обмеження", "SQL-запити", "Зміни відносно попереднього знімка"]
TAG = re.compile(r"^\s*-?[\d\s.,]+%?\s\[odb (\d{4})-(0[1-9]|1[0-2])\]\s*$")
PII_I = {"email", "secret"}  # з re.I лише ці; fio/edrpou/phone чутливі до регістру
PII = {"email": r"[\w.+-]+@[\w-]+\.[\w.-]+", "phone": r"(?<![\w:])(\+?380\d{9}|0\d{9})(?!\w)",
       "edrpou": r"\bUA\d{2}[\s\d]{20,}|ЄДРПОУ\D{0,5}\d{8}\b|(?<!\d)\d{8}(?!\d)",
       "fio": r"\b[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\b",
       "secret": r"(password|passwd|pwd|api[_-]?key|token|secret)\s*[:=]\s*\S+"}
# поріг панелі: «мін. панель N», «мінімальна панель для growth = N», «min_panel=N»
PANEL_RE = r"(?:мін(?:імальн\w*|\.)?\s*панел\w*|min_panel)[^\d\n]{0,40}(\d+)"
PANEL_ACT = r"norm\(growth\)\s*=\s*0|панел\w*[^\n]*виключ|виключ\w*[^\n]*панел"
res = []

def add(i, st, msg=""):
    res.append({"id": i, "status": st, "msg": msg})

def ok(i, cond, msg=""):
    add(i, "PASS" if cond else "FAIL", "" if cond else msg)

def norm(s):
    s = re.sub(r"[«»„“”\"]", '"', s); s = re.sub(r"[’ʼ`']", "'", s)
    s = re.sub(r"[—–]", "-", s); s = re.sub(r"[*_`>]", "", s)
    return re.sub(r"\s+", " ", s).strip().strip(".,;: ").lower()

def sections(text):
    parts = re.split(r"^## ", text, flags=re.M)[1:]
    return {p.split("\n", 1)[0].strip(): (p.split("\n", 1)[1] if "\n" in p else "") for p in parts}

def rows(sec):
    out = [[c.strip() for c in l.strip().strip("|").split("|")] for l in sec.splitlines()
           if l.startswith("|") and not re.match(r"^\|[\s:|-]+\|$", l)]
    return out[1:] if out else []

def num(c):
    m = re.match(r"\s*(-?[\d\s]*[\d][\d.,]*)", c)
    return float(re.sub(r"\s", "", m.group(1)).replace(",", ".")) if m else None

def load_csv(path):
    m = {"companies": {}, "revenue": {}, "growth": {}, "panel": {}}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f, delimiter=";"):
            c = (r.get("code") or r.get("sec") or "").strip().zfill(2)
            for k in m:
                v = (r.get(k) or (r.get("panel_n") if k == "panel" else "") or "").strip().replace(",", ".")
                if v:
                    m[k][c] = float(v)
    if not m["panel"]:
        del m["panel"]
    return m

def ref_codes():
    p = Path(__file__).resolve().parent.parent / "references" / "kved-2010-sections.md"
    t = p.read_text(encoding="utf-8").split("## Код → назва розділу", 1)[-1]
    return set(re.findall(r"^\|\s*(\d{2})\s*\|", t, re.M))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("file"); ap.add_argument("--param")
    ap.add_argument("--metrics"); ap.add_argument("--metrics-csv"); ap.add_argument("--min-panel", type=int)
    ap.add_argument("--snapshot"); ap.add_argument("--exclude", default="")
    a = ap.parse_args()
    text = Path(a.file).read_text(encoding="utf-8"); secs = sections(text)
    miss = [h for h in HEADERS if h not in secs]
    ok("SC-headers", not miss, "немає: " + ", ".join(miss))
    if miss:
        print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    snap = a.snapshot or (re.search(r"знімок реєстру:\s*(\d{4}-\d{2})", secs["Знімок даних"]) or [None, None])[1]
    top = [r for r in rows(secs["Топ-10"]) if r and r[0]]
    ok("SC-count", len(top) == 10, f"рядків {len(top)}")
    cols = [r for r in top if len(r) >= 8 and all(c for c in r[:8])]
    ok("SC-cols", len(cols) == len(top), f"неповних рядків: {len(top)-len(cols)}")
    bad = []
    for r in top:
        for k in (3, 4, 5):
            if len(r) > k:
                m = TAG.match(r[k])
                if not m or (snap and f"{m.group(1)}-{m.group(2)}" != snap):
                    bad.append(f"рядок {r[0]} кол.{k+1}")
    ok("SC-tag", snap is not None and not bad, "немає/інша дата тегу: " + "; ".join(bad[:5]) if snap else "дата знімка не знайдена")
    ok("SC-tag-score", not any(len(r) > 7 and "[odb" in r[7] for r in top), "бал має бути без тега")
    codes = [re.sub(r"\D", "", r[1])[:2] for r in top if len(r) > 1]
    full = [r for r in rows(secs["Повний рейтинг"]) if len(r) > 1]
    lv = {len(re.sub(r"\D", "", r[1])) for r in top + full if len(r) > 1}
    ok("SC-level", len(lv) <= 1, f"змішані довжини кодів {sorted(lv)}")
    ex = [x for x in a.exclude.split(",") if x]
    if ex:
        ok("SC-exclude", not (set(ex) & {re.sub(r"\D", "", r[1])[:2] for r in top + full if len(r) > 1}), "виключений розділ у рейтингу")
    else:
        add("SC-exclude", "MANUAL", "не передано --exclude; звірити виключення з параметром критерію")
    try:
        allc = ref_codes(); have = {re.sub(r"\D", "", r[1])[:2] for r in full} | set(ex)
        miss_c = sorted(allc - have); extra_c = sorted(have - allc)
        if miss_c or extra_c:
            add("SC-coverage", "WARN", ("розділів довідника немає в рейтингу й не виключено: " + ", ".join(miss_c)
                + "; назвати в «Якість даних» і у відкритих питаннях власнику реєстру (немає компаній з фінансами?)" if miss_c else "")
                + ("; коди поза довідником kved-2010-sections.md: " + ", ".join(extra_c) if extra_c else "")
                + ("" if ex else "; --exclude не передано: серед відсутніх можуть бути виключені розділи, передайте --exclude, щоб їх відокремити"))
        else:
            add("SC-coverage", "PASS")
    except Exception as e:
        add("SC-coverage", "MANUAL", f"довідник не прочитано ({type(e).__name__})")
    # SC-panel
    metrics = None
    if a.metrics_csv:
        metrics = load_csv(a.metrics_csv)
    elif a.metrics:
        try: metrics = json.load(open(a.metrics))
        except Exception: metrics = None
    pn = dict(metrics.get("panel", {})) if metrics else {}
    if not pn:
        qd = secs["Якість даних і обмеження"]
        mm_ = re.search(r"панел[іьяю]\w*[^:\n]*:\s*([^\n]*)", qd, re.I)
        if mm_:
            pn = {c: float(re.sub(r"\s", "", v)) for c, v in re.findall(r"(?<!\d)(\d{2})\s*[—-]\s*(\d[\d\s]*\d|\d)", mm_.group(1))}
    ptxt = Path(a.param).read_text(encoding="utf-8") if a.param else ""
    nmin = a.min_panel
    if nmin is None:
        pm_ = re.search(PANEL_RE, ptxt, re.I)
        nmin = int(pm_.group(1)) if pm_ else None
    ref = nmin is None; nmin = 30 if ref else nmin
    if pn:
        small = [f"{c} (панель {int(pn[c])})" for c in codes if c in pn and pn[c] < nmin]
        if small:
            add("SC-panel", "WARN", f"топ-10: панель зростання < {nmin}: " + ", ".join(small) + "; бал не змінено; "
                + ("N довідкове, поріг у параметрі не задано — питання Власнику продукту" if ref else "N з параметра")
                + "; назвати в «Якість даних»")
        else:
            add("SC-panel", "PASS")
    else:
        add("SC-panel", "MANUAL", "розмір панелі (panel_n) не передано (--metrics-csv з колонкою panel або рядок «Розмір панелі…» у «Якість даних»)")
    src = rows(secs["Рішення на ринку: джерела"])
    DATE = r"\d{4}-\d{2}-\d{2}"; nf = lambda c: re.match(r"не знайдено", c.strip(), re.I)
    bad_src, by = [], {}
    for r in src:
        if len(r) < 4 or not re.search(DATE, r[3]) or (not nf(r[1]) and not re.search(r"https?://", r[2])):
            bad_src.append(r[0] if r else "?")
        elif not nf(r[1]):
            by.setdefault(re.sub(r"\D", "", r[0])[:2], []).append(r)
    for r in top:
        if len(r) > 6 and not re.search(r"не знайдено \(" + DATE + r"\)", r[6]) and re.sub(r"\D", "", r[1])[:2] not in by:
            bad_src.append(f"{r[1]}: немає рядка джерел")
    ok("SC-sources", not bad_src, "джерела: " + "; ".join(bad_src[:6]) + " (рядок: розділ | рішення | URL | дата; «не знайдено» — без URL, з датою)")
    hits = [f"{k}:{i+1}" for i, l in enumerate(text.splitlines()) if not l.lstrip().startswith(("SELECT", "FROM", "WHERE", "#"))
            for k, p in PII.items() if re.search(p, l, re.I if k in PII_I else 0) and not (k == "edrpou" and re.search(r"\d{4}-\d{2}-\d{2}|\[odb", l) and not re.search(r"ЄДРПОУ", l))]
    ok("SC-nopii", not hits, "; ".join(hits[:8]))
    sq = secs["SQL-запити"]; qids = set(re.findall(r"^###\s*(Q\d+)", sq, re.M))
    blocks = re.split(r"^###\s*Q\d+", sq, flags=re.M)[1:]
    q_ok = bool(qids) and all("has_financials" in b and "1" in b for b in blocks if "fin_history GROUP BY" not in b and "kved" in b)
    used = set(re.findall(r"\bQ\d+\b", text.replace(sq, "")))
    hdr = secs["Топ-10"].splitlines()[0:3]; hdr = " ".join(l for l in hdr if l.startswith("|"))
    need = [q for q in ("Q2",) if not re.search(r"\b" + q + r"\b", hdr)]
    ok("SC-q", q_ok and used <= qids and bool(used) and not need, f"Qn без запиту: {sorted(used-qids)}; запити без has_financials; у заголовках Топ-10 немає: {need}")
    if a.param:
        crit = secs["Критерій ранжування"]
        pm = norm(Path(a.param).read_text(encoding="utf-8"))
        ok("SC-criterion", pm and pm in norm(crit), "формула параметра не знайдена дослівно")
    else:
        add("SC-criterion", "MANUAL", "не передано --param")
    # SC-order
    if metrics and re.search(PANEL_RE, ptxt, re.I) and re.search(PANEL_ACT, ptxt, re.I):
        add("SC-order", "MANUAL", "параметр задає дію для малих панелей (norm(growth)=0 або виключення розділу): скрипт її не реалізує; перерахувати вручну, зафіксувати в memo")
    elif metrics and (lack := sorted({re.sub(r"\D", "", r[1])[:2] for r in full} - set(metrics.get("companies", {})))):
        ok("SC-order", False, "CSV неповний: немає кодів із «Повного рейтингу»: " + ", ".join(lack[:10]) + " — перебудувати CSV із відповіді Q2")
    elif metrics:
        try:
            m = metrics
            w = {k: float(x) for x, k in re.findall(r"(\d*\.?\d+)\s*[·*]\s*norm\((\w+)\)", secs["Критерій ранжування"])}
            def mm(d):
                lo, hi = min(d.values()), max(d.values()); return {k: (v - lo) / (hi - lo) if hi > lo else 0 for k, v in d.items()}
            nm = {k: mm({s: float(v) for s, v in m[k].items()}) for k in w}
            sc = {s: sum(w[k] * nm[k][s] for k in w) for s in nm[next(iter(w))]}
            ranked = sorted(sc.items(), key=lambda x: -x[1]); exp = [s for s, _ in ranked][:10]
            # за рівних балів порядок довільний: порівнюємо множини в межах групи рівного балу
            good, i = True, 0
            while i < 10 and good:
                j = i
                while j < len(ranked) and abs(ranked[j][1] - ranked[i][1]) < 1e-9: j += 1
                lo, hi = i, min(j, 10)
                good = set(codes[lo:hi]) == set(exp[lo:hi]); i = j
            ok("SC-order", good and len(codes) == 10, f"очікувано {exp}, у файлі {codes}")
        except Exception as e:
            add("SC-order", "MANUAL", f"формула/метрики не розібрано ({type(e).__name__}); перерахувати вручну, зафіксувати в memo")
    else:
        add("SC-order", "MANUAL", "не передано --metrics/--metrics-csv; перерахувати бали за формулою, зафіксувати в memo")
    add("SC-repro", "MANUAL", "3 клітинки повторним запитом після округлення (scoring-formula.md §7); результат у memo")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)

main()
