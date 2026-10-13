"""Кроки заливки, що вмикають у Odoo все, чим користується модель: модулі (IoT, відвідування, доставка),
поля «Ворота / Фура / Техніка» на формах, графік зміни, зони поза WH/Stock, партії й палети, багатокрокові
маршрути (приймання плит через вхідний контроль, комплектація й розміщення ГП, відвантаження у 2 кроки),
правила поповнення, дочірні МО фасадів, простої верстатів, перевізники. Підмішуються до Push у odoo_push.py."""
from datetime import timedelta
from html import escape

from .odoo_demo import NOW, det, ts
from .odoo_rpc import key, utc

# зони, де товар ще (або вже) не вільний: як Input / Quality Control / Post-Production / Output у стандарті.
# Передвиробництво (візки KIT, етажерки фасадів) — у Stock: з нього МО бере фурнітуру й фасади
OUTSIDE_STOCK = {"Вхід", "Контроль якості", "Приймання", "Пост-виробництво", "Відвантаження"}
LOSS_STD = {"Налагодження": "Setup and Adjustments", "Очікування матеріалу": "Material Availability",
            "Поломка": "Equipment Failure"}
DAYS = ["Понеділок", "Вівторок", "Середа", "Четвер", "П'ятниця"]
# назви об'єктів, яких немає ні серед верстатів, ні серед обладнання, вентиляції, світла чи пожежних груп
NAMES = {
    "BOARD-RACKS": "Консольні стелажі плит (буфер перед порталом)", "FL-6": "Навантажувач плит 2",
    "RM6-1": "КТП 10 кВ (комірки RM6)", "SWB-1": "Головний розподільний щит ГРЩ", "EMS-1": "Лічильники енергії",
    "GENSET": "Дизель-генератор", "LP-1": "Щит освітлення LP-1", "LP-2": "Щит освітлення LP-2",
    "LP-3": "Щит освітлення LP-3", "EMERGENCY": "Аварійне освітлення", "FACP-1": "Приймально-контрольний прилад",
    "FA-MCP": "Ручні пожежні сповіщувачі", "FA-SND": "Оповіщувачі світлозвукові",
    "FA-FLAME": "Сповіщувачі полум'я (фарбування)", "SPARK-1": "Іскрогасіння аспірації",
    "ATS-1": "Автоматичне введення резерву", "BESS": "Накопичувач енергії", "PV-ROOF": "Сонячна станція: модулі",
    "PV-INV": "Сонячна станція: інвертори", "CHP": "Когенераційна установка",
    "SMOKE-VENTS": "Люки димовидалення", "SMOKE-CTRL": "Щит керування димовидаленням",
    "EXITS": "Евакуаційні двері", "LPS": "Блискавкозахист", "WATER": "Водомірний вузол",
    "ODOO-TABLETS": "Планшети робочих місць Odoo", "ODOO-SCANNERS": "Сканери штрихкодів", "WIFI": "Точки Wi-Fi",
    "SERVER": "Серверна шафа", "TURNSTILES": "Турнікети прохідної", "ACCESS": "Зчитувачі СКУД",
    "CCTV": "Відеоспостереження", "TRUCK-SCALE": "Автомобільні ваги", "GATE-W": "Шлагбаум в'їзду",
    "GATE-E": "Шлагбаум виїзду", "PRN-RCV": "Принтер етикеток: приймання",
    "PRN-PACK1": "Принтер етикеток: пакування 1", "PRN-PACK2": "Принтер етикеток: пакування 2",
    "PRN-OUT": "Принтер етикеток: відвантаження", "SCALE-OUT1": "Палетні ваги: відвантаження 1",
    "SCALE-OUT2": "Палетні ваги: відвантаження 2", "SCALE-RCV": "Палетні ваги: приймання",
    "IOT-RCV": "IoT Box: приймання", "IOT-PACK": "IoT Box: пакування", "IOT-OUT": "IoT Box: відвантаження",
    "EYE-CHG": "Фонтанчик для очей: зарядна", "EYE-PAINT": "Фонтанчик для очей: фарбування",
}
CATEGORY = {  # роль паспорта → категорія обладнання
    "Електропостачання": ("substation", "transformer", "main_switchboard", "acb", "busbar_dist", "pfc", "power_meter",
                          "ats", "genset", "bess", "pv_module", "pv_inverter", "chp", "lightning_air"),
    "Освітлення": ("highbay", "lighting_control", "emergency"),
    "Вентиляція й опалення": ("roofvent", "make_up_ahu", "ex_fan", "wall_fan", "biomass_boiler"),
    "Пожежна безпека": ("facp", "smoke_detector", "multi_detector", "heat_detector", "flame_detector", "mcp",
                        "sounder_beacon", "spark_detection", "smoke_vent", "smoke_control", "exit_door"),
    "Склад і транспорт": ("forklift", "board_forklift", "tugger", "board_rack", "board_storage", "highbay_rack",
                          "truck_scale", "barrier"),
    "Odoo та ІТ": ("iot_box", "label_printer", "scale", "shopfloor_tablet", "handheld_scanner", "wifi_ap",
                   "server_rack"),
    "Охорона й доступ": ("access_reader", "turnstile", "cctv_camera"),
    "Інженерні мережі": ("compressor", "dust_extraction", "water_meter"),
    "Охорона праці": ("eyewash",),
}
ROLE_CAT = {r: c for c, roles in CATEGORY.items() for r in roles}


