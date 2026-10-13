"""Перевірка наскрізного циклу в демо-даних: усе починається з вивантаження фури й закінчується
відвантаженням клієнту. Без Blender: python -m plant.cycle_check dist/odoo_demo.json"""
import json
import sys

# які товари приймають біля яких західних воріт (див. layout.RCV_GOODS)
DOOR_GOODS = {1: ("DSP", "MDF", "HDF"), 2: ("DSP", "MDF", "HDF"), 3: ("DSP", "MDF", "HDF"), 4: ("FUR",),
              5: ("EB",), 6: ("LFM", "PVC"), 7: ("PK",)}


def check(d):
    issues = []
    P = {p["name"]: p for p in d["pickings"]}
    L = d["locations"]

    def prods(loc):
        return {q["product"] for q in L.get(loc, {}).get("quants", [])}
    # приймання: кожне — через західні ворота, що приймають саме ці товари
    for p in d["pickings"]:
        if p["type"] == "incoming":
            dock = p.get("dock") or ""
            if not dock.startswith("DOCK-W"):
                issues.append(f"{p['name']}: приймання без західних воріт")
                continue
            k = int(dock[-1])
            bad = [ln["product"] for ln in p["lines"] if not ln["product"].startswith(DOOR_GOODS[k])]
            if bad:
                issues.append(f"{p['name']}: {', '.join(bad)} не приймають біля воріт {k}")
        if p["type"] == "outgoing":
            if not (p.get("dock") or "").startswith("DOCK-E"):
                issues.append(f"{p['name']}: відвантаження без східних воріт")
            so = next((s for s in d["sale_orders"] if s["name"] == p["origin"]), None)
            if not so:
                issues.append(f"{p['name']}: немає замовлення клієнта {p['origin']}")
            elif sorted(ln["product"] for ln in p["lines"]) != sorted(ln["product"] for ln in so["lines"]):
                issues.append(f"{p['name']}: рядки не збігаються із {so['name']}")
            for c in set(p.get("source_locations") or []):
                if not prods(c) & {ln["product"] for ln in p["lines"]}:
                    issues.append(f"{p['name']}: у комірці {c} немає товару відвантаження")
    # що лежить біля воріт — з приймань цих воріт
    for k in range(1, 8):
        got = {ln["product"] for p in d["pickings"] if p["type"] == "incoming" and p.get("dock") == f"DOCK-W{k}"
               for ln in p["lines"]}
        for loc in (f"UNLOAD-{k}", f"QC-PLT-{k}"):
            extra = prods(loc) - got
            if extra:
                issues.append(f"{loc}: {', '.join(sorted(extra))} — немає приймання через ворота {k}")
    # контроль якості — про товар свого приймання
    for q in d["quality_checks"]:
        p = P.get(q.get("picking")) if q.get("picking") else None
        if q.get("picking") and not p:
            issues.append(f"{q['name']}: немає документа {q['picking']}")
        elif p and q.get("product") and q["product"] not in {ln["product"] for ln in p["lines"]}:
            issues.append(f"{q['name']}: {q['product']} немає в {p['name']}")
    # кожне замовлення клієнта — з відвантаженням; кожне МО — від вивантаження до відвантаження
    for so in d["sale_orders"]:
        if so.get("delivery") not in P:
            issues.append(f"{so['name']}: немає відвантаження")
    for m in d["productions"]:
        s, dl = m.get("supply"), m.get("delivery")
        if not s or not any(st["code"].startswith("UNLOAD-") for st in s["steps"]):
            issues.append(f"{m['name']}: шлях плити не починається з вивантаження")
        if not dl or not dl["steps"][-1]["code"].startswith(("TRUCK-OUT", "DOCK-E")):
            issues.append(f"{m['name']}: шлях не закінчується відвантаженням")
        steps = (dl or {}).get("steps", [])
        if m["route"].startswith("F") and not any(st["code"].startswith("FRONTS-") for st in steps):
            issues.append(f"{m['name']}: фасади без етажерки в буфері")
        for c in m["components"]:
            if not c.get("door"):
                issues.append(f"{m['name']}: невідомо, звідки {c['product']}")
    return issues


if __name__ == "__main__":
    data = json.load(open(sys.argv[1] if len(sys.argv) > 1 else "dist/odoo_demo.json", encoding="utf-8"))
    res = check(data)
    print("\n".join(res) if res else "Цикл замкнений: усе від вивантаження до відвантаження.")
    sys.exit(1 if res else 0)
