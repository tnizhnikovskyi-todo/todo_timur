"""Чисті функції провайдера chains (M-01g): порт `Demo.mo_supply`, `component_sources`, `mo_delivery`,
`material_paths`, `ship_chain`, `sheet_chain` з `plant/odoo_demo.py` (R-10…R-13). Працюють над готовим
payload (контракт Додатка A) без ORM; результат пишуть у `productions[]` на місці."""

SHEET_PREFIXES = ("DSP", "MDF", "HDF")
SHEET_CATEG = "Плитні матеріали"
COMP_PREFIXES = ("DSP", "MDF", "HDF", "FUR", "EB", "LFM", "PVC", "PK")
DOOR_OF = {"FUR": 4, "EB": 5, "LFM": 6, "PVC": 6, "PK": 7}
KIND_OF = {"FUR": "фурнітура", "EB": "крайка", "LFM": "ЛФМ", "PVC": "плівка ПВХ", "PK": "пакування"}
PLT_DOORS = ("UNLOAD-1", "UNLOAD-2", "UNLOAD-3")  # ворота плит; 4–7 — фурнітура, крайка, ЛФМ, пакування


def is_sheet(payload, code):
    """Плита: категорія «Плитні матеріали» або префікс коду DSP|MDF|HDF (R-10)."""
    prod = (payload.get("products") or {}).get(code) or {}
    return prod.get("categ") == SHEET_CATEG or str(code).startswith(SHEET_PREFIXES)


def _first_loc(locations, prefix, product):
    """Перша локація з префіксом і ненульовим квантом товару (порядок зі статики)."""
    return next((c for c, loc in locations.items() if c.startswith(prefix)
                 and any(q.get("product") == product and q.get("qty") for q in loc.get("quants") or ())), None)


def _incoming(pickings):
    return sorted((p for p in pickings if p.get("type") == "incoming"), key=lambda p: p.get("scheduled_date") or "")


def _door(pick):
    return int(pick["dock"][-1]) if pick and pick.get("dock") else None


def mo_supply(payload):
    """R-10: `productions[].supply`."""
    locations = payload.get("locations") or {}
    incoming = _incoming(payload.get("pickings") or [])
    qc_by_pick = {q["picking"]: q for q in payload.get("quality_checks") or [] if q.get("picking")}
    for mo in payload.get("productions") or []:
        prod = next((c["product"] for c in mo.get("components") or [] if is_sheet(payload, c["product"])), None)
        if not prod:
            continue
        pick = next((p for p in incoming if any(ln["product"] == prod for ln in p.get("lines") or [])), None)
        door = _door(pick) or 1 + sum(map(ord, prod)) % 3
        gantry, rack = _first_loc(locations, "PLT-", prod), _first_loc(locations, "RCK-", prod)
        lot = next((q.get("lot") for q in locations[gantry].get("quants") or [] if q.get("product") == prod),
                   None) if gantry else None
        if pick and pick.get("truck"):  # така сама плита саме розвантажується
            steps = [dict(code=pick["truck"], label="фура", doc=pick["name"],
                          note=f"Ворота {door} · {pick['name']} — ця плита зараз розвантажується")]
        elif pick and not rack:  # дефіцит — чекаємо фуру
            steps = [dict(code=f"DOCK-W{door}", label="фура о " + pick["scheduled_date"][11:16], doc=pick["name"],
                          note=f"Ворота {door} · {pick['name']}: фура ще в дорозі")]
        else:
            steps = [dict(code=f"DOCK-W{door}", label="ворота", note=f"Ворота {door} · прийнято раніше"
                          + (f", лот {lot}" if lot else ""))]
        steps.insert(0, dict(code="GATE-W", label="в'їзд", note="КПП приймання, реєстрація фури"))
        qc = qc_by_pick.get(pick["name"]) if pick and pick.get("truck") else None
        steps += [dict(code=f"UNLOAD-{door}", label="вивантаження", note="звірка з накладною"),
                  dict(code=f"QC-PLT-{door}", label="контроль", doc=qc["name"] if qc else None,
                       note=(qc.get("note") if qc else None) or "вхідний контроль пройдено при прийманні")]
        if rack:
            steps.append(dict(code=rack, label="стелаж", note=locations[rack].get("complete_name")))
        if gantry:
            steps.append(dict(code=gantry, label="під порталом",
                              note=(f"лот {lot}" if lot else "") + " · портал кладе лист на стіл пили"))
        mo["supply"] = dict(product=prod, steps=steps, lot=lot,
                            warn=None if rack or gantry else "Плити немає ні в стелажах, ні під порталом",
                            note=None if rack else "У стелажах немає — під порталом останні аркуші; "
                            f"поповнення з {pick['name'] if pick else 'наступного приймання'}")


