"""API-01…API-08 (JSON-RPC, auth user). Ответ — `{ok: true, …}` або `{ok: false, code, message, …}` (HTTP 200).

Права — від імені користувача (без sudo), крім API-07 (публікація: sudo лише всередині `services.publish`
після перевірок).
"""

import logging
import re

from psycopg2 import IntegrityError

from odoo import Command, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from ..services import publish, snapshot, state as st
from ..services.checks import summarize

_logger = logging.getLogger(__name__)

MAX_OPS = 500
MAX_BODY_BYTES = 1024 * 1024
MANAGER = 'factory3d_constructor.group_f3d_constructor_manager'
ROLE_GROUPS = {
    'technologist': 'factory3d_constructor.group_f3d_constructor_technologist',
    'storekeeper': 'factory3d_constructor.group_f3d_constructor_storekeeper',
    'engineer': 'factory3d_constructor.group_f3d_constructor_engineer',
    'manager': MANAGER,
}
# Дозволені поля для API-04 (все інше — validation); посилання на нові записи — "@<tmp>"
SAVE_FIELDS = {
    'f3d.layer': {
        'uid',
        'name',
        'kind',
        'sequence',
        'elevation_m',
        'grid_step_m',
        'aisle_width_m',
        'max_floor_load_kn_m2',
        'bounds',
        'color',
        'opacity',
        'style',
        'visible',
        'aisles',
        'fire_paths',
        'utilities',
        'underlay_params',
        'underlay_attachment_id',
        'active',
        'allowed_slot_types',
        'edit_group_ids',
    },
    'f3d.slot': {
        'uid',
        'layer_id',
        'template',
        'code_prefix',
        'x_m',
        'y_m',
        'rotation',
        'params',
        'overrides',
        'parent_location_id',
        'note',
        'active',
    },
    'f3d.placement': {
        'uid',
        'layer_id',
        'variant_id',
        'slot_id',
        'cell_code',
        'code',
        'name',
        'x_m',
        'y_m',
        'rotation',
        'note',
        'active',
    },
    'f3d.check.config': {'check_key', 'enabled', 'mode', 'params'},
}
REF_FIELDS = {'layer_id', 'slot_id', 'variant_id'}
DICT_FUNCS = {'f3d.layer': st.layer_dict, 'f3d.slot': st.slot_dict, 'f3d.placement': st.placement_dict}


def fail(code, message, **extra):
    return dict(ok=False, code=code, message=message, **extra)


def params(env):
    get = env['ir.config_parameter'].sudo().get_param

    def num(key, default, cast=float):
        try:
            return cast(get('factory3d.constructor.' + key, default))
        except (TypeError, ValueError):
            return cast(default)

    return {
        'autosave_ms': num('autosave_ms', 1500, int),
        'max_model_mb': num('max_model_mb', 20),
        'max_triangles': num('max_triangles', 50000, int),
        'eps_mm': num('eps_mm', 1),
        'reach_default_m': num('reach_default_m', 15),
        'publish_enabled': get('factory3d.constructor.publish_enabled') == 'True',
    }


def find_site(env, site_id):
    """Площадка за id з урахуванням record rules; None — якщо немає або недоступна (`not_found`)."""
    try:
        site_id = int(site_id)
    except (TypeError, ValueError):
        return None
    return env['f3d.site'].search([('id', '=', site_id)], limit=1) or None


def is_manager(env):
    return env.user.has_group(MANAGER)


def error_from_exception(exc):
    if isinstance(exc, AccessError):
        return 'rights', str(exc)
    if isinstance(exc, (ValidationError, UserError)):
        return 'validation', str(exc)
    return 'validation', str(exc)


