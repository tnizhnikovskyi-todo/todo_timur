"""API-21…API-24: варіанти, коментарі, блокування, версії (F12, F13, F14, N-03). Заглушки W0-B, наповнює слайс S6."""

from odoo import http

from .stub import not_implemented


class TdCollabController(http.Controller):
    # --- API-21 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/variants', type='jsonrpc', auth='user', methods=['POST'])
    def variants(self, **kw):
        return not_implemented('API-21')

    # --- API-22 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/comments', type='jsonrpc', auth='user', methods=['POST'])
    def comments(self, **kw):
        return not_implemented('API-22')

    # --- API-23 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/locks', type='jsonrpc', auth='user', methods=['POST'])
    def locks(self, **kw):
        return not_implemented('API-23')

    # --- API-24 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/version/view', type='jsonrpc', auth='user', methods=['POST'])
    def version_view(self, **kw):
        return not_implemented('API-24')

    # --- API-24 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/version/checkpoint', type='jsonrpc', auth='user', methods=['POST'])
    def version_checkpoint(self, **kw):
        return not_implemented('API-24')
