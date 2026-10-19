from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import PASSWORD, F3DConstructorCase, F3DConstructorHttpCase

VARIANTS = '/f3d/constructor/variants'
COMMENTS = '/f3d/constructor/comments'
LOCKS = '/f3d/constructor/locks'
VIEW = '/f3d/constructor/version/view'
CHECKPOINT = '/f3d/constructor/version/checkpoint'
METRICS = {'cells': 24, 'places': 72, 'area': 10.5, 'volume': 33.3, 'max_weight': 24000}


def slot_uids(site):
    return sorted(site.env['td.slot'].search([('site_id', '=', site.id)]).mapped('uid'))


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s6")
class TestVariants(F3DConstructorCase):
    """F12 / O-04: варіанти — знімки гілок чернетки; перемикання не втрачає чернетку (R-14)."""

    def setUp(self):
        super().setUp()
        self.Variant = self.env['td.layout.variant']

    def test_ensure_creates_as_is(self):
        self.assertFalse(self.site.active_variant_id)
        variant = self.Variant.f3d_ensure(self.site)
        self.assertEqual((variant.name, variant.is_training), ("Як є", False))
        self.assertEqual(self.site.active_variant_id, variant)
        self.assertTrue(variant.snapshot_id)
        self.assertEqual(self.Variant.f3d_ensure(self.site), variant)  # повторно — той самий

    def test_create_switch_back_keeps_draft(self):
        self.make_slot(prefix='TQ-A1')
        base = self.Variant.f3d_ensure(self.site)
        proj = self.Variant.f3d_make(self.site, "Проєкт A", metrics=METRICS)
        self.assertEqual(self.site.active_variant_id, proj)
        self.assertEqual(proj.metrics['cells'], 24)
        before = slot_uids(self.site)
        self.make_slot(prefix='TQ-A2', x=40.0)  # правка в «Проєкт A»
        self.assertEqual(len(slot_uids(self.site)), len(before) + 1)
        rev = self.site.draft_rev
        base.f3d_activate(metrics=METRICS)  # назад в «Як є»: правки A лишаються в знімку A
        self.assertEqual(self.site.active_variant_id, base)
        self.assertEqual(slot_uids(self.site), before)
        self.assertGreater(self.site.draft_rev, rev)
        proj.f3d_activate()
        self.assertEqual(len(slot_uids(self.site)), len(before) + 1)  # нічого не втрачено
        self.assertEqual(
            self.env['td.slot'].search_count([('site_id', '=', self.site.id), ('code_prefix', '=', 'TQ-A2')]), 1
        )

    def test_delete_rules_and_limit(self):
        base = self.Variant.f3d_ensure(self.site)
        with self.assertRaises(UserError):
            base.unlink()  # активний
        proj = self.Variant.f3d_make(self.site, "Проєкт A")
        with self.assertRaises(UserError):
            proj.unlink()  # активний тепер він
        base.unlink()  # неактивний можна
        self.env['ir.config_parameter'].sudo().set_param('td.constructor.variants_max', '2')
        self.Variant.f3d_make(self.site, "Проєкт B")
        with self.assertRaises(UserError):
            self.Variant.f3d_make(self.site, "Проєкт C")
        with self.assertRaises(UserError):
            self.Variant.f3d_make(self.site, "проєкт b")  # назва вже є

    def test_rights_manager_only(self):
        self.Variant.f3d_ensure(self.site)
        for user in (self.u_tech, self.u_store, self.u_plain):
            with self.assertRaises(AccessError):
                self.Variant.with_user(user).f3d_make(self.site, "X")

    def test_training_copy_cancel_and_keep(self):
        self.make_slot(prefix='TQ-T0')
        base = self.Variant.f3d_ensure(self.site)
        before = slot_uids(self.site)
        train = self.Variant.f3d_make(self.site, "Навчальна копія", training=True)
        self.assertEqual((train.is_training, train.origin_id), (True, base))
        with self.assertRaises(UserError):
            self.Variant.f3d_make(self.site, "Ще одна", training=True)
        self.make_slot(prefix='TQ-T1', x=40.0)  # тур змінює дані
        version_vals = {'site_id': self.site.id, 'n': 90, 'kind': 'publish'}
        with self.assertRaises(UserError):  # не публікується
            self.env['td.layout.version'].create(version_vals)
        back = train.f3d_end_training(keep=False)
        self.assertEqual(back, base)
        self.assertEqual(self.site.active_variant_id, base)
        self.assertEqual(slot_uids(self.site), before)
        self.assertFalse(train.exists())
        # «Залишити зміни»: звичайний варіант
        train2 = self.Variant.f3d_make(self.site, "Навчальна копія", training=True)
        self.make_slot(prefix='TQ-T2', x=45.0)
        kept = train2.f3d_end_training(keep=True)
        self.assertEqual((kept.is_training, self.site.active_variant_id), (False, kept))
        self.assertEqual(
            self.env['td.slot'].search_count([('site_id', '=', self.site.id), ('code_prefix', '=', 'TQ-T2')]), 1
        )

    def test_publish_version_gets_variant(self):
        base = self.Variant.f3d_ensure(self.site)
        version = self.env['td.layout.version'].create({'site_id': self.site.id, 'n': 91})
        self.assertEqual(version.variant_id, base)


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s6")
class TestCollabApi(F3DConstructorHttpCase):
    """API-21 (варіанти) і API-24 (версії, контрольні точки) — правила API-01…10."""

    def call(self, user, route, **params):
        self.authenticate(user.login, PASSWORD)
        return self.rpc(route, **params)

    def test_variants_api_flow(self):
        self.make_slot(prefix='TQ-V1')
        res = self.call(self.u_plain, VARIANTS, site_id=self.site.id)  # читає кожен
        self.assertTrue(res['ok'], res)
        self.assertEqual([v['name'] for v in res['variants']], ["Як є"])
        self.assertFalse(res['can_edit'])
        denied = self.call(self.u_plain, VARIANTS, site_id=self.site.id, op='create', name="A")
        self.assertEqual((denied['ok'], denied['code']), (False, 'rights'))
        created = self.call(
            self.u_manager, VARIANTS, site_id=self.site.id, op='create', name="Проєкт A", metrics=METRICS
        )
        self.assertTrue(created['ok'], created)
        self.assertEqual(len(created['variants']), 2)
        active = next(v for v in created['variants'] if v['active'])
        self.assertEqual((active['name'], active['metrics']['cells']), ("Проєкт A", 24))
        self.assertTrue(all('ops' in v['metrics'] for v in created['variants']))
        dup = self.call(self.u_manager, VARIANTS, site_id=self.site.id, op='create', name="проєкт a")
        self.assertEqual((dup['ok'], dup['code']), (False, 'validation'))
        base_id = next(v['id'] for v in created['variants'] if not v['active'])
        switched = self.call(self.u_manager, VARIANTS, site_id=self.site.id, op='activate', id=base_id, metrics=METRICS)
        self.assertTrue(switched['ok'] and switched['reload'], switched)
        self.assertEqual(switched['active_id'], base_id)
        renamed = self.call(
            self.u_manager, VARIANTS, site_id=self.site.id, op='rename', id=active['id'], name="Проєкт Б"
        )
        self.assertEqual(sorted(v['name'] for v in renamed['variants']), ["Проєкт Б", "Як є"])
        bad = self.call(self.u_manager, VARIANTS, site_id=self.site.id, op='delete', id=base_id)  # активний
        self.assertEqual((bad['ok'], bad['code']), (False, 'validation'))
        gone = self.call(self.u_manager, VARIANTS, site_id=self.site.id, op='delete', id=active['id'])
        self.assertTrue(gone['ok'], gone)
        self.assertEqual(len(gone['variants']), 1)
        only = self.call(self.u_manager, VARIANTS, site_id=self.site.id, op='delete', id=base_id)
        self.assertFalse(only['ok'])
        missing = self.call(self.u_manager, VARIANTS, site_id=0)
        self.assertEqual(missing['code'], 'not_found')

    def test_training_via_api(self):
        res = self.call(
            self.u_manager, VARIANTS, site_id=self.site.id, op='create', name="Навчальна копія", training=True
        )
        self.assertTrue(res['ok'], res)
        self.assertEqual(res['training_id'], res['active_id'])
        end = self.call(
            self.u_manager, VARIANTS, site_id=self.site.id, op='end_training', id=res['training_id'], keep=False
        )
        self.assertTrue(end['ok'], end)
        self.assertIsNone(end['training_id'])
        self.assertEqual(len(end['variants']), 1)

    def test_checkpoint_and_view(self):
        slot = self.make_slot(prefix='TQ-C1')
        denied = self.call(self.u_plain, CHECKPOINT, site_id=self.site.id, note="x")
        self.assertEqual(denied['code'], 'rights')
        res = self.call(self.u_tech, CHECKPOINT, site_id=self.site.id, note="Перед змінами")
        self.assertTrue(res['ok'], res)
        version = res['version']
        self.assertEqual((version['kind'], version['state'], version['is_active']), ('checkpoint', 'superseded', False))
        lst = self.call(self.u_plain, VIEW, site_id=self.site.id)
        self.assertTrue(lst['ok'])
        self.assertIn(version['id'], [v['id'] for v in lst['versions']])
        view = self.call(self.u_plain, VIEW, version_id=version['id'])
        self.assertTrue(view['ok'], view)
        self.assertIn(slot.uid, [s['id'] for s in view['view']['slots']])
        self.assertEqual({'x', 'y', 'rotation'} <= set(view['view']['slots'][0]), True)
        note = self.call(self.u_manager, CHECKPOINT, op='note', version_id=version['id'], note="Нова нотатка")
        self.assertEqual(note['version']['note'], "Нова нотатка")
        denied = self.call(self.u_tech, CHECKPOINT, op='note', version_id=version['id'], note="чужа")
        self.assertEqual(denied['code'], 'rights')

    def test_checkpoints_pruned_publications_kept(self):
        from ..services import snapshot

        self.site.default_parent_location_id = self.wh_stock
        pub = snapshot.create_version(self.site, note="Публікація")
        self.env['ir.config_parameter'].sudo().set_param('td.constructor.versions_keep', '2')
        ids = [
            self.call(self.u_manager, CHECKPOINT, site_id=self.site.id, note="т%d" % i)['version']['id']
            for i in range(4)
        ]
        left = self.env['td.layout.version'].search([('site_id', '=', self.site.id), ('kind', '=', 'checkpoint')])
        self.assertEqual(sorted(left.ids), sorted(ids[-2:]))
        self.assertTrue(pub.exists())
        self.assertEqual(self.site.active_version_id, pub)  # контрольна точка не змінює активну версію


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s6")
class TestComments(F3DConstructorHttpCase):
    """F13 / API-22: коментарі й задачі; зв'язок з mail.activity."""

    def call(self, user, **params):
        self.authenticate(user.login, PASSWORD)
        return self.rpc(COMMENTS, site_id=self.site.id, **params)

    def add(self, user, text="Перевірити на місці", **vals):
        res = self.call(
            user,
            op='create',
            vals=dict({'target_kind': 'slot', 'target_uid': 'abc', 'target_label': "Ряд R1", 'text': text}, **vals),
        )
        self.assertTrue(res['ok'], res)
        return res

    def test_viewer_adds_designer_resolves(self):
        res = self.add(self.u_plain)  # «перегляд» пише
        comment = res['comments'][0]
        self.assertEqual(
            (comment['author'], comment['state'], comment['kind'], comment['mine']), ('f3d_plain', 'open', 'note', True)
        )
        self.assertTrue(comment['can_resolve'])  # автор
        other = self.call(self.u_store, op='list')['comments'][0]
        self.assertEqual(other['mine'], False)
        self.assertTrue(other['can_resolve'])  # «проєктування»
        viewer2 = self.env['res.users'].browse(self.u_plain.id)
        self.assertFalse(viewer2.has_group('td_constructor.group_td_constructor_technologist'))
        resolved = self.call(self.u_store, op='resolve', id=comment['id'])
        self.assertEqual(resolved['comments'][0]['state'], 'resolved')
        self.assertEqual(resolved['comments'][0]['resolved_by'], 'f3d_store')
        reopened = self.call(self.u_plain, op='resolve', id=comment['id'], resolved=False)
        self.assertEqual(reopened['comments'][0]['state'], 'open')

    def test_other_viewer_cannot_resolve_or_delete(self):
        extra = self._f3d_user('f3d_plain2', [])
        cid = self.add(self.u_plain)['comments'][0]['id']
        row = self.call(extra, op='list')['comments'][0]
        self.assertEqual((row['can_resolve'], row['can_delete']), (False, False))
        self.assertEqual(self.call(extra, op='resolve', id=cid)['code'], 'rights')
        self.assertEqual(self.call(extra, op='delete', id=cid)['code'], 'rights')
        gone = self.call(self.u_eng, op='delete', id=cid)  # чужі видаляє «проєктування»
        self.assertTrue(gone['ok'])
        self.assertEqual(gone['comments'], [])

    def test_validation(self):
        for vals in ({'text': '  '}, {'kind': 'bug'}, {'target_kind': 'planet'}, {'text': 'x' * 4001}):
            res = self.call(self.u_plain, op='create', vals=dict({'target_kind': 'slot', 'text': 'ok'}, **vals))
            self.assertEqual((res['ok'], res['code']), (False, 'validation'), vals)
        self.assertEqual(self.call(self.u_plain, op='bogus')['code'], 'validation')
        self.assertEqual(self.call(self.u_plain, op='resolve', id=0)['code'], 'not_found')

    def test_task_creates_activity_and_resolve_closes_it(self):
        users = self.call(self.u_tech, op='assignees')
        self.assertIn(self.u_store.id, [u['id'] for u in users['users']])
        res = self.add(self.u_tech, text="Перемірити прохід", kind='task', assignee_id=self.u_store.id)
        comment = self.env['td.comment'].browse(res['id'])
        activity = comment.activity_ids
        self.assertEqual((len(activity), activity.user_id), (1, self.u_store))
        self.assertIn("Перемірити прохід", activity.summary)
        self.call(self.u_store, op='resolve', id=comment.id)
        comment.invalidate_recordset()
        self.assertFalse(comment.activity_ids)  # завдання виконано
        self.assertEqual(comment.state, 'resolved')
        self.call(self.u_tech, op='resolve', id=comment.id, resolved=False)
        comment.invalidate_recordset()
        self.assertEqual(len(comment.activity_ids), 1)  # знову відкрита — знову завдання
        self.call(self.u_tech, op='update', id=comment.id, text="Інший текст")
        self.assertEqual(comment.text, "Інший текст")
        self.call(self.u_tech, op='delete', id=comment.id)
        self.assertFalse(comment.exists())

    def test_assignee_rules(self):
        bad = self.call(
            self.u_tech, op='create', vals={'target_kind': 'slot', 'text': 'x', 'assignee_id': self.u_store.id}
        )
        self.assertEqual(bad['code'], 'validation')  # виконавець лише в задачі
        outsider = self.env['res.users'].create(
            {'name': 'Out', 'login': 'f3d_out', 'group_ids': [(6, 0, [self.env.ref('base.group_user').id])]}
        )
        bad = self.call(
            self.u_tech,
            op='create',
            vals={'target_kind': 'slot', 'text': 'x', 'kind': 'task', 'assignee_id': outsider.id},
        )
        self.assertEqual(bad['code'], 'validation')

    def test_update_only_author_or_designer(self):
        cid = self.add(self.u_plain)['comments'][0]['id']
        extra = self._f3d_user('f3d_plain3', [])
        self.assertEqual(self.call(extra, op='update', id=cid, text='зламав')['code'], 'rights')
        self.assertTrue(self.call(self.u_plain, op='update', id=cid, text='мій')['ok'])


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s6")
class TestZoneLocks(F3DConstructorHttpCase):
    """F14 / API-23: оренда зони 5 хв; двоє не правлять одну зону; закінчення оренди."""

    def setUp(self):
        super().setUp()
        self.zone = self.make_slot(
            kind='production',
            prefix='ZN-A',
            template='zone',
            x=20.0,
            y=10.0,
            polygon=[[10, 5], [30, 5], [30, 15], [10, 15]],
        )
        self.rack = self.make_slot(prefix='TQ-L1', x=20.0, y=10.0)  # у зоні
        self.far = self.make_slot(prefix='TQ-L2', x=50.0, y=25.0)  # поза зонами

    def call(self, user, op='list', **params):
        self.authenticate(user.login, PASSWORD)
        return self.rpc(LOCKS, site_id=self.site.id, op=op, **params)

    def test_acquire_busy_release_and_params(self):
        res = self.call(self.u_store, 'acquire', zone_uid=self.zone.uid)
        self.assertTrue(res['ok'], res)
        self.assertEqual((res['ttl'], res['heartbeat']), (300, 60))
        self.assertEqual([(lk['zone_uid'], lk['mine']) for lk in res['locks']], [(self.zone.uid, True)])
        busy = self.call(self.u_manager, 'acquire', zone_uid=self.zone.uid)
        self.assertEqual((busy['ok'], busy['code']), (False, 'locked'))
        self.assertIn('f3d_store', busy['message'])
        self.assertIn('ZN-A', busy['message'])
        self.assertRegex(busy['message'], r'до \d\d:\d\d')
        self.assertFalse(busy['locks'][0]['mine'])
        again = self.call(self.u_store, 'acquire', zone_uid=self.zone.uid)  # продовження своєї
        self.assertTrue(again['ok'])
        self.assertEqual(len(again['locks']), 1)
        self.assertEqual(self.call(self.u_manager, 'release', zone_uid=self.zone.uid)['released'], 0)  # чужу не зняти
        self.assertEqual(self.call(self.u_store, 'release')['released'], 1)
        self.assertTrue(self.call(self.u_manager, 'acquire', zone_uid=self.zone.uid)['ok'])

    def test_view_only_cannot_lock_but_lists(self):
        self.assertEqual(self.call(self.u_plain, 'acquire', zone_uid=self.zone.uid)['code'], 'rights')
        self.assertTrue(self.call(self.u_plain)['ok'])
        self.assertEqual(self.call(self.u_store, 'acquire', zone_uid='')['code'], 'validation')
        self.assertEqual(self.call(self.u_store, 'bogus')['code'], 'validation')

    def test_foreign_lock_rejects_edits_in_zone(self):
        self.call(self.u_store, 'acquire', zone_uid=self.zone.uid)
        with self.assertRaises(AccessError) as ctx:
            self.rack.with_user(self.u_manager).write({'x_m': 21.0})
        self.assertIn('редагує f3d_store', str(ctx.exception))
        with self.assertRaises(AccessError):
            self.rack.with_user(self.u_manager).unlink()
        with self.assertRaises(AccessError):  # новий ряд у чужій зоні
            self.make_slot_as(self.u_manager, 'TQ-L9', 22.0, 11.0)
        with self.assertRaises(AccessError):  # переміщення з вільної частини в чужу зону
            self.far.with_user(self.u_manager).write({'x_m': 20.0, 'y_m': 10.0})
        self.rack.with_user(self.u_store).write({'x_m': 21.5})  # орендар править
        self.far.with_user(self.u_manager).write({'x_m': 51.0})  # поза зоною — вільно
        self.assertEqual(self.rack.sudo().x_m, 21.5)

    def test_expired_lease_does_not_block(self):
        self.call(self.u_store, 'acquire', zone_uid=self.zone.uid)
        lock = self.env['td.zone.lock'].search([('zone_uid', '=', self.zone.uid)])
        lock.write({'expires_at': fields.Datetime.now() - timedelta(seconds=1)})
        self.rack.with_user(self.u_manager).write({'x_m': 22.0})  # оренда сплила: правка проходить
        res = self.call(self.u_manager, 'acquire', zone_uid=self.zone.uid)  # і зону можна взяти
        self.assertTrue(res['ok'], res)
        self.assertEqual(res['locks'][0]['user'], 'f3d_manager')

    def test_object_outside_zone_locks_itself(self):
        self.call(self.u_store, 'acquire', zone_uid=self.far.uid)
        with self.assertRaises(AccessError):
            self.far.with_user(self.u_manager).write({'rotation': 90})
        self.rack.with_user(self.u_manager).write({'x_m': 23.0})  # інший об'єкт — вільно

    def test_save_api_rejects_with_message(self):
        self.call(self.u_store, 'acquire', zone_uid=self.zone.uid)
        self.authenticate(self.u_manager.login, PASSWORD)
        res = self.rpc(
            '/f3d/constructor/save',
            site_id=self.site.id,
            ops=[
                {
                    'model': 'td.slot',
                    'op': 'write',
                    'id': self.rack.id,
                    'etag': self.rack._f3d_etag(),
                    'vals': {'x_m': 24.0},
                }
            ],
        )
        self.assertEqual((res['ok'], res['code']), (False, 'rights'), res)
        self.assertIn('f3d_store', res['message'])

    def test_manager_can_free_via_unlink_and_su_ignores(self):
        self.call(self.u_store, 'acquire', zone_uid=self.zone.uid)
        self.env['td.zone.lock'].with_user(self.u_manager).search([]).unlink()
        self.rack.with_user(self.u_manager).write({'x_m': 25.0})
        self.call(self.u_store, 'acquire', zone_uid=self.zone.uid)
        self.rack.sudo().write({'x_m': 26.0})  # публікація/відновлення (sudo) не блокуються

    def make_slot_as(self, user, prefix, x, y):
        return (
            self.env['td.slot']
            .with_user(user)
            .create(
                {
                    'layer_id': self.layers['storage'].id,
                    'template': 'pallet_rack',
                    'code_prefix': prefix,
                    'x_m': x,
                    'y_m': y,
                    'params': {
                        'bays': 2,
                        'levels': 1,
                        'bay_width': 2.7,
                        'depth': 1.1,
                        'level_height': 1.5,
                        'positions_per_bay': 1,
                        'max_load_kg': 500,
                    },
                    'parent_location_id': self.wh_fg.id,
                }
            )
        )
