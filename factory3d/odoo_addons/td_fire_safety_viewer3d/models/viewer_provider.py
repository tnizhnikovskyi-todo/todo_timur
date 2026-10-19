"""M-17: провайдери переглядача `fire` (130) і `evacuation` (140); payload збирає основний модуль (R-20, R-21)."""

from odoo import api, models

from odoo.addons.td_fire_safety.tools import payload as fire_payload


class F3dViewerProviderFire(models.AbstractModel):
    # Контракт провайдера — duck typing за префіксом імені (viewer R-01 п. 3), без `_inherit`.
    _name = "td.viewer.provider.fire"
    _description = "3D: пожежна сигналізація"
    _td_sequence = 130
    _td_sections = ("fire",)
    _td_group = "td_factory3d.group_td_user"
    BUS_MODELS = ["td.fire.panel", "td.fire.zone", "td.fire.system", "td.fire.event", "td.fire.device"]

    @api.model
    def _td_viewer_bus_models(self):
        return list(self.BUS_MODELS)

    @api.model
    def _td_viewer_collect(self, payload, ctx):
        payload["fire"] = fire_payload.build_fire(self.env, ctx)

    @api.model
    def _td_viewer_delta(self, patch, ctx):
        if set(ctx.get("changes") or ()) & set(self.BUS_MODELS):
            patch["fire"] = fire_payload.build_fire(self.env, ctx)


class F3dViewerProviderEvacuation(models.AbstractModel):
    _name = "td.viewer.provider.evacuation"
    _description = "3D: евакуація"
    _td_sequence = 140
    _td_sections = ("evacuation",)
    _td_group = "td_factory3d.group_td_user"
    BUS_MODELS = ["td.fire.drill", "td.fire.route", "td.fire.exit"]

    @api.model
    def _td_viewer_bus_models(self):
        return list(self.BUS_MODELS)

    @api.model
    def _td_viewer_collect(self, payload, ctx):
        payload["evacuation"] = fire_payload.build_evacuation(self.env, ctx)

    @api.model
    def _td_viewer_delta(self, patch, ctx):
        if set(ctx.get("changes") or ()) & set(self.BUS_MODELS):
            patch["evacuation"] = fire_payload.build_evacuation(self.env, ctx)
