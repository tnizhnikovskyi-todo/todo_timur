#!/usr/bin/env python3
"""Детерміноване ранжування кандидатів segment-selector (A-05, B-01) за selection-criteria.md §2-§3.

Вхід — CSV з відповіді odb-catalog (лише code, name, employees, region, kved_ambig, rev_2024, rev_2025).
Ваги НЕ змінюються (рішення q39: затверджує Керівник напряму після першого запуску) — це константи нижче.
Вхід — пул ПІСЛЯ виключень crm.csv і попередніх раундів (скрипт виключень не робить); зайві колонки (kved_2010, revenue…) дозволені.
Запуск: python3 -I scripts/rank_candidates.py <in.csv> --lo 50 --hi 249 --snapshot 2026-08 [--priority-region Київ] [--top 6]
Скрипт застосовний, коли фільтр розміру = діапазон lo..hi: компонент розміру 1 у діапазоні, інакше 0 («поруч ±1 розряд = 0,5»
НЕ реалізовано — для пулу, ширшого за діапазон, компонент розміру рахувати вручну; скрипт друкує лічильник таких компаній).
Вихід (stdout): таблиця рангу, блок «Якість даних», WARN рівних балів, позначки «перевірити Sales» (евристичні).
"""
import argparse, csv, re, sys
from collections import Counter

W = {"size": 0.4, "dyn": 0.3, "compl": 0.2, "region": 0.1}  # пропозиція скіла, не затверджено
CLIP = 0.5          # обрізання зростання до [-0.5; +0.5]
JUMP = 2.0          # стрибок виручки > +200 % за рік -> «перевірити Sales»
TRADE = re.compile(r"\b(ТРЕЙД|TRADE|ТОРГ|ДИСТРИБ|DISTRIB)", re.I)   # початок слова: «ВОСТОРГ» не збігається
GROUPW = re.compile(r"(ГРУП|GROUP|ХОЛДИНГ|HOLDING|КОРПОРАЦ)", re.I)
LEGAL = re.compile(r"(ТОВАРИСТВО З ОБМЕЖЕНОЮ ВІДПОВІДАЛЬНІСТЮ|ПРИВАТНЕ ПІДПРИЄМСТВО|ПРИВАТНЕ АКЦІОНЕРНЕ ТОВАРИСТВО|"
                   r"ПУБЛІЧНЕ АКЦІОНЕРНЕ ТОВАРИСТВО|\b(?:ТОВ|ПП|ПРАТ|ПАТ|ФОП)\b)", re.I)
# галузеві загальні слова не ідентифікують групу («МЕБЛЕВИЙ ДІМ» і «МЕБЛЕВИЙ СВІТ» — різні компанії)
GENERIC = re.compile(r"^(МЕБЛ\w*|МЕБЕЛЬ|MEBLI|ДІМ|ФАБРИКА|ВИРОБНИЧ\w*|КОМПАНІЯ|ФІРМА|СВІТ|ПАРК|ЦЕНТР|ПЛЮС|ДЕРЕВО|ДЕРЕВ\w*)$", re.I)
EDRPOU = re.compile(r"^\d{8}$")
SNAP = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
NEED = ("code", "name", "employees", "region", "kved_ambig", "rev_2024", "rev_2025")


def num(x):
    try:
        return float(str(x).replace(",", ".").strip())
    except ValueError:
        return None


def stem(name):
    s = re.sub(r"[\"'«»“”]", " ", name.upper())
    s = LEGAL.sub(" ", s)
    w = [t.strip("-.,;:()") for t in s.split()]
    w = [t for t in w if len(t) > 2 and not TRADE.match(t) and not GROUPW.match(t) and not GENERIC.match(t)]
    return w[0] if w else None


def score(r, lo, hi, prio):
    emp, rev24, rev25 = num(r["employees"]), num(r["rev_2024"]), num(r["rev_2025"])
    size = 1.0 if emp is not None and lo <= emp <= hi else 0.0   # «поруч ±1 розряд = 0.5» не реалізовано (див. шапку)
    raw = (rev25 / rev24 - 1) if rev24 and rev24 > 0 and rev25 is not None else None
    dyn = 0.0 if raw is None else (max(-CLIP, min(CLIP, raw)) + CLIP)
    compl = 1.0 if str(r.get("kved_ambig", "0")) in ("0", "") and emp is not None and r.get("region") else 0.0
    reg = 1.0 if prio and r.get("region") == prio else 0.0
    s = round(W["size"] * size + W["dyn"] * dyn + W["compl"] * compl + W["region"] * reg, 3)
    return s, raw, rev25


