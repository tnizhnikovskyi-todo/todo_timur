"""M-11: провайдери 3D-переглядача `lighting` і `ventilation` (FR-20, A-06, R-26, R-27).

Контракт провайдера — duck typing (ARCHITECTURE §6.7): без `_inherit` моделей `td_viewer3d`, ім'я з префіксом
`td.viewer.provider.`; без `td_viewer3d` моделі не викликаються."""

from odoo import models

from ..tools import payload as payload_tools

BUS_MODELS = ["td.signal", "td.bms"]
LIGHTING_PREFIXES = ("lighting/", "energy/consumers/LP-")
VENTILATION_PREFIXES = (
    "ventilation/",
    "equipment/BOILER/",
    "infra/chp/",
    "infra/totals/chp_kw",
    "fire/totals/system_state",
    "infra/ats/src1_ok",
)


def _touched(ctx, prefixes):
    changes = ctx.get("changes") or {}
    if changes.get("td.bms"):
        return True
    return any(str(code).startswith(prefixes) for code in changes.get("td.signal") or ())


class F3dViewerProviderLighting(models.AbstractModel):
    _name = "td.viewer.provider.lighting"
    _description = "3D: освітлення"
    _f3d_sequence = 110
    _f3d_sections = ("lighting",)
    _f3d_group = "td_factory3d.group_td_user"

    def _f3d_viewer_collect(self, payload, ctx):
        static = (ctx.get("static") or {}).get("lighting") or {}
        payload["lighting"] = payload_tools.build_lighting(self.env, ctx, payload.get("lighting") or static)

    def _f3d_viewer_delta(self, patch, ctx):
        if _touched(ctx, LIGHTING_PREFIXES):
            tmp = {}
            self._f3d_viewer_collect(tmp, ctx)
            patch["lighting"] = tmp["lighting"]

    def _f3d_viewer_bus_models(self):
        return list(BUS_MODELS)


class F3dViewerProviderVentilation(models.AbstractModel):
    _name = "td.viewer.provider.ventilation"
    _description = "3D: вентиляція й опалення"
    _f3d_sequence = 120
    _f3d_sections = ("ventilation",)
    _f3d_group = "td_factory3d.group_td_user"

    def _f3d_viewer_collect(self, payload, ctx):
        static = (ctx.get("static") or {}).get("ventilation") or {}
        payload["ventilation"] = payload_tools.build_ventilation(self.env, ctx, payload.get("ventilation") or static)

    def _f3d_viewer_delta(self, patch, ctx):
        if _touched(ctx, VENTILATION_PREFIXES):
            tmp = {}
            self._f3d_viewer_collect(tmp, ctx)
            patch["ventilation"] = tmp["ventilation"]

    def _f3d_viewer_bus_models(self):
        return list(BUS_MODELS)
