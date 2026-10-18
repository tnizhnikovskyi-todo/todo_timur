"""Кроки заливки демо-даних (M-04): порт plant/odoo_flows.py + plant/odoo_push.py на ORM через OrmProxy (A-08).

Між маркерами «порт» і «Runner» текст збігається з plant/*.py, крім кількох правок (docks, equipment);
`test_demo_steps_diff` стежить, щоб відмінності не перевищували 80 рядків. Усе поза маркерами — обв'язка
(`print` перенаправлено в лог майстра, `Runner` запускає один крок і викликає хуки factory3d_base).
"""
import base64
import io
import json
import os
import zipfile
from datetime import datetime, timedelta
from html import escape

from .orm_proxy import OrmProxy, key, utc

NOW = datetime(2026, 10, 12, 10, 30)
DOOR_GOODS = {1: ("DSP", "MDF", "HDF"), 2: ("DSP", "MDF", "HDF"), 3: ("DSP", "MDF", "HDF"), 4: ("FUR",),
              5: ("EB",), 6: ("LFM", "PVC"), 7: ("PK",)}
PAYLOAD_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "static", "data", "demo_payload.json")
_LOG = [None]


def ts(dt):
    return dt.strftime("%Y-%m-%d %H:%M")


def det(*xs, mod=1000):
    """Детермінований «випадковий» відгук без random — щоб дані не змінювались між збірками."""
    h = 2166136261
    for x in xs:
        for ch in str(x):
            h = ((h ^ ord(ch)) * 16777619) & 0xFFFFFFFF
    return h % mod


def print(*args, **kw):  # noqa: A001 — кроки «друкують» у лог майстра
    if _LOG[0]:
        _LOG[0](" ".join(str(a) for a in args))


def load_payload():
    with open(PAYLOAD_PATH, encoding="utf-8") as fh:
        return json.load(fh)


