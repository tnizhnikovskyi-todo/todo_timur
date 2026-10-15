import re
from datetime import datetime, timedelta

from odoo import api, models
from odoo.tools import html2plaintext

from ..tools import dates
from ..tools import payload as payload_tools

# коефіцієнт завантаження за типом верстата (plant/energy.PROFILE): запасний, якщо у статиці немає energy.profile_k
PROFILE_KF = {
    "saw": 0.55, "saw_book": 0.6, "slide": 0.45, "vsaw": 0.4, "nest": 0.55, "edge": 0.65, "edge_robot": 0.65,
    "cnc": 0.5, "bore": 0.5, "dowel": 0.45, "hinge": 0.3, "sortbot": 0.45, "sand": 0.7, "press": 0.6, "glue": 0.7,
    "spray": 0.75, "autospray": 0.6, "dry": 0.75, "uv": 0.7, "asmline": 0.4, "asm": 0.35, "box": 0.45,
    "pack": 0.4, "packline": 0.65,
}
WO_RE = re.compile(r"^WO(\d{5})$")
MO_STATE = {"to_close": "progress", "draft": "confirmed"}


def _minutes(start, end):
    return max(0.0, (end - start).total_seconds() / 60)


def _num(value):
    value = float(value)
    return int(value) if value.is_integer() else round(value, 2)


