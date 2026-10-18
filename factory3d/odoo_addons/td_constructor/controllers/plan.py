"""API-17, API-18: зайнятість кодів, журнал і відкат публікації (F01-07, F02). Заглушки W0-B, наповнює слайс S2."""

from odoo import http

from .stub import not_implemented


class TdPlanController(http.Controller):
    # --- API-17 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/codes/check', type='jsonrpc', auth='user', methods=['POST'])
    def codes_check(self, **kw):
        return not_implemented('API-17')

    # --- API-18 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/publish/log', type='jsonrpc', auth='user', methods=['POST'])
    def publish_log(self, **kw):
        return not_implemented('API-18')

    # --- API-18 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/publish/rollback', type='jsonrpc', auth='user', methods=['POST'])
    def publish_rollback(self, **kw):
        return not_implemented('API-18')
