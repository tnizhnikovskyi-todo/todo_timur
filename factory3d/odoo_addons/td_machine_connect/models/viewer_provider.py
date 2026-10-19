import logging

from odoo import models

from ..tools import payload as payload_tools

_logger = logging.getLogger(__name__)


class F3dViewerProviderMachines(models.AbstractModel):
    # Контракт провайдера — duck typing (ARCH §6.7): без `_inherit` (td_viewer3d ще не зібрано, DEC-8).
    _name = "td.viewer.provider.machines"
    _description = "3D: живі стани верстатів, OEE, портал, карти розкрою"
    _td_sequence = 75
    _td_sections = ()
    _td_group = "td_factory3d.group_td_user"

    def _td_viewer_collect(self, payload, ctx):
        """R-25 п. 1–6: доповнює `workcenters`, `equipment`, `locations`, `productions`, `sheet_chain` на місці."""
        payload_tools.apply_machines(payload, payload_tools.build_machines(self.env, ctx, payload))

    def _td_viewer_delta(self, patch, ctx):
        """R-25 п. 7: ті самі п. 1–5 лише для вузлів, що є в `patch`."""
        payload_tools.apply_machines(patch, payload_tools.build_machines(self.env, ctx, patch))

    def _td_viewer_bus_models(self):
        return ["mrp.workcenter", "stock.location", "maintenance.equipment", "mrp.production"]
