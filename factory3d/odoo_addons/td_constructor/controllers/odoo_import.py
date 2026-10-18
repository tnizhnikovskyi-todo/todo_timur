"""API-16, API-20 (+ маршрут правил розбору): структура складу з Odoo, розбір таблиць, правила й лоток (F10, F11, F02-09/12).

Правила як у API-01…10: JSON-RPC, auth user, відповідь `{ok: true, …}` або `{ok: false, code, message}` (HTTP 200). Читає група «Перегляд»
(`group_td_user`; читання локацій і залишків — від імені сервера, `services/odoo_sync.py`); базу порівняння й правила розбору пише менеджер
чи проєктувальник із правом на шар площадки (як `/site/addr`).

* API-16 `/odoo/locations` `{site_id, op, warehouse_id?, offset?, limit?}`: `feed` (за замовчуванням) → `{feed: {root, warehouse, locations,
  total, truncated, next}}`; `sync` → `{feed (без локацій), diff: {appeared, disappeared, renamed, moved}, baseline: created|existing}`;
  `baseline` — база порівняння стає нинішньою стрічкою.
* API-20 `/parse/table` `{site_id?, filename, content (base64), sheet?}` → `{format, encoding?, delimiter?, sheets?, sheet?, rows, truncated}`.
* `/odoo/rules` `{site_id, parse_rules}` — запис `site.parse_rules` (правила розбору кодів і лоток «Не розміщено», схема R-22)."""

from psycopg2 import IntegrityError

from odoo import http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from ..services import odoo_sync, tabular
from .constructor import error_from_exception, fail, find_site, is_manager

GROUP_VIEW = 'td_factory3d.group_td_user'
OPS = ('feed', 'sync', 'baseline')


class TdOdooImportController(http.Controller):
    def _site(self, env, site_id, write=False):
        """Площадка для читання (група «Перегляд») чи запису (менеджер або проєктувальник шару) або готова відповідь-помилка."""
        if not env.user.has_group(GROUP_VIEW):
            return None, fail('rights', "Структуру складу читає група «Перегляд» конструктора.")
        site = find_site(env, site_id)
        if not site:
            return None, fail('not_found', "Площадку не знайдено.")
        if write and not is_manager(env) and not any(env['td.layer']._f3d_can_edit_layer(layer) for layer in site.layer_ids):
            return None, fail('rights', "Змінює менеджер чи проєктувальник із правом на шар площадки.")
        return site, None

    # --- API-16 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/odoo/locations', type='jsonrpc', auth='user', methods=['POST'])
    def odoo_locations(self, site_id=None, op='feed', warehouse_id=None, offset=0, limit=None, **kw):
        env = request.env
        if op not in OPS:
            return fail('validation', "op: очікується %s." % ', '.join(OPS))
        try:
            site, error = self._site(env, site_id, write=(op == 'baseline'))
            if error:
                return error
            if op == 'feed':
                return {'ok': True, 'feed': odoo_sync.locations_feed(env, site, warehouse_id, offset, limit)}
            if op == 'sync':
                return dict(ok=True, **odoo_sync.sync(env, site, warehouse_id))
            odoo_sync.save_baseline(site, odoo_sync.full_feed(env, site, warehouse_id)['locations'])
            return {'ok': True}
        except (AccessError, UserError, ValidationError) as exc:
            return fail(*error_from_exception(exc))

    # --- API-20 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/parse/table', type='jsonrpc', auth='user', methods=['POST'])
    def parse_table(self, site_id=None, filename=None, content=None, sheet=0, **kw):
        env = request.env
        if not env.user.has_group(GROUP_VIEW):
            return fail('rights', "Таблиці розбирає група «Перегляд» конструктора.")
        try:
            data = tabular.decode_payload(content)
            return dict(ok=True, **tabular.parse_table(str(filename or ''), data, sheet))
        except (AccessError, UserError, ValidationError) as exc:
            return fail(*error_from_exception(exc))

    # --- правила розбору й лоток -------------------------------------------------------------------
    @http.route('/f3d/constructor/odoo/rules', type='jsonrpc', auth='user', methods=['POST'])
    def parse_rules(self, site_id=None, parse_rules=None, **kw):
        env = request.env
        try:
            site, error = self._site(env, site_id, write=True)
            if error:
                return error
            rules = odoo_sync.normalize_parse_rules(parse_rules)
            with env.cr.savepoint():
                site.sudo().write({'parse_rules': rules})
                site._f3d_touch(1)
                env.flush_all()
        except (AccessError, UserError, ValidationError, IntegrityError) as exc:
            env.invalidate_all()
            return fail(*error_from_exception(exc))
        site.invalidate_recordset(['draft_rev', 'draft_changes', 'has_changes', 'parse_rules'])
        return {'ok': True, 'rev': site.draft_rev, 'draft_changes': site.draft_changes, 'has_changes': site.has_changes}
