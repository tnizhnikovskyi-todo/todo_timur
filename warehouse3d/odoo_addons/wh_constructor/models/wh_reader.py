from datetime import timedelta

from odoo import _, api, fields, models, release
from odoo.exceptions import AccessError, UserError

G_VIEW = "wh_constructor.group_wh_view"
PAGE_DEFAULT, PAGE_MAX = 2000, 5000
MOVES_DAYS, MOVES_DAYS_MAX = 90, 365  # окно движений для оборачиваемости (ABC): по умолчанию и максимум, дней

# Различия Odoo 18 и 19 (R-02): набор полей локации зависит от версии — отдаём только существующие.
# 18: posx / posy / posz и scrap_location; 19: их нет (скрап — локация с usage = inventory). replenish_location есть в обеих.
LOC_POS = ("posx", "posy", "posz")
LOC_FLAGS = ("replenish_location", "scrap_location")


class WhReader(models.AbstractModel):
    """Чтение данных склада для приложения (адаптер Odoo API, W-11): склады, локации, остатки, категории хранения,
    правила размещения, правила пополнения. Только чтение, права — группа «Конструктор: перегляд» и обычные права/правила Odoo
    (компании пользователя); большие выборки — постранично (offset / limit, ответ содержит total и next)."""
    _name = "wh.reader"
    _description = "Reader of stock data for the warehouse constructor"

    # ------------------------------------------------------------ общее
    @api.model
    def _reader(self):
        """Окружение чтения: проверка группы и все компании пользователя (а не только текущая), правила записей Odoo остаются в силе."""
        if not self.env.user.has_group(G_VIEW):
            raise AccessError(_("Немає права «Конструктор: перегляд»."))
        return self.with_context(allowed_company_ids=self.env.user.company_ids.ids).env

    @api.model
    def _warehouse(self, env, warehouse_id):
        wh = env["stock.warehouse"].search([("id", "=", int(warehouse_id or 0))], limit=1)
        if not wh:
            raise UserError(_("Склад не знайдено або він недоступний."))
        return wh

    @api.model
    def _page(self, model, domain, offset, limit, order="id"):
        offset = max(int(offset or 0), 0)
        limit = min(max(int(limit or PAGE_DEFAULT), 1), PAGE_MAX)
        total = model.search_count(domain)
        recs = model.search(domain, offset=offset, limit=limit, order=order)
        nxt = offset + limit
        return recs, {"total": total, "offset": offset, "limit": limit, "next": nxt if nxt < total else None}

    @api.model
    def _products(self, products):
        return {str(p.id): {"id": p.id, "default_code": p.default_code or None, "name": p.name, "uom": p.uom_id.name,
                            "categ": p.categ_id.name} for p in products}

    # ------------------------------------------------------------ склады
    @api.model
    def api_warehouses(self):
        env = self._reader()
        out = []
        for wh in env["stock.warehouse"].search([], order="id"):
            view = wh.view_location_id
            out.append({"id": wh.id, "code": wh.code, "name": wh.name, "company_id": wh.company_id.id, "company": wh.company_id.name,
                        "view_location_id": view.id,
                        "places": env["stock.location"].search_count([("id", "child_of", view.id), ("usage", "=", "internal")])})
        return {"version": {"series": release.series, "major": release.version_info[0]}, "db": self.env.cr.dbname,
                "now": fields.Datetime.now().strftime("%Y-%m-%d %H:%M"), "warehouses": out}

    # ------------------------------------------------------------ локации
    @api.model
    def api_locations(self, warehouse_id=None, offset=0, limit=None):
        """Внутренние и view-локации склада (включая его корневую view-локацию)."""
        env = self._reader()
        wh = self._warehouse(env, warehouse_id)
        Location = env["stock.location"]
        recs, page = self._page(Location, [("id", "child_of", wh.view_location_id.id), ("usage", "in", ["internal", "view"])], offset, limit)
        pos = [f for f in LOC_POS if f in Location._fields]
        flags = [f for f in LOC_FLAGS if f in Location._fields]
        rows = []
        for loc in recs:
            row = {"id": loc.id, "name": loc.name, "complete_name": loc.complete_name, "location_id": loc.location_id.id or None,
                   "usage": loc.usage, "barcode": loc.barcode or None, "company_id": loc.company_id.id or None,
                   "storage_category_id": loc.storage_category_id.id or None,
                   "removal_strategy_id": loc.removal_strategy_id.id or None, "removal_strategy": loc.removal_strategy_id.name or None}
            for f in pos:
                row[f] = loc[f]
            for f in flags:
                row[f] = bool(loc[f])
            rows.append(row)
        return {**page, "warehouse_id": wh.id, "locations": rows}

    # ------------------------------------------------------------ остатки
    @api.model
    def api_quants(self, warehouse_id=None, offset=0, limit=None):
        env = self._reader()
        wh = self._warehouse(env, warehouse_id)
        recs, page = self._page(env["stock.quant"], [("location_id", "child_of", wh.view_location_id.id), ("quantity", "!=", 0)], offset, limit)
        rows = [{"id": q.id, "location_id": q.location_id.id, "product_id": q.product_id.id, "quantity": q.quantity,
                 "reserved_quantity": q.reserved_quantity, "lot": q.lot_id.name or None, "package": q.package_id.name or None,
                 "in_date": fields.Datetime.to_string(q.in_date) if q.in_date else None} for q in recs]  # in_date — для возраста запаса (UTC)
        return {**page, "warehouse_id": wh.id, "quants": rows, "products": self._products(recs.product_id)}

    # ------------------------------------------------------------ категории хранения
    @api.model
    def api_storage_categories(self, warehouse_id=None, offset=0, limit=None):
        """Категории хранения: назначенные локациям склада или правилам размещения в нём и все категории компании склада (или без компании), с ёмкостями по товару и типу упаковки."""
        env = self._reader()
        wh = self._warehouse(env, warehouse_id)
        view = wh.view_location_id.id
        used = env["stock.location"].search([("id", "child_of", view), ("storage_category_id", "!=", False)]).storage_category_id
        used |= self._rules(env, wh).storage_category_id
        # назначенные и все свободные категории компании склада (W-14): новую категорию, ещё не назначенную, конструктор должен видеть, иначе создаст её повторно
        domain = ["|", ("id", "in", used.ids), ("company_id", "in", [False, wh.company_id.id])]
        recs, page = self._page(env["stock.storage.category"], domain, offset, limit)
        rows, products = [], env["product.product"]
        for c in recs:
            caps = [{"id": k.id, "product_id": k.product_id.id or None, "package_type_id": k.package_type_id.id or None,
                     "package_type": k.package_type_id.name or None, "quantity": k.quantity} for k in c.capacity_ids]
            products |= c.capacity_ids.product_id
            rows.append({"id": c.id, "name": c.name, "max_weight": c.max_weight, "allow_new_product": c.allow_new_product,
                         "company_id": c.company_id.id or None, "capacities": caps})
        return {**page, "warehouse_id": wh.id, "storage_categories": rows, "products": self._products(products)}

    # ------------------------------------------------------------ правила размещения
    @api.model
    def _rules(self, env, wh):
        view = wh.view_location_id.id
        return env["stock.putaway.rule"].search(["|", ("location_in_id", "child_of", view), ("location_out_id", "child_of", view)])

    @api.model
    def api_putaway_rules(self, warehouse_id=None, offset=0, limit=None):
        env = self._reader()
        wh = self._warehouse(env, warehouse_id)
        view = wh.view_location_id.id
        recs, page = self._page(env["stock.putaway.rule"], ["|", ("location_in_id", "child_of", view), ("location_out_id", "child_of", view)],
                                offset, limit, order="sequence, id")
        rows = [{"id": r.id, "sequence": r.sequence, "product_id": r.product_id.id or None, "category_id": r.category_id.id or None,
                 "category": r.category_id.name or None, "location_in_id": r.location_in_id.id or None,
                 "location_out_id": r.location_out_id.id or None, "storage_category_id": r.storage_category_id.id or None,
                 "package_types": [{"id": p.id, "name": p.name} for p in r.package_type_ids], "sublocation": r.sublocation,
                 "company_id": r.company_id.id or None} for r in recs]
        return {**page, "warehouse_id": wh.id, "putaway_rules": rows, "products": self._products(recs.product_id)}

    # ------------------------------------------------------------ правила пополнения по местам (min / max)
    @api.model
    def api_orderpoints(self, warehouse_id=None, offset=0, limit=None):
        env = self._reader()
        wh = self._warehouse(env, warehouse_id)
        recs, page = self._page(env["stock.warehouse.orderpoint"], [("location_id", "child_of", wh.view_location_id.id)], offset, limit)
        rows = [{"id": o.id, "name": o.name, "location_id": o.location_id.id, "product_id": o.product_id.id, "min": o.product_min_qty,
                 "max": o.product_max_qty, "trigger": o.trigger, "warehouse_id": o.warehouse_id.id or None} for o in recs]
        return {**page, "warehouse_id": wh.id, "orderpoints": rows, "products": self._products(recs.product_id)}

    # ------------------------------------------------------------ справочники для правок (W-14)
    @api.model
    def api_removal_strategies(self):
        """Стратегии списания базы (product.removal): id, название, метод (fifo, lifo, fefo, closest…); выбираются на зоне и месте (removal_strategy_id)."""
        env = self._reader()
        return {"removal_strategies": [{"id": r.id, "name": r.name, "method": r.method} for r in env["product.removal"].search([], order="id")]}

    @api.model
    def api_package_types(self):
        """Типы упаковки (stock.package.type) — для ёмкости категории хранения по упаковке."""
        env = self._reader()
        return {"package_types": [{"id": r.id, "name": r.name} for r in env["stock.package.type"].search([], order="id")]}

    # ------------------------------------------------------------ движения (оборачиваемость ABC, W-17)
    @api.model
    def api_moves(self, warehouse_id=None, days=None, offset=0, limit=None):
        """Выполненные движения (stock.move.line) за `days` дней, затрагивающие склад: агрегат по паре «откуда → куда»
        (число строк движений и количество в единицах товара); приложение складывает их по местам. Постранично по парам."""
        env = self._reader()
        wh = self._warehouse(env, warehouse_id)
        days = min(max(int(days or MOVES_DAYS), 1), MOVES_DAYS_MAX)
        view = wh.view_location_id.id
        since = fields.Datetime.now() - timedelta(days=days)
        domain = [("state", "=", "done"), ("date", ">=", since), "|", ("location_id", "child_of", view), ("location_dest_id", "child_of", view)]
        groups = env["stock.move.line"]._read_group(domain, ["location_id", "location_dest_id"], ["__count", "quantity_product_uom:sum"])
        rows = sorted(({"location_id": src.id, "location_dest_id": dst.id, "n": n, "qty": qty or 0.0} for src, dst, n, qty in groups),
                      key=lambda r: (r["location_id"], r["location_dest_id"]))
        offset = max(int(offset or 0), 0)
        limit = min(max(int(limit or PAGE_DEFAULT), 1), PAGE_MAX)
        nxt = offset + limit
        return {"total": len(rows), "offset": offset, "limit": limit, "next": nxt if nxt < len(rows) else None,
                "warehouse_id": wh.id, "days": days, "moves": rows[offset:nxt]}
