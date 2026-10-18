"""API-12: категорії зберігання й стратегії списання (F03). Заглушки W0-B, наповнює слайс S2."""

from odoo import http

from .stub import not_implemented


class TdStorageController(http.Controller):
    # --- API-12 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/storage_categories', type='jsonrpc', auth='user', methods=['POST'])
    def storage_categories(self, **kw):
        return not_implemented('API-12')

    # --- API-12 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/removal_strategies', type='jsonrpc', auth='user', methods=['POST'])
    def removal_strategies(self, **kw):
        return not_implemented('API-12')