def component_sources(payload):
    """R-11: `productions[].components[].door/receipt/expected/kind/to/path`."""
    locations = payload.get("locations") or {}
    workorders = payload.get("workorders") or {}
    incoming = _incoming(payload.get("pickings") or [])
    trucks = {_door(p): p["truck"] for p in incoming if p.get("truck") and p.get("dock")}
    kits = {loc.get("production"): c for c, loc in locations.items() if c.startswith("KIT-")}
    for mo in payload.get("productions") or []:
        wcs = [workorders[w]["workcenter"] for w in mo.get("workorders") or [] if w in workorders]

        def wc(*pre):
            return next((w for w in wcs if w.startswith(pre)), None)
        for c in mo.get("components") or []:
            prod = c["product"]
            pre = next((k for k in COMP_PREFIXES if prod.startswith(k)), "")
            rec = [p for p in incoming if any(ln["product"] == prod for ln in p.get("lines") or [])]
            got = [p for p in rec if (p.get("progress") or 0) > 0]  # уже розвантажене сьогодні
            pick = (got or rec or [None])[-1]
            c["door"] = _door(pick) or DOOR_OF.get(pre, 1 + sum(map(ord, prod)) % 3)
            if got:
                c["receipt"] = got[-1]["name"]
            elif rec:  # на складі із залишку, наступна партія ще їде
                c["expected"] = f"{rec[-1]['name']} о {rec[-1]['scheduled_date'][11:16]}"
            k = c["door"]
            path = [dict(code="GATE-W", label="в'їзд"),
                    dict(code=trucks.get(k) or f"DOCK-W{k}", label=f"ворота {k}"),
                    dict(code=f"UNLOAD-{k}", label="вивантаження")]
            if pre in SHEET_PREFIXES:
                c["kind"], c["to"] = "плита", wc("SAW", "NEST", "SLIDE", "VSAW")
                path.append(dict(code=f"QC-PLT-{k}", label="контроль"))
                for loc, lbl in ((_first_loc(locations, "RCK-", prod), "стелаж"),
                                 (_first_loc(locations, "PLT-", prod), "під порталом")):
                    if loc:
                        path.append(dict(code=loc, label=lbl))
            elif pre == "FUR":
                c["kind"] = KIND_OF[pre]
                c["to"] = wc("ASM", "ASMLINE") or wc("HINGE")
                path += [dict(code="QC-1", label="контроль"), dict(code="SCALE-RCV", label="зважування"),
                         dict(code="PRN-RCV", label="етикетка партії")]
                cell = _first_loc(locations, "FUR-", prod)
                if cell:
                    path.append(dict(code=cell, label="стелаж фурнітури"))
                if c["to"] and c["to"].startswith("ASM"):
                    path.append(dict(code=kits.get(mo["name"], "Z-PRE"), label="комплект WH/PC"
                                     if mo["name"] in kits else "буфер комплектів"))
                path.append(dict(code="TUGGER-1", label="тягач"))
            elif pre == "EB":
                c["kind"], c["to"] = KIND_OF[pre], wc("EDGE")
                cell = _first_loc(locations, "EB-", prod)
                if cell:
                    path.append(dict(code=cell, label="склад крайки"))
            elif pre in ("LFM", "PVC"):
                c["kind"] = KIND_OF[pre]
                c["to"] = (wc("PRESS") if pre == "PVC" else wc("GLUE") if prod == "LFM-GLUE"
                           else wc("AUTOSPRAY", "SPRAY", "UV")) or wc("GLUE", "SPRAY", "PRESS")
                path.append(dict(code="PAINT-STORE", label="склад ЛФМ"))
            elif pre == "PK":
                c["kind"], c["to"] = KIND_OF[pre], wc("BOX", "PACK")
                path += [dict(code="PACK-STORE", label="пакматеріали"), dict(code="PAL-1", label="піддони")]
                if c["to"] != "BOX-1":
                    path.append(dict(code="BOX-1", label="коробки з гофрокартону"))
            else:  # невідомий префікс: kind немає, to = null (клієнт не малює гілку)
                c["to"] = None
            c["path"] = path


