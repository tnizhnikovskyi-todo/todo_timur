#!/usr/bin/env python3
"""Збирає з фікстур еталонні expected-scoring.md, expected-top10.json і metrics.json (stdlib).
Використання: python3 -I build_expected.py <тека фікстур> <тека kved-довідника references/>"""
import json, re, sys
from pathlib import Path
d = Path(sys.argv[1]); ref = Path(sys.argv[2])
J = lambda n: json.load(open(d / n, encoding="utf-8"))
EX = {"84", "97", "98", "99"}
names = dict(re.findall(r"^\| (\d\d) \| (.+?) \|$", (ref / "kved-2010-sections.md").read_text(encoding="utf-8"), re.M))
co = {x["sec"]: x["companies"] for x in J("Q2.json") if x["sec"] not in EX}
rv = {x["sec"]: x["revenue"] for x in J("Q3.json") if x["sec"] not in EX}
gr = {x["sec"]: x["r_last"] / x["r_base"] - 1 for x in J("Q4.json") if x["sec"] not in EX}
mm = lambda m: {k: (v - min(m.values())) / (max(m.values()) - min(m.values())) for k, v in m.items()}
n = {"companies": mm(co), "revenue": mm(rv), "growth": mm(gr)}
sc = {s: .4 * n["companies"][s] + .4 * n["revenue"][s] + .2 * n["growth"][s] for s in co}
rank = sorted(sc, key=lambda s: -sc[s])
sol = {x["sec"]: x for x in J("search-results.json")}
(d / "metrics.json").write_text(json.dumps({"companies": co, "revenue": rv, "growth": gr}, ensure_ascii=False), encoding="utf-8")
(d / "expected-top10.json").write_text(json.dumps(rank[:10]), encoding="utf-8")
T = "[odb 2026-08]"; D = "2026-11-09"
def row(i, s, mkt):
    return f"| {i} | {s} | {names[s]} | {co[s]} {T} | {rv[s]/1e6:.1f} {T} | {gr[s]*100:.1f} {T} | " + (mkt + " | " if mkt is not None else "") + f"{sc[s]:.3f} |"
top = [row(i + 1, s, (sol[s]["vendor"] + " (див. джерела)") if s in sol else f"не знайдено ({D})") for i, s in enumerate(rank[:10])]
full = [row(i + 1, s, None) for i, s in enumerate(rank)]
src = [f"| {s} | {sol[s]['vendor']} | {sol[s]['url']} | {sol[s]['date']} |" if s in sol else f"| {s} | не знайдено | — | {D} |" for s in rank[:10]]
sq = "\n".join(f"### Q{i}\nSELECT ... WHERE has_financials=1 AND kved_2010 NOT IN ('84','97','98','99') -- фікстура Q{i}.json" for i in (1, 2, 3, 4, 5))
sq = sq.replace("### Q1\nSELECT ... WHERE has_financials=1 AND kved_2010 NOT IN ('84','97','98','99')", "### Q1\nSELECT year, COUNT(*) FROM fin_history GROUP BY year")
H = "| ранг | КВЕД-2010 (розділ) | назва розділу | компаній (Q2) | виручка 2025, млн грн (Q3) | зростання 2021→2025, % (панель) (Q4) |"
out = f"""# Скоринг галузей (A-01)

Запуск: {D}, наряд фікстура, режим: перший запуск.

## Знімок даних
- Джерело: odb-catalog (`has_financials=1`), знімок реєстру: 2026-08 (дата взята з: вхід наряду; не db_schema).
- Покриття fin_history за роками (Q1): 2020 → 653, 2021 → 298082, 2022 → 301613, 2023 → 9451, 2024 → 338611, 2025 → 347721.
- Рівень групування: розділ КВЕД-2010, 2 знаки. Останній рік виручки: 2025. Базовий рік зростання: 2021.

## Критерій ранжування
> {(d/'param.txt').read_text(encoding='utf-8').strip()}

Затвердив: Власник продукту, 2026-11-01. Виключені розділи: 84, 97, 98, 99. Джерело: `flow/decisions.md@abc1234`.

## Топ-10
{H} рішення на ринку | бал |
|---|---|---|---|---|---|---|---|
""" + "\n".join(top) + f"""

## Повний рейтинг
{H} бал |
|---|---|---|---|---|---|---|
""" + "\n".join(full) + """

## Рішення на ринку: джерела
| розділ | рішення | URL | дата перевірки |
|---|---|---|---|
""" + "\n".join(src) + """

## Якість даних і обмеження
- Дірки покриття: 2020 (653 рядки) і 2023 (9451 рядок) не придатні для порівняння, тому зростання рахується від 2021 по панелі компаній.
- Частка kved_ambig=1 за Q5 подана у відповідях запиту. Розділи з малою кількістю компаній потребують обережності.
- Дата знімка взята з входу наряду, не з даних. Рейтинг не є рекомендацією: рішення A-02 за Власником продукту.
- Відкриті питання до людини: немає.

## SQL-запити
""" + sq + """

## Зміни відносно попереднього знімка
перший запуск
"""
(d / "expected-scoring.md").write_text(out, encoding="utf-8")
print(rank[:10])
