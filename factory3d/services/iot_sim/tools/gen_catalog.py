#!/usr/bin/env python3
"""Генерує catalog/signals.csv і data/td_sim_signal.csv Odoo-модуля з Додатка A SPEC.

  python tools/gen_catalog.py          # згенерувати обидва файли
  python tools/gen_catalog.py --check  # звірити файли з Додатком A (код виходу 0/1)

Якщо SPEC недоступний (наприклад, у Docker-образі), --check лише порівнює два CSV між собою.
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
SERVICE_DIR = HERE.parents[1]
FACTORY3D = HERE.parents[3]
SPEC = FACTORY3D / "docs/modules/td_iot_sim/SPEC.md"
SIGNALS_CSV = SERVICE_DIR / "catalog/signals.csv"
ODOO_CSV = FACTORY3D / "odoo_addons/td_iot_sim/data/td_sim_signal.csv"

COLUMNS = ["n", "code", "device", "protocol", "address", "dtype", "unit", "scale",
           "nominal", "thresholds", "model", "status"]
EXPECTED_ROWS = 1168
ROW_RE = re.compile(r"^\| (\d+) \|")


def _cell(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s.startswith("`") and s.endswith("`") and s.count("`") == 2:
        s = s[1:-1]
    return s


def parse_spec(path: Path = SPEC) -> list[list[str]]:
    """Рядки таблиці Додатка A: [№, код, пристрій, P-xx, адреса, тип, одиниця, масштаб, номінал, пороги, модель, статус]."""
    text = path.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(text) if ln.startswith("## Додаток A."))
    rows: list[list[str]] = []
    for ln in text[start:]:
        if ln.startswith("*Кінець Додатка A"):
            break
        if not ROW_RE.match(ln):
            continue
        cells = [_cell(c) for c in ln.strip().strip("|").split(" | ")]
        if len(cells) != len(COLUMNS):
            raise SystemExit(f"Додаток A: очікувалось {len(COLUMNS)} колонок, отримано {len(cells)}: {ln[:80]}")
        rows.append(cells)
    return rows


def write_csv(path: Path, rows: list[list[str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(COLUMNS)
        w.writerows(rows)


def read_csv(path: Path) -> list[list[str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.reader(f))[1:]


def check() -> int:
    ok = True
    for p in (SIGNALS_CSV, ODOO_CSV):
        if not p.is_file():
            print(f"ПОМИЛКА: немає {p}", file=sys.stderr)
            return 1
    a, b = read_csv(SIGNALS_CSV), read_csv(ODOO_CSV)
    if a != b:
        print("ПОМИЛКА: signals.csv і td_sim_signal.csv розходяться", file=sys.stderr)
        ok = False
    if SPEC.is_file():
        spec = parse_spec()
        if len(spec) != EXPECTED_ROWS:
            print(f"ПОМИЛКА: у Додатку A {len(spec)} рядків, очікувалось {EXPECTED_ROWS}", file=sys.stderr)
            ok = False
        if spec != a:
            print("ПОМИЛКА: signals.csv не збігається з Додатком A (запустіть gen_catalog.py)", file=sys.stderr)
            ok = False
    else:
        print("SPEC недоступний — звірено лише два CSV між собою")
    codes = [r[1] for r in a]
    if len(set(codes)) != len(codes):
        print("ПОМИЛКА: дублікати кодів сигналів", file=sys.stderr)
        ok = False
    if ok:
        print(f"OK: {len(a)} сигналів")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="лише звірити, нічого не писати")
    args = ap.parse_args()
    if args.check:
        return check()
    rows = parse_spec()
    write_csv(SIGNALS_CSV, rows)
    write_csv(ODOO_CSV, rows)
    print(f"записано {len(rows)} сигналів: {SIGNALS_CSV}, {ODOO_CSV}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
