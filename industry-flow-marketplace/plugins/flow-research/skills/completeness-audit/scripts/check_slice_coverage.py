#!/usr/bin/env python3
"""Автоперевірки режиму slice-coverage completeness-audit (CS-*) для research/COVERAGE-SLICE.md. stdlib. Вивід: JSON [{id,status,msg}]; код виходу 1, якщо є FAIL.
Використання: check_slice_coverage.py <research/COVERAGE-SLICE.md> [--features concept/features.md] [--ai-decisions research/AI-DECISIONS.md]
               [--plan prototype-real/PLAN.md] [--addons package/addons] [--rejected research/REJECTED.md]
CS-sections  — розділи 1..5 і «Підсумок».
CS-status    — у §1 кожен рядок має статус з: модуль|стандарт|настройка|імітація|лише в документах|немає|відбраковано; «відбраковано» — з REJ-NNN у «Примітка/Де».
CS-cover     — (з --features) кожна F-xx концепції (без «знято») є в §1; шлях задано, а файлу немає або F-xx не витягнуто — FAIL; без --features — SKIP.
CS-cycle     — §2: ≥6 етапів; рядок з прогалиною має рекомендацію «в A | в B-C | не робимо».
CS-launch    — §3: усі 11 областей (локалізація, обмін з обліковою системою, банки, ПРРО, друковані форми, юрособи, права, майстер-дані, міграція, оновлення,
               мобільний доступ); статус закрито|частково|немає|не стосується; «немає/частково» — з рекомендацією.
CS-proposals — §4: ≥1 партія, ≤3; кожна P-NN унікальна, група «дешева на стандарті|нестандартна», рекомендація «в A|в B-C|не робимо»; є колонка «Вето власника».
CS-consistency — §5: 4 обов'язкові перевірки (REJECTED↔код, PLAN↔модулі, кількість показників, коробка показу=коробка входу), результат OK|ПРОГАЛИНА.
CS-ai        — (з --ai-decisions) кожна AI-NN, названа в файлі, існує в «Рішення»; шлях задано, файлу немає — FAIL; без прапорця — SKIP.
CS-plan-modules — (з --plan і --addons) кожне td_* з PLAN.md має каталог з __manifest__.py; якщо в §5 «PLAN ↔ модулі» стоїть OK, а модуля немає — FAIL
               (явна ПРОГАЛИНА в §5 при відсутньому модулі — PASS, прогалину названо); без прапорців — SKIP.
CS-rej-code  — (з --rejected і --addons) WARN-евристика: слова REJ-NNN (латиниця імен моделей/файлів td_*) збігаються з кодом; §5 «REJECTED ↔ код» = OK при збігу — WARN.
CS-manual    — MANUAL: «кількість показників» і «коробка показу = коробка входу» детерміновано не звіряються (рецензент; A-21.yaml звіряє мітки «Показників дашборда: N», «Коробка входу: X»).
CS-sum       — «Підсумок: covered=a, gaps=b, proposals=c» = підрахунок (немає рядка — WARN).
CS-money     — без грошових маркерів (окупн, TCO, вартість володіння, business-case, ROI, беззбитков, ставка розробки)."""
import argparse, json, re, sys
from pathlib import Path

res = []
ST1 = ("модуль", "стандарт", "настройка", "імітація", "лише в документах", "немає", "відбраковано")
COVERED = ("модуль", "стандарт", "настройка")
GAP1 = ("імітація", "лише в документах", "немає")
REC = ("в a", "в b-c", "не робимо")
AREAS = ["локалізація", "обмін з обліковою системою", "банки", "прро", "друковані форми", "юрособи", "права", "майстер-дані", "міграція", "оновлення", "мобільний доступ"]
ST3 = ("закрито", "частково", "немає", "не стосується")
CHK = [("rejected", "REJECTED"), ("plan", "PLAN"), ("показник", "показник"), ("коробк", "коробк")]
MONEY = re.compile(r"окупн|\bTCO\b|вартість\s+володіння|business[- ]case|бізнес-кейс|\bROI\b|беззбитков|ставк\w*\s+розробки", re.I)


def add(i, ok, msg="", status=None):
    res.append({"id": i, "status": status or ("PASS" if ok else "FAIL"), "msg": "" if ok else msg})


