"""HTTP/JSON API пульта КГУ (SPEC §7, API-01…07): маршрути `jsonrpc`, `auth="user"`; логіка — у `td.chp.pult`."""

from odoo import http
from odoo.http import request


class TdChpController(http.Controller):
    def _pult(self):
        return request.env["td.chp.pult"]

    @http.route("/td_chp/state", type="jsonrpc", auth="user", methods=["POST"])
    def state(self, unit=None, etag=None):
        return self._pult().get_state(unit=unit, etag=etag)

    @http.route("/td_chp/trend", type="jsonrpc", auth="user", methods=["POST"])
    def trend(self, unit=None, range_h=24):
        return self._pult().get_trend(unit=unit, range_h=range_h)

    @http.route("/td_chp/journal", type="jsonrpc", auth="user", methods=["POST"])
    def journal(self, unit=None, limit=50, before=None):
        return self._pult().get_journal(unit=unit, limit=limit, before=before)

    @http.route("/td_chp/ack", type="jsonrpc", auth="user", methods=["POST"])
    def ack(self, unit=None, ids=None):
        return self._pult().ack(unit=unit, ids=ids)

    @http.route("/td_chp/cmd", type="jsonrpc", auth="user", methods=["POST"])
    def cmd(self, op=None, unit=None, kind=None, params=None, ref=None, token=None):
        return self._pult().command(op, unit=unit, kind=kind, params=params, ref=ref, token=token)

    @http.route("/td_chp/maintenance", type="jsonrpc", auth="user", methods=["POST"])
    def maintenance(self, unit=None, rule_id=None):
        """`rule_id` порожній — перелік (`get_maintenance`); інакше «ТО виконано» (`maintenance_done`)."""
        if rule_id is None:
            return self._pult().get_maintenance(unit=unit)
        return self._pult().maintenance_done(rule_id)

    @http.route("/td_chp/sim", type="jsonrpc", auth="user", methods=["POST"])
    def sim(self, op=None, code=None, params=None):
        return self._pult().sim(op, code=code, params=params)
