from odoo import api, models

from ..tools import payload as payload_tools


class F3dViewerProvider(models.AbstractModel):
    """M-01: хук постачальника даних (C-02). Duck-typing (X-22): провайдер — будь-яка модель реєстру
    з іменем `td.viewer.provider.<key>`; цей клас дає умовчання для способу (а) `_inherit`."""

    _name = "td.viewer.provider"
    _description = "3D: постачальник даних переглядача"

    _td_sequence = 1000
    _td_sections = ()
    _td_group = payload_tools.DEFAULT_GROUP

    @api.model
    def _td_viewer_collect(self, payload, ctx):
        """Заповнює `payload` на місці; за замовчуванням нічого не робить."""

    @api.model
    def _td_viewer_delta(self, patch, ctx):
        """Заповнює `patch` для `ctx["changes"]`; за замовчуванням — дельта R-14 п. 5."""
        payload_tools.default_delta(self, patch, ctx)

    @api.model
    def _td_viewer_bus_models(self):
        return []

    @api.model
    def _td_providers(self):
        """Реєстр провайдерів за префіксом імені, у порядку виклику (R-01 п. 3)."""
        return payload_tools.get_providers(self.env)
