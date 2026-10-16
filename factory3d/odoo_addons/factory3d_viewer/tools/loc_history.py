"""R-24: історія комірки для картки (API-11) — як товар потрапив у комірку і куди він іде.

Окремий ліниво завантажуваний запит (не частина `/data`): картка бачить лише свою комірку. Усе — з правами
користувача, пакетними вибірками з обмеженнями (по одній на вид руху, без запитів у циклі).

Структура відповіді: `products[]` (за кодом товару) → `lots[]` (партії з залишком у комірці або з резервом) з
`arrived` (останні виконані надходження, ≤ 3) і `reserve` (відкриті рядки переміщень з комірки); на рівні товару
(рух не прив'язаний до партії) — `out` (з комірки, ще не зарезервовано) і `incoming` (очікується в комірку).
Документ, що є і в `reserve`, і в `out` (частково резервоване переміщення), показується один раз: у `reserve`
з `pending` (скільки ще не зарезервовано).
"""
from . import dates
from . import docs as docs_tools
from . import payload as payload_tools

LIMIT_QUANTS = 50
LIMIT_DONE = 300        # виконані рядки в комірку: вибірка, з якої беруться останні KEEP_DONE для товару/партії
LIMIT_OPEN = 200        # відкриті рядки й переміщення (кожна вибірка окремо)
KEEP_DONE = 3
KEEP_OPEN = 10          # записів кожного виду на товар / партію
OPEN_OUT = ("confirmed", "waiting", "partially_available")        # ще не (повністю) зарезервовано
OPEN_IN = ("draft", "waiting", "confirmed", "partially_available", "assigned")
NEEDED_MODELS = ("stock.location", "stock.quant", "stock.move", "stock.move.line")


def accessible(env):
    return all(payload_tools.access_ok(env, m) for m in NEEDED_MODELS)


def _num(value):
    value = float(value or 0)
    return int(value) if value.is_integer() else round(value, 2)


def _doc(env, mv, ml=None):
    """Документ переміщення: picking, інакше МО / утилізація / «Інвентаризація» / довідковий текст."""
    pick = (ml and ml.picking_id) or mv.picking_id
    if pick:
        return {"name": pick.name, "model": "stock.picking", "id": pick.id, "kind": "picking",
                "state": docs_tools.picking_state(pick.state)}
    prod = None
    if payload_tools.access_ok(env, "mrp.production"):
        prod = (ml and ml.production_id) or mv.production_id or mv.raw_material_production_id
    if prod:
        return {"name": prod.name, "model": "mrp.production", "id": prod.id, "kind": "production",
                "state": docs_tools.production_state(prod.state)}
    scrap = mv.scrap_id if payload_tools.access_ok(env, "stock.scrap") else None
    if scrap:
        return {"name": scrap.name, "model": "stock.scrap", "id": scrap.id, "kind": "scrap",
                "state": docs_tools.picking_state(scrap.state)}
    if mv.is_inventory:
        return {"name": "Інвентаризація", "model": None, "id": None, "kind": "inventory", "state": None}
    return {"name": mv.reference or mv.origin or "Переміщення", "model": None, "id": None, "kind": "move",
            "state": None}


def _place(loc):
    """Локація як {name, code}: код 3D-об'єкта (якщо є) і повна назва."""
    return {"code": loc.f3d_code or None, "name": loc.complete_name or loc.name}


def _key(doc):
    return (doc["model"], doc["id"]) if doc["id"] else (doc["kind"], doc["name"])


