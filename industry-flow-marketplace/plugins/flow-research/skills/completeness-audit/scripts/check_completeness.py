#!/usr/bin/env python3
"""Автоперевірки A-20b (CA-*) для research/AI-DECISIONS.md (розділ «Повнота»). stdlib. Вивід: JSON [{id,status,msg}]; код виходу 1, якщо є FAIL.
Використання: check_completeness.py <research/AI-DECISIONS.md> [--rounds N]
CA-sections  — є розділи «## Рішення» і «## Повнота …».
CA-checklist — у «Повнота» рівно 14 пунктів (№ 1..14); статус кожного: закрито | ризик.
CA-sum       — якщо є рядок «Підсумок: closed=a, risk=b», він дорівнює підрахунку статусів (числа йдуть у звіт `completeness`); немає рядка — WARN.
CA-gaps      — «Рішення»: ID `AI-\\d{2}` унікальні, ≤15 рядків; кожен пункт зі статусом «ризик» посилається в колонці «Де / AI-NN» на існуючий AI-NN
               (незакрите -> рядок AI-NN «ризик, перевірити на пілоті»).
CA-money     — у файлі немає грошових маркерів (окупн, TCO, вартість володіння, business-case/бізнес-кейс, вердикт про гроші, ROI, беззбитков, ставка розробки,
               годин × ставк).
CA-rounds    — коло критика ≤1: рядок «Коло критика: N» у «Повнота» (або --rounds N); N>1 — FAIL; не вказано — WARN."""
import argparse, json, re, sys
from pathlib import Path

res = []
ST = ("закрито", "ризик")
MONEY = re.compile(r"окупн|\bTCO\b|вартість\s+володіння|business[- ]case|бізнес-кейс|вердикт\s+про\s+гроші|\bROI\b|беззбитков|ставк\w*\s+розробки|годин.{0,20}(×|x|\*).{0,10}ставк", re.I)
MONEY_SKIP = re.compile(r"REJ-\d{3}|https?://")  # як в autocheck.py: рядок реєстру відкинутого і цитата з URL не рахуються


def add(i, ok, msg="", status=None):
    res.append({"id": i, "status": status or ("PASS" if ok else "FAIL"), "msg": "" if ok else msg})


def split_sections(t):
    out = {}
    for m in re.finditer(r"^##\s+([^\n]*)\n(.*?)(?=^##\s|\Z)", t, flags=re.M | re.S):
        out[m.group(1).strip()] = m.group(2)
    return out


def find(secs, word):
    for k, v in secs.items():
        if k.lower().startswith(word): return v
    return None


def table(sec):
    rows = [[c.strip() for c in l.strip().strip("|").split("|")] for l in sec.splitlines()
            if l.startswith("|") and not re.match(r"^\|[\s:|-]+\|$", l)]
    return (rows[0], rows[1:]) if rows else ([], [])


def status(v):
    v = v.strip().lower()
    for s in ST:
        if v.startswith(s): return s
    return None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("file"); ap.add_argument("--rounds", type=int); a = ap.parse_args()
    p = Path(a.file)
    if not p.exists():
        add("CA-sections", False, f"немає {a.file}"); print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    t = p.read_text(encoding="utf-8"); secs = split_sections(t)
    dec, full = find(secs, "рішення"), find(secs, "повнота")
    miss = [n for n, v in (("Рішення", dec), ("Повнота", full)) if v is None]
    add("CA-sections", not miss, f"немає розділів: {miss}")
    if miss:
        print(json.dumps(res, ensure_ascii=False, indent=1)); sys.exit(1)
    # CA-gaps (частина 1): реєстр AI-NN
    h2, r2 = table(dec); ids = []; why = []
    for r in r2:
        if not r or not r[0]: continue
        if not re.match(r"^AI-\d{2}$", r[0]): why.append(f"ID «{r[0]}» не AI-NN"); continue
        if r[0] in ids: why.append(f"дубль {r[0]}")
        ids.append(r[0])
    if len(ids) > 15: why.append(f"рядків «Рішення» {len(ids)} > 15")
    # CA-checklist, CA-sum
    h1, r1 = table(full); cnt = {s: 0 for s in ST}; bad = []; nums = []
    for r in r1:
        if not r or not r[0].strip().isdigit(): continue
        nums.append(int(r[0]))
        s = status(r[2]) if len(r) > 2 else None
        if s is None: bad.append(f"№{r[0]}: статус «{r[2] if len(r) > 2 else ''}»")
        else:
            cnt[s] += 1
            if s == "ризик":
                refs = re.findall(r"AI-\d{2}", r[3] if len(r) > 3 else "")
                if not refs: why.append(f"№{r[0]}: ризик без AI-NN у колонці «Де / AI-NN»")
                elif set(refs) - set(ids): why.append(f"№{r[0]}: {sorted(set(refs) - set(ids))} немає в «Рішення»")
    add("CA-gaps", not why, "; ".join(why[:8]))
    w2 = []
    if sorted(nums) != list(range(1, 15)): w2.append(f"пунктів чек-листа {len(nums)}, потрібні №1..14 без пропусків і дублів")
    w2 += bad
    add("CA-checklist", not w2, "; ".join(w2[:8]))
    m = re.search(r"closed\s*=\s*(\d+)\s*,\s*risk\s*=\s*(\d+)", full)
    if not m: res.append({"id": "CA-sum", "status": "WARN", "msg": "немає рядка «Підсумок: closed=a, risk=b» (допиши: числа йдуть у звіт completeness)"})
    else:
        got = tuple(map(int, m.groups())); exp = (cnt["закрито"], cnt["ризик"])
        add("CA-sum", got == exp, f"підсумок {got} ≠ підрахунок таблиці {exp}")
    # CA-money
    hit = sorted({x.group(0).lower() for ln in t.splitlines() if not MONEY_SKIP.search(ln) for x in MONEY.finditer(ln)})
    add("CA-money", not hit, f"грошові маркери у файлі: {hit}")
    # CA-rounds
    n = a.rounds
    if n is None:
        mr = re.search(r"Коло критика\s*:\s*(\d+)", full)
        n = int(mr.group(1)) if mr else None
    if n is None: res.append({"id": "CA-rounds", "status": "WARN", "msg": "не вказано «Коло критика: N» (≤1)"})
    else: add("CA-rounds", n <= 1, f"кіл критика {n} > 1")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)


main()