def sections(t):
    out = {}
    for m in re.finditer(r"^##\s+([^\n]*)\n(.*?)(?=^##\s|\Z)", t, flags=re.M | re.S):
        out[m.group(1).strip()] = m.group(2)
    return out


def table(sec):
    rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in sec.splitlines()
            if l.startswith("|") and not re.match(r"^\|[\s:|-]+\|$", l)]
    return (rows[0], rows[1:]) if rows else ([], [])


def col(h, *names):
    for n in names:
        for i, x in enumerate(h):
            if x.lower().startswith(n.lower()): return i
    return None


def cell(r, i):
    return r[i] if i is not None and i < len(r) else ""


def rec_ok(v):
    v = re.sub(r"[`*]", "", v).strip().lower().replace("в в-с", "в b-c").replace("в в—с", "в b-c")
    v = v.replace("в в", "в b").replace("в с", "в c").replace("в а", "в a")
    return any(v.startswith(x) for x in REC)


def plan_modules(txt):
    """Модулі PLAN: колонка «Модуль» таблиці або td_-токени в бектиках у рядках зі словом «модул». Решта td_ (поля) ігнорується."""
    out = set(); mcol = None
    for ln in txt.splitlines():
        if ln.lstrip().startswith("|"):
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if any(c.lower().startswith("модул") for c in cells):
                mcol = next(i for i, c in enumerate(cells) if c.lower().startswith("модул")); continue
            if mcol is not None and mcol < len(cells) and not set(cells[mcol]) <= set("-: "):
                out |= set(re.findall(r"\btd_[a-z0-9_]+", cells[mcol]))
            continue
        mcol = None
        if re.match(r"^[\s>*_#-]*модул", ln, re.I):
            out |= set(re.findall(r"\btd_[a-z0-9_]+", ln))
        elif re.search(r"модул", ln, re.I):
            out |= set(re.findall(r"`(td_[a-z0-9_]+)`", ln))
    return out


