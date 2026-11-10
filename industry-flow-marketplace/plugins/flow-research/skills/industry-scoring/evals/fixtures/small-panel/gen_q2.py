#!/usr/bin/env python3
"""Генерує синтетичний small-panel/Q2.json (stdlib, детерміновано): усі розділи довідника, крім виключених 84,97,98,99
і відсутніх 29, 61; у одного розділу топ-10 панель = 10.
Використання: python3 -I gen_q2.py <тека small-panel> <references/>"""
import json, random, re, sys
from pathlib import Path
d = Path(sys.argv[1]); ref = Path(sys.argv[2]); r = random.Random(7)
t = (ref / "kved-2010-sections.md").read_text(encoding="utf-8").split("## Код → назва розділу", 1)[-1]
codes = [c for c in sorted(set(re.findall(r"^\| (\d\d) \|", t, re.M))) if c not in {"84", "97", "98", "99", "29", "61"}]
q2 = []
for c in codes:
    base = r.randint(10**8, 10**11); q2.append({"sec": c, "companies": r.randint(300, 9000), "revenue": base * 2,
        "r_last": int(base * r.uniform(1.0, 1.9)), "r_base": base, "panel_n": r.randint(100, 3000)})
mm = lambda k: {x["sec"]: (x[k] - min(y[k] for y in q2)) / (max(y[k] for y in q2) - min(y[k] for y in q2)) for x in q2}
n = [mm("companies"), mm("revenue"), {x["sec"]: (x["r_last"] / x["r_base"] - 1) for x in q2}]
g = n[2]; lo, hi = min(g.values()), max(g.values()); n[2] = {k: (v - lo) / (hi - lo) for k, v in g.items()}
rank = sorted(codes, key=lambda s: -(.4 * n[0][s] + .4 * n[1][s] + .2 * n[2][s]))
for x in q2:
    if x["sec"] == rank[6]:
        x["panel_n"] = 10
json.dump(q2, open(d / "Q2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("top-10:", rank[:10], "панель 10 у", rank[6])
