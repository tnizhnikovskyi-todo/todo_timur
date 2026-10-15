import re
from datetime import timedelta

from odoo import api, models
from odoo.tools import html2plaintext

from ..tools import dates
from ..tools import payload as payload_tools

PICK_STATE = {"confirmed": "waiting", "waiting": "waiting", "assigned": "assigned", "done": "done",
              "draft": "draft"}
# внутрішні типи операцій за назвою (lower, uk) -> type
INTERNAL_TYPES = (
    ("розміщення плит", "putaway"), ("поповнення під портал", "replenish"),
    ("комплектація компонентів", "pick_components"), ("розміщення готової продукції", "store_finished"),
)
SRC_TYPES = ("outgoing", "putaway", "replenish", "pick_components")
DEST_CODE_TYPES = ("pick_components", "replenish", "putaway")
UNLOAD_RE = re.compile(r"^UNLOAD-(\d+)$")
DOCK_RE = re.compile(r"^DOCK-([WE])(\d+)$")


def _text(html, limit):
    return html2plaintext(html or "").strip()[:limit]


def _dock_code(loc, outgoing):
    """Код воріт із локації: DOCK-Wk/Ek або UNLOAD-k -> DOCK-Wk."""
    if not loc:
        return None
    for c in (loc.f3d_code, loc.f3d_alias, loc.barcode):
        if not c:
            continue
        if DOCK_RE.match(c):
            return c
        m = UNLOAD_RE.match(c)
        if m and not outgoing:
            return "DOCK-W%s" % m.group(1)
    return None


