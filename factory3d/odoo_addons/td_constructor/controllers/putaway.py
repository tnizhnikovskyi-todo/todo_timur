"""API-15: куди піде товар і чи вміститься (F04). Заглушки W0-B, наповнює слайс S2."""

from odoo import http

from .stub import not_implemented


class TdPutawayController(http.Controller):
    # --- API-15 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/putaway/where', type='jsonrpc', auth='user', methods=['POST'])
    def putaway_where(self, **kw):
        return not_implemented('API-15')

    # --- API-15 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/putaway/fit', type='jsonrpc', auth='user', methods=['POST'])
    def putaway_fit(self, **kw):
        return not_implemented('API-15')
