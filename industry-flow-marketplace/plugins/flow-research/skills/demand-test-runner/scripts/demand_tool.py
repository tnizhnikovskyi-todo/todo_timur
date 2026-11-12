#!/usr/bin/env python3
"""demand_tool.py: stdlib-перевірки й підрахунки demand-test-runner (A-23). Запуск: python3 -I demand_tool.py <cmd> ...
  aggregate --signals S.csv [--calls calls.md] --list mailing-list.csv --features features.md --start YYYY-MM-DD --end YYYY-MM-DD [--hot 3]
  pii FILE...        email/phone/ПІБ за flow-core/references/pii-patterns.md; друкує лише тип:файл:рядок
  utm FILE...        кожне посилання на лендинг (`https://{landing_url}/...`) має utm_campaign, utm_content; з #F-xx -- ще utm_term
  honesty FILE...    фрази з references/forbidden-claims.md (рядки з запереченням пропускаються); потрібні «Прототип» і «пілот з»
  complexity --complexity complexity.md --landing landing.md   F-xx «код/складно» -> «у плані пілоту»
  risks --features features.md --plan risk-plan.md [--decisions AI-DECISIONS.md]   кожна AI-NN зі статусом «прийнято» і «A-23» у колонці «Перевірка» має рядок плану (колонка «F-xx / AI-NN»); кожна F-xx зі статусом «вето власника» / «ризик:» має рядок плану перевірки (N-12) з експериментом, порогом і «якщо не підтвердиться»
  exp --plan risk-plan.md --landing landing.md        експерименти плану (fake-door / pack / price) мають блок у лендингу; тест ціни — лише з позначкою «гіпотеза, не пропозиція»
  materials --proto prototype-real [--intake OWNER-INTAKE.md] [--landing landing.md] [--plan mailing-plan.md] [--emails emails.md]   без --landing/--plan/--emails: лише «видано A-21c» (передперевірка); з ними — ще й використані (SHOW у emails.md або mailing-plan.md)
  raw FILE...        посилання на research/sources/ (internal-raw) у файлах скіла заборонені
  rejected --results results.md [--fail-variants A,C]   розділ «Відкинуто»: 8 колонок, REJ-ID, група, варіанти без порога внесені
  experiments --signals S.csv --start D --end D        агрегати експериментів групи 8 (колонки `експеримент`, `тариф` у signals.csv)
Контактів у вивід не друкує. Код виходу 1 при збігу/FAIL."""
import argparse, csv, json, re, sys

LV = {"Р1": 1, "Р2": 2, "Р3": 3, "Р4": 4, "Р5а": 5, "Р5б": 6}
FX = re.compile(r"\bF-\d{2,}\b")

def lvl(s):
    return (s or "").strip().replace("P", "Р").replace("a", "а").replace("b", "б")

