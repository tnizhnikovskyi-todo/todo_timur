"""M-20, A-04, CE-08: провайдери переглядача — `AbstractModel` без `_inherit` (duck typing, ARCHITECTURE §6.7).
Без `td_viewer3d` ці моделі просто не викликаються."""

from odoo import models

from ..tools import payload as payload_tools


class F3dViewerProviderEnergy(models.AbstractModel):
    _name = "td.viewer.provider.energy"
    _description = "3D: енергетика"
    _td_sequence = 100
    _td_sections = ("energy",)
    _td_group = "td_factory3d.group_td_user"

    def _td_viewer_collect(self, payload, ctx):
        payload_tools.build_energy(self.env, ctx or {}, payload)

    def _td_viewer_delta(self, patch, ctx):
        """R-18 п. 2: розділ `energy` будується цілком, коли зміни зачіпають енергетику чи МО."""
        if not payload_tools.wants_delta((ctx or {}).get("changes"), with_mrp=True):
            return
        tmp = {}
        payload_tools.build_energy(self.env, ctx or {}, tmp)
        if "energy" in tmp:
            patch["energy"] = tmp["energy"]
        payload_tools.fill_productions(self.env, ctx or {}, patch.get("productions"))

    def _td_viewer_bus_models(self):
        return ["td.signal", "td.energy", "mrp.production", "mrp.workorder"]


class F3dViewerProviderInfra(models.AbstractModel):
    _name = "td.viewer.provider.infra"
    _description = "3D: власна генерація й резерв"
    _td_sequence = 150
    _td_sections = ("infra",)
    _td_group = "td_factory3d.group_td_user"

    def _td_viewer_collect(self, payload, ctx):
        payload_tools.build_infra(self.env, ctx or {}, payload)

    def _td_viewer_delta(self, patch, ctx):
        """R-18 п. 3: глибоке злиття (A-22) — `patch['infra']` не присвоюється."""
        if not payload_tools.wants_delta((ctx or {}).get("changes"), with_mrp=False):
            return
        tmp = {}
        payload_tools.build_infra(self.env, ctx or {}, tmp)
        if "infra" in tmp:
            payload_tools.merge_into(patch.setdefault("infra", {}), tmp["infra"])

    def _td_viewer_bus_models(self):
        return ["td.signal", "td.energy"]
