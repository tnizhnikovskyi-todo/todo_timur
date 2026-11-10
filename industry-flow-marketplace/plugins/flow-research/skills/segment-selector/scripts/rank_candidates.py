#!/usr/bin/env python3
"""Детерміноване ранжування кандидатів segment-selector (A-05, B-01) за selection-criteria.md §2-§3.

Вхід — CSV з відповіді odb-catalog (лише code, name, employees, region, kved_ambig, rev_2024, rev_2025).
Ваги НЕ змінюються (рішення q39: затверджує Керівник напряму після першого запуску) — це константи нижче.
Запуск: python3 -I scripts/rank_candidates.py <in.csv> --lo 50 --hi 249 [--priority-region Київ] [--top 6] [--snapshot 2026-08]
Вихід (stdout): таблиця рангу, блок «Якість даних», WARN рівних балів, позначки «перевірити Sales».
"""
import argparse, csv, re, sys
from collections import Counter

W = {"size": 0.4, "dyn": 0.3, "compl": 0.2, "region": 0.1}  # пропозиція скіла, не затверджено
CLIP = 0.5          # обрізання зростання до [-0.5; +0.5]
JUMP = 2.0          # стрибок виручки > +200 % за рік -> «перевірити Sales»
TRADE = re.compile(r"(ТРЕЙД|TRADE|ТОРГ|ТОРГОВ|ДИСТРИБ|DISTRIB)", re.I)
GROUPW = re.compile(r"(ГРУП|GROUP|ХОЛДИНГ|HOLDING|КОРПОРАЦ)", re.I)
LEGAL = re.compile(r"(ТОВАРИСТВО З ОБМЕЖЕНОЮ ВІДПОВІДАЛЬНІСТЮ|ПРИВАТНЕ ПІДПРИЄМСТВО|ПРИВАТНЕ АКЦІОНЕРНЕ ТОВАРИСТВО|"
                   r"ПУБЛІЧНЕ АКЦІОНЕРНЕ ТОВАРИСТВО|ТОВ|ПП|ПРАТ|ПАТ|ФОП|ВИРОБНИЧО|ФАБРИКА|МЕБЛЕВА|МЕБЛІ)", re.I)


def num(x):
    try:
        return float(str(x).replace(",", ".").strip())
    except ValueError:
        return None


def stem(name):
    s = re.sub(r"[\"'«»“”]", " ", name.upper())
    s = LEGAL.sub(" ", s)
    w = [t for t in re.split(r"\W+", s) if len(t) > 2 and not TRADE.fullmatch(t)]
    return w[0] if w else None


def score(r, lo, hi, prio):
    emp, rev24, rev25 = num(r["employees"]), num(r["rev_2024"]), num(r["rev_2025"])
    size = 1.0 if emp is not None and lo <= emp <= hi else 0.0   # поруч (±1 розряд) = 0.5 — поза межами скрипта
    raw = (rev25 / rev24 - 1) if rev24 and rev24 > 0 and rev25 is not None else None
    dyn = 0.0 if raw is None else (max(-CLIP, min(CLIP, raw)) + CLIP)
    compl = 1.0 if str(r.get("kved_ambig", "0")) in ("0", "") and emp is not None and r.get("region") else 0.0
    reg = 1.0 if prio and r.get("region") == prio else 0.0
    s = round(W["size"] * size + W["dyn"] * dyn + W["compl"] * compl + W["region"] * reg, 3)
    return s, raw, rev25 or 0.0


def main():
    a = argparse.ArgumentParser()
    a.add_argument("csv"); a.add_argument("--lo", type=float, required=True); a.add_argument("--hi", type=float, required=True)
    a.add_argument("--priority-region", default=""); a.add_argument("--top", type=int, default=6)
    a.add_argument("--snapshot", default="YYYY-MM")
    o = a.parse_args()
    rows = list(csv.DictReader(open(o.csv, encoding="utf-8")))
    for r in rows:
        r["score"], r["raw"], r["rev"] = score(r, o.lo, o.hi, o.priority_region)
    # Детермінований порядок: бал ↓, виручка 2025 ↓, зростання (необрізане) ↓, ЄДРПОУ ↑
    rows.sort(key=lambda r: (-r["score"], -r["rev"], -(r["raw"] if r["raw"] is not None else -9e9), r["code"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    stems = Counter(stem(r["name"]) for r in rows if stem(r["name"]))
    for r in rows:
        f = []
        if r["raw"] is not None and r["raw"] > JUMP:
            f.append(f"стрибок виручки {r['raw']*100:+.0f} % за рік")
        if TRADE.search(r["name"]):
            f.append("торгова роль у назві")
        if GROUPW.search(r["name"]) or (stem(r["name"]) and stems[stem(r["name"])] > 1):
            f.append("можлива група компаній")
        r["flags"] = f
    N, top = len(rows), rows[: o.top]
    print("| Ранг | ЄДРПОУ | Бал | Виручка 2025 | Зростання | Позначки |\n|---|---|---|---|---|---|")
    for r in top:
        g = "н/д" if r["raw"] is None else f"{r['raw']*100:+.0f} %"
        fl = "; ".join(f"перевірити Sales: {x}" for x in r["flags"]) or "—"
        print(f"| {r['rank']} | {r['code']} | {r['score']:.3f} | {r['rev']:.0f} [odb {o.snapshot}] | {g} [odb {o.snapshot}] | {fl} |")
    clipped = [r for r in rows if r["raw"] is not None and r["raw"] >= CLIP]
    clipped_top = [r for r in top if r["raw"] is not None and r["raw"] >= CLIP]
    print("\n### Якість даних")
    print(f"- Динаміку обрізано до +{CLIP*100:.0f} %: {len(clipped)} з {N} компаній пулу, {len(clipped_top)} з {len(top)} у шортлісті "
          f"(у балі їм усім 1.0 за компонент; фактичне зростання — у колонці «Зростання»).")
    print(f"- Без динаміки (немає обох років): {sum(r['raw'] is None for r in rows)} з {N}.")
    print(f"- Аномалії (позначка «перевірити Sales», без виключення): {sum(bool(r['flags']) for r in rows)} з {N}.")
    groups = Counter(r["score"] for r in rows)
    cut = top[-1]["score"] if top else None
    k = groups[cut] if cut is not None else 0
    if k >= 3:
        tied = [r for r in rows if r["score"] == cut]
        print(f"\nWARN: бал не розрізняє: {k} з {N} рівні (бал {cut:.3f}) — ваги не затверджено "
              "(рішення q39: ваги затверджує Керівник напряму після першого запуску). "
              "Порядок усередині рівних — детермінований: виручка 2025 ↓, потім зростання ↓, потім ЄДРПОУ ↑.")
        print("\n| Ранг | ЄДРПОУ | Виручка 2025 | Зростання | У шортлісті |\n|---|---|---|---|---|")
        for r in tied:
            g = "н/д" if r["raw"] is None else f"{r['raw']*100:+.0f} %"
            print(f"| {r['rank']} | {r['code']} | {r['rev']:.0f} | {g} | {'так' if r['rank'] <= o.top else 'ні'} |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
