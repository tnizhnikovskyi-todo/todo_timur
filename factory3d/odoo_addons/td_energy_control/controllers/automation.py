"""API-24 `GET /td/energy/automation/config`, API-25 `POST /td/energy/automation/state` (C-39; Bearer-токен збирача)."""

from odoo import fields, http
from odoo.http import request

from odoo.addons.td_telemetry.controllers.telemetry import NO_STORE, F3dTelemetryController, _error, _json

from ..tools import config_builder

STATE_BODY_MAX = 256 * 1024
ACTIONS_MAX = 100
EVENTS_MAX = 200
RATE_HEADERS = NO_STORE + [("Retry-After", "10")]


class TdEnergyAutomationController(http.Controller):
    _auth = F3dTelemetryController()  # спільна автентифікація колектора, розбір тіла й ґард методів td_telemetry

    # --- API-24 ---------------------------------------------------------------------------------------------------
    @http.route("/td/energy/automation/config", type="http", auth="public", csrf=False)
    def config(self, **kw):
        def run():
            collector, env = self._auth._authenticate()
            if not collector._rate_check():
                return _error(429, "rate_limited", "Забагато запитів за хвилину", RATE_HEADERS)
            state = env["td.energy.control.state"].get()
            cfg = config_builder.build(env)
            etag = config_builder.etag(cfg)
            vals = {"last_config_pull_at": fields.Datetime.now()}
            if state.config_etag != etag:
                vals["config_etag"] = etag
            state.write(vals)
            cfg["etag"] = etag
            headers = [
                ("Cache-Control", "private, max-age=0"),
                ("ETag", '"%s"' % etag),
                ("X-Config-Version", str(cfg["config_version"])),
            ]
            inm = request.httprequest.headers.get("If-None-Match", "")
            if inm and etag in [p.strip().removeprefix("W/").strip('"') for p in inm.split(",")]:
                return request.make_response(b"", headers=headers, status=304)
            return _json(cfg, 200, headers)

        return self._auth._guard(run, "GET")

    # --- API-25 ---------------------------------------------------------------------------------------------------
    @http.route("/td/energy/automation/state", type="http", auth="public", csrf=False)
    def state(self, **kw):
        def run():
            collector, env = self._auth._authenticate()
            body = self._auth._body(limit=STATE_BODY_MAX)
            self._auth._check_collector(body, collector)
            actions, events = body.get("actions", []), body.get("events", [])
            if (
                not isinstance(actions, list)
                or not isinstance(events, list)
                or len(actions) > ACTIONS_MAX
                or len(events) > EVENTS_MAX
                or not isinstance(body.get("scenarios", {}), dict)
                or not isinstance(body.get("engine", {}), dict)
            ):
                return _error(400, "bad_schema", "Недопустима структура звіту")
            if not collector._rate_check():
                return _error(429, "rate_limited", "Забагато запитів за хвилину", RATE_HEADERS)
            result = env["td.energy.control.state"]._td_report(body, collector)
            return _json(result)

        return self._auth._guard(run, "POST")
