"""Заливка демо меблевої фабрики в справжню Odoo 19 через XML-RPC.

Береться той самий знімок, що й у переглядачі (plant/odoo_demo.py), і розкладається по моделях Odoo:
товари, комірки складу й залишки, робочі центри, обладнання ТО, співробітники, закупівлі з приймань,
продажі з відвантажень, внутрішні переміщення, виробничі замовлення з робочими завданнями в тих самих
станах, контроль якості й заявки на ТО. Назви документів (WH/MO/00231, WH/IN/00128, S00087 …) такі
самі, як у 3D, тож переглядач зіставляє їх напряму.

Кожен запис має зовнішній ID factory3d.* — повторний запуск оновлює довідники й пропускає документи,
які вже є, дублів не буде.

Запуск (доступи — лише зі змінних середовища, див. plant/odoo_rpc.py):
    python3 -m plant.odoo_push            # усе по черзі
    python3 -m plant.odoo_push --only base,locations
"""
import argparse
import sys
from datetime import datetime, timedelta

from .cycle_check import DOOR_GOODS
from .odoo_demo import NOW, Demo
from .odoo_flows import OUTSIDE_STOCK, FlowSteps
from .odoo_rpc import Odoo, key, utc

MOD = "factory3d"
STEPS = ["modules", "settings", "base", "views", "calendar", "locations", "workcenters", "people", "purchase",
         "sale", "internal", "production", "boms", "layout", "lots", "stock", "routes", "orderpoints", "children",
         "fronts", "mo_locations", "consumption", "po_links", "docks", "wc_tags", "losses", "quality", "maintenance",
         "equipment", "preventive", "attendance", "carriers", "finish"]
# усе, чим користується модель: без цих налаштувань Odoo ховає меню й поля
SETTINGS = {"group_stock_multi_locations": True,   # місця зберігання (комірки, стелажі, ворота)
            "group_mrp_routings": True,            # робочі замовлення й робочі центри
            "group_uom": True,                     # аркуш, комплект, рулон, кг, м
            "group_stock_production_lot": True,    # партії плит, крайки, ЛФМ
            "group_stock_tracking_lot": True,      # палети готової продукції (упаковки PACK…)
            "group_stock_adv_location": True}      # багатокрокові маршрути: приймання, виробництво, відвантаження
UOM = {"шт": ("Units", None), "м": ("m", None), "кг": ("kg", None),
       "арк": (None, "Аркуш"), "компл": (None, "Комплект"), "рул": (None, "Рулон")}
FG_PRICE = {"KC-B600": 6400, "KC-W800": 4800, "KC-T400": 7900, "OF-D3": 5600, "OF-T1400": 9800,
            "OF-C800": 8700, "BR-K4": 7400}
# текстові місця призначення в демо → групи комірок
DEST_GROUP = {"Склад крайки": "Сировина/Крайка", "Склад ЛФМ": "Сировина/ЛФМ",
              "Пакувальні матеріали": "Сировина/Пакування", "Склад фурнітури": "Сировина/Фурнітура",
              "Склад готової продукції": "Готова продукція"}
INTERNAL_TYPES = {  # тип у демо → (назва типу операції, префікс послідовності)
    "putaway": ("Розміщення плит у стелажі", "INT"), "replenish": ("Поповнення під портал", "INT"),
    "pick_components": ("Комплектація компонентів", "PC"),
    "store_finished": ("Розміщення готової продукції", "SFP")}