def passport_note(pp, extra=""):
    """Паспорт виробу в примітку обладнання: чому обрано, характеристики, габарити, джерела."""
    rows = "".join(f"<tr><td>{escape(k)}</td><td>{escape(str(v))}</td></tr>" for k, v in (pp.get("specs") or {}).items())
    facts = []
    if pp.get("units"):
        facts.append(f"Кількість: {pp['units']}")
    dims = pp.get("dimensions_mm")
    if dims:
        facts.append("Габарити: " + " × ".join(str(dims[k]) for k in ("L", "W", "H") if k in dims) + " мм")
    if pp.get("power_kw"):
        facts.append(f"Потужність: {pp['power_kw']} кВт")
    links = " ".join(f'<a href="{escape(u)}">[{i}]</a>' for i, u in enumerate(pp.get("sources") or [], 1))
    return (f"<p>{escape(pp.get('reason', ''))}</p>" + (f"<table>{rows}</table>" if rows else "") +
            (f"<p>{escape(' · '.join(facts))}</p>" if facts else "") + (f"<p>{escape(extra)}</p>" if extra else "") +
            (f"<p>Джерела: {links}</p>" if links else ""))


class FlowSteps:
    # ------------------------------------------------------------ модулі й форми
    def step_modules(self):
        mods = ("iot", "hr_attendance", "stock_delivery", "stock_picking_batch", "stock_fleet")
        self.o.install(*mods)
        print("modules: " + ", ".join(mods))

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
        """Зони приймання, контролю, карантину, пост-виробництва й відвантаження — поруч зі Stock, решта
        (сировина, передвиробництво, ГП) — у Stock. Резерви перед перенесенням знімаємо (повертає finish)."""
        o = self.o
        wh, stock = self.ref("loc_wh"), self.ref("loc_root")
        todo = {}
        for name in {loc["complete_name"].split("/")[1] for loc in self.d["locations"].values()}:
            code = next((c for c, loc in self.d["locations"].items() if loc["complete_name"] == f"WH/{name}"), None)
            rid = self.loc(code) if code else self.ref(key("locgrp", name))
            want = wh if name in OUTSIDE_STOCK else stock
            if rid and o("stock.location", "read", [rid], ["location_id"])[0]["location_id"][0] != want:
                todo.setdefault(want, []).append(rid)
        if not todo:
            print("layout: зони на своїх місцях")
            return
        picks = o("stock.picking", "search", [["state", "in", ["confirmed", "waiting", "assigned"]],
                                              ["picking_type_code", "!=", "incoming"]])
        moves = o("stock.move", "search", [["picking_id", "in", picks], ["picked", "=", True]])
        if moves:
            o("stock.move", "write", moves, {"picked": False})
        if picks:
            o("stock.picking", "do_unreserve", picks)
        mos = o("mrp.production", "search", [["state", "in", ["confirmed", "progress", "to_close"]]])
        raw = o("stock.move", "search", [["raw_material_production_id", "in", mos], ["picked", "=", True],
                                         ["state", "not in", ["done", "cancel"]]])
        if raw:
            o("stock.move", "write", raw, {"picked": False, "quantity": 0})
        if mos:
            o("mrp.production", "do_unreserve", mos)
        for parent, ids in todo.items():
            o("stock.location", "write", ids, {"location_id": parent})
        print(f"layout: перенесено зон — {sum(len(v) for v in todo.values())}, резерв знято з {len(picks)} "
              f"переміщень і {len(mos)} МО")

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
        vals = {"wh_input_stock_loc_id": g("Вхід"), "wh_output_stock_loc_id": g("Відвантаження")}
        cur = o("stock.warehouse", "read", [wid], list(vals) + [
            "reception_steps", "delivery_steps", "manufacture_steps", "qc_type_id", "manu_type_id",
            "pbm_type_id", "sam_type_id", "pbm_loc_id", "sam_loc_id"])[0]
        pc, sfp = self.ref(key("ptype", "pick_components")), self.ref(key("ptype", "store_finished"))
        if cur["manufacture_steps"] != "mrp_one_step":
            # виробництво — в 1 крок, як у моделі: плиту портал подає просто на пилу, крайку й ЛФМ беруть зі
            # своїх складів; через комплектацію (WH/PC у візки KIT) іде лише фурнітура. Стандартні типи й зони
            # Odoo повертаємо складу, свої типи лишаються окремими
            std = {r["sequence_code"]: r["id"] for r in o("stock.picking.type", "search_read", [
                ["warehouse_id", "=", wid], ["sequence_code", "in", ["PC", "SFP"]], ["id", "not in", [pc, sfp]],
                ["active", "in", [True, False]]], fields=["sequence_code"])}
            pre_post = {r["name"]: r["id"] for r in o("stock.location", "search_read", [
                ["name", "in", ["Pre-Production", "Post-Production"]], ["active", "in", [True, False]]],
                fields=["name"], context={"lang": "en_US"})}
            o("stock.warehouse", "write", [wid], {
                "pbm_type_id": std["PC"], "sam_type_id": std["SFP"], "pbm_loc_id": pre_post["Pre-Production"],
                "sam_loc_id": pre_post["Post-Production"]})
            o("stock.warehouse", "write", [wid], {"manufacture_steps": "mrp_one_step"})
        diff = {k: v for k, v in vals.items() if (cur[k] and cur[k][0]) != v}
        if diff:
            o("stock.warehouse", "write", [wid], diff)
        steps = {"reception_steps": "two_steps", "delivery_steps": "pick_ship"}
        steps = {k: v for k, v in steps.items() if cur[k] != v}
        if steps:
            o("stock.warehouse", "write", [wid], steps)
        stock, post, fg = self.ref("loc_root"), self.loc("POST-STAGE"), g("Готова продукція")
        o("stock.picking.type", "write", [pc], {"active": True, "default_location_src_id": g("Сировина/Фурнітура"),
                                               "default_location_dest_id": g("Передвиробництво")})
        o("stock.picking.type", "write", [sfp], {"active": True, "default_location_src_id": post,
                                                "default_location_dest_id": fg})
        o("stock.picking.type", "write", [cur["manu_type_id"][0]], {"default_location_src_id": stock,
                                                                   "default_location_dest_id": post})
        # ГП: пост-виробництво → склад ГП (WH/SFP), щойно МО закрито
        r_fg = self.ensure("route_fg_store", "stock.route", {
            "name": "ГП: пост-виробництво → склад ГП", "sequence": 5, "product_categ_selectable": True,
            "product_selectable": False})
        self.ensure("rule_fg_store", "stock.rule", {
            "name": "Пост-виробництво → склад ГП", "route_id": r_fg, "action": "push", "auto": "manual",
            "location_src_id": post, "location_dest_id": fg, "picking_type_id": sfp, "warehouse_id": wid})
        o("product.category", "write", [self.ref(key("categ", "Готова продукція"))], {"route_ids": [(4, r_fg)]})
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
        print("routes: приймання у 2 кроки (плити — через вхідний контроль у 3), виробництво з пост-виробництвом "
              "і розміщенням ГП, відвантаження у 2 кроки, поповнення під портал")

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
                why = wc.get("idle_reason") if ls["reason"] == "Очікування матеріалу" else None
                self.ensure(key("loss", code, i), "mrp.workcenter.productivity", {
                    "workcenter_id": self.ref(key("wc", code)), "loss_id": loss[ls["reason"]],
                    "date_start": utc(t.strftime("%Y-%m-%d %H:%M")), "date_end": utc(end.strftime("%Y-%m-%d %H:%M")),
                    "description": why or ls["reason"]})
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

    # ------------------------------------------------------------ робочі центри за дільницями
    def step_wc_tags(self):
        n = 0
        for zc, z in self.d["zones"].items():
            if not z["workcenters"]:
                continue
            tag = self.ensure(key("wctag", zc), "mrp.workcenter.tag", {"name": z["name"]})
            for code in z["workcenters"]:
                self.o("mrp.workcenter", "write", [self.ref(key("wc", code))], {"tag_ids": [(4, tag)]})
                n += 1
        print(f"wc_tags: {n} робочих центрів позначено дільницею")

    # ------------------------------------------------------------ усе обладнання з паспортами
    def equipment_names(self):
        d = self.d
        names = dict(NAMES)
        names.update({c: w["name"] for c, w in d["workcenters"].items()})
        names.update({c: e["name"] for c, e in d["equipment"].items()})
        names.update({c: u["name"] for c, u in d["ventilation"]["units"].items()})
        names.update({c: f"Пожежна сигналізація: {g['zone_name']} ({g['kind_name']})"
                      for c, g in d["fire"]["groups"].items()})
        names.update({c: f"Освітлення: {g['zone_name']}" for c, g in d["lighting"]["groups"].items()})
        return names

    def step_equipment(self):
        """Кожен виріб із паспортом (205) — одиниця обладнання ТО: модель, характеристики, джерела в примітці."""
        o, d = self.o, self.d
        names = self.equipment_names()
        team = self.ref("maint_team")
        cats = {}

        def cat(name):
            if name not in cats:
                cats[name] = self.ensure(key("eqcat", name), "maintenance.equipment.category", {"name": name})
            return cats[name]
        zone_of = {}
        for grp in (d["ventilation"]["units"], d["fire"]["groups"], d["lighting"]["groups"]):
            for c, g in grp.items():
                z = d["zones"].get(g.get("zone"))
                if z:
                    zone_of[c] = z["name"]
        new = upd = 0
        codes = list(d["passports"]) + [c for grp in (d["ventilation"]["units"], d["fire"]["groups"],
                                                      d["lighting"]["groups"]) for c in grp if c not in d["passports"]]
        for code in codes:
            pp = d["passports"].get(code, {})
            model = " ".join(x for x in (pp.get("manufacturer"), pp.get("model")) if x) or False
            extra = f"Зона: {zone_of[code]}" if code in zone_of else ""
            vals = {"model": model,
                    "note": passport_note(pp, extra) if pp else (f"<p>{escape(extra)}</p>" if extra else False)}
            xid = key("eq", code)
            if self.ref(xid):
                o("maintenance.equipment", "write", [self.ref(xid)], vals)
                upd += 1
                continue
            role = pp.get("role")
            vals.update(name=names.get(code, code), serial_no=code, maintenance_team_id=team,
                        category_id=cat("Верстати" if code in d["workcenters"] else
                                        ROLE_CAT.get(role) or ("Вентиляція й опалення" if code in
                                                               d["ventilation"]["units"] else "Інше")))
            if code in d["workcenters"]:
                vals["workcenter_id"] = self.ref(key("wc", code))
            self.ensure(xid, "maintenance.equipment", vals)
            new += 1
        print(f"equipment: {new} нових одиниць, {upd} доповнено паспортом")

    def step_preventive(self):
        """Планове ТО за датами з моделі; перевірки, що вже були, — виконаними заявками."""
        o, d = self.o, self.d
        stages = o("maintenance.stage", "search_read", [], fields=["id", "done"], order="sequence")
        new, done = stages[0]["id"], next((s["id"] for s in stages if s["done"]), stages[-1]["id"])
        team = self.ref("maint_team")
        planned = {m["equipment"] for m in d["maintenance_requests"] if m["maintenance_type"] == "preventive"}
        n = 0
        for code, e in d["equipment"].items():
            eid = self.ref(key("eq", code))
            if e.get("next_maintenance") and code not in planned:
                self.ensure(key("pm", code), "maintenance.request", {
                    "name": "Планове ТО", "equipment_id": eid, "maintenance_type": "preventive", "stage_id": new,
                    "maintenance_team_id": team, "schedule_date": utc(e["next_maintenance"]),
                    "request_date": ts(NOW)[:10]})
                n += 1
            for f, title in (("last_inspection", "Планова перевірка"), ("leak_check", "Перевірка на витоки")):
                if e.get(f):
                    self.ensure(key("pm", code, f), "maintenance.request", {
                        "name": title, "equipment_id": eid, "maintenance_type": "preventive", "stage_id": done,
                        "maintenance_team_id": team, "schedule_date": utc(e[f] + " 08:00"), "request_date": e[f],
                        "close_date": e[f]})
                    n += 1
        print(f"preventive: {n} заявок планового ТО")

    # ------------------------------------------------------------ люди на зміні
    def step_attendance(self):
        o = self.o
        n = 0
        for code, e in self.d["employees"].items():
            eid = self.ref(key("emp", code))
            o("hr.employee", "write", [eid], {"barcode": code.replace("-", "")})  # бейдж = код у сцені без дефісів
            start = NOW.replace(hour=6, minute=40) + timedelta(minutes=det(code, mod=20))
            self.ensure(key("att", code), "hr.attendance", {"employee_id": eid, "check_in": utc(ts(start))},
                        update=False)
            n += 1
        print(f"attendance: {n} людей відмітились на зміну 1")

    # ------------------------------------------------------------ споживання компонентів по операціях
    @staticmethod
    def consuming_op(product, ops, fronts):
        """На якій операції маршруту витрачається компонент (назви операцій — як у моделі)."""
        def first(*names):
            return next((op for op in ops if op.startswith(names)), None)
        if product.startswith(("DSP", "MDF", "HDF")):
            return ops[0]
        if product.startswith("EB"):
            return first("Крайкооблицювання")
        if product == "PVC-WG":
            return first("Облицювання")
        if product == "LFM-GLUE":
            return first("Нанесення клею")
        if product.startswith("LFM"):
            return first("Фарбування")
        if product.startswith("PK"):
            return first("Пакування", "Термоусадка", "Коробка")
        if product.startswith("FUR"):
            return first("Встановлення завіс") if fronts else first("Збирання")
        if product.startswith("FR-"):
            return first("Збирання")
        return ops[0]

    def step_mo_locations(self):
        """Звідки МО бере компоненти й куди здає виріб: компоненти — зі Stock (портал, склади, візки KIT,
        етажерки фасадів), корпуси — у пост-виробництво, фасади — на свою етажерку FRONTS."""
        o, d = self.o, self.d
        stock, post = self.ref("loc_root"), self.loc("POST-STAGE")
        cart = {loc.get("fronts_mo"): c for c, loc in d["locations"].items() if loc.get("fronts_mo")}
        n = 0
        for mo in d["productions"]:
            mid = self.ref(key("mo", mo["name"]))
            dest = self.loc(cart[mo["name"]]) if mo["name"] in cart else post
            cur = o("mrp.production", "read", [mid], ["location_src_id", "location_dest_id", "state"])[0]
            if cur["state"] in ("done", "cancel") or (cur["location_src_id"][0], cur["location_dest_id"][0]) == \
                    (stock, dest):
                continue
            raw = o("stock.move", "search", [["raw_material_production_id", "=", mid],
                                             ["state", "not in", ["done", "cancel"]]])
            o("stock.move", "write", raw, {"picked": False, "quantity": 0})
            o("mrp.production", "do_unreserve", [mid])
            o("mrp.production", "write", [mid], {"location_src_id": stock, "location_dest_id": dest})
            o("stock.move", "write", raw, {"location_id": stock})
            fin = o("stock.move", "search", [["production_id", "=", mid], ["state", "not in", ["done", "cancel"]]])
            o("stock.move", "write", fin, {"location_dest_id": dest})
            n += 1
        print(f"mo_locations: {n} МО — компоненти зі Stock, виріб у пост-виробництво або на етажерку фасадів")

    def step_consumption(self):
        """Компонент прив'язано до операції, на якій його витрачають (у специфікації й у МО); у МО в роботі
        все, що пішло на вже виконані операції, зареєстровано як спожите (проведеться під час закриття МО)."""
        o, d = self.o, self.d
        n_bom = n_mo = n_done = 0
        for bom in o("mrp.bom", "search_read", [["id", "in", [v for k, v in self.ids.items() if k.startswith("bom_")]]],
                     fields=["bom_line_ids", "operation_ids", "code"]):
            ops = o("mrp.routing.workcenter", "read", bom["operation_ids"], ["name"])
            names = [x["name"] for x in ops]
            for ln in o("mrp.bom.line", "read", bom["bom_line_ids"], ["product_id", "operation_id"]):
                code = self.code_of(ln["product_id"][0])
                op = self.consuming_op(code, names, bom["code"].startswith("фасади"))
                if op and not ln["operation_id"]:
                    o("mrp.bom.line", "write", [ln["id"]], {"operation_id": ops[names.index(op)]["id"]})
                    n_bom += 1
        # Odoo 19 під час запуску першого завдання сам позначає всі компоненти спожитими (без партій, із
        # WH/Stock); скидаємо це, резервуємо з реальних комірок і позначаємо спожитим лише те, що пішло на
        # вже виконані операції
        todo = []
        for mo in d["productions"]:
            mid = self.ref(key("mo", mo["name"]))
            wos = [d["workorders"][w] for w in mo["workorders"]]
            names = [w["name"] for w in wos]
            for mv in o("stock.move", "search_read", [["raw_material_production_id", "=", mid],
                                                      ["state", "not in", ["done", "cancel"]]],
                        fields=["product_id", "workorder_id", "picked", "product_uom_qty", "quantity"]):
                op = self.consuming_op(self.code_of(mv["product_id"][0]), names, mo["route"].startswith("F"))
                w = wos[names.index(op)] if op else None
                vals = {}
                if w and not mv["workorder_id"]:
                    wid = self.ref(key("wo", w["id"]))
                    vals["workorder_id"] = wid
                    opid = o("mrp.workorder", "read", [wid], ["operation_id"])[0]["operation_id"]
                    if opid:
                        vals["operation_id"] = opid[0]
                    n_mo += 1
                want = bool(w and w["state"] == "done")
                bad = mv["picked"] and bool(o("stock.move.line", "search", [
                    ["move_id", "=", mv["id"]], "|", ["location_id", "=", self.ref("loc_root")],
                    "&", ["product_id.tracking", "=", "lot"], ["lot_id", "=", False]], limit=1))
                if mv["picked"] and (bad or not want):
                    vals.update(picked=False, quantity=0)
                    mv["picked"] = False
                if want and not mv["picked"]:
                    todo.append((mv["id"], want, mv["product_uom_qty"]))
                if vals:
                    o("stock.move", "write", [mv["id"]], vals)
        mos = [self.ref(key("mo", m["name"])) for m in d["productions"] if m["state"] == "progress"]
        o("mrp.production", "action_assign", mos)
        for mid_, want, qty in todo:  # спожите — те, що зарезервовано з комірок (з партіями), не більше
            if want:
                o("stock.move", "write", [mid_], {"picked": True})
                n_done += 1
        print(f"consumption: {n_bom} рядків специфікацій і {n_mo} компонентів МО прив'язано до операцій, "
              f"{n_done} зареєстровано як спожиті")

    def code_of(self, pid):
        cache = self.__dict__.setdefault("_codes", {})
        if not cache:
            cache.update({self.prod(c): c for c in self.d["products"]})
        return cache.get(pid, "")

    # ------------------------------------------------------------ фасади — компонент корпусу
    def step_fronts(self):
        """Фасади з дочірнього МО — компонент МО корпусу (і рядок його специфікації); готові фасади
        йдуть прямо на збирання (рух дочірнього МО → компонент батьківського)."""
        o, d = self.o, self.d
        prod_loc = self.one("stock.location", [["usage", "=", "production"]])
        mos = {m["name"]: m for m in d["productions"]}
        n = 0
        for mo in d["productions"]:
            parent = mos.get(mo.get("origin"))
            if not (mo["route"].startswith("F") and parent):
                continue
            pid, cid, fr = self.ref(key("mo", parent["name"])), self.ref(key("mo", mo["name"])), self.prod(mo["product"])
            raw = o("stock.move", "search", [["raw_material_production_id", "=", pid], ["product_id", "=", fr]])
            if not raw:
                src = o("mrp.production", "read", [pid], ["location_src_id"])[0]["location_src_id"][0]
                o("mrp.production", "write", [pid], {"move_raw_ids": [(0, 0, {
                    "product_id": fr, "product_uom_qty": mo["qty"], "product_uom": self.uom("шт"),
                    "location_id": src, "location_dest_id": prod_loc})]})
                raw = o("stock.move", "search", [["raw_material_production_id", "=", pid], ["product_id", "=", fr]])
                n += 1
            fin = o("stock.move", "search", [["production_id", "=", cid], ["product_id", "=", fr]])
            if fin:
                o("stock.move", "write", fin, {"move_dest_ids": [(4, raw[0])]})
            # маршрут комплектації сам створює «комплектацію» фасадів Stock → Stock — фасади ж ідуть
            # із дочірнього МО; від'єднати й скасувати такі переміщення
            for orig in o("stock.move", "read", o("stock.move", "read", raw, ["move_orig_ids"])[0]["move_orig_ids"],
                          ["picking_id", "production_id"]):
                if orig["picking_id"] and not orig["production_id"]:
                    o("stock.move", "write", raw, {"move_orig_ids": [(3, orig["id"])]})
                    pk = orig["picking_id"][0]
                    o("stock.picking", "action_cancel", [pk])
                    o("stock.picking", "unlink", [pk])
            bom = self.ref(key("bom", parent["product"], parent["route"]))
            if bom and not o("mrp.bom.line", "search", [["bom_id", "=", bom], ["product_id.default_code", "=like",
                                                                                 "FR-%"]]):
                o("mrp.bom", "write", [bom], {"bom_line_ids": [(0, 0, {
                    "product_id": fr, "product_qty": round(mo["qty"] / parent["qty"], 4),
                    "product_uom_id": self.uom("шт")})]})
        print(f"fronts: {n} МО корпусів отримали фасади компонентом")

    # ------------------------------------------------------------ закупівлі з правил поповнення
    def step_po_links(self):
        o, n = self.o, 0
        for po in self.d["purchase_orders"]:
            if not po.get("locations"):
                continue
            lines = o("purchase.order.line", "search_read", [["order_id", "=", self.ref(key("po", po["name"]))]],
                      fields=["product_id", "orderpoint_id"])
            for ln, loc in zip(po["lines"], po["locations"]):
                pol = next((x for x in lines if x["product_id"][0] == self.prod(ln["product"]) and
                            not x["orderpoint_id"]), None)
                op = self.ref(key("op", loc))
                if pol and op:
                    o("purchase.order.line", "write", [pol["id"]], {"orderpoint_id": op})
                    pol["orderpoint_id"] = op
                    n += 1
        print(f"po_links: {n} рядків закупівлі прив'язано до правил поповнення комірок")

    # ------------------------------------------------------------ ворота й фури
    def step_docks(self):
        """Ворота як місця (західні — вивантаження біля воріт, східні — нові «Відвантаження/Ворота k») і пакетне
        переміщення на кожну фуру біля воріт: док, тип транспорту, документи."""
        o, d = self.o, self.d
        out = self.ref(key("locgrp", "Відвантаження"))
        dock = {}
        for k in range(1, 8):
            dock[f"DOCK-W{k}"] = self.loc(f"UNLOAD-{k}")
            dock[f"DOCK-E{k}"] = self.ensure(key("loc", f"DOCK-E{k}"), "stock.location", {
                "name": f"Ворота {k}", "location_id": out, "usage": "internal", "barcode": f"DOCK-E{k}"},
                update=False)
        truck = self.ensure("vehcat_truck", "fleet.vehicle.model.category", {"name": "Фура"})
        n = 0
        for p in d["pickings"]:
            if not p.get("truck"):
                continue
            pid = self.ref(key("pick", p["name"]))
            bid = self.ensure(key("batch", p["truck"]), "stock.picking.batch", {
                "description": f"{p['truck']} · {p['dock']}", "picking_ids": [(6, 0, [pid])],
                "dock_id": dock[p["dock"]], "vehicle_category_id": truck, "user_id": o.uid,
                "scheduled_date": utc(p["scheduled_date"])})
            if o("stock.picking.batch", "read", [bid], ["state"])[0]["state"] == "draft":
                o("stock.picking.batch", "action_confirm", [bid])
            n += 1
        print(f"docks: 14 воріт, {n} фур біля воріт як пакетні переміщення")

