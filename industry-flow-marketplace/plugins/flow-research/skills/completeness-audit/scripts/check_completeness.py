#!/usr/bin/env python3
"""Автоперевірки A-20b (CA-*) для research/COMPLETENESS.md. stdlib. Вивід: JSON [{id,status,msg}]; код виходу 1, якщо є FAIL.
Використання: check_completeness.py <research/COMPLETENESS.md> [--brief research/OWNER-BRIEF.md]
CA-sections — розділи §1-4 шаблону COMPLETENESS.tpl.md.
CA-checklist — у §1 рівно 22 пункти (№ 1..22), статус кожного: закрито | частково | відкрито.
CA-sum — рядок «Підсумок: closed=a, partial=b, open=c» дорівнює підрахунку статусів §1 (ці числа йдуть у звіт `completeness`).
CA-gaps — §2: ID `G-\\d{2}` унікальні; пріоритет P1|P2|P3; тип desk|human|decision; непорожні «прогалина» і «дія»;
          посилання G-xx у колонці «Прогалини» §1 існують у §2.
CA-p1 — прогалина P1 типу desk зі статусом у §4 не «закрито» — FAIL (бракує рядка в §4 — теж FAIL).
CA-rounds — §4: «Коло» ∈ {1,2}; кола 3+ немає (ліміт: до 2 кіл фінального критика).
CA-owner — з --brief: кожна незакрита прогалина (статус §4 або §2 ≠ закрито) названа за ID `G-xx` в OWNER-BRIEF («відкриті питання») — інакше FAIL."""
import argparse, json, re, sys
from pathlib import Path

res = []
ST = ("закрито", "частково", "відкрито")


def add(i, ok, msg="", status=None):
    res.append({"id": i, "status": status or ("PASS" if ok else "FAIL"), "msg": "" if ok else msg})


def sections(t):
    out = {}
    for m in re.finditer(r"^##\s+(\d+)\.[^\n]*\n(.*?)(?=^##\s+\d+\.|\Z)", t, flags=re.M | re.S):
        out[int(m.group(1))] = m.group(2)
    return out


def table(sec):
    rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in sec.splitlines()
            if l.startswith("|") and not re.match(r"^\|[\s:|-]+\|$", l)]
    return (rows[0], rows[1:]) if rows else ([], [])


def status(v):
    v = v.strip().lower()
    for s in ST:
        if v.startswith(s):
            return s
    return None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("file"); ap.add_argument("--brief"); a = ap.parse_args()
    p = Path(a.file)
    if not p.exists():
        add("CA-sections", False, f"немає {a.file}"); print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    t = p.read_text(encoding="utf-8"); sec = sections(t)
    miss = [n for n in (1, 2, 3, 4) if n not in sec]
    add("CA-sections", not miss, f"немає розділів §{miss}")
    if miss:
        print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    # CA-checklist, CA-sum
    h1, r1 = table(sec[1]); cnt = {s: 0 for s in ST}; bad = []; nums = []
    for r in r1:
        if not r or not r[0].strip().isdigit():
            continue
        nums.append(int(r[0]))
        s = status(r[2]) if len(r) > 2 else None
        if s is None: bad.append(f"№{r[0]}: статус «{r[2] if len(r) > 2 else ''}»")
        else: cnt[s] += 1
    why = []
    if sorted(nums) != list(range(1, 23)): why.append(f"пунктів чек-листа {len(nums)}, потрібні №1..22 без пропусків і дублів")
    why += bad
    add("CA-checklist", not why, "; ".join(why[:8]))
    m = re.search(r"closed\s*=\s*(\d+)\s*,\s*partial\s*=\s*(\d+)\s*,\s*open\s*=\s*(\d+)", sec[1])
    if not m: add("CA-sum", False, "немає рядка «Підсумок: closed=a, partial=b, open=c»")
    else:
        got = tuple(map(int, m.groups())); exp = (cnt["закрито"], cnt["частково"], cnt["відкрито"])
        add("CA-sum", got == exp, f"підсумок {got} ≠ підрахунок таблиці {exp}")
    # CA-gaps
    h2, r2 = table(sec[2]); gaps = {}; why = []
    for r in r2:
        if not r or not re.match(r"^G-\d{2}$", r[0]):
            if r and r[0]: why.append(f"ID «{r[0]}» не G-NN")
            continue
        if len(r) < 8: why.append(f"{r[0]}: менше 8 колонок"); continue
        if r[0] in gaps: why.append(f"дубль {r[0]}")
        if r[1] not in ("P1", "P2", "P3"): why.append(f"{r[0]}: пріоритет «{r[1]}»")
        if r[2] not in ("desk", "human", "decision"): why.append(f"{r[0]}: тип «{r[2]}»")
        if not r[4] or not r[5]: why.append(f"{r[0]}: порожня прогалина або дія")
        gaps[r[0]] = r
    refs = set(re.findall(r"G-\d{2}", "\n".join(" ".join(r[6:]) for r in r1 if len(r) > 6)))
    if refs - set(gaps): why.append(f"у §1 згадано G, яких немає в §2: {sorted(refs - set(gaps))}")
    add("CA-gaps", not why, "; ".join(why[:8]))
    # CA-p1, CA-rounds
    h4, r4 = table(sec[4]); st4 = {}; rounds = []; why = []
    for r in r4:
        if r and re.match(r"^G-\d{2}$", r[0]) and len(r) >= 3:
            st4[r[0]] = status(r[2]) or "відкрито"
            if len(r) >= 6 and r[5].strip():
                rounds.append((r[0], r[5].strip()))
    for g, r in gaps.items():
        if r[1] == "P1" and r[2] == "desk":
            if g not in st4: why.append(f"{g}: P1 desk без рядка в §4")
            elif st4[g] != "закрито": why.append(f"{g}: P1 desk не закрито ({st4[g]})")
    add("CA-p1", not why, "; ".join(why))
    badr = [f"{g}: коло «{c}»" for g, c in rounds if c not in ("1", "2")]
    add("CA-rounds", not badr, "; ".join(badr))
    # CA-owner
    if not a.brief: res.append({"id": "CA-owner", "status": "SKIP", "msg": "немає --brief"})
    else:
        bp = Path(a.brief)
        if not bp.exists(): add("CA-owner", False, f"немає {a.brief}")
        else:
            brief = bp.read_text(encoding="utf-8")
            open_g = sorted(g for g in gaps if st4.get(g, status(gaps[g][7]) if len(gaps[g]) > 7 else "відкрито") != "закрито")
            lost = [g for g in open_g if g not in brief]
            add("CA-owner", not lost, f"незакриті прогалини не названі в OWNER-BRIEF: {lost}")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)


main()
