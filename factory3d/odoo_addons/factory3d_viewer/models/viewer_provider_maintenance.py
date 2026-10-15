from datetime import timedelta

from odoo import api, models

from ..tools import dates
from ..tools import payload as payload_tools

STATIC_KEYS = ("state", "busy", "total", "boilers", "last_inspection", "leak_check")


class F3dViewerProviderMaintenance(models.AbstractModel):
    """M-01e: обладнання й заявки на обслуговування."""
    _name = "f3d.viewer.provider.maintenance"
    _inherit = "f3d.viewer.provider"
    _description = "3D: провайдер даних maintenance"

    _f3d_sequence = 50
    _f3d_sections = ("equipment", "maintenance_requests")
    _f3d_group = "base.group_user"

    @api.model
    def _f3d_viewer_bus_models(self):
        return ["maintenance.equipment", "maintenance.request"]

    @api.model
    def _f3d_viewer_collect(self, payload, ctx):
        env = self.env
        if not payload_tools.access_ok(env, "maintenance.equipment"):
            return
        static_eq = (ctx.get("static") or {}).get("equipment") or {}
        equipment = payload.setdefault("equipment", {})
        since = dates.utc(ctx["today"] + " 00:00") - timedelta(days=7)

        requests = env["maintenance.request"].browse()
        open_by_eq, next_prev = {}, {}
        if payload_tools.access_ok(env, "maintenance.request"):
            requests = env["maintenance.request"].search_fetch([
                ("equipment_id.f3d_code", "!=", False),
                "|", ("stage_id.done", "=", False), ("close_date", ">=", since.date())], order="request_date, id")
            for r in requests.filtered(lambda r: not r.stage_id.done):
                open_by_eq.setdefault(r.equipment_id.id, r.name)
                # в Odoo 19 немає next_action_date: найближча планова профілактика
                if r.maintenance_type == "preventive" and (r.schedule_date or r.request_date):
                    day = r.schedule_date.date() if r.schedule_date else r.request_date
                    next_prev[r.equipment_id.id] = min(day, next_prev.get(r.equipment_id.id, day))

        passport_ok = payload_tools.access_ok(env, "f3d.equipment.passport")
        tasks = {}
        if payload_tools.access_ok(env, "stock.picking.batch"):
            for b in env["stock.picking.batch"].search_fetch([("f3d_vehicle_id", "!=", False),
                                                        ("state", "in", ("in_progress", "draft"))], order="id"):
                tasks.setdefault(b.f3d_vehicle_id.id, b.name)

        for eq in env["maintenance.equipment"].search_fetch([("f3d_code", "!=", False)], order="id"):
            code = eq.f3d_code
            rec = {"name": eq.name, "category": eq.category_id.name or ""}
            if eq.serial_no and eq.serial_no != code:
                rec["serial"] = eq.serial_no
            if passport_ok and eq.f3d_manufacturer:
                rec["manufacturer"] = eq.f3d_manufacturer
            if passport_ok and eq.f3d_model:
                rec["model"] = eq.f3d_model
            nxt = eq.next_action_date if "next_action_date" in eq._fields else next_prev.get(eq.id)
            if nxt:
                rec["next_maintenance"] = str(nxt)
            if eq.id in open_by_eq:
                rec["maintenance_request"] = open_by_eq[eq.id]
            if eq.id in tasks:
                rec["current_task"] = tasks[eq.id]
            for k in STATIC_KEYS:
                if k in (static_eq.get(code) or {}):
                    rec[k] = static_eq[code][k]
            equipment.setdefault(code, {}).update(rec)

        out = []
        for r in requests:
            rec = {"id": r.name, "name": r.name, "equipment": r.equipment_id.f3d_code,
                   "maintenance_type": r.maintenance_type, "stage": r.stage_id.name,
                   "priority": r.priority or "0"}
            if r.request_date:
                rec["request_date"] = dates.date_to_local(r.request_date)
            if r.schedule_date:
                rec["schedule_date"] = dates.local(r.schedule_date)
            if r.user_id:
                rec["technician"] = r.user_id.name
            out.append(rec)
        payload["maintenance_requests"] = out

    @api.model
    def _f3d_viewer_delta(self, patch, ctx):
        """Заявки й обладнання з кодів."""
        changes = ctx.get("changes") or {}
        sel = set(ctx.get("codes") or ())
        for model in ("maintenance.equipment", "maintenance.request"):
            sel |= set(changes.get(model) or ())
        tmp = {}
        self._f3d_viewer_collect(tmp, ctx)
        reqs = [r for r in tmp.get("maintenance_requests") or [] if r["id"] in sel or r["equipment"] in sel]
        eq_sel = sel | {r["equipment"] for r in reqs}
        part = {"maintenance_requests": reqs,
                "equipment": {c: v for c, v in (tmp.get("equipment") or {}).items() if c in eq_sel}}
        part = {k: v for k, v in part.items() if v}
        if part:
            payload_tools.deep_merge(patch, part)