class Push(FlowSteps):
    def __init__(self, o, d):
        self.o, self.d = o, d
        self.o.ctx = {"lang": "uk_UA", "tz": "Europe/Kyiv", "tracking_disable": True,
                      "mail_create_nolog": True, "mail_notrack": True}
        rows = o("ir.model.data", "search_read", [["module", "=", MOD]], fields=["name", "model", "res_id"])
        self.ids = {r["name"]: r["res_id"] for r in rows}
        self.n_new = 0

    # ------------------------------------------------------------ службове
    def ref(self, name):
        return self.ids.get(name)

    def bind(self, name, model, rid):
        self.o("ir.model.data", "create", {"module": MOD, "name": name, "model": model, "res_id": rid,
                                           "noupdate": True})
        self.ids[name] = rid

    def ensure(self, name, model, vals, update=True):
        rid = self.ids.get(name)
        if rid:
            if update:
                self.o(model, "write", [rid], vals)
            return rid
        rid = self.o(model, "create", vals)
        self.bind(name, model, rid)
        self.n_new += 1
        return rid

    def one(self, model, domain, **kw):
        r = self.o(model, "search", domain, limit=1, **kw)
        return r[0] if r else False

    def prod(self, code):
        return self.ref(key("product", code))

    def prod_tmpl(self, code):
        return self.ref(key("tmpl", code))

    def loc(self, code):
        return self.ref(key("loc", code))

    def partner(self, name):
        return self.ref(key("partner", name)) if name else False

    def uom(self, u):
        return self.ref(key("uom", u))

    # ------------------------------------------------------------ налаштування
    def step_settings(self):
        o = self.o
        fields = o("res.config.settings", "fields_get", attributes=["type"])
        vals = {k: v for k, v in SETTINGS.items() if k in fields}
        wid = o("res.config.settings", "create", vals)
        o("res.config.settings", "execute", [wid])
        print(f"settings: {', '.join(vals)}")

    # ------------------------------------------------------------ довідники
    def step_base(self):
        o, d = self.o, self.d
        o("res.users", "write", [o.uid], {"lang": "uk_UA", "tz": "Europe/Kyiv"})
        for u, (std, new) in UOM.items():
            if std:
                rid = self.one("uom.uom", [["name", "=", std]], context={"lang": "en_US"})
                if not self.ref(key("uom", u)):
                    self.bind(key("uom", u), "uom.uom", rid)
            else:
                units = self.one("uom.uom", [["name", "=", "Units"]], context={"lang": "en_US"})
                self.ensure(key("uom", u), "uom.uom", {"name": new, "relative_factor": 1.0,
                                                        "relative_uom_id": units})
        all_cat = self.one("product.category", [["parent_id", "=", False]])
        for cat in sorted({p["categ"] for p in d["products"].values()}):
            self.ensure(key("categ", cat), "product.category", {"name": cat, "parent_id": all_cat})
        ua = self.one("res.country", [["code", "=", "UA"]])
        partners = {p["seller"] for p in d["products"].values() if p.get("seller")}
        partners |= {so["partner"] for so in d["sale_orders"]}
        partners |= {p["partner"] for p in d["pickings"] if p.get("partner")}
        partners |= {p["carrier"] for p in d["pickings"] if p.get("carrier") and "демо" in p["carrier"]}
        for name in sorted(partners):
            self.ensure(key("partner", name), "res.partner", {"name": name, "is_company": True, "country_id": ua})
        lots = {q["product"] for loc in d["locations"].values() for q in loc["quants"] if q.get("lot")}
        for code, p in d["products"].items():
            vals = {"name": p["name"], "default_code": code, "type": "consu", "is_storable": True,
                    "tracking": "lot" if code in lots else "none",
                    "categ_id": self.ref(key("categ", p["categ"])), "uom_id": self.uom(p["uom"]),
                    "sale_ok": p["categ"] == "Готова продукція", "purchase_ok": bool(p.get("seller")),
                    "list_price": FG_PRICE.get(code, 0)}
            tid = self.ensure(key("tmpl", code), "product.template", vals)
            if not self.prod(code):
                pid = o("product.product", "search", [["product_tmpl_id", "=", tid]])[0]
                self.bind(key("product", code), "product.product", pid)
            if p.get("seller"):
                self.ensure(key("seller", code), "product.supplierinfo",
                            {"partner_id": self.partner(p["seller"]), "product_tmpl_id": tid, "min_qty": 1})
        # поля, яких немає в стандарті: док (ворота) і техніка на переміщенні
        model_id = self.one("ir.model", [["model", "=", "stock.picking"]])
        for fname, label in (("x_dock", "Ворота (док)"), ("x_vehicle", "Техніка"), ("x_truck", "Фура")):
            if not self.one("ir.model.fields", [["model", "=", "stock.picking"], ["name", "=", fname]]):
                o("ir.model.fields", "create", {"name": fname, "model_id": model_id, "field_description": label,
                                                "ttype": "char", "state": "manual"})
        wh = o("stock.warehouse", "search_read", [], fields=["id", "lot_stock_id", "view_location_id"], limit=1)[0]
        o("stock.warehouse", "write", [wh["id"]], {"name": "Меблева фабрика"})
        self.bind_once("warehouse", "stock.warehouse", wh["id"])
        self.bind_once("loc_root", "stock.location", wh["lot_stock_id"][0])
        self.bind_once("loc_wh", "stock.location", wh["view_location_id"][0])
        stock = wh["lot_stock_id"][0]
        seq_model = "ir.sequence"
        for typ, (label, prefix) in INTERNAL_TYPES.items():
            seq = self.ensure(key("seq", typ), seq_model, {"name": f"WH {label}", "prefix": f"WH/{prefix}/",
                                                           "padding": 5, "code": False})
            self.ensure(key("ptype", typ), "stock.picking.type", {
                "name": label, "code": "internal", "sequence_code": prefix, "sequence_id": seq,
                "warehouse_id": wh["id"], "default_location_src_id": stock, "default_location_dest_id": stock})
        print(f"base: {len(d['products'])} товарів, {len(partners)} партнерів")

    def bind_once(self, name, model, rid):
        if not self.ref(name):
            self.bind(name, model, rid)

    # ------------------------------------------------------------ комірки складу
    def step_locations(self):
        """Комірки під WH/Stock; зони приймання, контролю, карантину, передвиробництва, пост-виробництва й
        відвантаження — поруч зі Stock (як Input/Quality Control/Output у стандарті): там товар ще не вільний."""
        root = self.ref("loc_root")
        groups = {"": root}
        made = 0
        for code, loc in sorted(self.d["locations"].items(), key=lambda kv: kv[1]["complete_name"]):
            parts = loc["complete_name"].split("/")[1:]  # без «WH»
            parent = self.ref("loc_wh") if parts[0] in OUTSIDE_STOCK else root
            for i in range(len(parts) - 1):
                path = "/".join(parts[: i + 1])
                if path not in groups:
                    xid = key("locgrp", path)
                    groups[path] = self.ensure(xid, "stock.location", {
                        "name": parts[i], "location_id": parent, "usage": "internal"}, update=False)
                parent = groups[path]
            path = "/".join(parts)
            rid = self.ensure(key("loc", code), "stock.location", {
                "name": parts[-1], "location_id": parent, "usage": "internal", "barcode": code}, update=False)
            groups[path] = rid
            made += 1
        for label, path in DEST_GROUP.items():  # групи, на які посилаються приймання
            if path not in groups:
                parent = groups.get(path.rsplit("/", 1)[0], root) if "/" in path else root
                groups[path] = self.ensure(key("locgrp", path), "stock.location",
                                           {"name": path.rsplit("/", 1)[-1], "location_id": parent,
                                            "usage": "internal"}, update=False)
        self.groups = groups
        print(f"locations: {made} комірок, {len(groups) - made} груп")

    def group(self, label):
        """Склад за текстовою назвою з демо: група комірок або комірка з тим самим шляхом (ЛФМ, пакування)."""
        path = DEST_GROUP[label]
        code = next((c for c, loc in self.d["locations"].items() if loc["complete_name"] == "WH/" + path), None)
        return self.loc(code) if code else self.ref(key("locgrp", path))

    # ------------------------------------------------------------ робочі центри, люди, обладнання
    def step_workcenters(self):
        for code, wc in self.d["workcenters"].items():
            note = " ".join(x for x in (wc.get("manufacturer"), wc.get("model")) if x)
            self.ensure(key("wc", code), "mrp.workcenter", {
                "name": wc["name"], "code": code, "time_efficiency": wc["time_efficiency"] * 100,
                "oee_target": 85, "time_start": 15, "note": f"<p>{note}</p>" if note else False,
                "resource_calendar_id": self.ref("calendar_shift1")})
        print(f"workcenters: {len(self.d['workcenters'])}")

    def step_people(self):
        o = self.o
        deps = {}
        for code, e in self.d["employees"].items():
            dep = e["department"]
            if dep not in deps:
                deps[dep] = self.ensure(key("dep", dep), "hr.department", {"name": dep})
            eid = self.ensure(key("emp", code), "hr.employee", {
                "name": e["name"], "job_title": e["job"], "department_id": deps[dep],
                "resource_calendar_id": self.ref("calendar_shift1")})
            if e.get("workcenter"):
                o("mrp.workcenter", "write", [self.ref(key("wc", e["workcenter"]))], {"employee_ids": [(4, eid)]})
        print(f"people: {len(self.d['employees'])} співробітників, {len(deps)} відділів")

    # ------------------------------------------------------------ закупівлі → приймання
    def picking_extra(self, pid, p, name):
        vals = {"name": name, "scheduled_date": utc(p["scheduled_date"]), "origin": p.get("origin") or False}
        for f, v in (("x_dock", p.get("dock")), ("x_vehicle", p.get("vehicle")), ("x_truck", p.get("truck"))):
            if v:
                vals[f] = v
        if p.get("note"):
            vals["note"] = f"<p>{p['note']}</p>"
        self.o("stock.picking", "write", [pid], vals)

    def set_done_qty(self, pid, lines, validate):
        """Скільки вже прийнято/зібрано: quantity + picked на рухах; повністю — підтвердити."""
        o = self.o
        moves = o("stock.move", "search_read", [["picking_id", "=", pid]], fields=["product_id", "product_uom_qty"])
        by_prod = {}
        for ln in lines:
            by_prod[self.prod(ln["product"])] = ln
        for m in moves:
            ln = by_prod.get(m["product_id"][0])
            done = ln["qty_done"] if ln else (m["product_uom_qty"] if validate else 0)
            if done:
                o("stock.move", "write", [m["id"]], {"quantity": done, "picked": True})
        if validate:
            res = o("stock.picking", "button_validate", [pid])
            if isinstance(res, dict) and res.get("res_model"):
                raise RuntimeError(f"підтвердження {pid} відкрило майстер {res['res_model']}")

    def step_purchase(self):
        o, d = self.o, self.d
        stock = self.ref("loc_root")
        pos = {po["name"]: po for po in d["purchase_orders"]}
        receipts = [p for p in d["pickings"] if p["type"] == "incoming"]
        # кожне приймання — зі своєї закупівлі; закупівля без фури (P00413) — теж
        orders = []
        for p in receipts:
            po = pos.get(p["origin"])
            lines = po["lines"] if po else [{"product": ln["product"], "qty": ln["qty"]} for ln in p["lines"]]
            orders.append((p["origin"], p["partner"], lines, p, po))
        for name, po in pos.items():
            if not any(x[0] == name for x in orders):
                orders.append((name, po["partner"], po["lines"], None, po))
        for name, partner, lines, pick, po in orders:
            xid = key("po", name)
            if self.ref(xid):
                continue
            date_order = po["date_order"] if po else pick["scheduled_date"][:10] + " 08:00"
            planned = po["date_planned"] if po else pick["scheduled_date"]
            if pick:
                planned = pick["scheduled_date"]
            dest = None
            if pick:
                ld = pick.get("location_dest", "")
                dest = self.loc(f"UNLOAD-{pick['dock'][-1]}") if ld.startswith("Вхід") else self.group(ld)
            vals = {"partner_id": self.partner(partner), "date_order": utc(date_order), "origin": False,
                    "order_line": [(0, 0, {"product_id": self.prod(ln["product"]), "product_qty": ln["qty"],
                                           "date_planned": utc(planned)}) for ln in lines]}
            rid = self.ensure(xid, "purchase.order", vals)
            o("purchase.order", "button_confirm", [rid])
            o("purchase.order", "write", [rid], {"name": name, "date_approve": utc(date_order)})
            picks = o("stock.picking", "search", [["purchase_id", "=", rid]])
            if not picks:
                continue
            pid = picks[0]
            if pick:
                self.bind(key("pick", pick["name"]), "stock.picking", pid)
                if dest:
                    o("stock.picking", "write", [pid], {"location_dest_id": dest})
                    mv = o("stock.move", "search", [["picking_id", "=", pid]])
                    o("stock.move", "write", mv, {"location_dest_id": dest})
                self.picking_extra(pid, pick, pick["name"])
                self.set_done_qty(pid, pick["lines"], pick["state"] == "done")
                if pick["state"] == "done":
                    o("stock.picking", "write", [pid], {"date_done": utc(pick["scheduled_date"])})
            else:  # фура ще не приїхала: ворота — ті, що приймають цей товар, номер — наступний за демо
                first = lines[0]["product"]
                door = next(k for k, goods in DOOR_GOODS.items() if first.startswith(goods))
                last = max(int(p["name"].rsplit("/", 1)[1]) for p in receipts)
                extra = sum(1 for x in orders if x[3] is None and x[0] < name)
                self.bind(key("pick", "receipt", name), "stock.picking", pid)
                o("stock.picking", "write", [pid], {
                    "name": f"WH/IN/{last + 1 + extra:05d}", "origin": name, "scheduled_date": utc(planned),
                    "location_dest_id": stock, "x_dock": f"DOCK-W{door}"})
        print(f"purchase: {len(orders)} закупівель, {len(receipts)} приймань")

    # ------------------------------------------------------------ продажі → відвантаження
    def step_sale(self):
        o, d = self.o, self.d
        outs = {p["origin"]: p for p in d["pickings"] if p["type"] == "outgoing"}
        for so in d["sale_orders"]:
            xid = key("so", so["name"])
            if self.ref(xid):
                continue
            vals = {"partner_id": self.partner(so["partner"]), "date_order": utc(so["date_order"]),
                    "commitment_date": utc(so["commitment_date"]),
                    "order_line": [(0, 0, {"product_id": self.prod(ln["product"]), "product_uom_qty": ln["qty"],
                                           "price_unit": FG_PRICE[ln["product"]], "tax_ids": [(6, 0, [])]})
                                   for ln in so["lines"]]}
            rid = self.ensure(xid, "sale.order", vals)
            o("sale.order", "action_confirm", [rid])
            o("sale.order", "write", [rid], {"name": so["name"], "date_order": utc(so["date_order"])})
            out = outs.get(so["name"])
            picks = o("stock.picking", "search", [["sale_id", "=", rid]])
            if out and picks:
                pid = picks[0]
                self.bind(key("pick", out["name"]), "stock.picking", pid)
                carrier = out.get("carrier")
                if carrier:
                    out = dict(out, note=(out.get("note") or "") + (" · " if out.get("note") else "") +
                               f"Перевізник: {carrier}")
                self.picking_extra(pid, out, out["name"])
        print(f"sale: {len(d['sale_orders'])} замовлень клієнтів")

    # ------------------------------------------------------------ внутрішні переміщення
    def step_internal(self):
        o, d = self.o, self.d
        n = 0
        for p in d["pickings"]:
            if p["type"] not in INTERNAL_TYPES or self.ref(key("pick", p["name"])):
                continue
            src_code = (p.get("source_locations") or [None])[0]
            if p["type"] == "pick_components":
                src = self.group("Склад фурнітури")
            elif p["type"] == "store_finished":
                src = self.loc("POST-STAGE")
            else:
                src = self.loc(src_code)
            ld = p.get("location_dest")
            dest = self.loc(ld) or (self.group(ld) if ld in DEST_GROUP else None)
            vals = {"picking_type_id": self.ref(key("ptype", p["type"])), "location_id": src,
                    "location_dest_id": dest, "scheduled_date": utc(p["scheduled_date"]),
                    "move_ids": [(0, 0, {"product_id": self.prod(ln["product"]), "product_uom_qty": ln["qty"],
                                         "location_id": src, "location_dest_id": dest})
                                 for ln in p["lines"]]}
            pid = self.ensure(key("pick", p["name"]), "stock.picking", vals)
            o("stock.picking", "action_confirm", [pid])
            self.picking_extra(pid, p, p["name"])
            self.set_done_qty(pid, p["lines"], p["state"] == "done")
            if p["state"] == "done":
                o("stock.picking", "write", [pid], {"date_done": utc(p["scheduled_date"])})
            n += 1
        print(f"internal: {n} переміщень")

    # ------------------------------------------------------------ виробництво
    def step_production(self):
        o, d = self.o, self.d
        stock = self.ref("loc_root")
        prod_loc = self.one("stock.location", [["usage", "=", "production"]])
        mo_type = self.one("stock.picking.type", [["code", "=", "mrp_operation"]])
        units = self.uom("шт")
        n = 0
        for mo in d["productions"]:
            xid = key("mo", mo["name"])
            wos = [d["workorders"][w] for w in mo["workorders"]]
            if self.ref(xid):
                self.run_workorders(mo, wos)  # МО вже є — лише доганяємо стан завдань
                continue
            vals = {
                "product_id": self.prod(mo["product"]), "product_qty": mo["qty"], "product_uom_id": units,
                "picking_type_id": mo_type, "location_src_id": stock, "location_dest_id": stock,
                "origin": mo["origin"], "date_start": utc(mo["date_start"]), "date_deadline": utc(mo["date_deadline"]),
                "move_raw_ids": [(0, 0, {"product_id": self.prod(c["product"]), "product_uom_qty": c["qty"],
                                         "product_uom": self.uom(d["products"][c["product"]]["uom"]),
                                         "location_id": stock, "location_dest_id": prod_loc})
                                 for c in mo["components"]],
                "workorder_ids": [(0, 0, {"name": w["name"], "workcenter_id": self.ref(key("wc", w["workcenter"])),
                                          "product_uom_id": units, "duration_expected": w["duration_expected"],
                                          "sequence": w["sequence"]}) for w in wos],
            }
            rid = self.ensure(xid, "mrp.production", vals)
            o("mrp.production", "write", [rid], {"name": mo["name"]})
            o("mrp.production", "action_confirm", [rid])
            odoo_wos = o("mrp.workorder", "search_read", [["production_id", "=", rid]],
                         fields=["id", "sequence", "name"], order="sequence,id")
            for w, ow in zip(wos, odoo_wos):
                self.bind(key("wo", w["id"]), "mrp.workorder", ow["id"])
            self.run_workorders(mo, wos)
            n += 1
        print(f"production: {n} нових виробничих замовлень")

    # ------------------------------------------------------------ специфікації й операції
    def step_boms(self):
        """Специфікація на кожну пару «виріб + лінія»: компоненти на 1 шт і операції маршруту.
        Наявні МО й завдання прив'язуються до неї (bom_id, operation_id)."""
        o, d = self.o, self.d
        units = self.uom("шт")
        first = {}
        for mo in d["productions"]:
            first.setdefault((mo["product"], mo["route"]), mo)
        for (pcode, route), mo in first.items():
            wos = [d["workorders"][w] for w in mo["workorders"]]
            xid = key("bom", pcode, route)
            if not self.ref(xid):
                per = {"Розкрій": 2.2, "Пакетний розкрій": 0.9, "Крайкооблицювання": 1.6, "Присадка": 2.0,
                       "Прохідна присадка": 0.8, "Шкантування": 1.0, "Сортування": 0.5, "Збирання": 6.0,
                       "Пакування": 3.0}
                self.ensure(xid, "mrp.bom", {
                    "product_tmpl_id": self.prod_tmpl(pcode), "product_qty": 1, "product_uom_id": units,
                    "code": f"лінія {route}" if not route.startswith("F") else f"фасади {route}",
                    "bom_line_ids": [(0, 0, {"product_id": self.prod(c["product"]),
                                             "product_qty": round(c["qty"] / mo["qty"], 4),
                                             "product_uom_id": self.uom(d["products"][c["product"]]["uom"])})
                                     for c in mo["components"]],
                    "operation_ids": [(0, 0, {"name": w["name"], "sequence": w["sequence"],
                                              "workcenter_id": self.ref(key("wc", w["workcenter"])),
                                              "time_mode": "manual",
                                              "time_cycle_manual": per.get(w["name"], 1.5)}) for w in wos]})
            bom = self.ref(xid)
            ops = o("mrp.routing.workcenter", "search_read", [["bom_id", "=", bom]], fields=["sequence"],
                    order="sequence,id")
            for m in d["productions"]:
                if (m["product"], m["route"]) != (pcode, route):
                    continue
                mid = self.ref(key("mo", m["name"]))
                if o("mrp.production", "read", [mid], ["bom_id"])[0]["bom_id"] is False:
                    o("mrp.production", "write", [mid], {"bom_id": bom})  # повторний запис скидає місця МО
                for w, op in zip([d["workorders"][x] for x in m["workorders"]], ops):
                    wid = self.ref(key("wo", w["id"]))
                    if not o("mrp.workorder", "read", [wid], ["operation_id"])[0]["operation_id"]:
                        o("mrp.workorder", "write", [wid], {"operation_id": op["id"]})
        print(f"boms: {len(first)} специфікацій з операціями")

    def run_workorders(self, mo, wos):
        if mo["state"] != "progress":
            return
        ids = [self.ref(key("wo", w["id"])) for w in wos]
        state = {r["id"]: r["state"] for r in self.o("mrp.workorder", "read", ids, ["state"])}
        for w, wid in zip(wos, ids):
            if w["state"] in ("done", "progress") and state[wid] not in ("done", w["state"]):
                self.run_workorder(wid, w, started=state[wid] == "progress")

    def operator(self, wc_code):
        """Оператор верстата з демо (OP-<код>) або перший із дозволених на робочому центрі."""
        emp = self.ref(key("emp", f"OP-{wc_code}"))
        if not emp:
            allowed = self.o("mrp.workcenter", "read", [self.ref(key("wc", wc_code))], ["employee_ids"])[0]
            emp = (allowed["employee_ids"] or [False])[0]
        return emp

    def run_workorder(self, wid, w, started=False):
        """Запустити/завершити робоче завдання від імені оператора й переписати час на демо."""
        o = self.o
        emp = self.operator(w["workcenter"])
        if not started:
            if emp:
                o("mrp.workorder", "start_employee", [wid], emp)
            else:
                o("mrp.workorder", "button_start", [wid])
        if w["state"] == "done":
            if emp:
                o("mrp.workorder", "stop_employee", [wid], [emp])
            o("mrp.workorder", "button_finish", [wid])
        logs = o("mrp.workcenter.productivity", "search", [["workorder_id", "=", wid]], order="id")
        if logs:
            start = w.get("date_start")
            vals = {"date_start": utc(start)}
            if w["state"] == "done":
                end = datetime.strptime(start, "%Y-%m-%d %H:%M")
                end = (end + timedelta(minutes=w.get("duration", w["duration_expected"]))).strftime("%Y-%m-%d %H:%M")
                vals["date_end"] = utc(end)
            o("mrp.workcenter.productivity", "write", logs[:1], vals)
            if len(logs) > 1:
                o("mrp.workcenter.productivity", "unlink", logs[1:])
        wvals = {"date_start": utc(w.get("date_start"))}
        if w["state"] == "done":
            wvals["date_finished"] = utc(w.get("date_finished"))
        o("mrp.workorder", "write", [wid], wvals)

    # ------------------------------------------------------------ залишки (інвентаризація)
    def step_stock(self):
        """Залишки по комірках — рівно як у демо, з партіями й палетами: інвентаризація виставляє
        абсолютну кількість на кожну пару «комірка + товар + партія + палета»."""
        o, d = self.o, self.d
        want = {}
        for code, loc in d["locations"].items():
            lid = self.loc(code)
            for q in loc["quants"]:
                if q["qty"]:
                    lot = self.lot_id(q["product"], self.lot_of(code, q))
                    pkg = self.package_id(q.get("package"))
                    k = (lid, self.prod(q["product"]), lot, pkg)
                    want[k] = want.get(k, 0) + q["qty"]
        have = o("stock.quant", "search_read", [["location_id", "child_of", self.ref("loc_wh")],
                                                ["location_id.usage", "=", "internal"]],
                 fields=["location_id", "product_id", "quantity", "lot_id", "package_id"])
        ctx = dict(self.o.ctx, inventory_mode=True)
        todo = []
        seen = set()
        for q in have:
            k = (q["location_id"][0], q["product_id"][0], q["lot_id"] and q["lot_id"][0],
                 q["package_id"] and q["package_id"][0])
            seen.add(k)
            tgt = want.get(k, 0)
            if abs(q["quantity"] - tgt) > 1e-6:
                todo.append(("w", q["id"], tgt))
        for k, qty in want.items():
            if k not in seen:
                todo.append(("c", k, qty))
        ids = []
        for kind, ref, qty in todo:
            if kind == "w":
                o("stock.quant", "write", [ref], {"inventory_quantity": qty}, context=ctx)
                ids.append(ref)
            else:
                ids.append(o("stock.quant", "create", {"location_id": ref[0], "product_id": ref[1],
                                                       "lot_id": ref[2], "package_id": ref[3],
                                                       "inventory_quantity": qty}, context=ctx))
        for i in range(0, len(ids), 200):
            o("stock.quant", "action_apply_inventory", ids[i:i + 200], context=ctx)
        print(f"stock: {len(want)} залишків, змінено {len(ids)}")

    # ------------------------------------------------------------ якість і ТО
    def step_quality(self):
        o, d = self.o, self.d
        if not o.has("quality.check"):
            print("quality: модуль не встановлено — пропуск")
            return
        team = self.one("quality.alert.team", [])
        ttype = self.one("quality.point.test_type", [["technical_name", "=", "passfail"]])
        rcv = self.one("stock.picking.type", [["code", "=", "incoming"]])
        mo_type = self.one("stock.picking.type", [["code", "=", "mrp_operation"]])
        sheets = self.ref(key("categ", "Плитні матеріали"))
        pts = {
            "Вхідний контроль плит": self.ensure("qp_sheets", "quality.point", {
                "title": "Вхідний контроль плит", "team_id": team, "test_type_id": ttype,
                "picking_type_ids": [(6, 0, [rcv])], "product_category_ids": [(6, 0, [sheets])],
                "note": "<p>Товщина в 4 точках (допуск ±0,3 мм), декор, кромки, вологість.</p>"}),
            "Контроль збирання": self.ensure("qp_asm", "quality.point", {
                "title": "Контроль збирання", "team_id": team, "test_type_id": ttype,
                "picking_type_ids": [(6, 0, [mo_type])],
                "note": "<p>Діагоналі корпусу, робота фасадів і ящиків.</p>"}),
        }
        for qc in d["quality_checks"]:
            xid = key("qc", qc["name"])
            if self.ref(xid):
                continue
            vals = {"point_id": pts[qc["title"]], "team_id": team, "test_type_id": ttype,
                    "product_id": self.prod(qc["product"]), "note": f"<p>{qc['note']}</p>"}
            if qc.get("picking"):
                vals["picking_id"] = self.ref(key("pick", qc["picking"]))
            if qc.get("production"):
                vals["production_id"] = self.ref(key("mo", qc["production"]))
            rid = self.ensure(xid, "quality.check", vals)
            o("quality.check", "write", [rid], {"name": qc["name"]})
            if qc["state"] == "pass":
                o("quality.check", "do_pass", [rid])
            elif qc["state"] == "fail":
                o("quality.check", "do_fail", [rid])
        # партія на перевірці й сповіщення про брак (карантинний стос QC-1, претензія постачальнику)
        for qc in d["quality_checks"]:
            rid = self.ref(key("qc", qc["name"]))
            lot = qc.get("lot") and self.lot_id(qc["product"], qc["lot"])
            if lot:
                o("quality.check", "write", [rid], {"lot_ids": [(6, 0, [lot])]})
            if qc["state"] == "fail":
                self.ensure(key("qa", qc["name"]), "quality.alert", {
                    "title": f"{qc['title']}: брак партії {qc.get('lot') or ''}".strip(),
                    "check_id": rid, "product_tmpl_id": self.prod_tmpl(qc["product"]),
                    "product_id": self.prod(qc["product"]), "lot_ids": [(6, 0, [lot] if lot else [])],
                    "team_id": team,
                    "picking_id": self.ref(key("pick", qc["picking"])) if qc.get("picking") else False,
                    "description": f"<p>{qc['note']} Стос — у карантині ({qc['location']}).</p>",
                    "partner_id": self.partner(next((p["partner"] for p in d["pickings"]
                                                     if p["name"] == qc.get("picking")), None))})
        print(f"quality: {len(d['quality_checks'])} перевірок, "
              f"{sum(q['state'] == 'fail' for q in d['quality_checks'])} сповіщення про брак")

    def step_maintenance(self):
        o, d = self.o, self.d
        if not o.has("maintenance.equipment"):
            print("maintenance: модуль не встановлено — пропуск")
            return
        cats = {}

        def cat(name):
            if name not in cats:
                cats[name] = self.ensure(key("eqcat", name), "maintenance.equipment.category", {"name": name})
            return cats[name]
        wc_link = "workcenter_id" in o("maintenance.equipment", "fields_get", attributes=["type"])
        team = self.ensure("maint_team", "maintenance.team", {"name": "Служба головного механіка",
                                                               "member_ids": [(6, 0, [o.uid])]})
        for code, wc in d["workcenters"].items():
            vals = {"name": wc["name"], "category_id": cat("Верстати"), "serial_no": code,
                    "maintenance_team_id": team,
                    "model": " ".join(x for x in (wc.get("manufacturer"), wc.get("model")) if x)}
            if wc_link:
                vals["workcenter_id"] = self.ref(key("wc", code))
            self.ensure(key("eq", code), "maintenance.equipment", vals)
        for code, eq in d["equipment"].items():
            vals = {"name": eq["name"], "category_id": cat(eq.get("category", "Інше")), "maintenance_team_id": team,
                    "serial_no": eq.get("serial") or code,
                    "model": " ".join(x for x in (eq.get("manufacturer"), eq.get("model")) if x) or False}
            self.ensure(key("eq", code), "maintenance.equipment", vals)
        extra = {"FA-FAC": ("Пожежна сигналізація, фасадна дільниця", "Безпека"),
                 "RV-05": ("Припливно-витяжна установка RV-05", "Вентиляція")}
        for code, (name, c) in extra.items():
            self.ensure(key("eq", code), "maintenance.equipment",
                        {"name": name, "category_id": cat(c), "serial_no": code, "maintenance_team_id": team})
        stages = o("maintenance.stage", "search_read", [], fields=["id", "name", "done"], order="sequence")
        stage = {"Новий": stages[0]["id"], "В роботі": stages[1]["id"] if len(stages) > 1 else stages[0]["id"]}
        for mr in d["maintenance_requests"]:
            xid = key("mr", mr["id"])
            vals = {"name": mr["name"], "equipment_id": self.ref(key("eq", mr["equipment"])),
                    "maintenance_type": mr["maintenance_type"], "stage_id": stage.get(mr["stage"], stages[0]["id"]),
                    "maintenance_team_id": team,
                    "priority": mr.get("priority", "1"),
                    "description": f"<p>{mr['id']}" + (f" · виконавець: {mr['technician']}" if mr.get("technician")
                                                         else "") + "</p>"}
            if mr.get("request_date"):
                vals["request_date"] = mr["request_date"][:10]
            if mr.get("schedule_date"):
                vals["schedule_date"] = utc(mr["schedule_date"])
            self.ensure(xid, "maintenance.request", vals)
        print(f"maintenance: {len(d['workcenters']) + len(d['equipment']) + len(extra)} одиниць, "
              f"{len(d['maintenance_requests'])} заявок")

    # ------------------------------------------------------------ дочищення
    def step_finish(self):
        o = self.o
        open_picks = o("stock.picking", "search", [["state", "in", ["confirmed", "waiting", "assigned"]]])
        if open_picks:
            o("stock.picking", "action_assign", open_picks)
        for p in self.d["pickings"]:  # почате, але не закінчене: зібрано/перевезено частину рядків
            pid = self.ref(key("pick", p["name"]))
            if pid and p["type"] != "incoming" and p["state"] != "done" and p["progress"]:
                self.set_done_qty(pid, p["lines"], False)
        mos = o("mrp.production", "search", [["state", "in", ["confirmed", "progress"]]])
        if mos:
            o("mrp.production", "action_assign", mos)
        # зупинений верстат (CNC-2): відкритий простій «поломка» блокує робочий центр, як у демо
        loss = self.one("mrp.workcenter.productivity.loss", [["name", "=", "Equipment Failure"]],
                        context={"lang": "en_US"}) or \
            self.one("mrp.workcenter.productivity.loss", [["loss_type", "=", "availability"]])
        for code, wc in self.d["workcenters"].items():
            if wc["status"] != "stop" or not loss:
                continue
            start = NOW - timedelta(minutes=next((x["minutes"] for x in wc["losses"] if x["reason"] == "Поломка"), 30))
            start_s = start.strftime("%Y-%m-%d %H:%M")
            self.ensure(key("block", code), "mrp.workcenter.productivity", {
                "workcenter_id": self.ref(key("wc", code)), "loss_id": loss, "date_start": utc(start_s),
                "description": wc.get("maintenance_request") or "Поломка"})
            # завдання на верстаті працювало до поломки: таймер зупинено в момент поломки
            w = self.d["workorders"].get(wc.get("current_workorder"))
            wid = w and self.ref(key("wo", w["id"]))
            if wid:
                begin = (start - timedelta(minutes=w.get("duration") or 30)).strftime("%Y-%m-%d %H:%M")
                logs = o("mrp.workcenter.productivity", "search", [["workorder_id", "=", wid]], order="id")
                if logs:
                    o("mrp.workcenter.productivity", "write", logs[:1],
                      {"date_start": utc(begin), "date_end": utc(start_s)})
                o("mrp.workorder", "write", [wid], {"date_start": utc(begin)})
        # нумерація далі за демо, щоб нові документи з інтерфейсу не перетиналися з назвами в 3D
        bumps = {"mrp.production": 263, "sale.order": 95, "purchase.order": 418}
        for code, nxt in bumps.items():
            for sid in o("ir.sequence", "search", [["code", "=", code]]):
                o("ir.sequence", "write", [sid], {"number_next": nxt})
        for ptype, nxt in (("incoming", 136), ("outgoing", 420)):
            for pt in o("stock.picking.type", "search_read", [["code", "=", ptype]], fields=["sequence_id"]):
                if pt["sequence_id"]:
                    o("ir.sequence", "write", [pt["sequence_id"][0]], {"number_next": nxt})
        print(f"finish: резерв для {len(open_picks)} переміщень і {len(mos)} МО, нумерацію зсунуто")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--only", help="кроки через кому: " + ",".join(STEPS))
    a = ap.parse_args(argv)
    steps = a.only.split(",") if a.only else STEPS
    o = Odoo()
    print(f"Odoo {o.version['server_version']} · {o.url} · база {o.db}, демо-час {NOW:%Y-%m-%d %H:%M}")
    p = Push(o, Demo().build())
    for s in steps:
        getattr(p, "step_" + s)()
    print(f"готово, нових записів: {p.n_new}")


if __name__ == "__main__":
    sys.exit(main())