# ===== порт plant/odoo_flows.py + plant/odoo_push.py =====
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
    rows = "".join(f"<tr><td>{escape(k)}</td><td>{escape(str(v))}</td></tr>"
            for k, v in (pp.get("specs") or {}).items())
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
                    "note": f"<p>{escape(extra)}</p>" if extra else False}  # паспорт — f3d_passport_id (base)
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
        for code, _e in self.d["employees"].items():
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
        for mid_, want, _qty in todo:  # спожите — те, що зарезервовано з комірок (з партіями), не більше
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
            pid, cid = self.ref(key("mo", parent["name"])), self.ref(key("mo", mo["name"]))
            fr = self.prod(mo["product"])
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
            for ln, loc in zip(po["lines"], po["locations"], strict=False):
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
        rows = []  # залишки від часткового приймання (backorder) стоять біля тих самих воріт
        for p in d["pickings"]:
            pid = self.ref(key("pick", p["name"]))
            if p.get("dock") and pid:
                rows.append((p, pid, p.get("truck") or p["name"], p["state"]))
                rows += [(p, b["id"], "bo_" + b["name"], b["state"]) for b in o(
                    "stock.picking", "search_read", [["backorder_id", "=", pid]], fields=["name", "state"])]
        for po in d["purchase_orders"]:  # закупівля без фури (P00413): ворота за товаром, як у step_purchase
            pid = self.ref(key("pick", "receipt", po["name"]))
            door = next((k for k, goods in DOOR_GOODS.items() if po["lines"][0]["product"].startswith(goods)), 1)
            if pid:
                rows.append(({"dock": f"DOCK-W{door}", "type": "incoming", "truck": None,
                              "scheduled_date": po["date_planned"]}, pid, "receipt_" + po["name"],
                             o("stock.picking", "read", [pid], ["state"])[0]["state"]))
        for p, pid, name, state in rows:
            closed = state in ("done", "cancel")  # закрите переміщення ORM у пакет не пускає (як base/hooks/batches)
            vals = {"description": f"{name} · {p['dock']}", "dock_id": dock[p["dock"]],
                    "vehicle_category_id": truck, "user_id": o.uid, "scheduled_date": utc(p["scheduled_date"])}
            if not closed:
                vals["picking_ids"] = [(6, 0, [pid])]
            if p.get("truck") == name:  # код фури в 3D і її назва з макета (base CB-06, X-15)
                vals.update(f3d_code=p["truck"], f3d_truck=p["truck"])
            src = o("stock.move", "search_read", [["picking_id", "=", pid]], fields=["location_id"])
            bid = self.ensure(key("batch", name), "stock.picking.batch", vals, update=not closed)
            for m in src if p["type"] == "outgoing" and not closed else []:  # stock_fleet кладе джерело на док
                o("stock.move", "write", [m["id"]], {"location_id": m["location_id"][0]})
            if closed:
                o.env.cr.execute("UPDATE stock_picking SET batch_id = %s WHERE id = %s", (bid, pid))
                o.env["stock.picking"].invalidate_model(["batch_id"])
                o.env["stock.picking.batch"].invalidate_model(["picking_ids", "state"])
                o("stock.picking.batch", "_compute_state", [bid])
            elif o("stock.picking.batch", "read", [bid], ["state"])[0]["state"] == "draft":
                o("stock.picking.batch", "action_confirm", [bid])
            n += 1
        print(f"docks: 14 воріт, {n} фур біля воріт як пакетні переміщення")


    # ------------------------------------------------------------ сигнали для модуля імітації IoT
    def signal_specs(self):
        """Сигнали з моделі: шлях у даних переглядача (x_code), стартове значення й поведінка датчика."""
        d = self.d
        en, eqs, specs = d["energy"]["consumers"], d["equipment"], []

        def add(path, name, eq, kind, unit, mode, value, seq, **kw):
            specs.append(dict(code=path, name=name, eq=eq, kind=kind, unit=unit, mode=mode, value=value, seq=seq, **kw))
        for code, wc in d["workcenters"].items():  # верстати: потужність від стану робочого центру + кВт·год
            c = en.get(code)
            if not c:
                continue
            p = f"energy/consumers/{code}"
            add(f"{p}/p_now", f"{wc['name']}: потужність", code, "Потужність", "кВт", "machine", c["p_now"], 10,
                wc=code, nominal=c["p_now"] if c["status"] == "work" else round(c["p_inst"] * 0.55, 1), noise=0.08,
                rate=round(c["p_inst"] * 0.08, 2))
            add(f"{p}/kwh_shift", f"{wc['name']}: енергія за зміну", code, "Енергія", "кВт·год", "energy",
                c.get("kwh_shift", 0), 20, source=f"{p}/p_now")
        for code in ("GANTRY-1", "COMPRESSOR", "DUST-1", "BOILER", "CHARGING"):  # інженерні споживачі
            c, p = en[code], f"energy/consumers/{code}"
            add(f"{p}/p_now", f"{c['name']}: потужність", code, "Потужність", "кВт", "noise", c["p_now"], 10,
                nominal=c["p_now"], noise=round(c["p_now"] * 0.04, 2))
            add(f"{p}/kwh_shift", f"{c['name']}: енергія за зміну", code, "Енергія", "кВт·год", "energy",
                c.get("kwh_shift", 0), 20, source=f"{p}/p_now")
        for code, e in eqs.items():
            p = f"equipment/{code}"
            if "battery" in e:  # навантажувачі й тягач: розряд у роботі, зарядка на межі 20 %
                add(f"{p}/battery", f"{e['name']} {code}: заряд АКБ", code, "Заряд АКБ", "%", "drain",
                    round(e["battery"] * 100, 1), 10, rate=0.15, limit=20, charging=e.get("state") == "charging")
                add(f"{p}/hours", f"{e['name']} {code}: мотогодини", code, "Мотогодини", "год", "hours", e["hours"],
                    20, source=f"{p}/battery")
        g, cp, du, bo = eqs["GANTRY-1"], eqs["COMPRESSOR"], eqs["DUST-1"], eqs["BOILER"]
        add("equipment/GANTRY-1/cycles_today", "Портал: циклів за день", "GANTRY-1", "Цикли", "шт", "counter",
            g["cycles_today"], 20, rate=3, source="energy/consumers/GANTRY-1/p_now")
        add("equipment/GANTRY-1/vacuum_kpa", "Портал: вакуум присосок", "GANTRY-1", "Вакуум", "кПа", "noise",
            g["vacuum_kpa"], 10, nominal=g["vacuum_kpa"], noise=0.5, alarm="above", threshold=-60)
        add("equipment/COMPRESSOR/pressure_bar", "Компресор: тиск", "COMPRESSOR", "Тиск", "бар", "noise",
            cp["pressure_bar"], 10, nominal=cp["pressure_bar"], noise=0.05, alarm="below", threshold=6.0)
        add("equipment/COMPRESSOR/load", "Компресор: завантаження", "COMPRESSOR", "Завантаження", "%", "noise",
            round(cp["load"] * 100), 10, nominal=round(cp["load"] * 100), noise=3)
        add("equipment/COMPRESSOR/hours", "Компресор: мотогодини", "COMPRESSOR", "Мотогодини", "год", "hours",
            cp["hours"], 20, source="energy/consumers/COMPRESSOR/p_now")
        add("equipment/DUST-1/airflow_m3h", "Аспірація: витрата повітря", "DUST-1", "Витрата", "м³/год", "noise",
            du["airflow_m3h"], 10, nominal=du["airflow_m3h"], noise=300)
        add("equipment/DUST-1/filter_dp_kpa", "Аспірація: перепад на фільтрі", "DUST-1", "Перепад", "кПа", "drift",
            du["filter_dp_kpa"], 10, nominal=1.0, rate=0.0005, alarm="above", threshold=1.8)
        add("equipment/BOILER/supply_c", "Котельня: подача", "BOILER", "Температура", "°C", "noise", bo["supply_c"],
            10, nominal=bo["supply_c"], noise=0.4)
        add("equipment/BOILER/silo_fill", "Котельня: бункер брикетів", "BOILER", "Рівень", "%", "level",
            round(bo["silo_fill"] * 100), 10, nominal=95, rate=0.02, limit=15)
        for code in ("SPRINKLERS", "AIR-RING"):
            e = eqs[code]
            add(f"equipment/{code}/pressure_bar", f"{e['name']}: тиск", code, "Тиск", "бар", "noise",
                e["pressure_bar"], 10, nominal=e["pressure_bar"], noise=0.04, alarm="below",
                threshold=6.5 if code == "SPRINKLERS" else 6.0)
        mrs = {m["equipment"]: m["id"] for m in d["maintenance_requests"]}
        for code, u in d["ventilation"]["units"].items():  # вентиляція: витрата, подача, фільтр забивається
            p = f"ventilation/units/{code}"
            add(f"{p}/airflow_m3h", f"{u['name']}: витрата", code, "Витрата", "м³/год", "noise", u["airflow_m3h"], 10,
                nominal=u["airflow_m3h"], noise=round(u["airflow_m3h"] * 0.02))
            if u.get("supply_c") is not None:
                add(f"{p}/supply_c", f"{u['name']}: подача", code, "Температура", "°C", "noise", u["supply_c"], 10,
                    nominal=u["supply_c"], noise=0.2)
            if u.get("filter_dp_pa") is not None:
                add(f"{p}/filter_dp_pa", f"{u['name']}: перепад на фільтрі", code, "Перепад", "Па", "drift",
                    u["filter_dp_pa"], 10, nominal=120, rate=0.05, alarm="above", threshold=250, request=mrs.get(code))
        add("fire/groups/FA-FAC/dust", "Сповіщувач 2.FAC.07: запиленість", "FA-FAC", "Запиленість", "%", "drift", 82,
            10, nominal=10, rate=0.01, alarm="above", threshold=90, request=mrs.get("FA-FAC"))
        for code, t in d["energy"]["transformers"].items():
            p = f"energy/transformers/{code}"
            add(f"{p}/p_kw", f"{t['name']}: навантаження", code, "Потужність", "кВт", "noise", t["p_kw"], 10,
                nominal=t["p_kw"], noise=round(t["p_kw"] * 0.03, 1))
            add(f"{p}/temp_c", f"{t['name']}: температура", code, "Температура", "°C", "noise", t["temp_c"], 10,
                nominal=t["temp_c"], noise=0.3, alarm="above", threshold=140)
        it = d["infra"]["totals"]
        h = NOW.hour + NOW.minute / 60
        add("infra/totals/pv_now", "СЕС: виробіток", "PV-INV", "Потужність", "кВт", "solar", it["pv_now"], 10,
            nominal=round(it["pv_now"] / max(0.05, 1 - ((h - 13) / 6) ** 2)))
        add("infra/totals/chp_kw", "Когенерація: електрична потужність", "CHP", "Потужність", "кВт", "noise",
            it["chp_kw"], 10, nominal=it["chp_kw"], noise=4)
        add("infra/totals/bess_soc", "Накопичувач: заряд", "BESS", "Заряд", "%", "noise", round(it["bess_soc"] * 100),
            10, nominal=round(it["bess_soc"] * 100), noise=0.3)
        return specs

    def step_iot_module(self):
        """Імпортувати data-модуль factory3d_iot_sim з odoo_addons/ (Застосунки → Імпортувати модуль)."""
        o = self.o
        root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "odoo_addons")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for base, _, files in os.walk(os.path.join(root, "factory3d_iot_sim")):
                for f in files:
                    full = os.path.join(base, f)
                    z.write(full, os.path.relpath(full, root))
        wid = o("base.import.module", "create", {"module_file": base64.b64encode(buf.getvalue()).decode(),
                                                 "force": True})
        o("base.import.module", "import_module", [wid])
        print(f"iot_module: factory3d_iot_sim — {o.installed('factory3d_iot_sim').get('factory3d_iot_sim')}")

    def step_signals(self):
        """Сигнали обладнання для модуля factory3d_iot_sim (імітація підключених датчиків)."""
        o = self.o
        if not o.has("x_f3d_signal"):
            print("signals: модуль factory3d_iot_sim не встановлено — пропуск")
            return
        specs = self.signal_specs()
        req = {}
        for mr in self.d["maintenance_requests"]:
            req[mr["id"]] = self.ref(key("mr", mr["id"]))
        n = 0
        for s in specs:  # спершу джерела (порядок 10), потім лічильники, що на них посилаються (20)
            eq = self.ref(key("eq", s["eq"]))
            vals = {"x_name": s["name"], "x_code": s["code"], "x_sequence": s["seq"], "x_active": True,
                    "x_equipment_id": eq or False, "x_kind": s["kind"], "x_unit": s["unit"], "x_mode": s["mode"],
                    "x_nominal": s.get("nominal", 0), "x_noise": s.get("noise", 0), "x_rate": s.get("rate", 0),
                    "x_limit": s.get("limit", 0), "x_alarm": s.get("alarm") or False,
                    "x_threshold": s.get("threshold", 0)}
            if s.get("wc"):
                vals["x_workcenter_id"] = self.ref(key("wc", s["wc"]))
            if s.get("source"):
                vals["x_source_id"] = self.ref(key("sig", s["source"]))
            xid = key("sig", s["code"])
            if not self.ref(xid):  # стартовий стан — лише при створенні, далі значення веде імітація
                vals.update(x_value=s["value"], x_charging=bool(s.get("charging")), x_state="норма",
                            x_seed=det(s["code"], mod=2 ** 31))
                if s.get("request") and req.get(s["request"]):
                    vals["x_request_id"] = req[s["request"]]
                n += 1
            self.ensure(xid, "x_f3d_signal", vals)
        print(f"signals: {len(specs)} сигналів ({n} нових) для імітації IoT")


