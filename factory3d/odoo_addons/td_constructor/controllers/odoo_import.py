"""API-16, API-20: стрічка локацій Odoo, розбір таблиць (F10, F11). Заглушки W0-B, наповнює слайс S4."""

from odoo import http

from .stub import not_implemented


class TdOdooImportController(http.Controller):
    # --- API-16 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/odoo/locations', type='jsonrpc', auth='user', methods=['POST'])
    def odoo_locations(self, **kw):
        return not_implemented('API-16')

    # --- API-20 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/parse/table', type='jsonrpc', auth='user', methods=['POST'])
    def parse_table(self, **kw):
        return not_implemented('API-20')
