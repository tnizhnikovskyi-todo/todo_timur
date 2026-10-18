"""M-17: провайдери переглядача `fire` (130) і `evacuation` (140); payload збирає основний модуль (R-20, R-21)."""
from odoo import api, models

from odoo.addons.factory3d_fire_safety.tools import payload as fire_payload


class F3dViewerProviderFire(models.AbstractModel):
    # Контракт провайдера — duck typing за префіксом імені (viewer R-01 п. 3), без `_inherit`.
    _name = "f3d.viewer.provider.fire"
    _description = "3D: пожежна сигналізація"
    _f3d_sequence = 130
    _f3d_sections = ("fire",)
    _f3d_group = "factory3d_base.group_f3d_user"
    BUS_MODELS = ["f3d.fire.panel", "f3d.fire.zone", "f3d.fire.system", "f3d.fire.event", "f3d.fire.device"]

    @api.model
    def _f3d_viewer_bus_models(self):
        return list(self.BUS_MODELS)

    @api.model
    def _f3d_viewer_collect(self, payload, ctx):
        payload["fire"] = fire_payload.build_fire(self.env, ctx)

    @api.model
    def _f3d_viewer_delta(self, patch, ctx):
        if set(ctx.get("changes") or ()) & set(self.BUS_MODELS):
            patch["fire"] = fire_payload.build_fire(self.env, ctx)


class F3dViewerProviderEvacuation(models.AbstractModel):
    _name = "f3d.viewer.provider.evacuation"
    _description = "3D: евакуація"
    _f3d_sequence = 140
    _f3d_sections = ("evacuation",)
    _f3d_group = "factory3d_base.group_f3d_user"
    BUS_MODELS = ["f3d.fire.drill", "f3d.fire.route", "f3d.fire.exit"]

    @api.model
    def _f3d_viewer_bus_models(self):
        return list(self.BUS_MODELS)

    @api.model
    def _f3d_viewer_collect(self, payload, ctx):
        payload["evacuation"] = fire_payload.build_evacuation(self.env, ctx)

    @api.model
    def _f3d_viewer_delta(self, patch, ctx):
        if set(ctx.get("changes") or ()) & set(self.BUS_MODELS):
            patch["evacuation"] = fire_payload.build_evacuation(self.env, ctx)
