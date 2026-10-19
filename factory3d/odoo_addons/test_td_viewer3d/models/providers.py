"""Тестові провайдери (SPEC §13.0). Реєструються лише при завантаженні модуля."""
from odoo import api, models

from odoo.addons.td_viewer3d.tools.payload import deep_merge


class ZzTestProvider(models.AbstractModel):
    """Спосіб (а): `_inherit`. Перший у черзі (sequence 5), пише zones["Z-TEST"]."""
    _name = "td.viewer.provider.zz_test"
    _inherit = "td.viewer.provider"
    _description = "3D: тестовий провайдер zz_test"

    _td_sequence = 5
    _td_sections = ("zones",)

    @api.model
    def _td_viewer_collect(self, payload, ctx):
        deep_merge(payload.setdefault("zones", {}), {"Z-TEST": {"name": "Тестова зона", "locations": []}})


class ZzFailProvider(models.AbstractModel):
    """Кидає ValueError("boom"). Щоб не засмічувати ERROR-логом чужі прогони, падає лише з
    `context["zz_fail"]` або параметром `td.test.zz_fail` (для ручного ТК-10)."""
    _name = "td.viewer.provider.zz_fail"
    _inherit = "td.viewer.provider"
    _description = "3D: тестовий провайдер zz_fail"

    _td_sequence = 6
    _td_sections = ("fire",)

    @api.model
    def _td_viewer_collect(self, payload, ctx):
        enabled = self.env.context.get("zz_fail") or self.env["ir.config_parameter"].sudo().get_param(
            "td.test.zz_fail")
        if enabled:
            payload.setdefault("fire", {})["partial"] = True  # частковий запис, який має відкотитись
            raise ValueError("boom")


class ZzDuckProvider(models.AbstractModel):
    """Спосіб (б): за префіксом імені, без `_inherit`; без `_td_viewer_delta` і `_td_viewer_bus_models`."""
    _name = "td.viewer.provider.zz_duck"
    _description = "3D: тестовий провайдер zz_duck (duck-typing)"

    _td_sequence = 152
    _td_sections = ("infra", "zz_duck")
    _td_group = "td_factory3d.group_td_user"

    @api.model
    def _td_viewer_collect(self, payload, ctx):
        deep_merge(payload.setdefault("infra", {}), {"cards": {"ZZ-DUCK": {"rows": [["Тест", "так"]]}}})
        payload["zz_duck"] = {"ok": True}
