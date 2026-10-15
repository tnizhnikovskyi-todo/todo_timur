from odoo import api, models

from ..tools import payload as payload_tools


class F3dViewerProvider(models.AbstractModel):
    """M-01: хук постачальника даних (C-02). Duck-typing (X-22): провайдер — будь-яка модель реєстру
    з іменем `f3d.viewer.provider.<key>`; цей клас дає умовчання для способу (а) `_inherit`."""
    _name = "f3d.viewer.provider"
    _description = "3D: постачальник даних переглядача"

    _f3d_sequence = 1000
    _f3d_sections = ()
    _f3d_group = payload_tools.DEFAULT_GROUP

    @api.model
    def _f3d_viewer_collect(self, payload, ctx):
        """Заповнює `payload` на місці; за замовчуванням нічого не робить."""

    @api.model
    def _f3d_viewer_delta(self, patch, ctx):
        """Заповнює `patch` для `ctx["changes"]`; за замовчуванням — дельта R-14 п. 5."""
        payload_tools.default_delta(self, patch, ctx)

    @api.model
    def _f3d_viewer_bus_models(self):
        return []

    @api.model
    def _f3d_providers(self):
        """Реєстр провайдерів за префіксом імені, у порядку виклику (R-01 п. 3)."""
        return payload_tools.get_providers(self.env)
