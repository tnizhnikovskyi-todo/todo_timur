"""Тестові провайдери (SPEC §13.0). Реєструються лише при завантаженні модуля."""
from odoo import api, models

from odoo.addons.factory3d_viewer.tools.payload import deep_merge


class ZzTestProvider(models.AbstractModel):
    """Спосіб (а): `_inherit`. Перший у черзі (sequence 5), пише zones["Z-TEST"]."""
    _name = "f3d.viewer.provider.zz_test"
    _inherit = "f3d.viewer.provider"
    _description = "3D: тестовий провайдер zz_test"

    _f3d_sequence = 5
    _f3d_sections = ("zones",)

    @api.model
    def _f3d_viewer_collect(self, payload, ctx):
        deep_merge(payload.setdefault("zones", {}), {"Z-TEST": {"name": "Тестова зона", "locations": []}})


class ZzFailProvider(models.AbstractModel):
    """Кидає ValueError("boom"). Щоб не засмічувати ERROR-логом чужі прогони, падає лише з
    `context["zz_fail"]` або параметром `factory3d.test.zz_fail` (для ручного ТК-10)."""
    _name = "f3d.viewer.provider.zz_fail"
    _inherit = "f3d.viewer.provider"
    _description = "3D: тестовий провайдер zz_fail"

    _f3d_sequence = 6
    _f3d_sections = ("fire",)

    @api.model
    def _f3d_viewer_collect(self, payload, ctx):
        enabled = self.env.context.get("zz_fail") or self.env["ir.config_parameter"].sudo().get_param(
            "factory3d.test.zz_fail")
        if enabled:
            payload.setdefault("fire", {})["partial"] = True  # частковий запис, який має відкотитись
            raise ValueError("boom")


class ZzDuckProvider(models.AbstractModel):
    """Спосіб (б): за префіксом імені, без `_inherit`; без `_f3d_viewer_delta` і `_f3d_viewer_bus_models`."""
    _name = "f3d.viewer.provider.zz_duck"
    _description = "3D: тестовий провайдер zz_duck (duck-typing)"

    _f3d_sequence = 152
    _f3d_sections = ("infra", "zz_duck")
    _f3d_group = "factory3d_base.group_f3d_user"

    @api.model
    def _f3d_viewer_collect(self, payload, ctx):
        deep_merge(payload.setdefault("infra", {}), {"cards": {"ZZ-DUCK": {"rows": [["Тест", "так"]]}}})
        payload["zz_duck"] = {"ok": True}