class F3dConstructorController(http.Controller):
    # --- API-01 -------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/sites', type='jsonrpc', auth='user', methods=['POST'])
    def sites(self, **kw):
        env = request.env
        manager = is_manager(env)
        result = []
        for site in env['f3d.site'].search([]):
            version = site.active_version_id
            can_edit = manager or any(env['f3d.layer']._f3d_can_edit_layer(layer) for layer in site.layer_ids)
            result.append(
                {
                    'id': site.id,
                    'name': site.name,
                    'code': site.code,
                    'company_id': site.company_id.id,
                    'seed': bool(site.seed_key),
                    'active_version': {'id': version.id, 'n': version.n} if version else None,
                    'draft_changes': site.draft_changes,
                    'has_changes': site.has_changes,
                    'can_edit': bool(can_edit),
                }
            )
        return {'ok': True, 'sites': result}

    # --- API-02 -------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/site/create', type='jsonrpc', auth='user', methods=['POST'])
    def site_create(self, name=None, code=None, building=None, **kw):
        env = request.env
        if not is_manager(env):
            return fail('rights', "Створювати площадки може лише менеджер конструктора.")
        name = (name or '').strip() if isinstance(name, str) else ''
        code = (code or '').strip() if isinstance(code, str) else ''
        if not name or len(name) > 128:
            return fail('validation', "Вкажіть назву площадки (до 128 символів).")
        if not re.match(r'^[A-Z0-9]{1,16}$', code):
            return fail('validation', "Код площадки: до 16 великих латинських літер і цифр.")
        vals = {'name': name, 'code': code}
        if building:
            try:
                vals.update(
                    building_length_m=float(building['l']),
                    building_width_m=float(building['w']),
                    building_height_m=float(building['h']),
                )
            except (KeyError, TypeError, ValueError):
                return fail('validation', "Габарити будівлі: числа l, w, h.")
        if (
            env['f3d.site']
            .with_context(active_test=False)
            .search_count([('code', '=', code), ('company_id', '=', env.company.id)])
        ):
            return fail('validation', "Код площадки має бути унікальним у компанії.")
        try:
            with env.cr.savepoint():
                site = env['f3d.site'].with_context(f3d_blank=True).create(vals)
        except (ValidationError, UserError, IntegrityError) as exc:
            env.invalidate_all()
            return fail(*error_from_exception(exc))
        return {'ok': True, 'site_id': site.id}

    # --- API-03 -------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/load', type='jsonrpc', auth='user', methods=['POST'])
    def load(self, site_id=None, **kw):
        env = request.env
        site = find_site(env, site_id)
        if not site:
            return fail('not_found', "Площадку не знайдено.")
        Layer = env['f3d.layer']
        layers = site.layer_ids.filtered('active')
        xmlids = layers.sudo().edit_group_ids.get_external_id()
        slots = env['f3d.slot'].search([('site_id', '=', site.id), ('layer_id', 'in', layers.ids)])
        placements = env['f3d.placement'].search([('site_id', '=', site.id), ('layer_id', 'in', layers.ids)])
        variants = env['f3d.equipment.variant'].search([('passport_id.active', '=', True)])
        catalog = {}
        for variant in variants:
            passport = variant.passport_id
            entry = catalog.setdefault(
                passport.id,
                {
                    'passport_id': passport.id,
                    'name': passport.name,
                    'role': passport.role,
                    'manufacturer': passport.manufacturer,
                    'model': passport.model,
                    'category': passport.f3d_category,
                    'variants': [],
                },
            )
            entry['variants'].append(st.variant_dict(variant))
        user_groups = env.user.all_group_ids
        roles = [role for role, xmlid in ROLE_GROUPS.items() if env.ref(xmlid) in user_groups]
        manager = 'manager' in roles
        versions = site.version_ids.sorted('n', reverse=True)[:50]
        version = site.active_version_id
        base = site.draft_base_version_id
        parent = site.default_parent_location_id
        data = {
            'site': {
                'id': site.id,
                'name': site.name,
                'code': site.code,
                'building': {
                    'length': site.building_length_m,
                    'width': site.building_width_m,
                    'height': site.building_height_m,
                },
                'column_grid': {'step_x': site.column_step_x_m, 'step_y': site.column_step_y_m},
                'default_parent_location': {'id': parent.id, 'name': parent.complete_name} if parent else None,
                'active_version': {'id': version.id, 'n': version.n} if version else None,
                'draft_base_version': {'id': base.id, 'n': base.n} if base else None,
                'draft_rev': site.draft_rev,
                'draft_changes': site.draft_changes,
                'has_changes': site.has_changes,
                'settings': params(env),
            },
            'layers': [st.layer_dict(layer, xmlids) for layer in layers],
            'slots': [st.slot_dict(s) for s in slots],
            'placements': [st.placement_dict(p) for p in placements],
            'catalog': list(catalog.values()),
            'checks': st.check_configs(site),
            'versions': [
                {
                    'id': v.id,
                    'n': v.n,
                    'published_at': str(v.published_at),
                    'by': v.published_by_id.name or '',
                    'note': v.note or '',
                    'state': v.state,
                    'counts': {
                        'layers': v.layer_count,
                        'slots': v.slot_count,
                        'cells': v.cell_count,
                        'placements': v.placement_count,
                    },
                }
                for v in versions
            ],
            'rights': {
                'is_manager': manager,
                'roles': roles,
                'editable_layer_ids': [layer.id for layer in layers if Layer._f3d_can_edit_layer(layer)],
                'can_publish': manager and params(env)['publish_enabled'],
                'can_edit_catalog': env.user.has_group(ROLE_GROUPS['technologist']),
            },
        }
        return dict(ok=True, **data)

    # --- API-04 -------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/save', type='jsonrpc', auth='user', methods=['POST'])
    def save(self, site_id=None, ops=None, **kw):
        env = request.env
        site = find_site(env, site_id)
        if not site:
            return fail('not_found', "Площадку не знайдено.")
        if not isinstance(ops, list):
            return fail('validation', "Очікується список операцій ops.")
        if len(ops) > MAX_OPS:
            return fail('too_many', "Забагато операцій в одному запиті (максимум %d)." % MAX_OPS)
        size = request.httprequest.content_length
        if size and size > MAX_BODY_BYTES:
            return fail('too_many', "Запит більший за 1 МБ.")
        id_map, touched, index = {}, {}, -1
        try:
            with env.cr.savepoint():
                for position, op in enumerate(ops):
                    index = position
                    self._save_op(site, op, id_map, touched)
                env.flush_all()
        except _OpError as exc:
            env.invalidate_all()
            return fail(exc.code, exc.message, op_index=index, **exc.extra)
        except (AccessError, ValidationError, UserError, IntegrityError) as exc:
            env.invalidate_all()
            code, message = error_from_exception(exc)
            if isinstance(exc, IntegrityError):
                message = "Порушено обмеження унікальності або обов'язкових полів."
            return fail(code, message, op_index=index)
        site.invalidate_recordset(['draft_rev', 'draft_changes', 'has_changes'])
        etags = {}
        for (model, rid), rec in touched.items():
            if rec.exists():
                etags['%s:%d' % (model, rid)] = rec._f3d_etag()
        return {
            'ok': True,
            'rev': site.draft_rev,
            'draft_changes': site.draft_changes,
            'has_changes': site.has_changes,
            'id_map': id_map,
            'etags': etags,
        }

    def _resolve(self, vals, id_map):
        out = {}
        for key, value in vals.items():
            if isinstance(value, str) and value.startswith('@'):
                tmp = value[1:]
                if tmp not in id_map:
                    raise _OpError('validation', "Невідомий тимчасовий ідентифікатор %s." % value)
                value = id_map[tmp]
            out[key] = value
        return out

    def _prepare_vals(self, site, model, vals, id_map, creating):
        env = request.env
        if not isinstance(vals, dict):
            raise _OpError('validation', "vals має бути об'єктом.")
        unknown = set(vals) - SAVE_FIELDS[model]
        if unknown:
            raise _OpError('validation', "Поля не можна змінювати через API: %s." % ", ".join(sorted(unknown)))
        vals = self._resolve(vals, id_map)
        if 'allowed_slot_types' in vals:
            keys = vals.pop('allowed_slot_types') or []
            terms = env['f3d.term'].search([('term_type', '=', 'slot_type'), ('key', 'in', keys)])
            vals['allowed_slot_type_ids'] = [Command.set(terms.ids)]
        if 'edit_group_ids' in vals:
            vals['edit_group_ids'] = [Command.set([int(i) for i in vals['edit_group_ids'] or []])]
        if model in ('f3d.slot', 'f3d.placement') and 'layer_id' in vals:
            layer = env['f3d.layer'].browse(vals['layer_id']).exists()
            if not layer or layer.site_id != site:
                raise _OpError('validation', "Шар не належить цій площадці.")
        if model == 'f3d.placement' and vals.get('slot_id'):
            slot = env['f3d.slot'].browse(vals['slot_id']).exists()
            if not slot or slot.site_id != site:
                raise _OpError('validation', "Місце не належить цій площадці.")
        if creating:
            if model in ('f3d.layer', 'f3d.check.config'):
                vals['site_id'] = site.id
        return vals

    def _save_op(self, site, op, id_map, touched):
        env = request.env
        if not isinstance(op, dict):
            raise _OpError('validation', "Операція має бути об'єктом.")
        model, kind = op.get('model'), op.get('op')
        if model not in SAVE_FIELDS:
            raise _OpError('validation', "Модель %s не підтримується." % model)
        Model = env[model]
        if kind == 'create':
            tmp = op.get('tmp')
            vals = self._prepare_vals(site, model, op.get('vals') or {}, id_map, True)
            rec = Model.create(vals)
            if tmp is not None:
                id_map[str(tmp)] = rec.id
            touched[(model, rec.id)] = rec
            return
        rec = Model.browse(op.get('id')).exists() if isinstance(op.get('id'), int) else Model
        if not rec or rec.site_id != site:
            raise _OpError('not_found', "Запис не знайдено.")
        etag = op.get('etag')
        if etag is not None and etag != rec._f3d_etag():
            current = DICT_FUNCS[model](rec) if model in DICT_FUNCS else {'id': rec.id, 'etag': rec._f3d_etag()}
            raise _OpError('conflict', "Запис змінено іншим користувачем.", current=current)
        if kind == 'write':
            rec.write(self._prepare_vals(site, model, op.get('vals') or {}, id_map, False))
            touched[(model, rec.id)] = rec
        elif kind == 'unlink':
            rec.unlink()
            touched.pop((model, op['id']), None)
        else:
            raise _OpError('validation', "Невідома операція %s." % kind)

    # --- API-05 -------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/validate', type='jsonrpc', auth='user', methods=['POST'])
    def validate(self, site_id=None, layer_id=None, **kw):
        site = find_site(request.env, site_id)
        if not site:
            return fail('not_found', "Площадку не знайдено.")
        issues = st.run_site_checks(site, layer_id if isinstance(layer_id, int) else None)
        return {'ok': True, 'issues': issues, 'summary': summarize(issues)}

    # --- API-06 -------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/publish/preview', type='jsonrpc', auth='user', methods=['POST'])
    def publish_preview(self, site_id=None, **kw):
        env = request.env
        site = find_site(env, site_id)
        if not site:
            return fail('not_found', "Площадку не знайдено.")
        if not is_manager(env):
            return fail('rights', "Публікувати розкладку може лише менеджер конструктора.")
        if not publish.publish_enabled(env):
            return fail('disabled', "Публікацію вимкнено: стоп-кран factory3d.constructor.publish_enabled.")
        plan = publish.build_plan(site)
        if not site.has_changes and not [line for line in plan['lines'] if line['kind'] in ('create', 'update')]:
            return fail('no_changes', "Немає змін для публікації")
        wizard = env['f3d.publish.wizard'].create({'site_id': site.id})
        wizard._f3d_rebuild(plan)
        return {'ok': True, 'action': wizard._f3d_action(from_editor=True), 'summary': publish.summary(plan)}

    # --- API-07 -------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/publish', type='jsonrpc', auth='user', methods=['POST'])
    def publish(self, site_id=None, note=None, archive_codes=None, confirm=None, **kw):
        env = request.env
        site = find_site(env, site_id)
        if not site:
            return fail('not_found', "Площадку не знайдено.")
        if confirm is not True:
            return fail('validation', "Підтвердіть публікацію: confirm = true.")
        if not is_manager(env):
            return fail('rights', "Публікувати розкладку може лише менеджер конструктора.")
        try:
            plan = publish.build_plan(site)
            result = publish.apply_plan(site, plan, set(archive_codes or []), note if isinstance(note, str) else '')
        except publish.PublishError as exc:
            return fail(exc.code, str(exc), issues=exc.issues)
        except AccessError as exc:
            return fail('rights', str(exc))
        version = result['version']
        return {
            'ok': True,
            'version': {'id': version.id, 'n': version.n},
            'created': result['created'],
            'updated': result['updated'],
            'archived': result['archived'],
            'counts': {k: len(result[k]) for k in ('created', 'updated', 'archived')},
            'warnings': result['warnings'],
        }

    # --- API-08 -------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/version/restore', type='jsonrpc', auth='user', methods=['POST'])
    def version_restore(self, version_id=None, **kw):
        env = request.env
        try:
            version = env['f3d.layout.version'].search([('id', '=', int(version_id))], limit=1)
        except (TypeError, ValueError):
            version = None
        if not version:
            return fail('not_found', "Версію не знайдено.")
        if not is_manager(env):
            return fail('rights', "Повертати чернетку може лише менеджер конструктора.")
        try:
            with env.cr.savepoint():
                snapshot.restore_draft(version)
        except (UserError, ValidationError) as exc:
            env.invalidate_all()
            return fail('validation', str(exc))
        site = version.site_id
        site.invalidate_recordset()
        return {'ok': True, 'site_id': site.id, 'rev': site.draft_rev, 'draft_changes': site.draft_changes}


class _OpError(Exception):
    def __init__(self, code, message, **extra):
        super().__init__(message)
        self.code, self.message, self.extra = code, message, extra