MOD = "factory3d"
STEPS = ["modules", "settings", "base", "views", "calendar", "locations", "workcenters", "people", "purchase",
         "sale", "internal", "production", "boms", "layout", "lots", "stock", "routes", "orderpoints", "children",
         "fronts", "mo_locations", "consumption", "po_links", "docks", "wc_tags", "losses", "quality", "maintenance",
         "equipment", "preventive", "iot_module", "signals", "attendance", "carriers", "finish"]
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
        for _label, path in DEST_GROUP.items():  # групи, на які посилаються приймання
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
            if e.get("workcenter") and "employee_ids" in o("mrp.workcenter", "fields_get", [], attributes=["type"]):
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
        if validate:  # Odoo 19: партійний товар не підтверджується без номера партії
            pname = o("stock.picking", "read", [pid], ["name"])[0]["name"]
            codes = {self.prod(c): c for c in getattr(self, "tracked", ())}
            for ml in o("stock.move.line", "search_read", [["picking_id", "=", pid], ["lot_id", "=", False],
                                                           ["lot_name", "=", False],
                                                           ["product_id.tracking", "=", "lot"]],
                        fields=["product_id"]):
                code = codes.get(ml["product_id"][0]) or o("product.product", "read", [ml["product_id"][0]],
                                                           ["default_code"])[0]["default_code"]
                o("stock.move.line", "write", [ml["id"]], {"lot_name": self.receipt_lot(code, pname)})
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
            for w, ow in zip(wos, odoo_wos, strict=False):
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
                for w, op in zip([d["workorders"][x] for x in m["workorders"]], ops, strict=False):
                    wid = self.ref(key("wo", w["id"]))
                    if not o("mrp.workorder", "read", [wid], ["operation_id"])[0]["operation_id"]:
                        o("mrp.workorder", "write", [wid], {"operation_id": op["id"]})
        print(f"boms: {len(first)} специфікацій з операціями")

    def run_workorders(self, mo, wos):
        if mo["state"] != "progress":
            return
        ids = [self.ref(key("wo", w["id"])) for w in wos]
        state = {r["id"]: r["state"] for r in self.o("mrp.workorder", "read", ids, ["state"])}
        for w, wid in zip(wos, ids, strict=False):
            if w["state"] in ("done", "progress") and state[wid] not in ("done", w["state"]):
                self.run_workorder(wid, w, started=state[wid] == "progress")

    def operator(self, wc_code):
        """Оператор верстата з демо (OP-<код>) або перший із дозволених на робочому центрі."""
        if "employee_ids" not in self.o("mrp.workcenter", "fields_get", [], attributes=["type"]):
            return False   # CE: ні входу за оператором (start_employee), ні списку допущених
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


