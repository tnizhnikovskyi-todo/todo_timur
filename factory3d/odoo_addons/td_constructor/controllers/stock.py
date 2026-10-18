"""API-13, API-14: залишки по кодах і пошук (F06, F07). Заглушки W0-B, наповнює слайс S3."""

from odoo import http

from .stub import not_implemented


class TdStockController(http.Controller):
    # --- API-13 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/stock/state', type='jsonrpc', auth='user', methods=['POST'])
    def stock_state(self, **kw):
        return not_implemented('API-13')

    # --- API-14 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/stock/find', type='jsonrpc', auth='user', methods=['POST'])
    def stock_find(self, **kw):
        return not_implemented('API-14')
