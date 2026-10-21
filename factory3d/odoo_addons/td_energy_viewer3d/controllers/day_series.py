"""R-59 (SPEC 8.4.5): `GET /f3d/viewer/energy/day` і `GET /f3d/kiosk/<token>/energy/day` — добові серії енергії для 3D
(лічильник ₴ у «Потоці зміни», розфарбування за часом, слайд «Енергія» на «стіні»). Один запит на добу; клієнт кешує.
Кіоск — через ту саму перевірку токена, що API-09 (`F3dKioskController._guard`); вартість у ньому лише за явним
`td.energy_viewer3d.kiosk_cost`."""

import datetime

from odoo import http
from odoo.http import request

from odoo.addons.td_energy.tools import dates
from odoo.addons.td_viewer3d.controllers.kiosk import F3dKioskController
from odoo.addons.td_viewer3d.controllers.viewer import DATE_RE, GROUP_USER, bad_request, forbidden, json_response

from ..tools import day_series


class F3dEnergyDayController(http.Controller):
    @staticmethod
    def serve_day(kw, kiosk=False):
        """Спільна частина: `day` (YYYY-MM-DD, за замовчуванням сьогодні за Києвом) → JSON серій."""
        env = request.env
        if not env["td.energy.interval"].has_access("read"):
            return forbidden("Немає доступу до енергетики")
        raw = kw.get("day")
        if raw:
            if not DATE_RE.match(raw):
                return bad_request("Невалідний параметр: day")
            try:
                day = datetime.date.fromisoformat(raw)
            except ValueError:
                return bad_request("Невалідний параметр: day")
        else:
            day = dates.local_day(dates.now_utc(env))
        data = day_series.build(env, day, day_series.cost_allowed(env, kiosk))
        return json_response(data, gzip_ok=True)

    @http.route("/f3d/viewer/energy/day", type="http", auth="user", methods=["GET"])
    def day(self, **kw):
        if not request.env.user.has_group(GROUP_USER):
            return forbidden()
        return self.serve_day(kw)

    @http.route(
        "/f3d/kiosk/<string:token>/energy/day",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        save_session=False,
    )
    def kiosk_day(self, token, **kw):
        return F3dKioskController()._guard(token) or self.serve_day(kw, kiosk=True)
