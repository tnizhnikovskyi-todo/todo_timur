"""`/site/wizard` (F16-04): стан майстра «З нуля» площадки (`td.site.wizard_state`).

Правила як у API-01…10 (і як `/site/addr`): JSON-RPC, auth user, відповідь `{ok: true, …}` або
`{ok: false, code, message}` (HTTP 200); права — менеджер або проєктувальник із правом на шар площадки (майстер
створює зони й ряди); запис без зміни лічильника чернетки (стан майстра — не частина розкладки). Json до 256 КБ,
вкладеність до 8 рівнів (R-22)."""

from psycopg2 import IntegrityError

from odoo import http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from ..services import schemas
from .constructor import error_from_exception, fail, find_site, is_manager


class TdWizardController(http.Controller):
    @http.route('/f3d/constructor/site/wizard', type='jsonrpc', auth='user', methods=['POST'])
    def site_wizard(self, site_id=None, state=None, **kw):
        env = request.env
        site = find_site(env, site_id)
        if not site:
            return fail('not_found', "Площадку не знайдено.")
        if not is_manager(env) and not any(env['td.layer']._td_can_edit_layer(layer) for layer in site.layer_ids):
            return fail('rights', "Майстер «З нуля» доступний менеджеру чи проєктувальнику із правом на шар площадки.")
        if state is None:
            return {'ok': True, 'wizard_state': site.wizard_state or {}}
        if not isinstance(state, dict):
            return fail('validation', "state: очікується об'єкт.")
        try:
            schemas.check_json_limits(state)
            with env.cr.savepoint():
                site.sudo().with_context(f3d_no_touch=True).write({'wizard_state': state})
                env.flush_all()
        except schemas.SchemaError as exc:
            return fail('validation', str(exc))
        except (AccessError, ValidationError, UserError, IntegrityError) as exc:
            env.invalidate_all()
            return fail(*error_from_exception(exc))
        return {'ok': True, 'wizard_state': state}