class F3dViewerProviderLogistics(models.AbstractModel):
    """M-01c: переміщення, ворота, замовлення клієнтів і постачальників (R-05, R-09)."""
    _name = "f3d.viewer.provider.logistics"
    _inherit = "f3d.viewer.provider"
    _description = "3D: провайдер даних logistics"

    _f3d_sequence = 40
    _f3d_sections = ("pickings", "docks", "sale_orders", "purchase_orders")
    _f3d_group = "stock.group_stock_user"

    @api.model
    def _f3d_viewer_bus_models(self):
        return ["stock.picking", "stock.move", "stock.picking.batch", "sale.order", "purchase.order"]

    # ------------------------------------------------------------------ collect
    @api.model
    def _f3d_viewer_collect(self, payload, ctx):
        env = self.env
        pickings = self._pickings(ctx)
        payload["pickings"] = pickings
        payload["docks"] = self._docks(pickings, ctx)
        for key, model, func in (("sale_orders", "sale.order", self._sale_orders),
                                 ("purchase_orders", "purchase.order", self._purchase_orders)):
            if payload_tools.access_ok(env, model):
                payload[key] = func(ctx)
            else:
                payload[key] = []
                ctx["sections"][key] = "missing" if model not in env else "denied"

    # ------------------------------------------------------------------ переміщення
    @api.model
    def _picking_type(self, picking):
        code = picking.picking_type_code
        if code in ("incoming", "outgoing"):
            return code
        if code == "internal":
            name = (picking.picking_type_id.name or "").strip().lower()
            for prefix, typ in INTERNAL_TYPES:
                if name.startswith(prefix):
                    return typ
        return None

    @api.model
    def _pickings(self, ctx):
        env = self.env
        today = ctx["today"]
        start = dates.utc(today + " 00:00") - timedelta(days=7)
        end = dates.utc(today + " 00:00") + timedelta(days=8)
        recs = env["stock.picking"].search_fetch([
            ("state", "!=", "cancel"), "|", "&", ("scheduled_date", ">=", start), ("scheduled_date", "<", end),
            ("state", "in", ("assigned", "waiting", "confirmed"))], order="scheduled_date, id")
        quality_fail = self._quality_fail(recs)
        moves_of = {}  # одна вибірка рядків замість o2m-читання на кожну комплектацію (AC-52)
        if recs:
            for mv in env["stock.move"].search_fetch([("picking_id", "in", recs.ids), ("state", "!=", "cancel")]):
                moves_of.setdefault(mv.picking_id.id, []).append(mv)
            (recs.move_line_ids.location_id | recs.move_line_ids.location_dest_id).mapped("f3d_code")
        has_carrier = "carrier_id" in env["stock.picking"]._fields
        out = []
        for p in recs:
            typ = self._picking_type(p)
            if not typ:
                continue
            moves = moves_of.get(p.id, [])
            lines = []
            for m in moves:
                done = m.quantity if (m.picked or m.state == "done") else 0
                lines.append({"product": m.product_id.default_code or m.product_id.name,
                              "qty": m.product_uom_qty, "qty_done": round(done, 2)})
            total = sum(x["qty"] for x in lines)
            progress = round(sum(min(x["qty_done"], x["qty"]) for x in lines) / max(total, 1), 2)
            state = PICK_STATE.get(p.state, p.state)
            sched = p.date_done if p.state == "done" and p.date_done else p.scheduled_date
            rec = {
                "name": p.name, "picking_type": p.picking_type_id.name, "type": typ,
                "partner": p.partner_id.name or "", "origin": p.origin or "", "state": state,
                "scheduled_date": dates.local(sched) if sched else None, "progress": progress, "lines": lines,
            }
            mls = p.move_line_ids
            batch = p.batch_id
            if typ in ("incoming", "outgoing"):
                dock = batch.dock_id.f3d_code if batch.dock_id and batch.dock_id.f3d_code else None
                if not dock:
                    dock = self._dock_from_locations(p, mls, typ)
                if dock:
                    rec["dock"] = dock
                rec["truck"] = batch.f3d_code or None
            if batch.f3d_vehicle_id.f3d_code:
                rec["vehicle"] = batch.f3d_vehicle_id.f3d_code
            if typ in SRC_TYPES:
                src = []
                for loc in mls.location_id:
                    # ворота (DOCK-*) — не комірка зберігання: резерв, зроблений на воротах, не є «звідки взято»
                    if loc.f3d_code and not loc.f3d_code.startswith("DOCK-") and loc.f3d_code not in src:
                        src.append(loc.f3d_code)
                if src:
                    rec["source_locations"] = src
            if typ in DEST_CODE_TYPES:
                dest = (mls.location_dest_id[:1] or p.location_dest_id)
                if dest.f3d_code:
                    rec["location_dest"] = dest.f3d_code
            elif typ in ("incoming", "store_finished"):
                name = p.location_dest_id.complete_name or ""
                rec["location_dest"] = name.split("/", 1)[1] if "/" in name else name
            note = self._note(p, typ, state, quality_fail)
            if note:
                rec["note"] = note
            if has_carrier and p.carrier_id:
                rec["carrier"] = p.carrier_id.name
            out.append(rec)
        return out

    @api.model
    def _dock_from_locations(self, p, mls, typ):
        outgoing = typ == "outgoing"
        if outgoing:
            cands = p.location_id | mls.location_id
        else:
            cands = p.location_dest_id | mls.location_dest_id
        for loc in cands:
            code = _dock_code(loc, outgoing)
            if code and DOCK_RE.match(code) and (code[5] == ("E" if outgoing else "W")):
                return code
        return None

    @api.model
    def _quality_fail(self, pickings):
        env = self.env
        if not pickings or not payload_tools.access_ok(env, "quality.check"):
            return {}
        res = {}
        for c in env["quality.check"].search_fetch([
                ("picking_id", "in", pickings.ids), ("quality_state", "=", "fail")]):
            # Odoo 19: лише lot_ids (m2m); перевірка без партій, як і раніше, відповідає рядкам без партії
            res.setdefault(c.picking_id.id, set()).update(c.lot_ids.ids or [False])
        return res

    @api.model
    def _note(self, p, typ, state, quality_fail):
        if typ == "outgoing" and p.state == "waiting":
            return "Чекає завершення МО"
        if typ == "incoming" and p.id in quality_fail:
            lots = quality_fail[p.id]
            bad = sum(ml.quantity for ml in p.move_line_ids if ml.lot_id.id in lots)
            total = sum(ml.quantity for ml in p.move_line_ids)
            if bad:
                return "%s арк. пройшли контроль; %s — у карантині (QC-1)" % (
                    _fmt(total - bad), _fmt(bad))
        return _text(p.note, 200)

    # ------------------------------------------------------------------ ворота (R-05)
    @api.model
    def _docks(self, pickings, ctx):
        today = ctx["today"]
        out = {}
        by_dock = {}
        for p in pickings:
            if p.get("dock"):
                by_dock.setdefault(p["dock"], []).append(p)
        for dock, items in by_dock.items():
            open_ = [p for p in items if p["state"] != "done"]  # вже за scheduled_date
            if open_:
                out[dock] = open_[0]["name"]
                continue
            done = [p for p in items if (p.get("scheduled_date") or "")[:10] == today]
            if done:
                out[dock] = done[-1]["name"]
        return out

    # ------------------------------------------------------------------ замовлення (R-09, A.7)
    @api.model
    def _sale_orders(self, ctx):
        env = self.env
        orders = env["sale.order"].search_fetch([("state", "not in", ("draft", "sent", "cancel"))], order="id")
        if not orders:
            return []
        names = orders.mapped("name")
        prod_by_origin, ship_by_origin = {}, {}
        if payload_tools.access_ok(env, "mrp.production"):
            for mo in env["mrp.production"].search_fetch([("origin", "in", names)], order="id"):
                prod_by_origin.setdefault(mo.origin, []).append(mo.name)
        for pk in env["stock.picking"].search_fetch([("origin", "in", names), ("picking_type_code", "=", "outgoing"),
                                               ("state", "!=", "cancel")], order="id"):
            ship_by_origin.setdefault(pk.origin, pk.name)
        lines_of = {}
        for ln in env["sale.order.line"].search_fetch([("order_id", "in", orders.ids)]):
            lines_of.setdefault(ln.order_id.id, []).append(ln)
        amounts = (not ctx.get("kiosk")) and env.user.has_group("sales_team.group_sale_salesman_all_leads")
        out = []
        for so in orders:
            rec = {
                "name": so.name, "partner": so.partner_id.name or "", "state": so.state,
                "date_order": dates.local(so.date_order) if so.date_order else None,
                "commitment_date": dates.local(so.commitment_date) if so.commitment_date else None,
                "lines": [{"product": ln.product_id.default_code or ln.product_id.name, "qty": ln.product_uom_qty}
                          for ln in lines_of.get(so.id, []) if not ln.display_type and ln.product_id],
                "productions": prod_by_origin.get(so.name, []),
                "delivery": ship_by_origin.get(so.name, ""),
            }
            if amounts:
                rec["amount"] = so.amount_untaxed
            out.append(rec)
        return out

    @api.model
    def _purchase_orders(self, ctx):
        env = self.env
        orders = env["purchase.order"].search_fetch([("state", "not in", ("draft", "sent", "cancel"))], order="id")
        out = []
        has_op = "orderpoint_id" in env["purchase.order.line"]._fields
        lines_of = {}
        if orders:
            for ln in env["purchase.order.line"].search_fetch([("order_id", "in", orders.ids)]):
                lines_of.setdefault(ln.order_id.id, []).append(ln)
        for po in orders:
            lines = [ln for ln in lines_of.get(po.id, []) if not ln.display_type and ln.product_id]
            locs = []
            if has_op:
                for ln in lines:
                    code = ln.orderpoint_id.location_id.f3d_code
                    if code and code not in locs:
                        locs.append(code)
            out.append({
                "name": po.name, "partner": po.partner_id.name or "", "state": po.state,
                "date_order": dates.local(po.date_order) if po.date_order else None,
                "date_planned": dates.local(po.date_planned) if po.date_planned else None,
                "lines": [{"product": ln.product_id.default_code or ln.product_id.name, "qty": ln.product_qty}
                          for ln in lines],
                "locations": locs,
            })
        return out

    # ------------------------------------------------------------------ delta (R-14)
    @api.model
    def _f3d_viewer_delta(self, patch, ctx):
        """Переміщення з назв у кодах і з `dock` у кодах, `docks` цілком, замовлення за назвами."""
        changes = ctx.get("changes") or {}
        sel = set(ctx.get("codes") or ())
        for model in ("stock.picking", "stock.move", "stock.picking.batch", "sale.order", "purchase.order"):
            sel |= set(changes.get(model) or ())
        tmp = {}
        self._f3d_viewer_collect(tmp, ctx)
        part = {"docks": tmp.get("docks") or {}}
        for key in ("pickings", "sale_orders", "purchase_orders"):
            part[key] = [r for r in tmp.get(key) or [] if r["name"] in sel or r.get("dock") in sel]
        part = {k: v for k, v in part.items() if v}
        if part:
            payload_tools.deep_merge(patch, part)


def _fmt(value):
    return str(int(value)) if float(value).is_integer() else str(round(value, 2))