def _fronts_buffer(locations, mo, order):
    buf = next((c for c, loc in locations.items() if c.startswith("FRONTS-") and loc.get("fronts_mo") == mo["name"]),
               None)
    if buf:
        return buf
    cand = f"FRONTS-{order + 1}"  # порядкове правило макета: k-те МО фасадів → FRONTS-{k+1}
    loc = locations.get(cand)
    return cand if loc is not None and not loc.get("fronts_mo") else None


def mo_delivery(payload):
    """R-12: `productions[].delivery` і `full_cycle_mo`. Повертає ім'я МО."""
    locations = payload.get("locations") or {}
    workorders = payload.get("workorders") or {}
    productions = payload.get("productions") or []
    pk = {p["name"]: p for p in payload.get("pickings") or []}
    sale = {so["name"]: so for so in payload.get("sale_orders") or []}
    sfp = {p["origin"]: p["name"] for p in payload.get("pickings") or [] if p.get("type") == "store_finished"}
    fg = [c for c in locations if c.startswith("FG-R")]

    def has(cell, product):
        return any(q.get("product") == product for q in locations[cell].get("quants") or ())
    for mo in productions:
        so = sale.get(mo.get("origin"))
        if not so:  # фасади йдуть у буфер комплектів до свого корпусу
            continue
        out = pk.get(so.get("delivery"))
        if not out or not out.get("dock"):
            continue
        k = out["dock"][-1]
        cell = next((c for c in out.get("source_locations") or [] if c in locations and has(c, mo["product"])), None)
        cell = cell or next((c for c in fg if has(c, mo["product"])), None)
        cell = cell or next((c for c in fg if not locations[c].get("quants")), None) or "FG-R1-B01-L1"
        wos = [workorders[w] for w in mo.get("workorders") or [] if w in workorders]
        last = wos[-1]["workcenter"] if wos else ""
        steps = [dict(code="PRN-PACK2" if last in ("PACK-2", "PACKLINE-1") else "PRN-PACK1",
                      label="етикетка SSCC", note="друк з Odoo через IoT Box")] if last.startswith("PACK") else []
        steps += [dict(code="POST-STAGE", label="вихід з пакування", doc=sfp.get(mo["name"]),
                       note="палета запакована, етикетка SSCC — чекає розміщення"),
                  dict(code=cell, label="склад ГП", note=(locations.get(cell) or {}).get("complete_name")),
                  dict(code="SCALE-OUT1" if int(k) <= 4 else "SCALE-OUT2", label="зважування палети",
                       note="вага в документ відвантаження"),
                  dict(code=f"Z-OUT-{k}", label=f"відвантаження · ворота {k}", doc=out["name"],
                       note=f"комплектування {out['name']} для {so.get('partner')}"),
                  dict(code=out["dock"], label="ворота", note=f"Ворота відвантаження {k}")]
        if out.get("truck"):
            steps.append(dict(code=out["truck"], label="фура клієнта",
                              note=f"{out.get('carrier') or ''} · завантаження {round((out.get('progress') or 0) * 100)} %"))
        steps += [dict(code="TRUCK-SCALE", label="вагова", note="контрольне зважування машини на виїзді"),
                  dict(code="GATE-E", label="виїзд", note="через КПП відвантаження")]
        mo["delivery"] = dict(picking=out["name"], partner=so.get("partner"), steps=steps,
                              note=None if out.get("truck") else
                              f"Машину ще не подано — відвантаження {out['scheduled_date'][:16].replace('-', '.')}"
                              + (" · чекає завершення МО" if out.get("state") == "waiting" else ""))
    # фасади: буфер фасадів → складання свого корпусу → далі шлях корпусу до клієнта
    by_name = {m["name"]: m for m in productions}
    order = 0
    for mo in productions:
        parent = by_name.get(mo.get("origin"))
        if not parent:
            continue
        n, order = order, order + 1
        if not parent.get("delivery"):
            continue
        buf = _fronts_buffer(locations, mo, n)
        asm = next((workorders[w]["workcenter"] for w in parent.get("workorders") or []
                    if w in workorders and workorders[w]["workcenter"].startswith("ASM")), None)
        steps = ([dict(code=buf, label="буфер фасадів", note=locations[buf].get("complete_name"))] if buf else [])
        if asm:
            steps.append(dict(code=asm, label=f"складання {parent['name'][-5:]}",
                              note=f"фасади ставлять на корпус {parent['name']}"))
        pd = parent["delivery"]
        mo["delivery"] = dict(picking=pd["picking"], partner=pd["partner"], via=parent["name"],
                              steps=steps + pd["steps"], note=pd["note"])
    full = next((m for m in productions if m.get("state") == "progress" and m.get("delivery")
                 and any(st["code"].startswith("TRUCK-OUT") for st in m["delivery"]["steps"])
                 and any(st["code"].startswith("TRUCK-IN") for st in (m.get("supply") or {}).get("steps", []))
                 and any(c["product"].startswith("FUR") and "KIT-" in str(c.get("path"))
                         for c in m.get("components") or [])), None)
    return full["name"] if full else (productions[0]["name"] if productions else None)


