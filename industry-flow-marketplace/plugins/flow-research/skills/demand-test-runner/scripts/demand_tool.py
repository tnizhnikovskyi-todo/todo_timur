#!/usr/bin/env python3
"""demand_tool.py: stdlib-перевірки й підрахунки demand-test-runner (A-23). Запуск: python3 -I demand_tool.py <cmd> ...
  aggregate --signals S.csv [--calls calls.md] --list mailing-list.csv --features features.md --start YYYY-MM-DD --end YYYY-MM-DD [--hot 3]
  pii FILE...        email/phone/ПІБ за flow-core/references/pii-patterns.md; друкує лише тип:файл:рядок
  utm FILE...        кожне http(s)-посилання має utm_campaign, utm_content; з #F-xx -- ще utm_term
  honesty FILE...    фрази з references/forbidden-claims.md (рядки з запереченням пропускаються); потрібні «Прототип» і «пілот з»
  complexity --complexity complexity.md --landing landing.md   F-xx «код/складно» -> «у плані пілоту»
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
NEG = re.compile(r"(не|без)\s+(є\s+|називаємо\s+|гарантуємо\s+)?(робоч\w+|готов\w+|цін\w*|гарант\w+)|ціни не|умови пілоту", re.I)

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

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("cmd"); ap.add_argument("files", nargs="*")
    for k in ("signals", "calls", "list", "features", "start", "end", "complexity", "landing"): ap.add_argument("--" + k)
    ap.add_argument("--hot", type=int, default=3); a = ap.parse_args(); rc = 0
    if a.cmd == "aggregate": aggregate(a)
    elif a.cmd == "pii": rc = scan(list(PII.items()), a.files)
    elif a.cmd == "honesty":
        rc = scan([("claim", "|".join(CLAIMS))], a.files, NEG)
        for p in a.files:
            t = open(p, encoding="utf-8").read()
            if p.endswith(("landing.md", "emails.md")) and not ("Прототип" in t and "пілот з" in t):
                print(f"missing-marks:{p}"); rc = 1
    elif a.cmd == "utm":
        for p, i, ln in lines(a.files):
            for u in re.findall(r"https?://[^\s)>\]]+", ln):
                need = ["utm_campaign=", "utm_content="] + (["utm_term=F-"] if "#F-" in u else [])
                if any(n not in u for n in need): print(f"utm:{p}:{i}"); rc = 1
    elif a.cmd == "complexity":
        hard = {x for ln in open(a.complexity, encoding="utf-8") if re.search(r"код|складно", ln, re.I) for x in FX.findall(ln)}
        blocks = re.split(r"(?m)^#{2,3} ", open(a.landing, encoding="utf-8").read())
        for x in sorted(hard):
            b = [s for s in blocks if s.startswith(x)]
            if not b or "у плані пілоту" not in b[0]: print(f"complexity:{x}"); rc = 1
    sys.exit(rc)

main()