def rows_signals(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            yield {"id": (r.get("ЄДРПОУ") or "").strip(), "v": (r.get("варіант") or "").strip(), "lv": lvl(r.get("рівень")),
                   "fx": FX.findall(r.get("F-xx") or ""), "d": (r.get("дата") or "").strip(),
                   "n": int((r.get("кількість") or "1").strip() or 1), "mark": False}

def rows_calls(path):
    for ln in open(path, encoding="utf-8"):
        p = [x.strip() for x in ln.split("|")]
        if len(p) >= 5 and re.match(r"\d{4}-\d{2}-\d{2}$", p[0]):
            yield {"id": p[1], "v": "", "lv": lvl(p[2]), "fx": FX.findall(p[3]), "d": p[0], "n": 1,
                   "mark": len(p) > 5 and "хоче спробувати сам" in p[5].lower()}

def aggregate(a):
    ev = list(rows_signals(a.signals)) + (list(rows_calls(a.calls)) if a.calls else [])
    lst = {}
    with open(a.list, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            lst[r["ЄДРПОУ"].strip()] = r["варіант"].strip()
    feats = sorted(set(FX.findall(open(a.features, encoding="utf-8").read())))
    out = {"sent": len(lst), "sent_by_variant": {}, "invalid": [], "out_of_period": 0}
    for v in lst.values():
        out["sent_by_variant"][v] = out["sent_by_variant"].get(v, 0) + 1
    p12, p2f, best, mention3, mention45, oom = {}, {}, {}, {}, {}, {}
    for e in ev:
        if e["lv"] not in LV:
            out["invalid"].append(f"невідомий рівень: {e['lv']!r}"); continue
        if not (a.start <= e["d"] <= a.end):
            out["out_of_period"] += 1; continue
        for x in e["fx"]:
            if x not in feats: oom[x] = oom.get(x, 0) + 1
        if LV[e["lv"]] <= 2:
            t = p12.setdefault(e["lv"], {"total": 0})
            t["total"] += e["n"]; t[e["v"]] = t.get(e["v"], 0) + e["n"]
            if e["lv"] == "Р2":
                for x in e["fx"]: p2f[x] = p2f.get(x, 0) + e["n"]
            continue
        if not re.fullmatch(r"\d{8}|ФОП-\d+", e["id"]):
            out["invalid"].append("Р3+ без ЄДРПОУ/ФОП-n"); continue
        b = best.setdefault(e["id"], {"lv": e["lv"], "v": lst.get(e["id"]) or e["v"], "mark": False, "fx": set()})
        if LV[e["lv"]] > LV[b["lv"]]: b["lv"] = e["lv"]
        b["mark"] = b["mark"] or e["mark"]; b["fx"].update(e["fx"])
        if e["id"] in lst:
            m = mention3 if e["lv"] == "Р3" else mention45
            for x in e["fx"]:
                m.setdefault(x, set()).add(e["id"])
    out["p1_p2"] = p12
    inl = {k: b for k, b in best.items() if k in lst}
    out["demand_total"] = len(inl)
    out["out_of_list"] = sorted((k, b["lv"], b["v"]) for k, b in best.items() if k not in lst)
    out["highest"] = {}; out["reached"] = {}
    for L in ("Р3", "Р4", "Р5а", "Р5б"):
        for key, pred in (("highest", lambda b: b["lv"] == L), ("reached", lambda b: LV[b["lv"]] >= LV[L])):
            sel = [b for b in inl.values() if pred(b)]
            d = {"total": len(sel)}
            for b in sel: d[b["v"]] = d.get(b["v"], 0) + 1
            out[key][L] = d
    out["featmap"] = sorted(({"F": x, "Р2": p2f.get(x, 0), "Р3": len(mention3.get(x, ())), "Р4+": len(mention45.get(x, ())),
                              "score": len(mention3.get(x, ())) + len(mention45.get(x, ()))} for x in feats),
                            key=lambda r: (-r["score"], r["F"]))
    out["out_of_map"] = oom
    out["hot"] = sorted((k, b["lv"], b["v"], sorted(b["fx"]), "B-01" + (",A-22" if b["mark"] else ""),
                         "у розсилці" if k in lst else "поза розсилкою")
                        for k, b in best.items() if LV[b["lv"]] >= a.hot)
    print(json.dumps(out, ensure_ascii=False, indent=1))

PII = {"email": r"[\w.+-]+@[\w-]+\.[\w.-]+", "phone": r"(?<![\w:])(\+?380\d{9}|0\d{9})(?!\w)",
       "ПІБ": r"\b[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\s+[А-ЯІЇЄҐ][а-яіїєґ'’-]+\b"}
CLAIMS = [r"готов\w+\s+(продукт|рішення|до використання)|готов\w+\s+(продукт|решение)", r"вже працю\w+|працює з коробки|встановіть і користуйтесь|уже работает",
          r"гаранту\w+|гарантія результату|гарантир\w+", r"(впровад\w+|внедр\w+)\s+за\s+\d+|запуск\s+за\s+\d+",
          r"економі\w+\s+\d+\s*%|окупність|\bROI\b|зменшимо витрати", r"\bціна\b|\bціни\b|вартість|від\s+\d[\d\s]*(грн|\$|€)|знижк\w+|тариф|\bцена\b|стоимость",
          r"конкуренти гірші|єдине рішення|№\s?1", r"обмежена пропозиція|лише сьогодні"]
NEG = re.compile(r"(не|без)\s+(є\s+|називаємо\s+|називати\s+|гарантуємо\s+)?(робоч\w+|готов\w+|цін\w*|гарант\w+)|ціни не|умови пілоту", re.I)

def lines(files):
    for p in files:
        for i, ln in enumerate(open(p, encoding="utf-8"), 1):
            yield p, i, ln

def scan(pats, files, skip=None):
    bad = 0
    for p, i, ln in lines(files):
        if skip and skip.search(ln): continue
        for name, rx in pats:
            if re.search(rx, ln, re.I if name != "ПІБ" else 0):
                print(f"{name}:{p}:{i}"); bad = 1
    return bad

PRICE = re.compile(CLAIMS[5], re.I)
HEAD = re.compile(r"^#{1,4}\s")

def price_scan(files):
    """Ціни — лише в розділі «Тест ціни» лендингу й лише з позначкою «гіпотеза» і «не пропозиція»; у листах і поза розділом — заборонено."""
    bad = 0
    for p in files:
        in_price, marks = False, [False, False]; start = 0
        for i, ln in enumerate(open(p, encoding="utf-8"), 1):
            if HEAD.match(ln):
                if in_price and not all(marks): print(f"price-unmarked:{p}:{start}"); bad = 1
                in_price = bool(re.search(r"Тест ціни", ln)) and p.endswith("landing.md"); marks = [False, False]; start = i
            if in_price:
                marks[0] = marks[0] or "гіпотез" in ln.lower(); marks[1] = marks[1] or bool(re.search(r"не\s+пропозиці", ln, re.I)); continue
            if NEG.search(ln): continue
            if PRICE.search(ln): print(f"claim:{p}:{i}"); bad = 1
        if in_price and not all(marks): print(f"price-unmarked:{p}:{start}"); bad = 1
    return bad

def cells(ln): return [c.strip() for c in ln.strip().strip("|").split("|")]

def table(path, header_key):
    """Рядки першої таблиці, чий заголовок містить header_key -> (колонки, рядки)."""
    cols, rows, on = [], [], False
    for ln in open(path, encoding="utf-8"):
        if ln.lstrip().startswith("|"):
            c = cells(ln)
            if not on and any(header_key in x for x in c): cols, on = c, True; continue
            if on and not all(set(x) <= set("-: ") for x in c): rows.append(c)
        elif on and rows: break
    return cols, rows

def risks(a):
    feats = open(a.features, encoding="utf-8").read().splitlines(); need = {}
    for ln in feats:
        if ln.lstrip().startswith("|") and re.search(r"вето власника|ризик:", ln):
            m = FX.search(ln)
            if m: need[m.group(0)] = 1
    cols, rows = table(a.plan, "Експеримент"); rc = 0
    def col(name):
        for i, c in enumerate(cols):
            if name in c: return i
        return None
    iE, iT, iN, iF = col("Експеримент"), col("поріг"), col("Якщо не підтвердиться"), col("F-xx")
    if None in (iE, iT, iN, iF): print("risks:plan-header (потрібні колонки F-xx, Експеримент, Сигнал і поріг, Якщо не підтвердиться)"); sys.exit(1)
    covered = set()
    for n, r in enumerate(rows, 1):
        if len(r) <= max(iE, iT, iN, iF): print(f"risks:row-{n}-short"); rc = 1; continue
        for x in FX.findall(r[iF]): covered.add(x)
        for name, i in (("експеримент", iE), ("поріг", iT), ("fallback", iN)):
            if not r[i] or r[i] in ("—", "-", "TODO", "?"): print(f"risks:row-{n}-no-{name}"); rc = 1
    for x in sorted(need):
        if x not in covered: print(f"risks:{x}-not-in-plan"); rc = 1
    if getattr(a, "decisions", None):
        dcols, drows = table(a.decisions, "Рішення AI")
        iS = next((i for i, c in enumerate(dcols) if "Статус" in c), None)
        iV = next((i for i, c in enumerate(dcols) if "Перевірка" in c), None)
        iI = next((i for i, c in enumerate(dcols) if c.strip() == "ID"), 0)
        if iS is None or iV is None: print("risks:decisions-header (потрібні колонки ID, Перевірка, Статус)"); rc = 1
        else:
            plan_ai = set()
            for r in rows:
                if len(r) > iF: plan_ai |= set(re.findall(r"\bAI-\d{2}\b", r[iF]))
            for r in drows:
                if len(r) <= max(iS, iV, iI) or not re.fullmatch(r"AI-\d{2}", r[iI]): continue
                if "прийнято" in r[iS].lower() and "A-23" in r[iV] and r[iI] not in plan_ai: print(f"risks:{r[iI]}-not-in-plan"); rc = 1
    if not need: print("risks-info: у features.md немає позицій «вето власника» / «ризик:» — перевір SALES §4/§7 вручну")
    return rc

def exp(a):
    cols, rows = table(a.plan, "Експеримент"); rc = 0
    iE = next((i for i, c in enumerate(cols) if "Експеримент" in c), None)
    if iE is None: print("exp:plan-header"); return 1
    kinds = {k for r in rows if len(r) > iE for k in ("fake-door", "pack", "price") if k in r[iE].lower()}
    land = open(a.landing, encoding="utf-8").read()
    need = {"fake-door": r"(?m)^#{2,3}\s+.*Голосування за функції", "pack": r"(?m)^#{2,3}\s+.*Збери свій пакет", "price": r"(?m)^#{2,3}\s+.*Тест ціни"}
    for k in sorted(kinds):
        if not re.search(need[k], land): print(f"exp:{k}-block-missing"); rc = 1
    return rc

DEFAULT_FORMATS = ["video_16x9", "reels_9x16", "one_pager"]

def intake_formats(path):
    """Повертає (формати, попередження). Рядковий `formats: [a, b]` або блоковий список `formats:\n  - a`.
    Не знайдено -> повний набір + попередження (друкується як materials:intake-formats-not-found)."""
    if not path: return DEFAULT_FORMATS, None
    t = open(path, encoding="utf-8").read()
    m = re.search(r"formats:[ \t]*\[([^\]]*)\]", t)
    if m: fm = [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()]
    else:
        m = re.search(r"(?m)^([ \t]*)formats:[ \t]*(?:#.*)?\n((?:[ \t]*-[ \t]*[^\n]*\n?)+)", t)
        fm = [re.sub(r"\s+#.*$", "", x.strip()[1:]).strip().strip("'\"") for x in m.group(2).splitlines() if x.strip().startswith("-")] if m else []
    if fm: return fm, None
    return DEFAULT_FORMATS, "materials:intake-formats-not-found (у анкеті немає materials.formats; перевірено повний набір)"

def materials(a):
    """Фаза 1 (без --landing/--plan/--emails): лише «видано A-21c» (файл існує й не порожній).
    Фаза 2 (є --landing/--plan/--emails): ще й використання: відео 16x9 і SHOW у лендингу, Reels у плані/листах/лендингу, SHOW (one_pager) у листах або плані."""
    import glob, os
    import os as _os
    if a.intake and not _os.path.isfile(a.intake): print(f"materials:intake-missing:{a.intake}"); return 2
    fm, warn = intake_formats(a.intake)
    if warn: print(warn)
    rd = lambda p: open(p, encoding="utf-8").read() if p else None
    landing, plan, emails = rd(a.landing), rd(a.plan), rd(a.emails); rc = 0
    want = []
    if "video_16x9" in fm: want.append(("video_16x9", "video/*-16x9.mp4"))
    if "reels_9x16" in fm: want.append(("reels_9x16", "video/*-9x16.mp4"))
    if "one_pager" in fm: want.append(("one_pager", "SHOW.pdf"))
    for name, pat in want:
        hits = [h for h in glob.glob(os.path.join(a.proto, pat)) if not os.path.basename(h).startswith("sample-") and os.path.getsize(h) > 0]
        if not hits: print(f"materials:{name}-not-delivered (A-21c не віддав непорожній {pat})"); rc = 1; continue
        base = os.path.basename(hits[0])
        if name == "video_16x9" and landing is not None and base not in landing: print(f"materials:{name}-not-in-landing:{base}"); rc = 1
        if name == "reels_9x16" and (plan is not None or emails is not None or landing is not None) and not any(base in (x or "") for x in (plan, emails, landing)): print(f"materials:{name}-not-in-plan:{base}"); rc = 1
        if name == "one_pager":
            if landing is not None and base not in landing: print(f"materials:{name}-not-in-landing:{base}"); rc = 1
            if (emails is not None or plan is not None) and not any(base in (x or "") for x in (emails, plan)): print(f"materials:{name}-not-in-emails-or-plan:{base}"); rc = 1
    return rc

def raw(files):
    bad = 0
    for p, i, ln in lines(files):
        if re.search(r"research/sources/", ln): print(f"raw:{p}:{i}"); bad = 1
    return bad

def rejected(a):
    t = open(a.results, encoding="utf-8").read(); m = re.search(r"(?ms)^##\s+Відкинуто\s*$(.*?)(?=^##\s|\Z)", t)
    if not m: print("rejected:no-section"); return 1
    rows = [cells(ln) for ln in m.group(1).splitlines() if ln.lstrip().startswith("|")]
    rows = [r for r in rows if not all(set(x) <= set("-: ") for x in r)]
    hdr = [c.lower() for c in rows[0]] if rows else []; rows = rows[1:]; rc = 0
    # короткий формат 0.3.0: ID · що не робимо · чому [· коли повернутись]; старі 8-колонкові таблиці проходять (колонки за назвами)
    iw = next((i for i, h in enumerate(hdr) if re.search(r"що|назва", h)), 1)
    iy = next((i for i, h in enumerate(hdr) if re.search(r"чому|причина", h)), 2)
    for n, r in enumerate(rows, 1):
        if len(r) < 3: print(f"rejected:row-{n}-cols"); rc = 1; continue
        if not re.fullmatch(r"REJ-\d{3}", r[0]): print(f"rejected:row-{n}-id"); rc = 1
        if len(r) <= iy or not r[iy].strip(" —-"): print(f"rejected:row-{n}-why"); rc = 1
    if a.plan:
        ids = sorted({x for ln in open(a.plan, encoding="utf-8") if ln.lstrip().startswith("|") for x in FX.findall(cells(ln)[0] if cells(ln) else "")})
        sec = re.search(r"(?ms)^##\s+Перевірка ризиків\s*$(.*?)(?=^##\s|\Z)", t)
        if not sec: print("rejected:no-risk-check-section"); rc = 1
        else:
            body = sec.group(1)
            for x in ids:
                ln = next((l for l in body.splitlines() if l.lstrip().startswith("|") and x in l), None)
                if not ln: print(f"rejected:risk-{x}-not-checked"); rc = 1; continue
                cs = cells(ln); verdict = cs[-1] if cs else ""; fact = cs[-2] if len(cs) >= 3 else ""
                if not re.search(r"підтверджено|підтвердилось", verdict, re.I): print(f"rejected:risk-{x}-no-verdict"); rc = 1; continue
                if not fact.strip(" —-"): print(f"rejected:risk-{x}-no-fact"); rc = 1; continue
                if re.search(r"не підтверджено|не підтвердилось", ln, re.I) and not any(x in " ".join(r) for r in rows): print(f"rejected:risk-{x}-unconfirmed-not-in-rejected"); rc = 1
    for v in [x.strip() for x in (a.fail_variants or "").split(",") if x.strip()]:
        if not any(re.search(rf"варіант\s+{re.escape(v)}\b", r[iw]) for r in rows if len(r) > iw): print(f"rejected:variant-{v}-missing"); rc = 1
    return rc

def experiments(a):
    out = {"fake_door": {}, "pack": {"events": 0, "companies": 0}, "price": {"events": {}, "companies": {}}}; best = {}
    with open(a.signals, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            e = (r.get("експеримент") or "").strip().lower(); d = (r.get("дата") or "").strip()
            if not e or not (a.start <= d <= a.end): continue
            lv = LV.get(lvl(r.get("рівень")), 0); n = int((r.get("кількість") or "1").strip() or 1); t = (r.get("тариф") or "—").strip() or "—"
            if lv <= 2:
                if e == "fake-door":
                    for x in FX.findall(r.get("F-xx") or ""): out["fake_door"][x] = out["fake_door"].get(x, 0) + n
                elif e == "pack": out["pack"]["events"] += n
                elif e == "price": out["price"]["events"][t] = out["price"]["events"].get(t, 0) + n
            else:
                k = (e, (r.get("ЄДРПОУ") or "").strip()); 
                if k[1] and (k not in best or lv > best[k][0]): best[k] = (lv, t)
    for (e, _), (lv, t) in best.items():
        if e == "pack": out["pack"]["companies"] += 1
        elif e == "price": out["price"]["companies"][t] = out["price"]["companies"].get(t, 0) + 1
    print(json.dumps(out, ensure_ascii=False, indent=1))

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("files", nargs="*")
    for k in ("signals", "calls", "list", "features", "start", "end", "complexity", "landing", "plan", "emails", "proto", "intake", "results", "fail-variants", "decisions"): ap.add_argument("--" + k)
    ap.add_argument("--hot", type=int, default=3); ap.add_argument("--json", action="store_true"); a = ap.parse_args(); rc = 0
    if a.json and a.cmd != "aggregate" and a.cmd != "experiments":
        import io, contextlib
        buf = io.StringIO(); code = 0
        try:
            with contextlib.redirect_stdout(buf): code = run(a)
        except SystemExit as e: code = e.code or 0
        msgs = [x for x in buf.getvalue().splitlines() if x]
        ident = {"materials": "DT-materials", "risks": "DT-risks", "exp": "DT-exp", "raw": "DT-raw", "rejected": "DT-rejected", "pii": "DT-no-pii"}.get(a.cmd, "DT-" + a.cmd)
        st = "FAIL" if code else ("WARN" if msgs else "PASS")
        print(json.dumps([{"id": ident, "status": st, "msg": "; ".join(msgs)}], ensure_ascii=False)); sys.exit(code)
    sys.exit(run(a))

def run(a):
    rc = 0
    if a.cmd == "aggregate": aggregate(a)
    elif a.cmd == "pii": rc = scan(list(PII.items()), a.files)
    elif a.cmd == "honesty":
        rc = scan([("claim", "|".join(CLAIMS[:5] + CLAIMS[6:]))], a.files, NEG)
        rc |= price_scan(a.files)
        for p in a.files:
            t = open(p, encoding="utf-8").read()
            if p.endswith(("landing.md", "emails.md")) and not ("Прототип" in t and "пілот з" in t):
                print(f"missing-marks:{p}"); rc = 1
    elif a.cmd == "utm":
        for p, i, ln in lines(a.files):
            for u in re.findall(r"https?://[^\s)>\]`]+", ln):
                if u.endswith("..."): continue
                if "{landing_url}" not in u:
                    if "utm_" not in u: print(f"utm-warn:{p}:{i}: https-посилання без {{landing_url}} — UTM не перевірено")
                    continue  # UTM перевіряється лише в посиланнях на лендинг (плейсхолдер)
                need = ["utm_campaign=", "utm_content="] + (["utm_term=F-"] if "#F-" in u else [])
                if any(n not in u for n in need): print(f"utm:{p}:{i}"); rc = 1
    elif a.cmd == "risks": rc = risks(a)
    elif a.cmd == "exp": rc = exp(a)
    elif a.cmd == "materials": rc = materials(a)
    elif a.cmd == "raw": rc = raw(a.files)
    elif a.cmd == "rejected": rc = rejected(a)
    elif a.cmd == "experiments": experiments(a)
    elif a.cmd == "complexity":
        hard = {x for ln in open(a.complexity, encoding="utf-8") if re.search(r"код|складно", ln, re.I) for x in FX.findall(ln)}
        blocks = re.split(r"(?m)^#{2,3} ", open(a.landing, encoding="utf-8").read())
        for x in sorted(hard):
            b = [s for s in blocks if s.startswith(x)]
            if not b or "у плані пілоту" not in b[0]: print(f"complexity:{x}"); rc = 1
    return rc

main()
