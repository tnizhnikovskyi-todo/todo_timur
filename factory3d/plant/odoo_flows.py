"""Кроки заливки, що вмикають у Odoo все, чим користується модель: модулі (IoT, відвідування, доставка),
поля «Ворота / Фура / Техніка» на формах, графік зміни, зони поза WH/Stock, партії й палети, багатокрокові
маршрути (приймання плит через вхідний контроль, комплектація й розміщення ГП, відвантаження у 2 кроки),
правила поповнення, дочірні МО фасадів, простої верстатів, перевізники. Підмішуються до Push у odoo_push.py."""
from datetime import timedelta

from .odoo_demo import NOW
from .odoo_rpc import key, utc

# зони, де товар ще (або вже) не вільний: як Input / Quality Control / Pre-/Post-Production / Output у стандарті
OUTSIDE_STOCK = {"Вхід", "Контроль якості", "Приймання", "Передвиробництво", "Пост-виробництво", "Відвантаження"}
LOSS_STD = {"Налагодження": "Setup and Adjustments", "Очікування матеріалу": "Material Availability",
            "Поломка": "Equipment Failure"}
DAYS = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця"]


class FlowSteps:
    # ------------------------------------------------------------ модулі й форми
    def step_modules(self):
        self.o.install("iot", "hr_attendance", "stock_delivery")
        print("modules: iot, hr_attendance, stock_delivery")

    def xmlid(self, module, name):
        r = self.o("ir.model.data", "search_read", [["module", "=", module], ["name", "=", name]], fields=["res_id"])
        return r[0]["res_id"] if r else False

    def step_views(self):
        form = self.xmlid("stock", "view_picking_form")
        tree = self.xmlid("stock", "vpicktree")
        self.ensure("view_picking_form_dock", "ir.ui.view", {
            "name": "factory3d: ворота, фура, техніка", "model": "stock.picking", "inherit_id": form, "arch": (
                '<data><xpath expr="//field[@name=\'origin\']" position="after">'
                '<field name="x_dock" invisible="not x_dock"/><field name="x_truck" invisible="not x_truck"/>'
                '<field name="x_vehicle" invisible="not x_vehicle"/></xpath></data>')})
        self.ensure("view_picking_list_dock", "ir.ui.view", {
            "name": "factory3d: ворота в списку", "model": "stock.picking", "inherit_id": tree, "arch": (
                '<data><xpath expr="//field[@name=\'origin\']" position="after">'
                '<field name="x_dock" optional="show"/><field name="x_vehicle" optional="hide"/></xpath></data>')})
        print("views: ворота, фура й техніка на формі та в списку переміщень")

    def step_calendar(self):
        att = []
        for i, day in enumerate(DAYS):
            att += [(0, 0, {"name": f"{day}, до обіду", "dayofweek": str(i), "hour_from": 7, "hour_to": 11.5,
                            "day_period": "morning"}),
                    (0, 0, {"name": f"{day}, після обіду", "dayofweek": str(i), "hour_from": 12, "hour_to": 15.5,
                            "day_period": "afternoon"})]
        cal = self.ensure("calendar_shift1", "resource.calendar", {
            "name": "Зміна 1 (07:00–15:30)", "tz": "Europe/Kyiv", "attendance_ids": [(5, 0, 0)] + att}, update=False)
        self.o("res.company", "write", [1], {"resource_calendar_id": cal})
        print("calendar: Зміна 1 (07:00–15:30), пн–пт, обід 11:30–12:00")

    # ------------------------------------------------------------ зони поза WH/Stock
    def step_layout(self):
        """Перенести зони приймання, контролю, карантину, передвиробництва, пост-виробництва й відвантаження
        поруч зі Stock. Резерви перед цим знімаємо (повертаються в кроці finish)."""
        o = self.o
        wh = self.ref("loc_wh")
        todo = []
        for name in OUTSIDE_STOCK:
            code = next((c for c, loc in self.d["locations"].items() if loc["complete_name"] == f"WH/{name}"), None)
            rid = self.loc(code) if code else self.ref(key("locgrp", name))
            if rid and o("stock.location", "read", [rid], ["location_id"])[0]["location_id"][0] != wh:
                todo.append(rid)
        if not todo:
            print("layout: зони вже поза WH/Stock")
            return
        picks = o("stock.picking", "search", [["state", "in", ["confirmed", "waiting", "assigned"]],
                                              ["picking_type_code", "!=", "incoming"]])
        moves = o("stock.move", "search", [["picking_id", "in", picks], ["picked", "=", True]])
        if moves:
            o("stock.move", "write", moves, {"picked": False})
        if picks:
            o("stock.picking", "do_unreserve", picks)
        mos = o("mrp.production", "search", [["state", "in", ["confirmed", "progress", "to_close"]]])
        if mos:
            o("mrp.production", "do_unreserve", mos)
        o("stock.location", "write", todo, {"location_id": wh})
        print(f"layout: {len(todo)} зон перенесено поза WH/Stock, резерв знято з {len(picks)} переміщень і "
              f"{len(mos)} МО")

    # ------------------------------------------------------------ партії й палети
    @property
    def tracked(self):
        if not hasattr(self, "_tracked"):
            self._tracked = {q["product"] for loc in self.d["locations"].values() for q in loc["quants"]
                             if q.get("lot")}
        return self._tracked

    def lot_of(self, code, q):
        """Партія залишку: з моделі, а для стосів біля воріт і на контролі — за прийманням цих воріт."""
        if q.get("lot"):
            return q["lot"]
        if q["product"] not in self.tracked:
            return None
        if code.startswith(("UNLOAD-", "QC-PLT-")):
            door = f"DOCK-W{code.rsplit('-', 1)[1]}"
            for p in self.d["pickings"]:
                if p["type"] == "incoming" and p.get("dock") == door and \
                        any(ln["product"] == q["product"] and ln["qty_done"] for ln in p["lines"]):
                    return self.receipt_lot(q["product"], p["name"])
        return f"{q['product']}-{code}"

    @staticmethod
    def receipt_lot(product, picking):
        return f"{product}-{picking.rsplit('/', 1)[1]}"

    def lot_id(self, product, name):
        if not name:
            return False
        cache = self.__dict__.setdefault("_lots", {})
        k = (product, name)
        if k not in cache:
            pid = self.prod(product)
            cache[k] = self.one("stock.lot", [["name", "=", name], ["product_id", "=", pid]]) or \
                self.o("stock.lot", "create", {"name": name, "product_id": pid})
        return cache[k]

    def package_id(self, name):
        if not name:
            return False
        cache = self.__dict__.setdefault("_pkgs", {})
        if name not in cache:
            cache[name] = self.one("stock.package", [["name", "=", name]]) or \
                self.o("stock.package", "create", {"name": name})
        return cache[name]

    def step_lots(self):
        """Партії на вже вивантажених рядках приймань (фура ще біля воріт)."""
        o, n = self.o, 0
        codes = {self.prod(c): c for c in self.tracked}
        for p in self.d["pickings"]:
            pid = self.ref(key("pick", p["name"]))
            if p["type"] != "incoming" or p["state"] == "done" or not pid:
                continue
            for ml in o("stock.move.line", "search_read", [["picking_id", "=", pid], ["lot_id", "=", False],
                                                           ["lot_name", "=", False],
                                                           ["product_id.tracking", "=", "lot"]],
                        fields=["product_id"]):
                o("stock.move.line", "write", [ml["id"]],
                  {"lot_name": self.receipt_lot(codes[ml["product_id"][0]], p["name"])})
                n += 1
        print(f"lots: партії на {n} рядках приймань; облік партій — {len(self.tracked)} товарів")

    # ------------------------------------------------------------ маршрути
    def step_routes(self):
        o = self.o
        wid = self.ref("warehouse")

        def g(path):
            return self.ref(key("locgrp", path))
        # контроль якості — лише для плит (власний маршрут нижче); стандартну зону QC склад вимикає сам
        vals = {"wh_input_stock_loc_id": g("Вхід"), "wh_output_stock_loc_id": g("Відвантаження"), "pbm_loc_id": g("Передвиробництво"),
                "sam_loc_id": self.loc("POST-STAGE"), "pbm_type_id": self.ref(key("ptype", "pick_components")),
                "sam_type_id": self.ref(key("ptype", "store_finished"))}
        cur = o("stock.warehouse", "read", [wid], list(vals) + ["reception_steps", "delivery_steps",
                                                                 "manufacture_steps", "qc_type_id"])[0]
        diff = {k: v for k, v in vals.items() if (cur[k] and cur[k][0]) != v}
        if diff:
            o("stock.warehouse", "write", [wid], diff)
        steps = {"reception_steps": "two_steps", "delivery_steps": "pick_ship", "manufacture_steps": "pbm_sam"}
        steps = {k: v for k, v in steps.items() if cur[k] != v}
        if steps:
            o("stock.warehouse", "write", [wid], steps)
        # плити: вивантаження → вхідний контроль → стелажі (поверх двокрокового приймання складу)
        qc_type = cur["qc_type_id"][0]
        o("stock.picking.type", "write", [qc_type], {"active": True, "name": "Вхідний контроль плит"})
        racks, portal = g("Сировина/Плити/Стелажі"), g("Сировина/Плити/Портал")
        sheets = self.ref(key("categ", "Плитні матеріали"))
        r_qc = self.ensure("route_sheets_qc", "stock.route", {
            "name": "Плити: вивантаження → вхідний контроль → стелажі", "sequence": 5,
            "product_categ_selectable": True, "product_selectable": False})
        self.ensure("rule_sheets_in_qc", "stock.rule", {
            "name": "Вхід → контроль якості (плити)", "route_id": r_qc, "action": "push", "auto": "manual",
            "location_src_id": g("Вхід"), "location_dest_id": g("Контроль якості"), "picking_type_id": qc_type,
            "warehouse_id": wid})
        self.ensure("rule_sheets_qc_rack", "stock.rule", {
            "name": "Контроль якості → стелажі (плити)", "route_id": r_qc, "action": "push", "auto": "manual",
            "location_src_id": g("Контроль якості"), "location_dest_id": racks,
            "picking_type_id": self.ref(key("ptype", "putaway")), "warehouse_id": wid})
        # плити: стелажі → ряд під порталом (правила поповнення на стосах порталу)
        r_portal = self.ensure("route_portal", "stock.route", {
            "name": "Поповнення під портал", "sequence": 6, "product_categ_selectable": True,
            "product_selectable": True})
        self.ensure("rule_portal", "stock.rule", {
            "name": "Стелажі → портал", "route_id": r_portal, "action": "pull", "procure_method": "make_to_stock",
            "location_src_id": racks, "location_dest_id": portal, "warehouse_id": wid,
            "picking_type_id": self.ref(key("ptype", "replenish"))})
        o("product.category", "write", [sheets], {"route_ids": [(4, r_qc), (4, r_portal)]})
        print("routes: приймання у 2 кроки (плити — через вхідний контроль у 3), комплектація й розміщення ГП "
              "(виробництво у 3 кроки), відвантаження у 2 кроки, поповнення під портал")

    def step_orderpoints(self):
        d = self.d
        wid = self.ref("warehouse")
        buy = self.xmlid("purchase_stock", "route_warehouse0_buy")
        portal = self.ref("route_portal")
        n_hw = n_pl = 0
        for code, loc in d["locations"].items():
            op = loc.get("orderpoint")
            if op:  # комірки фурнітури: мін/макс — як у моделі, дозамовлення в постачальника
                self.ensure(key("op", code), "stock.warehouse.orderpoint", {
                    "product_id": self.prod(op["product"]), "location_id": self.loc(code), "warehouse_id": wid,
                    "product_min_qty": op["min"], "product_max_qty": op["max"], "trigger": "manual",
                    "route_id": buy})
                n_hw += 1
            elif code.startswith("PLT-") and loc["quants"] and portal:  # стос під порталом: 10…60 аркушів
                self.ensure(key("op", code), "stock.warehouse.orderpoint", {
                    "product_id": self.prod(loc["quants"][0]["product"]), "location_id": self.loc(code),
                    "warehouse_id": wid, "product_min_qty": 10, "product_max_qty": loc["capacity"],
                    "trigger": "manual", "route_id": portal})
                n_pl += 1
        print(f"orderpoints: {n_hw} комірок фурнітури (закупівля), {n_pl} стосів порталу (зі стелажів)")

    # ------------------------------------------------------------ виробництво
    def step_children(self):
        """Групи МО з назвами замовлень; фасади — дочірні МО до МО корпусу."""
        o, d = self.o, self.d
        grp = {}
        for mo in d["productions"]:
            mid = self.ref(key("mo", mo["name"]))
            g = o("mrp.production", "read", [mid], ["production_group_id"])[0]["production_group_id"]
            if g:
                grp[mo["name"]] = g[0]
                if g[1] != mo["name"]:
                    o("mrp.production.group", "write", [g[0]], {"name": mo["name"]})
        n = 0
        for mo in d["productions"]:
            parent = mo.get("origin")
            if mo["route"].startswith("F") and parent in grp and mo["name"] in grp:
                o("mrp.production.group", "write", [grp[parent]], {"child_ids": [(4, grp[mo["name"]])]})
                n += 1
        print(f"children: {n} МО фасадів прив'язано до МО корпусів")

    def step_losses(self):
        d = self.d
        loss = {r: self.one("mrp.workcenter.productivity.loss", [["name", "=", en]], context={"lang": "en_US"})
                for r, en in LOSS_STD.items()}
        for r, xid in (("Заміна інструменту", "loss_tool"), ("Перерва", "loss_break")):
            loss[r] = self.ensure(xid, "mrp.workcenter.productivity.loss",
                                  {"name": r, "loss_type": "availability", "manual": True})
        n = 0
        for code, wc in d["workcenters"].items():
            t = NOW.replace(hour=7, minute=0)
            for i, ls in enumerate(wc["losses"]):
                if ls["reason"] == "Поломка" and wc["status"] == "stop":
                    continue  # відкритий простій CNC-2 ставить крок finish
                end = t + timedelta(minutes=ls["minutes"])
                self.ensure(key("loss", code, i), "mrp.workcenter.productivity", {
                    "workcenter_id": self.ref(key("wc", code)), "loss_id": loss[ls["reason"]],
                    "date_start": utc(t.strftime("%Y-%m-%d %H:%M")), "date_end": utc(end.strftime("%Y-%m-%d %H:%M")),
                    "description": ls["reason"]}, update=False)
                t = end
                n += 1
        print(f"losses: {n} простоїв верстатів за зміну")

    # ------------------------------------------------------------ перевізники
    def step_carriers(self):
        o, d = self.o, self.d
        if not o.has("delivery.carrier"):
            print("carriers: модуль доставки не встановлено — пропуск")
            return
        tid = self.ensure("tmpl_delivery", "product.template", {
            "name": "Доставка", "default_code": "DELIVERY", "type": "service", "sale_ok": False,
            "purchase_ok": False, "list_price": 0})
        pid = o("product.product", "search", [["product_tmpl_id", "=", tid]])[0]
        carriers = {}
        for name in sorted({p["carrier"] for p in d["pickings"] if p.get("carrier")}):
            carriers[name] = self.ensure(key("carrier", name), "delivery.carrier", {
                "name": name, "delivery_type": "fixed", "fixed_price": 0, "product_id": pid})
        for p in d["pickings"]:
            if p.get("carrier"):
                o("stock.picking", "write", [self.ref(key("pick", p["name"]))], {"carrier_id": carriers[p["carrier"]]})
                so = self.ref(key("so", p["origin"]))
                if so:
                    o("sale.order", "write", [so], {"carrier_id": carriers[p["carrier"]]})
        print(f"carriers: {len(carriers)} перевізники на відвантаженнях і замовленнях")