class F3dViewerProviderProduction(models.AbstractModel):
    """M-01b: робочі центри, виробничі замовлення й завдання (R-06, R-07, R-08)."""
    _name = "f3d.viewer.provider.production"
    _inherit = "f3d.viewer.provider"
    _description = "3D: провайдер даних production"

    _f3d_sequence = 30
    _f3d_sections = ("workcenters", "productions", "workorders")
    _f3d_group = "mrp.group_mrp_user"

    @api.model
    def _f3d_viewer_bus_models(self):
        return ["mrp.production", "mrp.workorder", "mrp.workcenter", "mrp.workcenter.productivity"]

    # ------------------------------------------------------------------ collect
    @api.model
    def _f3d_viewer_collect(self, payload, ctx):
        env = self.env
        if not all(payload_tools.access_ok(env, m) for m in (
                "mrp.workcenter", "mrp.production", "mrp.workorder", "mrp.workcenter.productivity")):
            return
        now = ctx["now"]
        static = ctx.get("static") or {}
        today_start = dates.utc(ctx["today"] + " 00:00")

        mos = env["mrp.production"].search([
            ("state", "!=", "cancel"), "|", ("state", "in", ("confirmed", "progress", "to_close")),
            ("date_finished", ">=", today_start)], order="id")
        wos_all = env["mrp.workorder"].search([("production_id", "in", mos.ids)], order="sequence, id")
        wcs = env["mrp.workcenter"].search([("f3d_code", "!=", False)], order="id")

        # --- журнал продуктивності: по завданнях (будь-коли) і по центрах (сьогодні)
        logs_wo = env["mrp.workcenter.productivity"].search([("workorder_id", "in", wos_all.ids)])
        worked, first, last = {}, {}, {}
        for lg in logs_wo:
            k = lg.workorder_id.id
            worked[k] = worked.get(k, 0.0) + _minutes(lg.date_start, lg.date_end or now)
            first[k] = min(first.get(k, lg.date_start), lg.date_start)
            if lg.date_end:
                last[k] = max(last.get(k, lg.date_end), lg.date_end)
        logs_today = env["mrp.workcenter.productivity"].search([
            ("workcenter_id", "in", wcs.ids), "|", ("date_end", "=", False), ("date_start", ">=", today_start)])

        # --- робочі завдання й МО
        wo_out, mo_out = {}, []
        derived = {}  # wo.id -> (id, state)
        children = {}
        if mos:
            for child in env["mrp.production"].search([("origin", "in", mos.mapped("name"))]):
                children.setdefault(child.origin, []).append(child.name)
        comp_locs = self._component_locations(mos, static)
        consumers = (static.get("energy") or {}).get("consumers") or {}
        machines = (static.get("layout") or {}).get("machines") or {}
        kf_map = (static.get("energy") or {}).get("profile_k") or {}
        tariff = ((static.get("energy") or {}).get("meta") or {}).get("tariff_uah") or 0

        for mo in mos:
            res_waiting = mo.reservation_state == "confirmed" and mo.state == "confirmed"
            state = MO_STATE.get(mo.state, mo.state)
            ws = wos_all.filtered(lambda w: w.production_id == mo and w.state != "cancel")
            prev = "done"
            ids, kwh = [], 0.0
            n_done, sum_prog = 0, 0.0
            for k, wo in enumerate(ws):
                wid = f"WO{wo.id:05d}"
                st = wo.state
                if st in ("ready", "blocked", "pending"):
                    st = "waiting" if (k == 0 and res_waiting) else "ready" if prev in ("done", "progress") else "pending"
                prev = st
                mins = worked.get(wo.id, 0.0)
                rec = {"id": wid, "name": wo.name, "production": mo.name,
                       "workcenter": wo.workcenter_id.f3d_code or "", "state": st, "sequence": k + 1,
                       "duration_expected": round(wo.duration_expected or 0)}
                start = first.get(wo.id) or wo.date_start
                if st == "done":
                    fin = last.get(wo.id) or wo.date_finished
                    rec.update(progress=1.0, duration=round(mins))
                    if start:
                        rec["date_start"] = dates.local(start)
                    if fin:
                        rec["date_finished"] = dates.local(fin)
                    n_done += 1
                elif st == "progress":
                    prog = round(min(0.99, mins / max(1, wo.duration_expected or 0)), 2)
                    rec.update(progress=prog, duration=round(mins))
                    if start:
                        rec["date_start"] = dates.local(start)
                        rec["date_planned_finished"] = dates.local(
                            start + timedelta(minutes=wo.duration_expected or 0))
                    if wo.working_state == "blocked":
                        rec["blocked"] = True
                    sum_prog += prog
                else:
                    rec["progress"] = 0.0
                if st in ("done", "progress"):
                    code = rec["workcenter"]
                    p_inst = (consumers.get(code) or {}).get("p_inst")
                    if p_inst:
                        typ = (machines.get(code) or {}).get("type")
                        kf = kf_map.get(typ, PROFILE_KF.get(typ, 0.5))
                        if isinstance(kf, (list, tuple)):
                            kf = kf[0]
                        kwh += p_inst * kf * rec["duration"] / 60
                wo_out[wid] = rec
                derived[wo.id] = (wid, st, wo)
                ids.append(wid)
            n = len(ws)
            item = {
                "name": mo.name, "product": mo.product_id.default_code or "", "product_name": mo.product_id.name,
                "qty": mo.product_qty, "uom": mo.product_uom_id.name, "state": state,
                "origin": mo.origin or "", "route": mo.bom_id.code or "", "workorders": ids,
                "date_start": dates.local(mo.date_start) if mo.date_start else None,
                "date_deadline": (dates.local(mo.date_deadline or mo.date_finished)
                                  if (mo.date_deadline or mo.date_finished) else None),
                "progress": round((n_done + sum_prog) / n, 2) if n else 0.0,
                "components": self._components(mo, comp_locs),
                "energy_kwh": round(kwh, 1),
            }
            if res_waiting:
                item["reservation_state"] = "waiting"
            if children.get(mo.name):
                item["child_productions"] = children[mo.name]
            if ctx.get("energy_cost") and not ctx.get("kiosk"):
                item["energy_cost"] = round(kwh * tariff)
            mo_out.append(item)

        payload["productions"] = mo_out
        payload["workorders"] = wo_out
        wc_out = payload.setdefault("workcenters", {})
        self._workcenters(wc_out, wcs, derived, logs_today, ctx, static)

    # ------------------------------------------------------------------ робочі центри (R-06)
    @api.model
    def _workcenters(self, out, wcs, derived, logs_today, ctx, static):
        env = self.env
        now = ctx["now"]
        today_start = dates.utc(ctx["today"] + " 00:00")
        now_local = datetime.strptime(ctx["now_local"], dates.FMT)
        weekday = now_local.weekday()
        consumers = (static.get("energy") or {}).get("consumers") or {}

        # обладнання центрів і відкриті заявки
        eq_by_wc, req_by_eq = {}, {}
        if payload_tools.access_ok(env, "maintenance.equipment"):
            eqs = env["maintenance.equipment"].search([("f3d_code", "!=", False)])
            link = "workcenter_id" in env["maintenance.equipment"]._fields
            for eq in eqs:
                wc_code = (eq.workcenter_id.f3d_code if link and eq.workcenter_id else None) or eq.f3d_code
                eq_by_wc.setdefault(wc_code, eq)
            if payload_tools.access_ok(env, "maintenance.request"):
                for r in env["maintenance.request"].search([("stage_id.done", "=", False),
                                                            ("equipment_id", "in", eqs.ids)],
                                                           order="request_date, id"):
                    req_by_eq.setdefault(r.equipment_id.id, r.name)

        passport_ok = payload_tools.access_ok(env, "f3d.equipment.passport")
        prod_min, loss_min = {}, {}
        for lg in logs_today:
            wcid = lg.workcenter_id.id
            start = max(lg.date_start, today_start)
            minutes = _minutes(start, lg.date_end or now) if not lg.date_end else (lg.duration or 0.0)
            if lg.loss_id.loss_type == "productive":
                prod_min[wcid] = prod_min.get(wcid, 0.0) + minutes
            else:
                d = loss_min.setdefault(wcid, {})
                d[lg.loss_id.name] = d.get(lg.loss_id.name, 0.0) + minutes

        by_wc = {}
        for wid, st, wo in derived.values():
            by_wc.setdefault(wo.workcenter_id.id, []).append((wid, st, wo))

        for wc in wcs:
            code = wc.f3d_code
            items = by_wc.get(wc.id, [])
            cur = sorted((x for x in items if x[1] == "progress"), key=lambda x: x[2].date_start or now)
            queue = sorted((x for x in items if x[1] in ("ready", "waiting", "pending")),
                           key=lambda x: (x[1] != "ready", x[2].production_id.name))[:8]
            current = cur[0][0] if cur else None
            status = "stop" if wc.working_state == "blocked" else "work" if current else "idle"
            productive = round(prod_min.get(wc.id, 0.0))
            shift_start, shift_end = self._shift(wc, now_local, weekday)
            elapsed = _minutes(shift_start, min(now_local, shift_end))
            oee = max(0.0, min(1.0, round(productive / max(1, elapsed), 2)))
            cap_row = wc.capacity_ids.filtered(lambda c: not c.product_id)[:1]
            capacity = _num(cap_row.capacity) if cap_row else 1
            eq = eq_by_wc.get(code)
            passport = (static.get("passports") or {}).get(code) or (static.get("workcenters") or {}).get(code) or {}
            rec = {
                "name": wc.name, "code": code, "status": status, "working_state": wc.working_state,
                "oee": oee, "capacity": capacity, "time_efficiency": round((wc.time_efficiency or 100) / 100, 2),
                "productive_minutes": productive,
                "losses": sorted(({"reason": r, "minutes": round(m)} for r, m in loss_min.get(wc.id, {}).items()),
                                 key=lambda x: -x["minutes"]),
                "current_workorder": current, "queue": [x[0] for x in queue],
                "manufacturer": (eq and passport_ok and eq.f3d_manufacturer) or passport.get("manufacturer") or "",
                "model": (eq and passport_ok and eq.f3d_model) or passport.get("model") or "",
            }
            cons = consumers.get(code)
            if cons:
                rec["energy"] = {"p_now": cons.get("p_now"), "line": cons.get("line")}
            if status == "idle":
                note = html2plaintext(wc.note or "").strip().split("\n")[0].strip() if wc.note else ""
                waiting = next((x for x in queue if x[1] == "waiting"), None)
                if note:
                    rec["idle_reason"] = note
                elif waiting:
                    rec["idle_reason"] = "Чекає компонентів для %s" % waiting[2].production_id.name
            if eq and eq.id in req_by_eq:
                rec["maintenance_request"] = req_by_eq[eq.id]
            out.setdefault(code, {}).update(rec)

    @api.model
    def _shift(self, wc, now_local, weekday):
        """Початок і кінець зміни за календарем центру; без календаря — з 07:00."""
        day = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
        atts = wc.resource_calendar_id.attendance_ids.filtered(
            lambda a: a.dayofweek == str(weekday) and a.day_period != "lunch" and not a.display_type)
        if atts:
            return (day + timedelta(hours=min(atts.mapped("hour_from"))),
                    day + timedelta(hours=max(atts.mapped("hour_to"))))
        return day + timedelta(hours=7), day + timedelta(days=1)

    # ------------------------------------------------------------------ компоненти (R-08)
    @api.model
    def _component_locations(self, mos, static):
        env = self.env
        if not mos or not payload_tools.access_ok(env, "stock.quant"):
            return {}
        pids = mos.move_raw_ids.filtered(lambda m: m.state != "cancel").product_id.ids
        quants = env["stock.quant"].search([("product_id", "in", pids), ("quantity", "!=", 0),
                                            ("location_id.f3d_code", "!=", False)])
        order = {c: i for i, c in enumerate(((static.get("layout") or {}).get("locations") or {}))}
        res = {}
        for q in quants:
            res.setdefault(q.product_id.id, set()).add(q.location_id.f3d_code)
        return {pid: sorted(codes, key=lambda c: (order.get(c, 1 << 30), c)) for pid, codes in res.items()}

    @api.model
    def _components(self, mo, comp_locs):
        groups = {}
        for mv in mo.move_raw_ids.filtered(lambda m: m.state != "cancel"):
            g = groups.setdefault(mv.product_id, {"qty": 0.0, "avail": 0.0, "done": True})
            g["qty"] += mv.product_uom_qty
            g["avail"] += mv.quantity
            g["done"] = g["done"] and mv.state == "done"
        out = []
        for product, g in groups.items():
            out.append({
                "product": product.default_code or "", "qty": round(g["qty"]),
                "available": g["avail"] >= g["qty"] or g["done"],
                "locations": comp_locs.get(product.id, [])[:12]})
        return out

    # ------------------------------------------------------------------ delta (R-14)
    @api.model
    def _f3d_viewer_delta(self, patch, ctx):
        """Завдання з кодів `WO*`, їхні МО, МО з кодів, центри з кодів і центри цих завдань."""
        changes = ctx.get("changes") or {}
        sel = set(ctx.get("codes") or ())
        for model in ("mrp.production", "mrp.workorder", "mrp.workcenter", "mrp.workcenter.productivity"):
            sel |= set(changes.get(model) or ())
        tmp = {}
        self._f3d_viewer_collect(tmp, ctx)
        wos = tmp.get("workorders") or {}
        mo_names = {w["production"] for k, w in wos.items() if k in sel}
        mo_names |= {c for c in sel if not WO_RE.match(c)}
        prods = [m for m in (tmp.get("productions") or []) if m["name"] in mo_names]
        wo_sel = {k for k, w in wos.items() if k in sel or w["production"] in mo_names}
        wc_sel = {wos[k]["workcenter"] for k in wo_sel} | sel
        part = {
            "productions": prods,
            "workorders": {k: wos[k] for k in wo_sel},
            "workcenters": {c: v for c, v in (tmp.get("workcenters") or {}).items() if c in wc_sel},
        }
        part = {k: v for k, v in part.items() if v}
        if part:
            payload_tools.deep_merge(patch, part)
