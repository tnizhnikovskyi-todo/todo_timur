#!/usr/bin/env python3
"""Генерує catalog/evac_routes.json для сценарію ``fire_evacuation`` (S-24).

  python tools/gen_evac_catalog.py          # згенерувати файл
  python tools/gen_evac_catalog.py --check  # звірити файл з plant/evac_routes.json і model_static.json (код 0/1)

Звідки дані (образ емулятора не бачить plant/ і Odoo, тому каталог лежить поруч зі сценарієм):

* ``exits`` і ``routes`` — ``factory3d/plant/evac_routes.json`` (виходи EX-*, маршрути зон: вихід, довжина, шлях);
* ``operators`` — ``barcode`` працівника (``OPSAW1`` = ``OP-SAW-1`` без дефісів) -> зона: оператор ``OP-<РЦ>`` у зоні
  свого робочого центра (``model_static.json``, ``zones[*].workcenters``), ``OP-W1…W7`` — домашні зони СКУД
  (``td_access/data/scene_home_zones.csv``);
* ``doors`` — код виходу -> ``door_id`` BioStar: ``EX-IN`` — турнікет ``1``; аварійні виходи — ``11…21``
  (двері створює міст ``td_fire_safety_access``, їхні ``biostar_id`` мають збігатися);
* ``readers_zone`` і ``dwell_min`` — зона технічних дверей (ACR-ELEC → Z-ELEC …) і скільки хвилин людина там лишається.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
SERVICE_DIR = HERE.parents[1]
FACTORY3D = HERE.parents[3]
PLANT = FACTORY3D / "plant/evac_routes.json"
STATIC = FACTORY3D / "odoo_addons/td_viewer3d/static/data/model_static.json"
HOME = FACTORY3D / "odoo_addons/td_access/data/scene_home_zones.csv"
OUT = SERVICE_DIR / "catalog/evac_routes.json"

OPERATORS = [
    "OP-SAW-1",
    "OP-SAW-2",
    "OP-SLIDE-1",
    "OP-NEST-1",
    "OP-EDGE-1",
    "OP-EDGE-2",
    "OP-CNC-3",
    "OP-CNC-1",
    "OP-CNC-2",
    "OP-BORE-1",
    "OP-CNC-4",
    "OP-DOWEL-1",
    "OP-SAND-1",
    "OP-AUTOSPRAY-1",
    "OP-HINGE-1",
    "OP-GLUE-1",
    "OP-PRESS-1",
    "OP-SPRAY-1",
    "OP-ASMLINE-1",
    "OP-ASM-1",
    "OP-ASM-2",
    "OP-ASM-3",
    "OP-ASM-4",
    "OP-ASM-6",
    "OP-PACK-1",
    "OP-PACK-2",
    "OP-BOX-1",
    "OP-PACKLINE-1",
]
DOOR_FIRST = 11  # аварійні виходи в порядку plant/evac_routes.json: EX-S1…EX-N4 -> 11…21
# зона, у якій людина перебуває `DWELL_MIN` хв після проходу технічними дверима
# (td_access/data/td_access_device_data.xml: `zone_to_id` і `dwell_min` дверей DOOR-ELEC, DOOR-CHG, DOOR-PAINT,
# DOOR-SRV; повернення в домашню зону — access R-17)
READERS_ZONE = {"ACR-ELEC": "Z-ELEC", "ACR-CHG": "Z-CHG", "ACR-PAINT": "Z-FAC", "ACR-SRV": "Z-MAINT"}
DWELL_MIN = 30


def build() -> dict:
    plant = json.loads(PLANT.read_text(encoding="utf-8"))
    static = json.loads(STATIC.read_text(encoding="utf-8"))
    wc_zone = {wc: zone for zone, v in static["zones"].items() for wc in v.get("workcenters", [])}
    exits, doors, n = {}, {}, DOOR_FIRST
    for e in plant["exits"]:
        exits[e["code"]] = {"x": e["x"], "y": e["y"], "side": e["side"]}
        if e["code"] == "EX-IN":
            doors[e["code"]] = "1"
        else:
            doors[e["code"]] = str(n)
            n += 1
    routes = {
        zone: {"exit": r["exit"], "length": r["length"], "path": r["path"]} for zone, r in plant["routes"].items()
    }
    operators = {c.replace("-", ""): wc_zone[c[3:]] for c in OPERATORS}
    with HOME.open(encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            operators[row["code"].replace("-", "")] = row["zone"]
    return {
        "exits": exits,
        "doors": doors,
        "routes": routes,
        "operators": dict(sorted(operators.items())),
        "readers_zone": READERS_ZONE,
        "dwell_min": DWELL_MIN,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    text = json.dumps(build(), ensure_ascii=False, indent=1) + "\n"
    if args.check:
        ok = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("OK" if ok else "catalog/evac_routes.json застарів: запустіть tools/gen_evac_catalog.py")
        return 0 if ok else 1
    OUT.write_text(text, encoding="utf-8")
    print(f"{OUT.relative_to(FACTORY3D)}: {len(text)} байт")
    return 0


if __name__ == "__main__":
    sys.exit(main())
