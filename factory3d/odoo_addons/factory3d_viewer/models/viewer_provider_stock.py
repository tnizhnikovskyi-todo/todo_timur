from odoo import api, models

from ..tools import dates
from ..tools import payload as payload_tools

PRODUCTS_LIMIT = 5000


def _num(value):
    """Ціле — int, інакше round(…, 2) (R-04)."""
    value = float(value)
    return int(value) if value.is_integer() else round(value, 2)


class F3dViewerProviderStock(models.AbstractModel):
    """M-01a: товари й локації (R-03, R-04)."""
    _name = "f3d.viewer.provider.stock"
    _inherit = "f3d.viewer.provider"
    _description = "3D: провайдер даних stock"

    _f3d_sequence = 20
    _f3d_sections = ("products", "locations")
    _f3d_group = "stock.group_stock_user"

    @api.model
    def _f3d_viewer_bus_models(self):
        return ["stock.quant", "stock.move.line", "stock.location"]

    # ------------------------------------------------------------------ collect
    @api.model
    def _f3d_viewer_collect(self, payload, ctx):
        env = self.env
        if not all(payload_tools.access_ok(env, m) for m in
                   ("product.product", "stock.location", "stock.quant", "stock.move.line")):
            return
        static_locs = ((ctx.get("static") or {}).get("layout") or {}).get("locations") or {}
        locs = env["stock.location"].search([("f3d_code", "!=", False), ("usage", "in", ("internal", "transit"))])
        quants = env["stock.quant"].search_read(
            [("location_id", "in", locs.ids), ("quantity", "!=", 0)],
            ["location_id", "product_id", "quantity", "reserved_quantity", "lot_id", "package_id"]) if locs else []

        # --- товари
        pids = {q["product_id"][0] for q in quants}
        extra = set()
        if payload_tools.access_ok(env, "mrp.production"):
            mos = env["mrp.production"].search([("state", "not in", ("done", "cancel"))])
            extra = set(mos.product_id.ids) | set(mos.move_raw_ids.product_id.ids)
        if len(pids | extra) <= PRODUCTS_LIMIT:
            pids |= extra
        products = env["product.product"].with_context(active_test=False).search(
            [("id", "in", list(pids)), ("default_code", "!=", False)])
        code_of = {p.id: p.default_code for p in products}
        prod_out = {}
        for p in products:
            item = {"default_code": p.default_code, "name": p.name, "uom": p.uom_id.name,
                    "categ": p.categ_id.name or ""}
            seller = p.seller_ids[:1].partner_id.name
            if seller:
                item["seller"] = seller
            prod_out[p.default_code] = item
        payload["products"] = prod_out

        # --- допоміжні вибірки по локаціях
        reserved_for = self._reserved_for(locs)
        picking_of = self._received_today(locs, ctx)
        quality_of = self._quality_by_lot()
        kit_links = self._kit_links(locs)
        orderpoints = self._orderpoints(locs)

        out = {}
        by_loc = {}
        for q in quants:
            by_loc.setdefault(q["location_id"][0], []).append(q)
        for loc in locs:
            code = loc.f3d_code
            st = static_locs.get(code) or {}
            rows = []
            for q in by_loc.get(loc.id, []):
                product = code_of.get(q["product_id"][0])
                if not product:
                    continue
                lot = q["lot_id"][1] if q["lot_id"] else None
                package = q["package_id"][1] if q["package_id"] else None
                item = {"product": product, "qty": round(q["quantity"], 2)}
                if q["reserved_quantity"] > 0:
                    item["reserved"] = round(q["reserved_quantity"], 2)
                    rf = (reserved_for.get((loc.id, q["product_id"][0], q["lot_id"] and q["lot_id"][0],
                                            q["package_id"] and q["package_id"][0]))
                          or reserved_for.get((loc.id, q["product_id"][0], None, None)))
                    if rf:
                        item["reserved_for"] = rf
                if lot:
                    item["lot"] = lot
                    if q["lot_id"][0] in quality_of:
                        item["quality"] = quality_of[q["lot_id"][0]]
                if package:
                    item["package"] = package
                pk = picking_of.get((loc.id, q["product_id"][0]))
                if pk:
                    item["picking"] = pk
                rows.append(item)
            rows.sort(key=lambda r: (r["product"], r.get("package") or "", r.get("lot") or ""))
            kind = loc.f3d_loc_kind or st.get("kind")
            ops = orderpoints.get(loc.id)
            capacity = self._capacity(loc, st, ops)
            total = sum(r["qty"] for r in rows)
            if kind == "pallet_cell":
                fill = min(1.0, len(rows) / 2)
            elif capacity:
                fill = min(1.0, total / capacity)
            else:
                fill = None
            rec = {"complete_name": loc.complete_name, "quants": rows, "capacity": capacity,
                   "fill": None if fill is None else round(fill, 4), "kind": kind}
            if code in kit_links:
                rec["picking"], rec["production"] = kit_links[code]
            if ops:
                op = ops[0]
                have = sum(r["qty"] for r in rows if r["product"] == op["product"])
                rec["orderpoint"] = op
                rec["state"] = "out" if have <= 0 else "low" if have < op["min"] else "ok"
            out[code] = rec
        payload["locations"] = out

    @api.model
    def _capacity(self, loc, st, ops):
        """R-04: base f3d_capacity > 0, інакше статика, для bin — max правила."""
        if loc.f3d_capacity and loc.f3d_capacity > 0:
            return _num(loc.f3d_capacity)
        cap = st.get("capacity")
        if cap is None and (loc.f3d_loc_kind or st.get("kind")) == "bin" and ops:
            cap = ops[0]["max"]
        return None if cap is None else _num(cap)

    @api.model
    def _reserved_for(self, locs):
        env = self.env
        if not locs:
            return {}
        lines = env["stock.move.line"].search([
            ("location_id", "in", locs.ids), ("state", "in", ("assigned", "partially_available")),
            ("picking_id.picking_type_code", "=", "outgoing")])
        res = {}
        for ml in lines:
            name = ml.picking_id.name
            pid = ml.product_id.id
            res.setdefault((ml.location_id.id, pid, ml.lot_id.id or None, ml.package_id.id or None), name)
            res.setdefault((ml.location_id.id, pid, None, None), name)
        return res

    @api.model
    def _received_today(self, locs, ctx):
        """Приймання сьогодні в локаціях UNLOAD-* (за кодом, аліасом або штрихкодом)."""
        env = self.env
        unload = locs.filtered(lambda loc: any(
            (c or "").startswith("UNLOAD-") for c in (loc.f3d_code, loc.f3d_alias, loc.barcode)))
        if not unload:
            return {}
        start = dates.utc(ctx["today"] + " 00:00")
        lines = env["stock.move.line"].search([
            ("location_dest_id", "in", unload.ids), ("state", "=", "done"), ("date", ">=", start)],
            order="date, id")
        res = {}
        for ml in lines:
            if ml.picking_id:
                res.setdefault((ml.location_dest_id.id, ml.product_id.id), ml.picking_id.name)
        return res

    @api.model
    def _kit_links(self, locs):
        """R-04: візок `KIT-*` -> (комплектація, МО): остання комплектація з цим призначенням; МО = її `origin`."""
        kits = locs.filtered(lambda loc: (loc.f3d_code or "").startswith("KIT-"))
        if not kits:
            return {}
        res = {}
        moves = self.env["stock.move"].search([
            ("location_dest_id", "in", kits.ids), ("picking_id", "!=", False), ("state", "!=", "cancel")],
            order="date, id")
        for mv in moves:
            pk = mv.picking_id
            res[mv.location_dest_id.f3d_code] = (pk.name, pk.origin or None)
        return {c: v for c, v in res.items() if v[1]}

    @api.model
    def _quality_by_lot(self):
        env = self.env
        if not payload_tools.access_ok(env, "quality.check"):
            return {}
        checks = env["quality.check"].search([("quality_state", "=", "fail"), ("lot_id", "!=", False)])
        return {c.lot_id.id: c.name for c in checks}

    @api.model
    def _orderpoints(self, locs):
        env = self.env
        if not locs or not payload_tools.access_ok(env, "stock.warehouse.orderpoint"):
            return {}
        ops = env["stock.warehouse.orderpoint"].search([("location_id", "in", locs.ids),
                                                        ("product_id.default_code", "!=", False)])
        purchase = {}
        if ops and payload_tools.access_ok(env, "purchase.order.line") \
                and "orderpoint_id" in env["purchase.order.line"]._fields:
            for line in env["purchase.order.line"].search([("orderpoint_id", "in", ops.ids),
                                                           ("order_id.state", "=", "purchase")]):
                purchase.setdefault(line.orderpoint_id.id, line.order_id.name)
        res = {}
        for op in ops:
            item = {"product": op.product_id.default_code, "min": _num(op.product_min_qty),
                    "max": _num(op.product_max_qty)}
            if op.id in purchase:
                item["purchase"] = purchase[op.id]
            res.setdefault(op.location_id.id, []).append(item)
        return res

    # ------------------------------------------------------------------ delta
    @api.model
    def _f3d_viewer_delta(self, patch, ctx):
        """R-14: локації з кодів і з подій stock.quant / stock.move.line / stock.location."""
        changes = ctx.get("changes") or {}
        sel = set(ctx.get("codes") or ())
        for model in ("stock.quant", "stock.move.line", "stock.location"):
            sel |= set(changes.get(model) or ())
        tmp = {}
        self._f3d_viewer_collect(tmp, ctx)
        part = {"locations": {c: v for c, v in (tmp.get("locations") or {}).items() if c in sel}}
        if part["locations"]:
            payload_tools.deep_merge(patch, part)
