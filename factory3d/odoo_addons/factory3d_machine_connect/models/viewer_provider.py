import logging

from odoo import models

_logger = logging.getLogger(__name__)


class F3dViewerProviderMachines(models.AbstractModel):
    # Контракт провайдера — duck typing (ARCH §6.7): без `_inherit` (factory3d_viewer ще не зібрано, DEC-8).
    _name = "f3d.viewer.provider.machines"
    _description = "3D: живі стани верстатів, OEE, портал, карти розкрою"
    _f3d_sequence = 75
    _f3d_sections = ()
    _f3d_group = "factory3d_base.group_f3d_user"

    def _f3d_viewer_collect(self, payload, ctx):
        """R-25 (W8). Каркас: payload не змінює."""
        return payload

    def _f3d_viewer_delta(self, patch, ctx):
        """R-25 п. 7 (W8). Каркас: patch не змінює."""
        return patch

    def _f3d_viewer_bus_models(self):
        return ["mrp.workcenter", "stock.location", "maintenance.equipment", "mrp.production"]