def main():
    a = argparse.ArgumentParser()
    a.add_argument("csv"); a.add_argument("--lo", type=float, required=True); a.add_argument("--hi", type=float, required=True)
    a.add_argument("--priority-region", default=""); a.add_argument("--top", type=int, default=6)
    a.add_argument("--snapshot", required=True, help="дата знімка odb-catalog, YYYY-MM (з опису MCP або inputs наряду)")
    o = a.parse_args()
    if not SNAP.match(o.snapshot):
        print("ERROR: --snapshot має бути YYYY-MM (дата невідома -> стоп до запису)", file=sys.stderr); return 2
    rd = csv.DictReader(open(o.csv, encoding="utf-8"))
    miss = [c for c in NEED if c not in (rd.fieldnames or [])]
    if miss:
        print(f"ERROR: у CSV немає колонок: {', '.join(miss)}", file=sys.stderr); return 2
    rows = list(rd)
    if not rows:
        print("ERROR: порожній пул (0 рядків) — ранжувати нічого", file=sys.stderr); return 2
    bad = [r["code"] for r in rows if not EDRPOU.match(str(r["code"]))]
    if bad:
        print(f"ERROR: ЄДРПОУ не 8 цифр (втрачений провідний нуль?): {', '.join(bad[:10])}", file=sys.stderr); return 2
    for r in rows:
        r["score"], r["raw"], r["rev"] = score(r, o.lo, o.hi, o.priority_region)
    # Детермінований порядок: бал ↓, виручка 2025 ↓, зростання (необрізане) ↓, ЄДРПОУ ↑
    rows.sort(key=lambda r: (-r["score"], -(r["rev"] if r["rev"] is not None else -1), -(r["raw"] if r["raw"] is not None else -9e9), r["code"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    stems = {}
    for r in rows:
        if stem(r["name"]):
            stems.setdefault(stem(r["name"]), []).append(r["code"])
    for r in rows:
        f = []
        if r["raw"] is not None and r["raw"] > JUMP:
            f.append(f"стрибок виручки {r['raw']*100:+.0f} % за рік")
        if TRADE.search(r["name"]):
            f.append("торгова роль у назві")
        if GROUPW.search(r["name"]) or (stem(r["name"]) and len(stems[stem(r["name"])]) > 1):
            peers = [c for c in stems.get(stem(r["name"]), []) if c != r["code"]]
            f.append("можлива група компаній" + (f" (пара в пулі: {', '.join(peers)})" if peers else ""))
        r["flags"] = f
    N, top = len(rows), rows[: o.top]
    fmt = lambda v: "н/д" if v is None else f"{v:.0f} [odb {o.snapshot}]"
    print("ПРИМІТКА: позначки аномалій евристичні (за назвою) — перевіряє Sales; скрипт застосовний лише коли фільтр розміру = діапазон lo..hi.")
    print("| Ранг | ЄДРПОУ | Бал | Виручка 2025 | Зростання | Позначки |\n|---|---|---|---|---|---|")
    for r in top:
        g = "н/д" if r["raw"] is None else f"{r['raw']*100:+.0f} %"
        fl = "; ".join(f"перевірити Sales: {x}" for x in r["flags"]) or "—"
        print(f"| {r['rank']} | {r['code']} | {r['score']:.3f} | {fmt(r['rev'])} | {g}{'' if r['raw'] is None else f' [odb {o.snapshot}]'} | {fl} |")
    clipped = [r for r in rows if r["raw"] is not None and r["raw"] >= CLIP]
    clipped_top = [r for r in top if r["raw"] is not None and r["raw"] >= CLIP]
    print("\n### Якість даних")
    print(f"- Динаміку обрізано до +{CLIP*100:.0f} %: {len(clipped)} з {N} компаній пулу, {len(clipped_top)} з {len(top)} у шортлісті "
          f"(у балі їм усім 1.0 за компонент; фактичне зростання — у колонці «Зростання»).")
    print(f"- Без динаміки (немає обох років): {sum(r['raw'] is None for r in rows)} з {N}.")
    out = [r for r in rows if num(r["employees"]) is None or not (o.lo <= num(r["employees"]) <= o.hi)]
    print(f"- Поза діапазоном розміру {o.lo:.0f}–{o.hi:.0f} (компонент розміру 0; «поруч ±1 розряд = 0,5» скрипт не рахує — вручну): {len(out)} з {N}.")
    print(f"- Аномалії (позначка «перевірити Sales», без виключення): {sum(bool(r['flags']) for r in rows)} з {N}.")
    groups = Counter(r["score"] for r in rows)
    top_scores = sorted({r["score"] for r in top}, reverse=True)
    for sc in top_scores:   # кожна група рівного балу k >= 3, у якій є хоч один кандидат шортліста
        k = groups[sc]
        if k < 3:
            continue
        tied = [r for r in rows if r["score"] == sc]
        print(f"\nWARN: бал не розрізняє: {k} з {N} рівні (бал {sc:.3f}) — ваги не затверджено "
              "(рішення q39: ваги затверджує Керівник напряму після першого запуску). "
              "Порядок усередині рівних — детермінований: виручка 2025 ↓, потім зростання ↓, потім ЄДРПОУ ↑.")
        print("\n| Ранг | ЄДРПОУ | Виручка 2025 | Зростання | У шортлісті |\n|---|---|---|---|---|")
        for r in tied:
            g = "н/д" if r["raw"] is None else f"{r['raw']*100:+.0f} %"
            print(f"| {r['rank']} | {r['code']} | {'н/д' if r['rev'] is None else format(r['rev'], '.0f')} | {g} | {'так' if r['rank'] <= o.top else 'ні'} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
