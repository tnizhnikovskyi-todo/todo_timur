"""API-11 `/library` (F08, F09-06/07): типи й пресети бібліотеки; `/site/addr` (F01): адресація площадки.

Правила як у API-01…10: JSON-RPC, auth user, відповідь `{ok: true, …}` або `{ok: false, code, message}` (HTTP 200);
права — від імені користувача (без sudo): читає «перегляд» (`group_td_user`), пише проєктувальник (технолог, комірник,
інженер) чи менеджер, видаляє менеджер. Каталог (типи без `is_custom`) змінює лише менеджер."""

from psycopg2 import IntegrityError

from odoo import http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from ..services import addr as addr_mod, state as st
from .constructor import ROLE_GROUPS, error_from_exception, fail, find_site, is_manager

TYPE_SAVE_FIELDS = {'code', 'name', 'description', 'group', 'template', 'shape', 'params', 'loc_kind', 'relevance'}
PRESET_SAVE_FIELDS = {'name', 'type_id', 'kind', 'data'}
TYPE_UPDATE_BLOCKED = {'code'}  # ключ типу стабільний: ним посилаються пресети й знімки
MODELS = {'type': 'td.slot.type', 'preset': 'td.slot.preset'}
DICTS = {'type': st.type_dict, 'preset': st.preset_dict}
RENUMBER_MODES = ('new', 'all')


def can_design(env):
    """Проєктувальник бібліотеки: менеджер чи будь-яка з ролей технолог/комірник/інженер."""
    groups = env.user.all_group_ids
    return any(env.ref(xmlid) in groups for xmlid in ROLE_GROUPS.values())


class TdLibraryController(http.Controller):
    # --- API-11 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/library', type='jsonrpc', auth='user', methods=['POST'])
    def library(self, op=None, kind=None, id=None, vals=None, **kw):
        env = request.env
        if op == 'list':
            return dict(ok=True, **st.library_state(env))
        if op not in ('save', 'delete'):
            return fail('validation', "op: очікується list, save або delete.")
        if kind not in MODELS:
            return fail('validation', "kind: очікується type або preset.")
        if op == 'save':
            return self._save(env, kind, id, vals)
        return self._delete(env, kind, id)

    def _save(self, env, kind, rec_id, vals):
        if not can_design(env):
            return fail('rights', "Бібліотеку пише проєктувальник: технолог, комірник, інженер чи менеджер.")
        if not isinstance(vals, dict):
            return fail('validation', "vals має бути об'єктом.")
        allowed = TYPE_SAVE_FIELDS if kind == 'type' else PRESET_SAVE_FIELDS
        unknown = set(vals) - allowed
        if unknown:
            return fail('validation', "Поля не можна змінювати через API: %s." % ", ".join(sorted(unknown)))
        Model = env[MODELS[kind]]
        vals = dict(vals)
        if kind == 'preset' and vals.get('type_id'):
            if not isinstance(vals['type_id'], int) or not env['td.slot.type'].browse(vals['type_id']).exists():
                return fail('validation', "Поле type_id: тип не знайдено.")
        try:
            with env.cr.savepoint():
                if rec_id in (None, False, 0):
                    if kind == 'type':
                        vals.update(is_custom=True, company_id=env.company.id)
                    else:
                        vals.setdefault('company_id', env.company.id)
                    record = Model.create(vals)
                else:
                    record = Model.search([('id', '=', rec_id if isinstance(rec_id, int) else 0)])  # + ir.rule
                    if not record:
                        return fail('not_found', "Запис бібліотеки не знайдено.")
                    if kind == 'type' and TYPE_UPDATE_BLOCKED & set(vals):
                        return fail('validation', "Ключ типу змінювати не можна.")
                    record.write(vals)
                env.flush_all()
        except (AccessError, ValidationError, UserError, IntegrityError) as exc:
            env.invalidate_all()
            code, message = error_from_exception(exc)
            if isinstance(exc, IntegrityError):
                message = "Порушено обмеження унікальності або обов'язкових полів."
            return fail(code, message)
        return {'ok': True, 'kind': kind, 'record': DICTS[kind](record)}

    def _delete(self, env, kind, rec_id):
        if not is_manager(env):
            return fail('rights', "Видаляти з бібліотеки може лише менеджер конструктора.")
        record = env[MODELS[kind]].search([('id', '=', rec_id if isinstance(rec_id, int) else 0)])
        if not record:
            return fail('not_found', "Запис бібліотеки не знайдено.")
        if kind == 'type':
            if not record.is_custom:
                return fail('validation', "Тип каталогу видалити не можна: лише власні типи бібліотеки.")
            used = env['td.slot'].sudo().with_context(active_test=False).search_count([('type_id', '=', record.id)])
            if used:
                return fail('validation', "Тип використовується в %d місцях: спершу змініть тип цих місць." % used)
        try:
            with env.cr.savepoint():
                record.unlink()
        except (AccessError, ValidationError, UserError, IntegrityError) as exc:
            env.invalidate_all()
            return fail(*error_from_exception(exc))
        return {'ok': True, 'kind': kind, 'id': rec_id}

    # --- адресація площадки (F01-03, F01-06): запис полів td.site проєктувальником -------------------
    @http.route('/f3d/constructor/site/addr', type='jsonrpc', auth='user', methods=['POST'])
    def site_addr(self, site_id=None, addr=None, loc_tree=None, depth_mode=None, renumber='new', **kw):
        env = request.env
        site = find_site(env, site_id)
        if not site:
            return fail('not_found', "Площадку не знайдено.")
        manager = is_manager(env)
        if not manager and not any(env['td.layer']._f3d_can_edit_layer(layer) for layer in site.layer_ids):
            return fail('rights', "Адресацію площадки змінює менеджер чи проєктувальник із правом на шар площадки.")
        if renumber not in RENUMBER_MODES:
            return fail('validation', "renumber: очікується new або all.")
        vals = {}
        if addr is not None:
            vals['addr'] = addr
        if depth_mode is not None:
            try:
                vals['depth_mode'] = addr_mod.normalize_depth_mode(depth_mode) or 'level'
            except addr_mod.AddrError as exc:
                return fail('validation', str(exc))
        if loc_tree is not None:
            if loc_tree not in addr_mod.LOC_TREES:
                return fail('validation', "loc_tree: очікується flat, row або section.")
            vals['loc_tree'] = loc_tree
        if not vals:
            return fail('validation', "Немає полів для запису: addr, depth_mode, loc_tree.")
        published = site._f3d_published_slot_uids()
        if not manager and published and (renumber == 'all' or vals.get('loc_tree', site.loc_tree) != site.loc_tree):
            return fail(
                'rights',
                "Перенумерувати все чи змінити ієрархію локацій опублікованої площадки може лише менеджер "
                "(зміняться імена й штрихкоди, потрібні нові етикетки).",
            )
        try:
            with env.cr.savepoint():
                result = site._f3d_apply_addr(vals, renumber)
                site._f3d_touch(1)
                env.flush_all()
        except (AccessError, ValidationError, UserError, IntegrityError) as exc:
            env.invalidate_all()
            return fail(*error_from_exception(exc))
        site.invalidate_recordset(['draft_rev', 'draft_changes', 'has_changes', 'addr', 'loc_tree', 'depth_mode'])
        return {
            'ok': True,
            'pinned': result['pinned'],
            'rev': site.draft_rev,
            'draft_changes': site.draft_changes,
            'has_changes': site.has_changes,
            'addr': site.addr or {},
            'loc_tree': site.loc_tree,
            'depth_mode': site.depth_mode,
        }