def material_paths(payload):
    """R-13: типовий шлях кожного виду матеріалу (з першого МО, де він є)."""
    out = {}
    wcs = payload.get("workcenters") or {}
    for mo in payload.get("productions") or []:
        for c in mo.get("components") or []:
            k = c.get("kind")
            if k and k not in out and c.get("to"):
                out[k] = dict(kind=k, product=c["product"], mo=mo["name"],
                              steps=c["path"] + [dict(code=c["to"], label=(wcs.get(c["to"]) or {}).get("name"))])
    return list(out.values())


def ship_chain(payload):
    """R-13: ланцюжок відвантаження від пакування до машини клієнта."""
    pickings = payload.get("pickings") or []
    locations = payload.get("locations") or {}
    outs = [p for p in pickings if p.get("type") == "outgoing"]
    fg = [c for c in locations if c.startswith("FG-R")]
    full = sum(1 for c in fg if locations[c].get("quants"))
    sfp = sum(1 for p in pickings if p.get("type") == "store_finished")
    steps = [
        dict(n=1, title="Пакування", codes=["PACK-1", "PACK-2", "PACKLINE-1"], stock="",
             desc="Остання операція МО: палетообмотувачі й лінія термоусадки."),
        dict(n=2, title="Вихід з пакування", codes=["POST-STAGE"], stock=f"{sfp} палети на розміщення",
             desc="Палета з етикеткою SSCC чекає навантажувача (WH/SFP — розміщення готової продукції)."),
        dict(n=3, title="Склад готової продукції", codes=[f"FG-RACK-R{r}" for r in range(1, 6)],
             stock=f"{full} з {len(fg)} комірок зайнято",
             desc="Палетні стелажі; під кожне відвантаження резервуються комірки."),
        dict(n=4, title="Зона відвантаження перед воротами", codes=[f"Z-OUT-{k}" for k in range(1, 8)],
             stock=f"{len(outs)} відвантажень сьогодні",
             desc="Комплектування WH/OUT у коридорі перед своїми воротами."),
        dict(n=5, title="Фура клієнта", codes=[p["truck"] for p in outs if p.get("truck")],
             stock=f"{sum(1 for p in outs if p.get('truck'))} машини біля воріт",
             desc="Завантаження через докшелтер, документи — з Odoo."),
    ]
    return dict(steps=steps)


def _pick_open(pickings, ptype):
    """Перше незавершене переміщення типу з технікою, інакше перше незавершене, інакше перше."""
    rows = [p for p in pickings if p.get("type") == ptype]
    opened = [p for p in rows if p.get("state") != "done"]
    return next((p for p in opened if p.get("vehicle")), None) or next(iter(opened), None) or next(iter(rows), None)


def _plural_stacks(n):
    word = "стос" if n % 10 == 1 and n % 100 != 11 else \
        "стоси" if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14 else "стосів"
    return f"{n} {word}"