def build(env, loc, code=None):
    """Історія комірки `loc` (stock.location, не порожня); `code` — запитаний код (код або аліас 3D-об'єкта)."""
    out = {"code": code or loc.f3d_code, "complete_name": loc.complete_name, "products": [], "truncated": False}
    quants = env["stock.quant"].search_fetch(
        [("location_id", "=", loc.id), ("quantity", "!=", 0)],
        ["product_id", "lot_id", "quantity", "reserved_quantity"], order="id", limit=LIMIT_QUANTS + 1)
    if len(quants) > LIMIT_QUANTS:
        out["truncated"] = True
        quants = quants[:LIMIT_QUANTS]

    lines_done = env["stock.move.line"].search_fetch(
        [("location_dest_id", "=", loc.id), ("state", "=", "done")],
        ["product_id", "lot_id", "quantity_product_uom", "date", "move_id", "picking_id", "location_id"],
        order="date desc, id desc", limit=LIMIT_DONE)
    lines_res = env["stock.move.line"].search_fetch(
        [("location_id", "=", loc.id), ("state", "not in", ("done", "cancel")), ("quantity", ">", 0)],
        ["product_id", "lot_id", "quantity_product_uom", "move_id", "picking_id", "location_dest_id"],
        order="id", limit=LIMIT_OPEN)
    moves_out = env["stock.move"].search_fetch(
        [("location_id", "=", loc.id), ("location_dest_id", "!=", loc.id), ("state", "in", OPEN_OUT)],
        ["product_id", "product_qty", "move_line_ids", "picking_id", "location_dest_id", "date", "state"],
        order="date, id", limit=LIMIT_OPEN)
    moves_in = env["stock.move"].search_fetch(
        [("location_dest_id", "=", loc.id), ("location_id", "!=", loc.id), ("state", "in", OPEN_IN)],
        ["product_id", "product_qty", "picking_id", "location_id", "date", "state"],
        order="date, id", limit=LIMIT_OPEN)
    if any(len(r) >= lim for r, lim in ((lines_done, LIMIT_DONE), (lines_res, LIMIT_OPEN),
                                        (moves_out, LIMIT_OPEN), (moves_in, LIMIT_OPEN))):
        out["truncated"] = True

    # попереднє читання для пакетного доступу до m2o (ORM читає по всьому набору)
    (lines_done.move_id | lines_res.move_id | moves_out | moves_in).mapped("picking_id.name")
    prods = {}      # product.id -> {"rec", "lots": {lot.id|0: {...}}, "out": [], "incoming": []}

    def product(p):
        return prods.setdefault(p.id, {"rec": p, "lots": {}, "out": [], "incoming": []})

    def lot_of(p, lot):
        return product(p)["lots"].setdefault(lot.id or 0, {
            "rec": lot, "qty": 0.0, "reserved": 0.0, "arrived": [], "reserve": []})

    for q in quants:
        row = lot_of(q.product_id, q.lot_id)
        row["qty"] += q.quantity
        row["reserved"] += q.reserved_quantity
    for ml in lines_done:
        row = prods.get(ml.product_id.id, {}).get("lots", {}).get(ml.lot_id.id or 0)
        if row is None:
            continue            # лише товари/партії, що зараз є в комірці
        if len(row["arrived"]) < KEEP_DONE:
            row["arrived"].append({
                "doc": _doc(env, ml.move_id, ml), "date": dates.local(ml.date), "qty": _num(ml.quantity_product_uom),
                "from": _place(ml.location_id)})
    for ml in lines_res:
        row = lot_of(ml.product_id, ml.lot_id)
        row["reserve"].append({"doc": _doc(env, ml.move_id, ml), "qty": _num(ml.quantity_product_uom),
                               "pending": 0, "to": _place(ml.location_dest_id)})
    for mv in moves_out:
        reserved = sum(mv.move_line_ids.mapped("quantity_product_uom"))
        left = mv.product_qty - reserved
        if left <= 0:
            continue
        product(mv.product_id)["out"].append({
            "doc": _doc(env, mv), "qty": _num(left), "to": _place(mv.location_dest_id), "date": dates.local(mv.date)})
    for mv in moves_in:
        product(mv.product_id)["incoming"].append({
            "doc": _doc(env, mv), "qty": _num(mv.product_qty), "from": _place(mv.location_id),
            "date": dates.local(mv.date)})

    # «Іде з комірки» зливається з «Резерв», якщо це той самий документ (залишок → pending)
    for pr in prods.values():
        by_doc = {_key(r["doc"]): r for lot in pr["lots"].values() for r in lot["reserve"]}
        rest = []
        for item in pr["out"]:
            tgt = by_doc.get(_key(item["doc"]))
            if tgt:
                tgt["pending"] = _num(tgt["pending"] + item["qty"])
            else:
                rest.append(item)
        pr["out"] = rest

    for pr in sorted(prods.values(), key=lambda x: x["rec"].default_code or x["rec"].name or ""):
        p = pr["rec"]
        lots = []
        for lot in sorted(pr["lots"].values(), key=lambda r: r["rec"].name or ""):
            if not (lot["qty"] or lot["reserved"] or lot["reserve"] or lot["arrived"]):
                continue
            lots.append({"lot": lot["rec"].name or None, "qty": _num(lot["qty"]), "reserved": _num(lot["reserved"]),
                         "arrived": lot["arrived"], "reserve": lot["reserve"][:KEEP_OPEN]})
        if not (lots or pr["out"] or pr["incoming"]):
            continue
        out["products"].append({
            "product": p.default_code or p.name, "name": p.name, "uom": p.uom_id.name,
            "qty": _num(sum(x["qty"] for x in lots)), "reserved": _num(sum(x["reserved"] for x in lots)),
            "lots": lots, "out": pr["out"][:KEEP_OPEN], "incoming": pr["incoming"][:KEEP_OPEN]})
    return out
