"""Генератор `data/mc_machines.csv` (SPEC Додаток A). Запуск: `python3 tools/gen_mc_data.py` з каталогу модуля.

Розкладка I/O = iot_sim §8.4.2 (4 модулі ADAM × 5 позицій), оператори — base Додаток B (без: SAW-3, VSAW-1, EDGE-3,
SORT-1, DRY-1, UV-1, ASM-5). Без залежностей від Odoo.
"""

import csv
import sys
from pathlib import Path

HEADER = ["code", "protocol", "source", "io_unit", "io_slot", "auto_start_mode", "operator_code"]
OPCUA = [
    "SAW-1", "SAW-2", "SAW-3", "NEST-1", "EDGE-1", "EDGE-2", "EDGE-3", "CNC-1", "CNC-2", "CNC-3", "CNC-4",
    "BORE-1", "DOWEL-1", "SORT-1", "ASMLINE-1",
]  # fmt: skip
IO_MODULES = [
    ("MB-U80-IO1", 80, ["SLIDE-1", "VSAW-1", "SAND-1", "PRESS-1", "GLUE-1"]),
    ("MB-U81-IO2", 81, ["SPRAY-1", "AUTOSPRAY-1", "DRY-1", "UV-1", "HINGE-1"]),
    ("MB-U82-IO3", 82, ["BOX-1", "PACK-1", "PACK-2", "PACKLINE-1", "ASM-1"]),
    ("MB-U83-IO4", 83, ["ASM-2", "ASM-3", "ASM-4", "ASM-5", "ASM-6"]),
]  # fmt: skip
NO_OPERATOR = {"SAW-3", "VSAW-1", "EDGE-3", "SORT-1", "DRY-1", "UV-1", "ASM-5"}


def rows():
    for code in OPCUA:
        yield [code, "opcua", "UA-" + code, "", "", "job_or_single", "" if code in NO_OPERATOR else "OP-" + code]
    for source, unit, codes in IO_MODULES:
        for slot, code in enumerate(codes):
            op = "" if code in NO_OPERATOR else "OP-" + code
            yield [code, "io", source, unit, slot, "job_or_single", op]


def main(path=None):
    path = Path(path) if path else Path(__file__).resolve().parent.parent / "data" / "mc_machines.csv"
    with open(path, "w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(HEADER)
        writer.writerows(rows())


if __name__ == "__main__":
    main(*sys.argv[1:2])
