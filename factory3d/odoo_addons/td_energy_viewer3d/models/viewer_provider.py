"""M-41: провайдер переглядача `energy_layer` — шар «Енергетика в 3D» (SPEC 8.4.2, R-57).

`AbstractModel` без `_inherit` моделей переглядача (duck typing, ARCHITECTURE §6.7): без `td_viewer3d` ця модель
просто не викликається. Додає лише ключ `energy.layer` — `meta.schema` не змінюється, клієнт без моста його ігнорує.
"""

from odoo import models

from ..tools import layer as layer_tools


class F3dViewerProviderEnergyLayer(models.AbstractModel):
    _name = "td.viewer.provider.energy_layer"
    _description = "3D: шар «Енергетика в 3D»"
    _f3d_sequence = 101  # після td.viewer.provider.energy (100): розділ `energy` уже створено
    _f3d_sections = ("energy",)
    _f3d_group = "td_factory3d.group_td_user"

    def _f3d_viewer_collect(self, payload, ctx):
        from odoo.addons.td_viewer3d.tools.payload import deep_merge  # noqa: PLC0415

        deep_merge(payload.setdefault("energy", {}), {"layer": layer_tools.build(self.env, ctx or {})})

    def _f3d_viewer_delta(self, patch, ctx):
        """Зміни `td.energy` чи енергетичних сигналів → шар замінюється цілком (списки не склеюються)."""
        from odoo.addons.td_energy.tools.payload import wants_delta  # noqa: PLC0415
        from odoo.addons.td_viewer3d.tools.payload import deep_merge  # noqa: PLC0415

        if not wants_delta((ctx or {}).get("changes"), with_mrp=False):
            return
        deep_merge(patch.setdefault("energy", {}), {"layer": layer_tools.build(self.env, ctx or {})})

    def _f3d_viewer_bus_models(self):
        return ["td.signal", "td.energy"]
