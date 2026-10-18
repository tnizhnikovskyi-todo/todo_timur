import re

from odoo import api, models

from ..tools import dates
from ..tools import payload as payload_tools

OP_RE = re.compile(r"^OP-(.+)$")


class F3dViewerProviderPeople(models.AbstractModel):
    """M-01f: співробітники (hr.employee.public, без sudo, X-09)."""
    _name = "f3d.viewer.provider.people"
    _inherit = "f3d.viewer.provider"
    _description = "3D: провайдер даних people"

    _f3d_sequence = 60
    _f3d_sections = ("employees",)
    _f3d_group = "base.group_user"

    @api.model
    def _f3d_viewer_bus_models(self):
        return ["hr.employee", "mrp.workorder", "hr.attendance"]

    @api.model
    def _f3d_viewer_collect(self, payload, ctx):
        env = self.env
        if not payload_tools.access_ok(env, "hr.employee.public"):
            return
        rows = env["hr.employee.public"].search_read(
            [("f3d_code", "!=", False), ("active", "=", True)],
            ["f3d_code", "name", "job_title", "job_id", "department_id", "resource_calendar_id"], order="id")
        out = payload.setdefault("employees", {})
        op_wo, wo_by_wc = self._operators(env)
        known_wc = set(wo_by_wc) | set(((ctx.get("static") or {}).get("workcenters") or {}))
        present = self._present(env, [r["id"] for r in rows], ctx)
        for r in rows:
            code = r["f3d_code"]
            rec = {
                "name": r["name"],
                "job": r["job_title"] or (r["job_id"] and r["job_id"][1]) or "",
                "department": (r["department_id"] and r["department_id"][1]) or "",
                "shift": (r["resource_calendar_id"] and r["resource_calendar_id"][1]) or "",
            }
            wc, wo = op_wo.get(r["id"], (None, None))
            if not wc:
                m = OP_RE.match(code)
                if m and m.group(1) in known_wc:
                    wc = m.group(1)
                    wo = wo_by_wc.get(wc)
            if wc:
                rec["workcenter"] = wc
                if wo:
                    rec["current_workorder"] = wo
            if r["id"] in present:
                rec["present"] = True
            out.setdefault(code, {}).update(rec)

    @api.model
    def _operators(self, env):
        """(employee_id -> (код центру, WO-id)), (код центру -> WO-id) для завдань у роботі."""
        op_wo, wo_by_wc = {}, {}
        if not payload_tools.access_ok(env, "mrp.workorder"):
            return op_wo, wo_by_wc
        for wo in env["mrp.workorder"].search_fetch([("state", "=", "progress")], order="date_start, id"):
            code = wo.workcenter_id.f3d_code
            if not code:
                continue
            wid = f"WO{wo.id:05d}"
            wo_by_wc.setdefault(code, wid)
            for emp_id in self._employees_of(wo):
                op_wo.setdefault(emp_id, (code, wid))
        return op_wo, wo_by_wc

    @api.model
    def _employees_of(self, wo):
        ids = []
        if "employee_ids" in wo._fields:
            ids += wo.employee_ids.ids
        if "employee_id" in wo._fields and wo.employee_id:
            ids.append(wo.employee_id.id)
        return ids

    @api.model
    def _present(self, env, emp_ids, ctx):
        if not emp_ids or not payload_tools.access_ok(env, "hr.attendance"):
            return set()
        start = dates.utc(ctx["today"] + " 00:00")
        att = env["hr.attendance"].search_fetch([("employee_id", "in", emp_ids), ("check_in", ">=", start),
                                           ("check_out", "=", False)])
        return set(att.employee_id.ids)

    @api.model
    def _f3d_viewer_delta(self, patch, ctx):
        """Співробітники `OP-*` з кодів центрів і за прямими кодами."""
        changes = ctx.get("changes") or {}
        sel = set(ctx.get("codes") or ())
        for model in ("hr.employee", "mrp.workorder", "hr.attendance"):
            sel |= set(changes.get(model) or ())
        tmp = {}
        self._f3d_viewer_collect(tmp, ctx)
        part = {c: v for c, v in (tmp.get("employees") or {}).items()
                if c in sel or v.get("workcenter") in sel or c.replace("OP-", "", 1) in sel}
        if part:
            payload_tools.deep_merge(patch, {"employees": part})