def sheet_chain(payload):
    """R-13: ланцюжок плит від фури до пили."""
    locations = payload.get("locations") or {}
    pickings = payload.get("pickings") or []
    workorders = payload.get("workorders") or {}

    def match(prefix):
        pre = tuple(prefix) if isinstance(prefix, (tuple, list)) else (prefix,)
        return [(c, loc) for c, loc in locations.items() if c.startswith(pre) and loc.get("quants")]

    def sheets(prefix):
        return sum(q.get("qty") or 0 for _, loc in match(prefix) for q in loc["quants"])

    def stacks(prefix):
        n = sum(len(loc["quants"]) if c.startswith(("UNLOAD-", "QC-PLT-")) else 1 for c, loc in match(prefix))
        return _plural_stacks(n)

    def uniq(seq):
        return list(dict.fromkeys(x for x in seq if x))

    put, rep = _pick_open(pickings, "putaway"), _pick_open(pickings, "replenish")
    put_dest = (put or {}).get("location_dest") or "RCK-R1-1A"
    rep_dest = (rep or {}).get("location_dest") or "PLT-01A"
    recs = [p for p in _incoming(pickings) if p.get("truck") and any(
        is_sheet(payload, ln["product"]) for ln in p.get("lines") or [])]
    qcs = [q["name"] for q in payload.get("quality_checks") or [] if str(q.get("location") or "").startswith("QC-")]

    def docs_of(ptype):
        rows = [p for p in pickings if p.get("type") == ptype]
        return [p["name"] for p in sorted(rows, key=lambda p: p.get("state") == "done")]
    saw_mo = next((m["name"] for m in payload.get("productions") or [] if m.get("state") == "progress" and any(
        workorders.get(w, {}).get("workcenter") == "SAW-1" and workorders[w].get("state") == "progress"
        for w in m.get("workorders") or [])), None)
    if not saw_mo and payload.get("productions"):
        saw_mo = payload["productions"][0]["name"]
    rec_codes = []
    for p in recs:
        rec_codes += [p["truck"], f"UNLOAD-{_door(p)}" if _door(p) else None]
    steps = [
        dict(n=1, title="Вивантаження з фури", docs=[p["name"] for p in recs],
             codes=uniq(rec_codes + list(PLT_DOORS)),
             stock=f"{stacks(PLT_DOORS)} · {sheets(PLT_DOORS)} арк.",
             desc="Стоси знімають із фури біля воріт 1–3 і звіряють із накладною (WH/IN → Вхід)."),
        dict(n=2, title="Приймання й контроль якості", docs=qcs, codes=["QC-PLT-1", "QC-PLT-2", "QC-PLT-3", "QC-1"],
             stock=f"{stacks('QC-PLT-')} · {sheets('QC-PLT-')} арк.",
             desc="Товщина, декор, кромки, вологість. Брак — у карантин біля воріт 4, решта — у стелажі."),
        dict(n=3, title="Склад плит · стелажі", docs=docs_of("putaway"),
             codes=uniq(["BOARD-RACKS", (put or {}).get("location_dest"), (put or {}).get("vehicle")]),
             stock=f"{stacks('RCK-')} · {sheets('RCK-')} арк.",
             desc="8 ліній стелажів по 4 яруси; навантажувач кладе стос із площадки контролю."),
        dict(n=4, title="Склад під порталом", docs=docs_of("replenish"),
             codes=uniq(["GANTRY-1", (rep or {}).get("location_dest"), (rep or {}).get("vehicle")]),
             stock=f"{stacks('PLT-')} · {sheets('PLT-')} арк.",
             desc="Навантажувач ставить цілий стос у ряд під порталом через ворота з блокуванням зони."),
        dict(n=5, title="Виробництво", docs=[saw_mo] if saw_mo else [],
             codes=["SAW-1", "SAW-2", "SAW-3", "NEST-1"], stock="портал подає по одному листу",
             desc="Портал кладе лист на підйомний стіл розкрійного центру чи нестингу."),
    ]
    first = recs[0] if recs else None
    k = _door(first) or 1
    path = [((first or {}).get("truck") or "TRUCK-IN-1", "1 · фура"), (f"UNLOAD-{k}", "1 · вивантаження"),
            (f"QC-PLT-{k}", "2 · контроль"), (put_dest, "3 · стелаж"), (rep_dest, "4 · під порталом"),
            ("SAW-1", "5 · розкрій")]
    return dict(steps=steps, path=[dict(code=c, label=lbl) for c, lbl in path])


def compute(payload):
    """Усі обчислення розділу chains: правки `productions[]` на місці + чотири ключі верхнього рівня."""
    mo_supply(payload)
    component_sources(payload)
    full = mo_delivery(payload)
    return dict(sheet_chain=sheet_chain(payload), ship_chain=ship_chain(payload),
                material_paths=material_paths(payload), full_cycle_mo=full)
