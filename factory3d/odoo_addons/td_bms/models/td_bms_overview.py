"""M-10 td.bms.overview: дані огляду будівлі (FR-14, R-28). Права користувача запиту, без `sudo`."""

from datetime import timezone

from odoo import api, fields, models
from odoo.exceptions import AccessError

from ..tools import schedule, titles

OPEN_MODELS = ("td.bms.light.group", "td.bms.light.panel", "td.bms.hvac.unit", "td.zone")
HEAT_KEYS = (
    "outdoor_c",
    "heat_need_kw",
    "chp_heat_now_kw",
    "chp_source",
    "boilers_on_calc",
    "boilers_on",
    "boiler_state",
    "boiler_load",
    "boiler_heat_kw",
    "supply_c",
    "return_c",
    "silo_fill",
    "deficit_kw",
    "deviation",
    "deviation_text",
)


def _kyiv(dt):
    return dt.replace(tzinfo=timezone.utc).astimezone(titles.KYIV).strftime("%Y-%m-%d %H:%M")


class F3dBmsOverview(models.AbstractModel):
    _name = "td.bms.overview"
    _description = "Будівля: огляд"

    def _can_read(self, model):
        return model in self.env and self.env[model].has_access("read")

    def _search(self, model, domain=None):
        """Записи моделі за правами користувача; без доступу — порожній набір (R-28)."""
        return self.env[model].search(domain or []) if self._can_read(model) else self.env[model]

    def _work_time(self, now):
        icp = self.env["ir.config_parameter"].sudo()
        cal_id = (icp.get_param("td.bms.calendar_id") or "").strip()
        calendar = self.env["resource.calendar"].sudo().browse(int(cal_id)) if cal_id.isdigit() else None
        if not calendar or not calendar.exists():
            calendar = self.env.company.sudo().resource_calendar_id
        return schedule.work_interval_at(calendar, now) is not None

    @api.model
    def get_overview_data(self):
        env = self.env
        now = fields.Datetime.now()
        icp = env["ir.config_parameter"].sudo()
        groups = self._search("td.bms.light.group")
        panels = self._search("td.bms.light.panel")
        units = self._search("td.bms.hvac.unit")
        zones = self._search("td.zone", [("zone_type", "!=", "outdoor")])
        group_by_zone = {}
        for g in groups.sorted(lambda g: (g.sequence, g.code)):
            group_by_zone.setdefault(g.zone_id.id, g)
        heat = self._heat()
        deviations = self._deviations()
        requests = self._open_requests((groups, units))
        group_rows = [
            {
                "id": g.id,
                "code": g.code,
                "zone": g.zone_id.td_code,
                "e_now": g.e_now,
                "e_norm": g.e_norm,
                "level": round(g.level_pct / 100.0, 3),
                "faults": g.faults,
                "state": g.plan_state,
                "deviation_text": g.deviation_text or "",
            }
            for g in groups.sorted(lambda g: (g.sequence, g.code))
        ]
        unit_rows = [
            {
                "id": u.id,
                "code": u.code,
                "kind": u.kind,
                "x": u.x,
                "y": u.y,
                "zone": u.zone_id.td_code,
                "mode_label": u.mode_label,
                "state": u.state,
                "plan_state": u.plan_state,
                "airflow": u.airflow_m3h,
                "filter_dp": u.filter_dp_pa,
                "deviation_text": u.deviation_text or "",
            }
            for u in units
        ]
        live = heat["live"]
        return {
            "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "work_time": self._work_time(now),
            "plan": {
                "width": float(icp.get_param("td.base.plant_length_m", 150)),
                "depth": float(icp.get_param("td.base.plant_width_m", 72)),
            },
            "zones": [
                {
                    "id": z.id,
                    "code": z.td_code,
                    "name": z.name,
                    "polygon": z.polygon or [],
                    "group": group_by_zone[z.id].code if z.id in group_by_zone else None,
                    "state": group_by_zone[z.id].plan_state if z.id in group_by_zone else None,
                }
                for z in zones
            ],
            "groups": group_rows,
            "panels": [
                {"id": p.id, "code": p.code, "x": p.x, "y": p.y, "state": p.state, "p_now": p.p_now_kw} for p in panels
            ],
            "units": unit_rows,
            "kpi": {
                "groups_ok": sum(1 for g in groups if g.plan_state == "ok"),
                "groups_total": len(groups),
                "lighting_kw": round(sum(groups.mapped("p_now_kw")), 1),
                "units_on": sum(1 for u in units if u.state == "on"),
                "units_total": len(units),
                "airflow": round(sum(units.mapped("airflow_m3h")), -2),
                "heat_need": live.get("heat_need_kw", 0.0),
                "chp_heat": round(live.get("chp_heat_now_kw", 0.0)),
                "boilers_on": live.get("boilers_on", 0),
                "deficit": live.get("deficit_kw", 0.0),
                "open_deviations": deviations["count"],
                "open_requests": requests,
            },
            "heat": heat["data"],
            "deviations": deviations["rows"],
        }

    def _heat(self):
        if not self._can_read("td.bms.heat.balance"):
            return {"live": {}, "data": {}}
        bal = self.env["td.bms.heat.balance"]._f3d_bms_get()
        live = bal._f3d_bms_live()
        data = {k: live[k] for k in HEAT_KEYS}
        data["design"] = {
            "total": bal.total_kw,
            "capacity": bal.capacity_kw,
            "chp": round(bal.chp_heat_kw),
            "reserve": bal.reserve,
            "lines": [{"name": line.name, "kw": line.kw_round} for line in bal.line_ids.sorted("sequence")],
        }
        return {"live": live, "data": data}

    def _deviations(self):
        if not self._can_read("td.bms.deviation"):
            return {"count": 0, "rows": []}
        Dev = self.env["td.bms.deviation"]
        domain = [("state", "=", "open")]
        return {
            "count": Dev.search_count(domain),
            "rows": [
                {
                    "id": d.id,
                    "started": _kyiv(d.started),
                    "object_code": d.object_code,
                    "rule": d.rule,
                    "name": d.name,
                    "request": d.request_id.name or False,
                }
                for d in Dev.search(domain, order="started desc, id desc", limit=50)
            ],
        }

    def _open_requests(self, objects):
        if not self._can_read("maintenance.request"):
            return 0
        reqs = self.env["maintenance.request"]
        for objs in objects:
            for rec in objs:
                reqs |= rec.request_ids
        return len(reqs)

    @api.model
    def action_open(self, model, res_id, what):
        if model not in OPEN_MODELS:
            raise AccessError("Перехід до цього об'єкта недоступний.")
        record = self.env[model].browse(int(res_id))
        record.check_access("read")
        if what == "show3d":
            return record.action_f3d_show()
        if what == "form":
            return {
                "type": "ir.actions.act_window",
                "res_model": model,
                "res_id": record.id,
                "view_mode": "form",
                "views": [(False, "form")],
                "target": "current",
            }
        raise AccessError("Невідома дія огляду.")