def sec_by(secs, num):
    for k, v in secs.items():
        if re.match(rf"^{num}[.\s]", k): return v
    return None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("file"); ap.add_argument("--features"); ap.add_argument("--ai-decisions"); ap.add_argument("--plan"); ap.add_argument("--addons"); ap.add_argument("--rejected"); a = ap.parse_args()
    p = Path(a.file)
    if not p.exists():
        add("CS-sections", False, f"немає {a.file}"); print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    t = p.read_text(encoding="utf-8"); secs = sections(t)
    s = {n: sec_by(secs, n) for n in range(1, 6)}
    summ = next((v for k, v in secs.items() if k.lower().startswith("підсумок")), None)
    miss = [f"§{n}" for n, v in s.items() if v is None] + (["Підсумок"] if summ is None else [])
    add("CS-sections", not miss, f"немає розділів: {miss}")
    if miss:
        print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    # §1
    h, r1 = table(s[1]); cF, cS, cN = col(h, "F-xx", "F"), col(h, "Статус"), col(h, "Примітка")
    cW = col(h, "Де")
    why = []; cnt = {"cov": 0, "gap": 0}; ids = []
    for r in r1:
        f = cell(r, cF)
        if not re.match(r"^F-\d+$", f): continue
        ids.append(f); st = cell(r, cS).lower().strip("` *")
        if st not in ST1: why.append(f"{f}: статус «{cell(r, cS)}» не з {list(ST1)}"); continue
        if st == "відбраковано" and not re.search(r"REJ-\d{3}", cell(r, cN) + cell(r, cW)): why.append(f"{f}: «відбраковано» без REJ-NNN")
        if st in COVERED: cnt["cov"] += 1
        elif st in GAP1: cnt["gap"] += 1
    if not ids: why.append("§1 без рядків F-xx")
    add("CS-status", not why, "; ".join(why[:8]))
    if a.features and not Path(a.features).exists():
        add("CS-cover", False, f"немає {a.features}")
    elif a.features:
        ft = Path(a.features).read_text(encoding="utf-8")
        hf, rf = table(sections(ft).get("Функції", "")); live = []
        for r in rf:
            if re.match(r"^F-\d+$", r[0]) and not any(x.strip().lower().startswith("знято") for x in r[1:]): live.append(r[0])
        lost = sorted(set(live) - set(ids))
        if not live: add("CS-cover", False, "у features.md немає F-xx у розділі «Функції»")
        else: add("CS-cover", not lost, f"F-xx концепції без рядка в §1: {lost[:15]}")
    else:
        res.append({"id": "CS-cover", "status": "SKIP", "msg": "без --features"})
    # §2
    h, r2 = table(s[2]); cP, cRec, cG = col(h, "Покрито"), col(h, "Рекомендація"), col(h, "Прогалина")
    why = []
    rows2 = [r for r in r2 if r and r[0].strip()]
    if len(rows2) < 6: why.append(f"етапів циклу {len(rows2)} < 6")
    for r in rows2:
        gap = cell(r, cG).strip().strip("`* ").lower()
        if gap in ("", "—", "-", "–", "немає", "ні"): continue
        cnt["gap"] += 1
        if not rec_ok(cell(r, cRec)): why.append(f"етап {r[0]}: прогалина без рекомендації «в A | в B-C | не робимо»")
    add("CS-cycle", not why, "; ".join(why[:8]))
    # §3
    h, r3 = table(s[3]); cA, cSt, cR = col(h, "Область"), col(h, "Статус"), col(h, "Рекомендація")
    why = []; seen = {}
    for r in r3:
        ar = cell(r, cA).strip().lower()
        for x in AREAS:
            if ar.startswith(x): seen[x] = r
    for x in AREAS:
        if x not in seen: why.append(f"немає області «{x}»"); continue
        r = seen[x]; st = cell(r, cSt).lower().strip("` *")
        if st not in ST3: why.append(f"{x}: статус «{cell(r, cSt)}»")
        elif st in ("немає", "частково"):
            cnt["gap"] += 1
            if not rec_ok(cell(r, cR)): why.append(f"{x}: «{st}» без рекомендації")
    add("CS-launch", not why, "; ".join(why[:8]))
    # §4
    batches = re.findall(r"^###\s+Партія\s+\d+", s[4], flags=re.M)
    why = []
    if not 1 <= len(batches) <= 3: why.append(f"партій {len(batches)} (потрібно 1..3)")
    h, r4 = table(s[4]); cPN, cG4, cRec4, cV = col(h, "P-NN", "P"), col(h, "Група"), col(h, "Рекомендація"), col(h, "Вето")
    if cV is None: why.append("немає колонки «Вето власника»")
    pids = []
    for r in r4:
        pid = cell(r, cPN)
        if not re.match(r"^P-\d+$", pid): continue
        if pid in pids: why.append(f"дубль {pid}")
        pids.append(pid)
        g = cell(r, cG4).lower()
        if not (g.startswith("дешев") or g.startswith("нестандарт")): why.append(f"{pid}: група «{cell(r, cG4)}»")
        if not rec_ok(cell(r, cRec4)): why.append(f"{pid}: рекомендація «{cell(r, cRec4)}»")
    if not pids: why.append("§4 без пропозицій P-NN")
    add("CS-proposals", not why, "; ".join(why[:8]))
    prow = r"^\|\s*P-\d+\s*\|"
    parts = re.split(r"^###\s+Партія\s+\d+.*$", s[4], flags=re.M)[1:]
    odd = [f"партія {i+1}: {len(re.findall(prow, p_, flags=re.M))}" for i, p_ in enumerate(parts) if not 5 <= len(re.findall(prow, p_, flags=re.M)) <= 8]
    if odd: res.append({"id": "CS-batch-size", "status": "WARN", "msg": "розмір партії поза 5–8 P-NN: " + "; ".join(odd)})
    if re.search(r"в\s*[aа]\b", " ".join(re.sub(r"[`*]", "", x).lower() for rr in (r4 + r3) for x in rr)) and not re.search(r"AI-\d{2}", t):
        res.append({"id": "CS-ai-rows", "status": "WARN", "msg": "є рекомендації «в A», але в файлі немає жодного AI-NN"})
    # §5
    h, r5 = table(s[5]); cC, cRes = col(h, "Перевірка"), col(h, "Результат")
    why = []
    for key, name in CHK:
        row = next((r for r in r5 if key in cell(r, cC).lower()), None)
        if row is None: why.append(f"немає перевірки «{name}»"); continue
        v = cell(row, cRes).strip("` *").upper()
        if v.startswith("ПРОГАЛИНА"): cnt["gap"] += 1
        elif not v.startswith("OK"): why.append(f"«{name}»: результат «{cell(row, cRes)}» (OK | ПРОГАЛИНА)")
    add("CS-consistency", not why, "; ".join(why[:8]))
    # CS-plan-modules / CS-rej-code
    row5 = {k: next((r for r in r5 if k in cell(r, cC).lower()), None) for k in ("plan", "rejected")}
    mods = set()
    if a.addons and Path(a.addons).is_dir():
        mods = {m.parent.name for m in Path(a.addons).glob("td_*/__manifest__.py")}
    if a.plan and a.addons:
        if not Path(a.plan).exists(): add("CS-plan-modules", False, f"немає {a.plan}")
        else:
            need = plan_modules(Path(a.plan).read_text(encoding="utf-8"))
            lack = sorted(need - mods)
            v = cell(row5["plan"], cRes).strip("` *").upper() if row5["plan"] else ""
            if lack and v.startswith("OK"): add("CS-plan-modules", False, f"§5 «PLAN ↔ модулі» = OK, але немає каталогу з __manifest__.py: {lack}")
            else: add("CS-plan-modules", True)
    else:
        res.append({"id": "CS-plan-modules", "status": "SKIP", "msg": "без --plan/--addons"})
    if a.rejected and a.addons and Path(a.rejected).exists() and mods:
        rt = Path(a.rejected).read_text(encoding="utf-8"); hits = []
        for ln in rt.splitlines():
            m = re.search(r"REJ-\d{3}", ln)
            if not m: continue
            for w in {w for w in re.findall(r"[a-z][a-z0-9]{3,}", ln.lower()) if not w.startswith(("rej", "http"))}:
                for d in Path(a.addons).glob("td_*"):
                    if w in d.name.lower() or any(w in f.name.lower() for f in d.glob("models/*.py")): hits.append(f"{m.group(0)}:{w}@{d.name}")
        v = cell(row5["rejected"], cRes).strip("` *").upper() if row5["rejected"] else ""
        if hits and v.startswith("OK"): res.append({"id": "CS-rej-code", "status": "WARN", "msg": f"§5 «REJECTED ↔ код» = OK, але збіги: {sorted(set(hits))[:6]}"})
        else: add("CS-rej-code", True)
    else:
        res.append({"id": "CS-rej-code", "status": "SKIP", "msg": "без --rejected/--addons"})
    res.append({"id": "CS-manual", "status": "MANUAL", "msg": "кількість показників і «коробка показу = коробка входу» — рецензент (A-21.yaml звіряє мітки)"})
    # CS-ai
    if a.ai_decisions and not Path(a.ai_decisions).exists():
        add("CS-ai", False, f"немає {a.ai_decisions}")
    elif a.ai_decisions:
        dec = sections(Path(a.ai_decisions).read_text(encoding="utf-8"))
        have = set(re.findall(r"^\|\s*(AI-\d{2})\s*\|", dec.get("Рішення", ""), flags=re.M))
        used = set(re.findall(r"AI-\d{2}", t))
        add("CS-ai", not (used - have), f"AI-NN немає в «Рішення»: {sorted(used - have)}")
    else:
        res.append({"id": "CS-ai", "status": "SKIP", "msg": "без --ai-decisions"})
    # CS-sum
    m = re.search(r"covered\s*=\s*(\d+)\s*,\s*gaps\s*=\s*(\d+)\s*,\s*proposals\s*=\s*(\d+)", summ)
    exp = (cnt["cov"], cnt["gap"], len(pids))
    if not m: res.append({"id": "CS-sum", "status": "WARN", "msg": "немає «Підсумок: covered=a, gaps=b, proposals=c»"})
    else:
        got = tuple(map(int, m.groups())); add("CS-sum", got == exp, f"підсумок {got} ≠ підрахунок {exp}")
    hit = sorted({x.group(0).lower() for ln in t.splitlines() if not re.search(r"REJ-\d{3}|https?://", ln) for x in MONEY.finditer(ln)})
    add("CS-money", not hit, f"грошові маркери: {hit}")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)


main()
