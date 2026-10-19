"""API-13, API-14: залишки по кодах і пошук «де лежить» (F06, F07).

Правила як у API-01…10: JSON-RPC, auth user, відповідь `{ok: true, …}` або `{ok: false, code, message}` (HTTP 200);
читає група «Перегляд» (площадка перевіряється record rules). Розрахунок — `services/metrics.py`."""

from odoo import http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from ..services import metrics
from .constructor import error_from_exception, fail, find_site

MAX_CODES = 5000
MAX_QUERY = 200
FIND_MODES = ('any', 'product', 'lot', 'package')
GROUP_VIEW = 'td_factory3d.group_td_user'


class TdStockController(http.Controller):
    def _site(self, env, site_id):
        """Площадка для читання або готова відповідь-помилка."""
        if not env.user.has_group(GROUP_VIEW):
            return None, fail('rights', "Залишки читає група «Перегляд» конструктора.")
        site = find_site(env, site_id)
        if not site:
            return None, fail('not_found', "Площадку не знайдено.")
        return site, None

    # --- API-13 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/stock/state', type='jsonrpc', auth='user', methods=['POST'])
    def stock_state(self, site_id=None, codes=None, days=None, detail=False, offset=0, limit=None, **kw):
        env = request.env
        try:
            site, error = self._site(env, site_id)
            if error:
                return error
            if codes is not None and (
                not isinstance(codes, list) or len(codes) > MAX_CODES or not all(isinstance(c, str) for c in codes)
            ):
                return fail('validation', "codes: список рядків (до %s)." % MAX_CODES)
            try:
                days = int(days) if days else None
                offset = max(0, int(offset or 0))
                limit = min(metrics.LOCATION_BATCH, max(1, int(limit))) if limit else metrics.LOCATION_BATCH
            except (TypeError, ValueError):
                return fail('validation', "days, offset і limit мають бути числами.")
            if days is not None and not 1 <= days <= 3650:
                return fail('validation', "days: від 1 до 3650.")
            # подробиці (рядки, рух, правила) — лише для невеликого списку кодів (картка місця)
            detail = bool(detail) and codes is not None and len(codes) <= 20
            return dict(ok=True, **metrics.stock_state(env, site, codes, days, detail, offset, limit))
        except (AccessError, UserError, ValidationError) as exc:
            return fail(*error_from_exception(exc))

    # --- API-14 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/stock/find', type='jsonrpc', auth='user', methods=['POST'])
    def stock_find(self, site_id=None, q=None, mode='any', **kw):
        env = request.env
        try:
            site, error = self._site(env, site_id)
            if error:
                return error
            if not isinstance(q, str) or not q.strip():
                return fail('validation', "q: порожній запит.")
            if len(q) > MAX_QUERY or mode not in FIND_MODES:
                return fail('validation', "q: до %s символів; mode — %s." % (MAX_QUERY, ', '.join(FIND_MODES)))
            return dict(ok=True, **metrics.stock_find(env, site, q, mode))
        except (AccessError, UserError, ValidationError) as exc:
            return fail(*error_from_exception(exc))
