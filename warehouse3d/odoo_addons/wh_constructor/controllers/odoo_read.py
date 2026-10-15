from odoo import http
from odoo.http import request

from .main import BASE, JSON, _guard

# Чтение данных склада для адаптера приложения (W-11); логика и проверка прав — в модели wh.reader.


class WhConstructorRead(http.Controller):

    @http.route(BASE + "/api/read/warehouses", type=JSON, auth="user")
    @_guard
    def read_warehouses(self, **kw):
        return {"status": "ok", **request.env["wh.reader"].api_warehouses()}

    def _paged(self, method, warehouse_id, offset, limit):
        return {"status": "ok", **getattr(request.env["wh.reader"], method)(warehouse_id, offset, limit)}

    @http.route(BASE + "/api/read/locations", type=JSON, auth="user")
    @_guard
    def read_locations(self, warehouse_id=None, offset=0, limit=None, **kw):
        return self._paged("api_locations", warehouse_id, offset, limit)

    @http.route(BASE + "/api/read/quants", type=JSON, auth="user")
    @_guard
    def read_quants(self, warehouse_id=None, offset=0, limit=None, **kw):
        return self._paged("api_quants", warehouse_id, offset, limit)

    @http.route(BASE + "/api/read/storage_categories", type=JSON, auth="user")
    @_guard
    def read_storage_categories(self, warehouse_id=None, offset=0, limit=None, **kw):
        return self._paged("api_storage_categories", warehouse_id, offset, limit)

    @http.route(BASE + "/api/read/putaway_rules", type=JSON, auth="user")
    @_guard
    def read_putaway_rules(self, warehouse_id=None, offset=0, limit=None, **kw):
        return self._paged("api_putaway_rules", warehouse_id, offset, limit)

    @http.route(BASE + "/api/read/orderpoints", type=JSON, auth="user")
    @_guard
    def read_orderpoints(self, warehouse_id=None, offset=0, limit=None, **kw):
        return self._paged("api_orderpoints", warehouse_id, offset, limit)
