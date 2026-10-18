"""API-17, API-18: зайнятість кодів, журнал і відкат публікації (F01-07, F02-08, F02-11).

Правила як у API-01…10: JSON-RPC, auth user, відповідь `{ok: true, …}` або `{ok: false, code, message}` (HTTP 200);
читання — від імені користувача (record rules по компанії), відкат — лише менеджер (усередині — sudo після перевірки).
"""

from odoo import http
from odoo.exceptions import AccessError, UserError
from odoo.http import request

from ..services import publish
from .constructor import fail, find_site, is_manager

MAX_CODES = 5000


class TdPlanController(http.Controller):
    # --- API-17 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/codes/check', type='jsonrpc', auth='user', methods=['POST'])
    def codes_check(self, site_id=None, codes=None, **kw):
        """Зайнятість кодів/штрихкодів у Odoo для площадки: `{код: {state: free|own|match|busy, reason}}`."""
        env = request.env
        site = find_site(env, site_id)
        if not site:
            return fail('not_found', "Площадку не знайдено.")
        if not isinstance(codes, list) or not all(isinstance(c, str) for c in codes):
            return fail('validation', "codes має бути списком рядків.")
        if len(codes) > MAX_CODES:
            return fail('too_many', "Не більше %d кодів за виклик." % MAX_CODES)
        return {'ok': True, 'codes': publish.code_states(env, site.sudo(), sorted(set(codes)))}

    # --- API-18 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/publish/log', type='jsonrpc', auth='user', methods=['POST'])
    def publish_log(self, site_id=None, version_id=None, limit=None, **kw):
        """Журнал публікацій: версії з числом операцій за видами й ознакою «можна відкотити»; з `version_id` — ще й
        операції цієї версії."""
        env = request.env
        site = find_site(env, site_id)
        if not site:
            return fail('not_found', "Площадку не знайдено.")
        limit = limit if isinstance(limit, int) and not isinstance(limit, bool) and 0 < limit <= 100 else 20
        out = {'ok': True, 'versions': publish.publish_log(site, limit), 'can_rollback': is_manager(env)}
        if version_id is not None:
            version = env['td.layout.version'].search([('id', '=', version_id), ('site_id', '=', site.id)], limit=1)
            if not version:
                return fail('not_found', "Версію не знайдено.")
            out['ops'] = publish.op_rows(version.sudo())
        return out

    # --- API-18 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/publish/rollback', type='jsonrpc', auth='user', methods=['POST'])
    def publish_rollback(self, site_id=None, version_id=None, confirm=None, **kw):
        """Відкат публікації (лише записи Odoo; чернетка не змінюється): створене → в архів, значення назад."""
        env = request.env
        site = find_site(env, site_id)
        if not site:
            return fail('not_found', "Площадку не знайдено.")
        if confirm is not True:
            return fail('validation', "Підтвердіть відкат: confirm = true.")
        if not is_manager(env):
            return fail('rights', "Відкотити публікацію може лише менеджер конструктора.")
        version = env['td.layout.version'].search(
            [('id', '=', version_id if isinstance(version_id, int) else 0), ('site_id', '=', site.id)], limit=1
        )
        if not version:
            return fail('not_found', "Версію не знайдено.")
        try:
            result = publish.rollback_version(site, version)
        except publish.PublishError as exc:
            return fail(exc.code, str(exc), issues=exc.issues)
        except AccessError as exc:
            return fail('rights', str(exc))
        except UserError as exc:
            return fail('validation', str(exc))
        return {
            'ok': True,
            'version': {'id': version.id, 'n': version.n},
            'reverted': result['reverted'],
            'versions': publish.publish_log(site, 20),
        }
