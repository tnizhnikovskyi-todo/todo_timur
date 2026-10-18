from odoo.exceptions import ValidationError
from odoo.tests import tagged

from ..hooks import seed
from ..services import cells, publish, snapshot
from .common import F3DConstructorCase

DEMO_CODE = 'FG-R1-B01-L1'  # локація макета: є лише в копії демо-бази


class SeedPublishCase(F3DConstructorCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('td.constructor.publish_enabled', 'True')
        cls.seed_site = cls.env['td.site'].search([('seed_key', '=', 'main_demo')], limit=1)
        cls.demo = bool(cls.env['stock.location'].search_count([('td_code', '=', DEMO_CODE)]))

    def wizard(self, site=None):
        action = (site or self.seed_site).with_user(self.u_manager).action_publish_wizard()
        return self.env['td.publish.wizard'].with_user(self.u_manager).browse(action['res_id'])

    def kinds(self, plan):
        out = {}
        for line in plan['lines']:
            out[line['kind']] = out.get(line['kind'], 0) + 1
        return out

    def assertPlanEmpty(self, plan):
        summary = publish.summary(plan)
        details = [(line['kind'], line['res_model'], line['code'], line['changes'][:80]) for line in plan['lines'][:6]]
        self.assertEqual(
            (summary['create'], summary['update'], summary['archive_offer'], summary['archive']),
            (0, 0, 0, 0),
            details,
        )
        blocks = [i['message'] for i in plan['issues'] if i['severity'] == 'block']
        self.assertEqual(blocks, [])
        self.assertGreater(plan['unchanged'], 0)


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestSeedPublishIdempotent(SeedPublishCase):
    """Публікація незміненого сіда: порожній план, жодної заборони, майстер показує лише «Без змін»."""

    def test_demo_unchanged_seed_gives_empty_plan(self):
        if not self.demo:
            self.skipTest("Немає демо-даних (локацій і обладнання макета): перевірка лише на копії демо-бази")
        self.assertTrue(self.seed_site, "Сід «Меблеве підприємство» не завантажено")
        plan = publish.build_plan(self.seed_site)
        self.assertPlanEmpty(plan)
        self.assertEqual(self.kinds(plan), {})
        wizard = self.wizard()
        self.assertEqual(
            (wizard.n_create, wizard.n_update, wizard.n_archive_offer, wizard.n_archive, wizard.n_block, wizard.n_warn),
            (0, 0, 0, 0, 0, 0),
        )
        self.assertEqual(wizard.n_unchanged, plan['unchanged'])
        self.assertFalse(wizard.line_ids)
        self.assertFalse(wizard.issue_ids)
        self.assertFalse(wizard.can_publish)
        with self.assertRaises(publish.PublishError) as ctx:
            publish.apply_plan(self.seed_site, plan)
        self.assertEqual(ctx.exception.code, 'no_changes')

    def test_demo_placements_keep_real_passports(self):
        """Об'єкт з наявним обладнанням, що має паспорт, стоїть на варіанті ЦЬОГО паспорта, а не зведеного."""
        if not self.demo:
            self.skipTest("Немає демо-даних: перевірка лише на копії демо-бази")
        placements = self.env['td.placement'].search([('site_id', '=', self.seed_site.id)])
        checked = 0
        for placement in placements:
            equipment = placement.equipment_id
            if equipment and equipment.td_passport_id:
                self.assertEqual(placement.variant_id.passport_id, equipment.td_passport_id, placement.code)
                checked += 1
        self.assertGreater(checked, 100)
        for code in ('ATS-1', 'BESS', 'CHP', 'COMPRESSOR', 'EF-CHG', 'RV-01', 'LT-OUT-1'):
            placement = placements.filtered(lambda p, c=code: p.code == c)
            self.assertFalse(placement.variant_id.passport_id.role.startswith('scene_'), code)

    def test_demo_unlinked_codes_are_scene_only(self):
        """Усі локації макета прив'язані (UNLOAD-N — до воріт за другим кодом сцени); WASTE — не склад Odoo."""
        if not self.demo:
            self.skipTest("Немає демо-даних: перевірка лише на копії демо-бази")
        from .. import hooks

        report = hooks.run_seed_hook(self.env)
        self.assertEqual(report['unlinked']['locations'], [])
        gate = self.env['stock.location'].search([('td_alias', '=', 'UNLOAD-3')])
        self.assertEqual((gate.td_code, gate.td_site_id), ('DOCK-W3', self.seed_site))
        waste = self.env['td.slot'].search([('site_id', '=', self.seed_site.id), ('code_prefix', '=', 'WASTE')])
        self.assertEqual(waste._f3d_cells(), [])

    def test_plain_db_publish_then_plan_is_empty(self):
        """База без демо-даних: план — лише створення (без оновлень, архівацій, заборон); після публікації порожній."""
        if self.demo:
            self.skipTest("Копія демо-бази: порожній план перевіряє test_demo_unchanged_seed_gives_empty_plan")
        site = self.seed_site
        self.assertTrue(site)
        plan = publish.build_plan(site)
        self.assertEqual([i['message'] for i in plan['issues'] if i['severity'] == 'block'], [])
        kinds = self.kinds(plan)
        self.assertEqual((kinds.get('update', 0), kinds.get('archive', 0)), (0, 0))
        self.assertGreater(kinds.get('create', 0), 600)
        scene = set(
            self.env['td.placement']
            .search([('site_id', '=', site.id), ('variant_id.create_equipment', '=', False)])
            .mapped('code')
        )
        self.assertGreater(len(scene), 100)
        created_eq = {
            line['code']
            for line in plan['lines']
            if line['kind'] == 'create' and line['res_model'] == publish.EQUIPMENT
        }
        self.assertTrue(created_eq)
        self.assertFalse(created_eq & scene, "Об'єкти сцени не створюють maintenance.equipment")
        self.wizard(site).action_confirm()
        again = publish.build_plan(site)
        self.assertPlanEmpty(again)
        self.assertEqual(self.kinds(again), {})
        wizard = self.wizard(site)
        self.assertEqual((wizard.n_create, wizard.n_update, wizard.n_archive_offer, wizard.n_block), (0, 0, 0, 0))
        self.assertFalse(wizard.can_publish)


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestSeedMigration(SeedPublishCase):
    """19.0.1.0.1: старий сід виправляється на місці (`seed.resync_site`), ідемпотентно й лише в стані сіда."""

    def _degrade_to_old_seed(self):
        """Повертає сід до стану 19.0.1.0.0: зведені варіанти й паспорти, вид локацій `stack`, комірка WASTE."""
        site = self.seed_site
        env = self.env(context=dict(self.env.context, f3d_no_touch=True, tracking_disable=True))
        data = seed.normalize_seed(seed.read_seed())
        variants, _skipped = seed.ensure_variants(env, data)
        placements = {p.uid: p for p in env['td.placement'].search([('site_id', '=', site.id)])}
        for item in data['placements']:
            placements[item['uid']].write({'variant_id': variants[item['variant']].id})
        for slot in env['td.slot'].search([('site_id', '=', site.id)]):
            if slot.template == 'floor_stack' and (slot.params or {}).get('code_style') == 'exact':
                slot.write({'params': dict(slot.params, loc_kind='stack'), 'overrides': {}})
        for variant in variants.values():
            variant.create_equipment = True
        snapshot.rebuild_version(site, site.version_ids)

    def test_old_seed_is_fixed_in_place(self):
        if not self.demo:
            self.skipTest("Немає демо-даних: перевірка лише на копії демо-бази")
        site = self.seed_site
        version = site.version_ids
        baseline = snapshot.load_snapshot(version)['baseline']
        self._degrade_to_old_seed()
        old_sha = version.snapshot_sha1
        before = publish.summary(publish.build_plan(site))
        self.assertGreater(before['create'], 30)  # обладнання об'єктів сцени + WASTE
        self.assertGreater(before['update'], 30)  # вид локацій: stack → area/kit
        counts = {
            model: self.env[model].with_context(active_test=False).search_count([])
            for model in ('maintenance.equipment', 'stock.location', 'td.equipment.passport')
        }
        rev = (site.draft_rev, site.published_rev, site.active_version_id)

        report = seed.resync_site(self.env)

        self.assertEqual(report['status'], 'fixed')
        self.assertGreater(report['placements'], 90)
        self.assertGreater(report['slots'], 30)
        self.assertPlanEmpty(publish.build_plan(site))
        self.assertEqual(
            counts,
            {
                model: self.env[model].with_context(active_test=False).search_count([])
                for model in ('maintenance.equipment', 'stock.location', 'td.equipment.passport')
            },
            "Записи Odoo не створюються й не видаляються",
        )
        self.assertEqual(rev, (site.draft_rev, site.published_rev, site.active_version_id))
        self.assertFalse(site.has_changes)
        # знімок v1 перебудовано: збігається з чернеткою, baseline збережено
        self.assertNotEqual(version.snapshot_sha1, old_sha)
        snap = snapshot.load_snapshot(version)
        self.assertEqual(snap['baseline'], baseline)
        self.assertEqual(snapshot.count_differences(snapshot.build_snapshot(site), snap), 0)
        self.assertEqual(version.cell_count, snap['counts']['cells'])
        # повторно: нічого не змінюється
        sha = version.snapshot_sha1
        again = seed.resync_site(self.env)
        self.assertEqual((again['flags'], again['slots'], again['placements']), (0, 0, 0))
        self.assertEqual(version.snapshot_sha1, sha)
        self.assertPlanEmpty(publish.build_plan(site))

    def test_layer_visibility_is_restored(self):
        """Старий сід ігнорував `visible`: усі шари видимі; міграція вимикає дах, інженерні мережі, територію."""
        site = self.seed_site
        env = self.env(context=dict(self.env.context, f3d_no_touch=True, tracking_disable=True))
        data = seed.normalize_seed(seed.read_seed())
        want = {item['uid']: bool(item.get('visible', True)) for item in data['layers']}
        layers = env['td.layer'].with_context(active_test=False).search([('site_id', '=', site.id)])
        layers.write({'visible': True})
        snapshot.rebuild_version(site, site.version_ids)
        report = seed.resync_site(self.env)
        self.assertEqual(report['status'], 'fixed')
        self.assertEqual(report['layers'], sum(1 for visible in want.values() if not visible))
        self.assertEqual({layer.uid: layer.visible for layer in layers}, want)
        self.assertEqual(
            snapshot.count_differences(snapshot.build_snapshot(site), snapshot.load_snapshot(site.version_ids)), 0
        )
        self.assertEqual(seed.resync_site(self.env)['layers'], 0)

    def test_changed_draft_is_not_touched(self):
        site = self.seed_site
        self.assertTrue(site)
        self.assertEqual(seed.resync_site(self.env)['status'], 'fixed')
        placement = self.env['td.placement'].search([('site_id', '=', site.id)], limit=1)
        placement.sudo().with_context(f3d_no_touch=False).write({'name': "Змінено користувачем"})
        self.assertTrue(site.has_changes)
        sha = site.version_ids.snapshot_sha1
        report = seed.resync_site(self.env)
        self.assertEqual(report['status'], 'skipped')
        self.assertEqual(site.version_ids.snapshot_sha1, sha)


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestPublishRules(F3DConstructorCase):
    """Правила плану: прапорець create_equipment, зведений паспорт не перезаписує справжній, alias, вид локації."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('td.constructor.publish_enabled', 'True')
        Passport = cls.env['td.equipment.passport']
        cls.scene_passport = Passport.create(
            {'role': 'scene_test', 'manufacturer': "—", 'model': "Об’єкти сцени · Тест", 'td_category': 'other'}
        )
        cls.scene_variant = cls.env['td.equipment.variant'].create(
            {
                'passport_id': cls.scene_passport.id,
                'name': "Сцена",
                'length_mm': 1000,
                'width_mm': 800,
                'height_mm': 500,
            }
        )
        cls.real_passport = Passport.create(
            {'role': 'real_ats', 'manufacturer': "Socomec", 'model': "ATyS", 'td_category': 'panel'}
        )

    def plan_lines(self, kind, model):
        plan = publish.build_plan(self.site)
        return [line for line in plan['lines'] if line['kind'] == kind and line['res_model'] == model]

    def test_scene_variant_flag_default_and_no_equipment(self):
        self.assertFalse(self.scene_variant.create_equipment)
        self.assertTrue(self.variant.create_equipment)
        self.make_placement(code='TQM-1', variant=self.scene_variant)
        self.make_placement(code='TQM-2', variant=self.variant, x=24.0)
        codes = [line['code'] for line in self.plan_lines('create', publish.EQUIPMENT)]
        self.assertEqual(codes, ['TQM-2'])
        self.scene_variant.create_equipment = True  # свідомо ввімкнено
        codes = [line['code'] for line in self.plan_lines('create', publish.EQUIPMENT)]
        self.assertEqual(sorted(codes), ['TQM-1', 'TQM-2'])

    def test_generic_passport_never_overwrites_existing(self):
        equipment = self.env['maintenance.equipment'].create(
            {'name': "ATS", 'td_code': 'TQM-3', 'td_passport_id': self.real_passport.id}
        )
        empty = self.env['maintenance.equipment'].create({'name': "Без паспорта", 'td_code': 'TQM-4'})
        self.make_placement(code='TQM-3', variant=self.scene_variant)
        self.make_placement(code='TQM-4', variant=self.scene_variant, x=24.0)
        for line in self.plan_lines('update', publish.EQUIPMENT):
            self.assertNotIn('td_passport_id', line['vals'], line['code'])
        self.wizard_confirm()
        self.assertEqual(equipment.td_passport_id, self.real_passport)
        self.assertFalse(empty.td_passport_id)
        # справжній паспорт, відмінний від наявного, лишається пропозицією оновлення (R-12)
        self.make_placement(code='TQM-5', variant=self.variant, x=28.0)
        other = self.env['maintenance.equipment'].create(
            {'name': "Інший", 'td_code': 'TQM-5', 'td_passport_id': self.real_passport.id}
        )
        lines = self.plan_lines('update', publish.EQUIPMENT)
        self.assertEqual(
            [(line['code'], line['vals']['td_passport_id']) for line in lines if line['code'] == 'TQM-5'],
            [('TQM-5', self.passport.id)],
        )
        self.assertEqual(other.td_passport_id, self.real_passport)

    def wizard_confirm(self):
        action = self.site.with_user(self.u_manager).action_publish_wizard()
        wizard = self.env['td.publish.wizard'].with_user(self.u_manager).browse(action['res_id'])
        wizard.action_confirm()

    def test_existing_equipment_zone_is_not_changed(self):
        existing = self.env['maintenance.equipment'].create({'name': "Старий", 'td_code': 'TQM-6'})
        self.make_placement(code='TQM-6', variant=self.variant)
        self.wizard_confirm()
        self.assertFalse(existing.td_zone_id)  # зону наявного обладнання задає каталог base, не публікація

    def test_second_scene_code_alias_is_not_a_conflict(self):
        """Ворота DOCK-T1 = майданчик UNL-T1 (td_alias): місце UNL-T1 зв'язується з ними, без конфлікту й архівації."""
        gate = self.env['stock.location'].create(
            {
                'name': "Ворота T1",
                'usage': 'internal',
                'location_id': self.wh_stock.id,
                'barcode': 'UNL-T1',
                'td_code': 'DOCK-T1',
                'td_alias': 'UNL-T1',
                'td_loc_kind': 'area',
            }
        )
        gate.sudo().write({'td_site_id': self.site.id})
        slot = self.make_slot(
            prefix='UNL-T1', template='floor_stack', rows=1, cols=1, cell_l=3.0, cell_w=2.0, max_height=1.0,
            code_style='exact', loc_kind='area',
        )  # fmt: skip
        slot.parent_location_id = False
        plan = publish.build_plan(self.site)
        self.assertEqual([i for i in plan['issues'] if i['check'] == 'conflict'], [])
        self.assertEqual([line['code'] for line in plan['lines'] if line['res_model'] == publish.LOCATION], ['UNL-T1'])
        self.assertEqual(self.plan_lines('archive', publish.LOCATION), [])
        # kind 'area' збігається з локацією; різні види — оновлення
        update = self.plan_lines('update', publish.LOCATION)
        self.assertEqual([line['vals'] for line in update], [{'td_slot_uid': slot.uid}])
        slot.params = dict(slot.params, loc_kind='kit')
        update = self.plan_lines('update', publish.LOCATION)
        self.assertEqual(update[0]['vals']['td_loc_kind'], 'kit')

    def test_barcode_with_other_scene_code_is_still_a_conflict(self):
        self.env['stock.location'].create(
            {
                'name': "Чужі ворота",
                'usage': 'internal',
                'location_id': self.wh_stock.id,
                'barcode': 'UNL-T2',
                'td_code': 'DOCK-T2',
            }
        )
        self.make_slot(
            prefix='UNL-T2', template='floor_stack', rows=1, cols=1, cell_l=3.0, cell_w=2.0, max_height=1.0,
            code_style='exact',
        )  # fmt: skip
        plan = publish.build_plan(self.site)
        self.assertEqual([i['check'] for i in plan['issues'] if i['severity'] == 'block'], ['conflict'])

    def test_floor_stack_loc_kind_param(self):
        params = {'rows': 1, 'cols': 1, 'code_style': 'exact'}
        self.assertEqual(cells.generate_cells('floor_stack', 'AB-1', 0, 0, 0, params)[0]['kind'], 'stack')
        for kind in ('area', 'kit'):
            found = cells.generate_cells('floor_stack', 'AB-1', 0, 0, 0, dict(params, loc_kind=kind))
            self.assertEqual(found[0]['kind'], kind)
        with self.assertRaises(cells.CellsError):
            cells.normalize_params('floor_stack', dict(params, loc_kind='nope'))
        with self.assertRaises(ValidationError):
            self.make_slot(prefix='AB-2', template='floor_stack', loc_kind='nope')

    def test_seed_variant_of_the_equipment_passport(self):
        """Сід: розміщення з наявним обладнанням, що має паспорт, отримує варіант ЦЬОГО паспорта (геометрія та сама)."""
        self.env['maintenance.equipment'].create(
            {'name': "ATS", 'td_code': 'TQM-7', 'td_passport_id': self.real_passport.id}
        )
        data = {
            'placements': [
                {'uid': 'u7', 'code': 'TQM-7', 'variant': 'k'},
                {'uid': 'u8', 'code': 'TQM-8', 'variant': 'k'},
            ]
        }
        found = seed.placement_variants(self.env, data, {'k': self.scene_variant})
        variant = found['u7']
        self.assertEqual(variant.passport_id, self.real_passport)
        self.assertEqual((variant.length_mm, variant.width_mm), (1000, 800))
        self.assertTrue(variant.create_equipment)
        self.assertEqual(found['u8'], self.scene_variant)  # обладнання немає — зведений варіант
        again = seed.placement_variants(self.env, data, {'k': self.scene_variant})
        self.assertEqual(again['u7'], variant)  # повторно той самий варіант, без дублів