# ===== Runner =====
class Skip(Exception):
    """Крок не виконується в модулі; текст — повідомлення в рядку кроку."""


class Runner(Push):
    """Запускає кроки заливки на ORM поточного env; `log(msg)` — рядки кроків."""

    HOOKS = {"locations": ("codes.locations",), "workcenters": ("codes.workcenters",),
             "people": ("codes.employees",), "equipment": ("codes.equipment", "passports.link"),
             "docks": ("docks.register", "codes.locations", "zones.bind"),
             "finish": ("codes.locations", "codes.workcenters", "codes.employees", "codes.equipment",
                        "passports.link", "zones.bind")}

    def __init__(self, env, payload=None, log=None):
        self.env = env
        self.log = log or (lambda msg: None)
        self.msgs = []
        super().__init__(OrmProxy(env), payload or load_payload())

    def _say(self, msg):
        self.msgs.append(msg)
        self.log(msg)

    def run(self, step):
        """Один крок → ('done'|'skipped', повідомлення). Помилки підіймаються до виклику."""
        from odoo.addons.factory3d_base import hooks as base_hooks
        _LOG[0], self.msgs = self._say, []
        try:
            try:
                getattr(self, "step_" + step)()
            except Skip as e:
                return "skipped", str(e)
            for name in self.HOOKS.get(step, ()):
                mod, func = name.split(".")
                getattr(getattr(base_hooks, mod), func)(self.env)
            self.env.flush_all()
            return "done", (self.msgs[-1] if self.msgs else "")[:250]
        finally:
            _LOG[0] = None

    # --- кроки, що в модулі працюють інакше
    def step_modules(self):
        mods = ("iot", "hr_attendance", "stock_delivery", "stock_picking_batch", "stock_fleet")
        todo = [m for m, st in self.o.installed(*mods).items() if st != "installed"]  # iot (Enterprise) нема в CE
        if todo:
            raise Skip("встановіть із Застосунків: " + ", ".join(todo))
        print("modules: усі потрібні модулі встановлені")

    def step_settings(self):
        lang = self.env["res.lang"].with_context(active_test=False).search([("code", "=", "uk_UA")], limit=1)
        if lang and not lang.active:
            self.env["base.language.install"].create({"lang_ids": [(6, 0, lang.ids)]}).lang_install()
        self.o.refresh_lang()
        super().step_settings()

    def step_views(self):
        raise Skip("поля x_* заборонені; ворота й фури — пакетні переміщення (крок docks)")

    def step_iot_module(self):
        if self.o.installed("factory3d_iot_sim").get("factory3d_iot_sim") == "installed":
            raise Skip("factory3d_iot_sim уже встановлено")
        raise Skip("встановіть factory3d_iot_sim з Застосунків")
