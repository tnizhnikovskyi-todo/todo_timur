"""Провайдер переглядача `layout` (180): опублікована розкладка конструктора (PHASE2_VIEWER, bridge R-01)."""
from odoo import api, models

from ..tools import layout as layout_tools


class F3dViewerProviderLayout(models.AbstractModel):
    # Контракт провайдера — duck typing за префіксом імені (viewer R-01 п. 3), без `_inherit`.
    _name = "td.viewer.provider.layout"
    _description = "3D: розкладка конструктора"
    _f3d_sequence = 180
    _f3d_sections = ("layout",)
    _f3d_group = "td_factory3d.group_td_user"
    BUS_MODELS = ["td.layout.version", "td.site"]

    @api.model
    def _f3d_viewer_bus_models(self):
        return list(self.BUS_MODELS)

    @api.model
    def _f3d_viewer_collect(self, payload, ctx):
        layout = layout_tools.build_layout(self.env)
        if layout is not None:
            payload["layout"] = layout

    @api.model
    def _f3d_viewer_delta(self, patch, ctx):
        if "td.layout.version" in (ctx.get("changes") or {}):
            layout = layout_tools.build_layout(self.env)
            # `None` — клієнт скидає розкладку до бази (версію прибрано або немає права читати)
            patch["layout"] = layout
