"""API-21…API-24: варіанти, коментарі, блокування, версії (F12, F13, F14, N-03); сторінка «Інструкція» (F19).

Правила як у API-01…10: JSON-RPC, auth user, відповідь `{ok: true, …}` або `{ok: false, code, message}` (HTTP 200).
Права: читає «перегляд» (`group_td_user`); варіантами керує менеджер (чернетка спільна: перемикання підмінює її
для всіх);
коментарі додає будь-хто з доступом, вирішує автор чи «Проєктування», видаляє автор чи «Проєктування» (F13-04); оренду
зони бере «Проєктування»; контрольну точку створює «Проєктування», нотатку версії міняє менеджер.
"""

from odoo import fields, http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from ..services import snapshot
from .constructor import MANAGER, ROLE_GROUPS, error_from_exception, fail, find_site, is_manager

LIST_LIMIT = 2000
VERSION_KEEP_DEFAULT = 50


def can_design(env):
    """Проєктувальник: менеджер чи будь-яка з ролей технолог/комірник/інженер."""
    groups = env.user.all_group_ids
    return any(env.ref(xmlid) in groups for xmlid in ROLE_GROUPS.values())


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


class TdCollabController(http.Controller):
    # --- API-21: варіанти ------------------------------------------------------------------------------
    @http.route('/f3d/constructor/variants', type='jsonrpc', auth='user', methods=['POST'])
    def variants(
        self, site_id=None, op='list', id=None, name=None, metrics=None, training=False, activate=True, keep=False, **kw
    ):
        env = request.env
        site = find_site(env, site_id)
        if not site:
            return fail('not_found', "Площадку не знайдено.")
        Variant = env['td.layout.variant']
        if op not in ('list', 'create', 'activate', 'rename', 'delete', 'end_training'):
            return fail('validation', "op: list, create, activate, rename, delete або end_training.")
        try:
            with env.cr.savepoint():
                result = self._variants_op(env, site, Variant, op, id, name, metrics, training, activate, keep)
        except AccessError as exc:
            env.invalidate_all()
            return fail('rights', str(exc))
        except (UserError, ValidationError) as exc:
            env.invalidate_all()
            return fail('validation', str(exc))
        if result.get('ok') is False:
            return result
        site.invalidate_recordset()
        return self._variants_state(env, site, Variant, reload=op in ('activate', 'end_training'), **(result or {}))

    def _variants_op(self, env, site, Variant, op, rec_id, name, metrics, training, activate, keep):
        if op == 'list':
            return {}
        if op == 'create':
            variant = Variant.f3d_make(site, name, training=bool(training), activate=bool(activate), metrics=metrics)
            return {'id': variant.id}
        variant = Variant.sudo().browse(_int(rec_id)).exists()
        if not variant or variant.site_id != site:
            return fail('not_found', "Варіант не знайдено.")
        Variant._td_assert_manager()
        if op == 'activate':
            variant.f3d_activate(metrics)
        elif op == 'rename':
            new = (name or '').strip()
            if not new:
                raise UserError("Вкажіть назву варіанта.")
            if Variant.sudo().search_count(
                [
                    ('site_id', '=', site.id),
                    ('id', '!=', variant.id),
                    ('is_training', '=', False),
                    ('name', '=ilike', new),
                ]
            ):
                raise UserError("Варіант «%s» уже існує." % new)
            variant.write({'name': new})
        elif op == 'delete':
            siblings = Variant.sudo().search_count([('site_id', '=', site.id), ('is_training', '=', False)])
            if variant.site_id.active_variant_id == variant:
                raise UserError("Активний варіант видалити не можна: спершу перемкніться на інший.")
            if siblings <= 1 and not variant.is_training:
                raise UserError("Єдиний варіант видалити не можна.")
            variant.unlink()
        else:
            variant.f3d_end_training(keep=bool(keep))
        return {} if op == 'delete' else {'id': variant.id}

    def _variants_state(self, env, site, Variant, reload=False, id=None):
        Variant.f3d_ensure(site)
        site = site.sudo()
        active = site.active_variant_id
        base = snapshot.load_snapshot(site.active_version_id) if site.active_version_id.snapshot_id else None
        out = []
        for variant in Variant.sudo().search([('site_id', '=', site.id)]):
            if variant == active:
                ops = site.draft_changes
            elif base is not None and variant.snapshot_id:
                ops = snapshot.count_differences(snapshot.load_snapshot(variant), base)
            else:
                ops = None
            out.append(variant.f3d_dict(ops))
        return {
            'ok': True,
            'variants': out,
            'active_id': active.id,
            'training_id': next((v['id'] for v in out if v['is_training']), None),
            'max': Variant._td_max(),
            'can_edit': is_manager(env),
            'id': id,
            'reload': reload,
            'draft': {'rev': site.draft_rev, 'changes': site.draft_changes},
        }

    # --- API-22: коментарі та задачі -------------------------------------------------------------------
    @http.route('/f3d/constructor/comments', type='jsonrpc', auth='user', methods=['POST'])
    def comments(self, site_id=None, op='list', id=None, vals=None, text=None, resolved=True, **kw):
        env = request.env
        site = find_site(env, site_id)
        if not site:
            return fail('not_found', "Площадку не знайдено.")
        Comment = env['td.comment']
        if op not in ('list', 'create', 'update', 'resolve', 'delete', 'assignees'):
            return fail('validation', "op: list, create, update, resolve, delete або assignees.")
        try:
            with env.cr.savepoint():
                if op == 'list':
                    return self._comments_list(env, site)
                if op == 'assignees':
                    return self._assignees(env)
                if op == 'create':
                    comment = Comment.f3d_add(site, vals or {})
                    return dict(self._comments_list(env, site), id=comment.id)
                comment = Comment.browse(_int(id)).exists()  # від імені користувача: права перевіряє модель
                if not comment or comment.site_id != site:
                    return fail('not_found', "Коментар не знайдено.")
                if op == 'update':
                    comment.f3d_set_text(text)
                elif op == 'resolve':
                    comment.f3d_resolve(bool(resolved))
                else:
                    comment.f3d_remove()
                return dict(self._comments_list(env, site), id=comment.id if op != 'delete' else None)
        except AccessError as exc:
            env.invalidate_all()
            return fail('rights', str(exc))
        except (UserError, ValidationError) as exc:
            env.invalidate_all()
            code, message = error_from_exception(exc)
            return fail(code, message)

    def _comments_list(self, env, site):
        rows = env['td.comment'].search([('site_id', '=', site.id)], order='id desc', limit=LIST_LIMIT)
        return {
            'ok': True,
            'comments': [c.f3d_dict() for c in rows],
            'at': fields.Datetime.to_string(fields.Datetime.now()),
        }

    def _assignees(self, env):
        group = env.ref('td_factory3d.group_td_user')
        users = env['res.users'].sudo().search([('group_ids', 'in', group.id), ('share', '=', False)], order='name')
        return {'ok': True, 'users': [{'id': u.id, 'name': u.name} for u in users], 'me': env.user.id}

    # --- API-23: блокування зон ------------------------------------------------------------------------
    @http.route('/f3d/constructor/locks', type='jsonrpc', auth='user', methods=['POST'])
    def locks(self, site_id=None, op='list', zone_uid=None, **kw):
        env = request.env
        site = find_site(env, site_id)
        if not site:
            return fail('not_found', "Площадку не знайдено.")
        Lock = env['td.zone.lock']
        if op not in ('list', 'acquire', 'release'):
            return fail('validation', "op: list, acquire або release.")
        if op != 'list' and not can_design(env):
            return fail('rights', "Зону блокує «Проєктування»: технолог, комірник, інженер або менеджер.")
        Lock.f3d_purge(site)
        extra = {}
        try:
            if op == 'acquire':
                if not isinstance(zone_uid, str) or not zone_uid or len(zone_uid) > 32:
                    return fail('validation', "zone_uid: рядок до 32 символів.")
                ok, lock = Lock.f3d_acquire(site, zone_uid)
                extra['lock'] = lock.f3d_dict() if lock else None
                if not ok:
                    return fail(
                        'locked',
                        Lock._td_busy_message(lock, Lock.f3d_label(site, zone_uid)),
                        lock=extra['lock'],
                        **self._lock_state(env, site, Lock),
                    )
            elif op == 'release':
                extra['released'] = Lock.f3d_release(site, zone_uid if isinstance(zone_uid, str) and zone_uid else None)
        except AccessError as exc:
            env.invalidate_all()
            return fail('rights', str(exc))
        return dict(self._lock_state(env, site, Lock), ok=True, **extra)

    def _lock_state(self, env, site, Lock):
        return {
            'locks': [lock.f3d_dict() for lock in Lock.f3d_active(site)],
            'ttl': Lock.f3d_ttl(),
            'heartbeat': Lock.f3d_heartbeat(),
            'now': fields.Datetime.to_string(fields.Datetime.now()),
        }

    # --- API-24: версії ----------------------------------------------------------------------------------
    @http.route('/f3d/constructor/version/view', type='jsonrpc', auth='user', methods=['POST'])
    def version_view(self, site_id=None, version_id=None, **kw):
        env = request.env
        if version_id is not None:
            version = env['td.layout.version'].search([('id', '=', _int(version_id))], limit=1)
            if not version:
                return fail('not_found', "Версію не знайдено.")
            try:
                snap = snapshot.load_snapshot(version.sudo())
            except UserError as exc:
                return fail('validation', str(exc))
            return {'ok': True, 'version': self._version_dict(version), 'view': self._snapshot_view(snap)}
        site = find_site(env, site_id)
        if not site:
            return fail('not_found', "Площадку не знайдено.")
        keep = self._keep(env)
        versions = site.version_ids.sorted('n', reverse=True)[:keep]
        return {'ok': True, 'versions': [self._version_dict(v) for v in versions], 'keep': keep}

    @http.route('/f3d/constructor/version/checkpoint', type='jsonrpc', auth='user', methods=['POST'])
    def version_checkpoint(self, site_id=None, op='create', note=None, version_id=None, **kw):
        env = request.env
        if op == 'note':
            version = env['td.layout.version'].search([('id', '=', _int(version_id))], limit=1)
            if not version:
                return fail('not_found', "Версію не знайдено.")
            if not env.user.has_group(MANAGER):
                return fail('rights', "Нотатку версії змінює менеджер конструктора.")
            version.write({'note': (note or '').strip()[:2000] or False})
            return {'ok': True, 'version': self._version_dict(version)}
        if op != 'create':
            return fail('validation', "op: create або note.")
        site = find_site(env, site_id)
        if not site:
            return fail('not_found', "Площадку не знайдено.")
        if not can_design(env):
            return fail('rights', "Контрольну точку створює «Проєктування»: технолог, комірник, інженер або менеджер.")
        try:
            with env.cr.savepoint():
                version = self._create_checkpoint(env, site, note)
        except (UserError, ValidationError) as exc:
            env.invalidate_all()
            return fail('validation', str(exc))
        return {'ok': True, 'version': self._version_dict(version)}

    @staticmethod
    def _keep(env):
        try:
            return max(
                1,
                int(env['ir.config_parameter'].sudo().get_param('td.constructor.versions_keep', VERSION_KEEP_DEFAULT)),
            )
        except (TypeError, ValueError):
            return VERSION_KEEP_DEFAULT

    def _create_checkpoint(self, env, site, note):
        """N-03: знімок чернетки без публікації: активна версія й база чернетки не змінюються; старі точки (понад
        `versions_keep`) прибираються, публікації — ніколи."""
        site = site.sudo()
        env.cr.execute("SELECT id FROM td_site WHERE id = %s FOR UPDATE", (site.id,))
        Version = env['td.layout.version'].sudo()
        previous = Version.search([('site_id', '=', site.id)], order='n desc', limit=1)
        snap = snapshot.build_snapshot(site)
        raw, sha1 = snapshot.dump_snapshot(snap)
        version = Version.create(
            {
                'site_id': site.id,
                'n': (previous.n if previous else 0) + 1,
                'note': (note or '').strip()[:2000] or "Контрольна точка",
                'published_by_id': env.user.id,
                'published_at': fields.Datetime.now(),
                'state': 'superseded',
                'kind': 'checkpoint',
                'variant_id': site.active_variant_id.id or False,
                'snapshot_sha1': sha1,
                'draft_rev': site.draft_rev,
                'layer_count': snap['counts']['layers'],
                'slot_count': snap['counts']['slots'],
                'cell_count': snap['counts']['cells'],
                'placement_count': snap['counts']['placements'],
            }
        )
        version.snapshot_id = (
            env['ir.attachment']
            .sudo()
            .create(
                {
                    'name': 'f3d_layout_%s_v%d.json' % (site.code, version.n),
                    'raw': raw,
                    'mimetype': 'application/json',
                    'res_model': 'td.layout.version',
                    'res_id': version.id,
                    'type': 'binary',
                }
            )
        )
        keep = self._keep(env)
        points = Version.search([('site_id', '=', site.id), ('kind', '=', 'checkpoint')], order='n desc')
        old = points[keep:]
        if old:
            old.snapshot_id.sudo().unlink()
            old.unlink()
        return version

    @staticmethod
    def _version_dict(v):
        return {
            'id': v.id,
            'n': v.n,
            'kind': v.kind,
            'state': v.state,
            'published_at': str(v.published_at),
            'by': v.published_by_id.name or '',
            'note': v.note or '',
            'is_active': v.state == 'active' and v.kind == 'publish',
            'has_snapshot': bool(v.snapshot_id),
            'counts': {
                'layers': v.layer_count,
                'slots': v.slot_count,
                'cells': v.cell_count,
                'placements': v.placement_count,
            },
        }

    @staticmethod
    def _snapshot_view(snap):
        """Знімок R-14 → стан у форматі API-03 (id = uid): лише геометрія для перегляду й цифр (тільки читання)."""
        layers = [
            {
                'id': ly['uid'],
                'name': ly['name'],
                'kind': ly['kind'],
                'elevation': ly.get('elevation_m') or 0,
                'color': ly.get('color'),
                'opacity': ly.get('opacity'),
                'bounds': ly.get('bounds'),
                'visible': ly.get('visible', True),
            }
            for ly in snap.get('layers', [])
            if ly.get('active', True)
        ]
        live = {ly['id'] for ly in layers}
        slots = [
            {
                'id': s['uid'],
                'layer_id': s['layer_uid'],
                'template': s['template'],
                'code_prefix': s['code_prefix'],
                'x': s['x_m'],
                'y': s['y_m'],
                'rotation': s['rotation'],
                'params': s.get('params') or {},
                'overrides': s.get('overrides') or {},
            }
            for s in snap.get('slots', [])
            if s.get('active', True) and s['layer_uid'] in live
        ]
        placements = [
            {
                'id': p['uid'],
                'layer_id': p['layer_uid'],
                'variant_id': p['variant_id'],
                'x': p['x_m'],
                'y': p['y_m'],
                'rotation': p['rotation'],
                'code': p['code'],
                'name': p['name'],
            }
            for p in snap.get('placements', [])
            if p.get('active', True) and p['layer_uid'] in live
        ]
        info = snap.get('site') or {}
        return {
            'site': {'name': info.get('name'), 'building': info.get('building')},
            'layers': layers,
            'slots': slots,
            'placements': placements,
            'counts': snap.get('counts') or {},
        }

    # --- F19: сторінка «Інструкція» ---------------------------------------------------------------------
    @http.route('/f3d/constructor/help', type='http', auth='user', methods=['GET'])
    def help_page(self, lang=None, **kw):
        """Мова сторінки: `?lang=en|uk`; за замовчуванням українська (як у редакторі)."""
        return request.render('td_constructor.td_help_page', {'en': (lang or '').lower().startswith('en')})
