#!/usr/bin/env python3
"""Детермінована перевірка глибини A-03b. stdlib. Вивід: JSON [{id,status,msg}]. Код виходу 1, якщо є FAIL.
Використання: check_depth.py <research/subsegments-deep.md> [--features research/competitor-features.md] [--profiles research/competitors/]
  DEPTH-subseg   — кожен підсегмент (заголовок ## ) має ≥10 підрозділів (заголовки ###) АБО рядок «рішення неможливе: <причина ≥10 символів>»; 0 підсегментів = FAIL.
                   Назви підрозділів не перевіряються (їх змістовність — ручна перевірка рецензента).
  DEPTH-matrix   — з --features: рядків матриці (таблиця, перша клітинка — ID на кшталт F-NN/M-NN, не заголовок) 60–100; поза межами = FAIL.
  DEPTH-profiles — з --profiles: файлів competitors/*.md 8–12; поза межами = FAIL.
Евристика кількості, не доказ змісту: порожні підрозділи ловить ручна перевірка.
"""
import json, re, sys
from pathlib import Path

res = []
def add(i, s, m=""):
    res.append({"id": i, "status": s, "msg": m})

def main():
    a = sys.argv[1:]
    opt = {}
    for k in ("--features", "--profiles"):
        if k in a:
            j = a.index(k)
            opt[k] = a[j + 1] if j + 1 < len(a) else ""
            del a[j:j + 2]
    if len(a) != 1:
        print(__doc__); sys.exit(2)
    p = Path(a[0])
    if not p.exists():
        add("DEPTH-subseg", "FAIL", f"немає файла {p}")
    else:
        secs, cur = [], None
        for l in p.read_text(encoding="utf-8").splitlines():
            if re.match(r"##\s+\S", l) and not l.startswith("###"):
                cur = {"name": l.lstrip("# ").strip(), "h3": 0, "na": False}
                secs.append(cur)
            elif cur is not None:
                if re.match(r"###\s+\S", l):
                    cur["h3"] += 1
                if re.search(r"рішення неможливе:\s*\S.{9,}", l, re.I):
                    cur["na"] = True
        bad = [f"«{s['name']}»: {s['h3']} підрозділів із 10" for s in secs if s["h3"] < 10 and not s["na"]]
        if not secs:
            add("DEPTH-subseg", "FAIL", "немає жодного підсегмента (заголовок ##)")
        else:
            add("DEPTH-subseg", "FAIL" if bad else "PASS", "; ".join(bad))
    if "--features" in opt:
        fp = Path(opt["--features"])
        if not fp.exists():
            add("DEPTH-matrix", "FAIL", f"немає файла {fp}")
        else:
            n = 0
            for l in fp.read_text(encoding="utf-8").splitlines():
                l = l.strip()
                if l.startswith("|") and not re.match(r"^\|[\s:|-]+\|$", l):
                    c = l.strip("|").split("|")[0].strip("` *")
                    if re.fullmatch(r"[A-Za-zА-Яа-я]{1,3}-\d{1,3}", c):
                        n += 1
            add("DEPTH-matrix", "PASS" if 60 <= n <= 100 else "FAIL", "" if 60 <= n <= 100 else f"рядків матриці {n}, треба 60–100")
    if "--profiles" in opt:
        d = Path(opt["--profiles"])
        n = len(list(d.glob("*.md"))) if d.is_dir() else -1
        if n < 0:
            add("DEPTH-profiles", "FAIL", f"немає теки {d}")
        else:
            add("DEPTH-profiles", "PASS" if 8 <= n <= 12 else "FAIL", "" if 8 <= n <= 12 else f"профілів {n}, треба 8–12")
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sys.exit(1 if any(r["status"] == "FAIL" for r in res) else 0)

main()
