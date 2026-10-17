"""GLB варіанта обладнання для кіоска: `/f3d/kiosk/<token>/layout/model/<variant_id>` (токен, без сесії).

Звичайний переглядач бере GLB з API-10 конструктора (`auth="user"`); кіоск працює без сесії, тож віддаємо той самий файл
за токеном кіоска від імені `user_kiosk` (права читання варіанта перевіряє API-10).
"""
from odoo import http

from odoo.addons.factory3d_constructor.controllers.model import F3dModelController
from odoo.addons.factory3d_viewer.controllers.kiosk import F3dKioskController


class F3dLayoutKioskController(http.Controller):
    @http.route(
        "/f3d/kiosk/<string:token>/layout/model/<int:variant_id>", type="http", auth="public", methods=["GET"],
        csrf=False, save_session=False)
    def kiosk_model(self, token, variant_id, **kw):
        denied = F3dKioskController()._guard(token)
        return denied or F3dModelController().download(variant_id, "glb")
