"""Сідинг стенду: 35 працівників зі штрих-кодами сцени (SPEC §13.2 ТК-01), домашні зони, демо-відмітки 12.10."""
from __future__ import annotations

# (зона, префікс штрих-коду, f3d_code-префікс, кількість) — розподіл «Люди по зонах» з ТК-01 (35 карток)
LAYOUT = [
    ("Z-CUT", "OPSAW", "OP-SAW-", 4), ("Z-EB", "OPEB", "OP-EB-", 3), ("Z-CNC", "OPCNC", "OP-CNC-", 5),
    ("Z-FAC", "OPFAC", "OP-FAC-", 6), ("Z-ASM", "OPASM", "OP-ASM-", 6), ("Z-PACK", "OPPACK", "OP-PACK-", 4),
]
OFFICE_W = [("OP-W1", "Z-HW"), ("OP-W2", "Z-HW"), ("OP-W3", "Z-RCV-2"), ("OP-W4", "Z-RCV-4"),
            ("OP-W5", "Z-SHEETS"), ("OP-W6", "Z-POST"), ("OP-W7", "Z-OUT-3")]
DEMO_DAY = "2026-10-12"


def employees():
    """[(f3d_code, barcode, home_zone_code)] — рівно 35."""
    rows = []
    for zone, bprefix, cprefix, count in LAYOUT:
        for i in range(1, count + 1):
            rows.append((f"{cprefix}{i}", f"{bprefix}{i}", zone))
    for code, zone in OFFICE_W:
        rows.append((code, code.replace("-", ""), zone))
    return rows


def seed_employees(od):
    """Ідемпотентно створює 35 працівників і відкриті демо-відмітки 12.10 (`in_mode='manual'`)."""
    zones = {z["f3d_code"]: z["id"] for z in od.k("f3d.zone", "search_read", [], ["f3d_code"])}
    made = 0
    for code, barcode, zone in employees():
        ids = od.k("hr.employee", "search", [("barcode", "=", barcode)])
        if ids:
            continue
        vals = {"name": f"Стенд {code}", "barcode": barcode, "f3d_code": code}
        if zone in zones:
            vals["f3d_home_zone_id"] = zones[zone]
        emp = od.k("hr.employee", "create", vals)
        od.k("hr.attendance", "create", {"employee_id": emp, "check_in": f"{DEMO_DAY} 05:00:00"})
        made += 1
    return made
