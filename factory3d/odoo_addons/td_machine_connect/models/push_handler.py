import logging

from odoo import models

_logger = logging.getLogger(__name__)

# Обов'язкові поля payload за видом події (SPEC §7.1: EV-01…EV-03).
EV_OPCUA_REQUIRED = ("kind", "source", "machine", "time", "category", "text")
EV_KINDS = {
    "mc_opcua": {"event": (), "alarm": ()},
    "mc_woodstore": {"status": ("status",), "stacks": ("items",), "jobs": ("items",), "events": ("items",)},
    "mc_cutopt": {"job": ("job",), "plan": ("plan",), "mpr": ("part", "text")},
}
# (маршрут, kind) -> (модель власника, метод); власники реалізують методи в W2/W3 (EV-01), W5 (EV-02), W6 (EV-03).
ROUTES = {
    ("mc_woodstore", "status"): ("td.gantry.job", "_f3d_apply_status"),
    ("mc_woodstore", "stacks"): ("td.gantry.stack", "_f3d_apply_ws"),
    ("mc_woodstore", "jobs"): ("td.gantry.job", "_f3d_apply_ws"),
    ("mc_woodstore", "events"): ("td.gantry.job", "_f3d_apply_events"),
    ("mc_cutopt", "job"): ("td.cut.map", "_f3d_apply_job"),
    ("mc_cutopt", "plan"): ("td.cut.map", "_f3d_apply_plan"),
    ("mc_cutopt", "mpr"): ("td.cut.map", "_f3d_apply_mpr"),
}


class F3dPushHandlerMachineConnect(models.AbstractModel):
    _name = "td.push.handler.machine_connect"
    _inherit = "td.push.handler"
    _description = "Верстати: обробник подій колектора"
    _f3d_push_routes = ("mc_opcua", "mc_woodstore", "mc_cutopt")

    def _f3d_handle_push(self, route, event):
        payload = event["payload"]
        kinds = EV_KINDS.get(route)
        if kinds is None:
            return None
        kind = payload.get("kind") if isinstance(payload, dict) else None
        if kind not in kinds:
            raise ValueError("%s: kind" % route)
        required = EV_OPCUA_REQUIRED if route == "mc_opcua" else ("kind", "source", *kinds[kind])
        for key in required:
            if key not in payload or payload[key] is None:
                raise ValueError("%s: %s" % (route, key))
        # id події колектора читають власники (W2 `_f3d_apply_event`: ext_event_id)
        ctx = {"f3d_push_event_id": event.get("event_id")}
        if route == "mc_opcua":
            return self.env["td.machine"].sudo().with_context(**ctx)._f3d_apply_event(payload)
        model, method = ROUTES[(route, kind)]
        owner = self.env[model].sudo().with_context(**ctx)
        func = getattr(owner, method, None)
        if func is None:
            raise ValueError("%s: обробник %s.%s ще не реалізовано" % (route, model, method))
        if route == "mc_woodstore" and kind == "status":
            return func(payload["status"], event.get("ts"))
        if route == "mc_woodstore":
            return func(payload["items"], event.get("ts")) if kind != "events" else func(payload["items"])
        return self._f3d_route_cutopt(owner, kind, payload, event)

    def _f3d_route_cutopt(self, owner, kind, payload, event):
        """EV-03: найти карту за `map` (номер) і передати частину payload."""
        job_id = payload.get("job_id") or (payload.get("job") or {}).get("job_id")
        cut_map = owner._f3d_find_for_event(payload.get("map"), job_id)
        if not cut_map:
            raise ValueError("mc_cutopt: map %s / job %s" % (payload.get("map"), job_id))
        if kind == "job":
            return cut_map._f3d_apply_job(payload["job"])
        if kind == "plan":
            return cut_map._f3d_apply_plan(payload["plan"])
        return cut_map._f3d_apply_mpr(payload["part"], payload["text"])
