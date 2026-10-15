import logging

from odoo import models

_logger = logging.getLogger(__name__)

# Обов'язкові поля payload за видом події (SPEC §7.1: EV-01…EV-03).
EV_OPCUA_REQUIRED = ("kind", "source", "machine", "time", "category", "text")
EV_KINDS = {
    "mc_opcua": {"event": (), "alarm": ()},
    "mc_woodstore": {"status": ("status",), "stacks": ("items",), "jobs": ("items",), "events": ("items",)},
    "mc_cutopt": {"job": ("map", "job"), "plan": ("map", "plan"), "mpr": ("map", "part", "text")},
}
# (маршрут, kind) -> (модель власника, метод); власники реалізують методи в W2/W3 (EV-01), W5 (EV-02), W6 (EV-03).
ROUTES = {
    ("mc_woodstore", "status"): ("f3d.gantry.job", "_f3d_apply_status"),
    ("mc_woodstore", "stacks"): ("f3d.gantry.stack", "_f3d_apply_ws"),
    ("mc_woodstore", "jobs"): ("f3d.gantry.job", "_f3d_apply_ws"),
    ("mc_woodstore", "events"): ("f3d.gantry.job", "_f3d_apply_events"),
    ("mc_cutopt", "job"): ("f3d.cut.map", "_f3d_apply_job"),
    ("mc_cutopt", "plan"): ("f3d.cut.map", "_f3d_apply_plan"),
    ("mc_cutopt", "mpr"): ("f3d.cut.map", "_f3d_apply_mpr"),
}


class F3dPushHandlerMachineConnect(models.AbstractModel):
    _name = "f3d.push.handler.machine_connect"
    _inherit = "f3d.push.handler"
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
        if route == "mc_opcua":
            return self.env["f3d.machine"].sudo()._f3d_apply_event(payload)
        model, method = ROUTES[(route, kind)]
        owner = self.env[model].sudo()
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
        cut_map = owner.search([("name", "=", payload["map"])], limit=1)
        if not cut_map:
            raise ValueError("mc_cutopt: map %s" % payload["map"])
        if kind == "job":
            return cut_map._f3d_apply_job(payload["job"])
        if kind == "plan":
            return cut_map._f3d_apply_plan(payload["plan"])
        return cut_map._f3d_apply_mpr(payload["part"], payload["text"])
