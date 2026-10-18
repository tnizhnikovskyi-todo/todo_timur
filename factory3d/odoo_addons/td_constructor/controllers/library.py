"""API-11: бібліотека типів і пресетів (F08, F09-06/07). Заглушки W0-B, наповнює слайс S1."""

from odoo import http

from .stub import not_implemented


class TdLibraryController(http.Controller):
    # --- API-11 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/library', type='jsonrpc', auth='user', methods=['POST'])
    def library(self, **kw):
        return not_implemented('API-11')
