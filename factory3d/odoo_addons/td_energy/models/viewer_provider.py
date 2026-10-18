"""M-20, A-04, CE-08: провайдери переглядача — `AbstractModel` без `_inherit` (duck typing, ARCHITECTURE §6.7).
Без `factory3d_viewer` ці моделі просто не викликаються."""

from odoo import models

from ..tools import payload as payload_tools


class F3dViewerProviderEnergy(models.AbstractModel):
    _name = "f3d.viewer.provider.energy"
    _description = "3D: енергетика"
    _f3d_sequence = 100
    _f3d_sections = ("energy",)
    _f3d_group = "factory3d_base.group_f3d_user"

    def _f3d_viewer_collect(self, payload, ctx):
        payload_tools.build_energy(self.env, ctx or {}, payload)

    def _f3d_viewer_delta(self, patch, ctx):
        """R-18 п. 2: розділ `energy` будується цілком, коли зміни зачіпають енергетику чи МО."""
        if not payload_tools.wants_delta((ctx or {}).get("changes"), with_mrp=True):
            return
        tmp = {}
        payload_tools.build_energy(self.env, ctx or {}, tmp)
        if "energy" in tmp:
            patch["energy"] = tmp["energy"]
        payload_tools.fill_productions(self.env, ctx or {}, patch.get("productions"))

    def _f3d_viewer_bus_models(self):
        return ["f3d.signal", "f3d.energy", "mrp.production", "mrp.workorder"]


class F3dViewerProviderInfra(models.AbstractModel):
    _name = "f3d.viewer.provider.infra"
    _description = "3D: власна генерація й резерв"
    _f3d_sequence = 150
    _f3d_sections = ("infra",)
    _f3d_group = "factory3d_base.group_f3d_user"

    def _f3d_viewer_collect(self, payload, ctx):
        payload_tools.build_infra(self.env, ctx or {}, payload)

    def _f3d_viewer_delta(self, patch, ctx):
        """R-18 п. 3: глибоке злиття (A-22) — `patch['infra']` не присвоюється."""
        if not payload_tools.wants_delta((ctx or {}).get("changes"), with_mrp=False):
            return
        tmp = {}
        payload_tools.build_infra(self.env, ctx or {}, tmp)
        if "infra" in tmp:
            payload_tools.merge_into(patch.setdefault("infra", {}), tmp["infra"])

    def _f3d_viewer_bus_models(self):
        return ["f3d.signal", "f3d.energy"]
