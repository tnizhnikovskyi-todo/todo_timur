from unittest.mock import patch

from odoo.tests import tagged
from odoo.tools import mute_logger

from ..services import publish
from .common import F3DConstructorCase


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestPublish(F3DConstructorCase):
    """AC-06, AC-30 (публікація), AC-50…AC-57: R-12, R-13."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('factory3d.constructor.publish_enabled', 'True')

    # --- помічники ---------------------------------------------------------------------------------
    def wizard(self, site=None, user=None):
        site = (site or self.site).with_user(user or self.u_manager)
        action = site.action_publish_wizard()
        return self.env['f3d.publish.wizard'].with_user(user or self.u_manager).browse(action['res_id'])

    def publish(self, site=None, note='', tick=()):
        """Повний шлях користувача: майстер → відмітити архівацію → підтвердити."""
        wizard = self.wizard(site)
        for line in wizard.line_ids:
            if line.kind == 'archive' and (line.code in tick):
                line.selected = True
        wizard.note = note
        wizard.action_confirm()
        return wizard

    def count(self, model):
        return self.env[model].with_context(active_test=False).search_count([])

    def rack(self, prefix='TQ-R1', bays=18, levels=4, **kw):
        return self.make_slot(prefix=prefix, x=30.0, y=10.0, bays=bays, levels=levels, **kw)

    # --- AC-50 -------------------------------------------------------------------------------------
    def test_ac50_preview_changes_nothing(self):
        self.rack(bays=4, levels=2)
        self.make_placement(code='TQM-1')
        before = (self.count('stock.location'), self.count('maintenance.equipment'), self.count('mrp.workcenter'))
        wizard = self.wizard()
        self.assertEqual(wizard.n_create, 8 + 1 + 1)  # 8 комірок + обладнання + робочий центр
        self.assertEqual((wizard.n_update, wizard.n_archive_offer), (0, 0))
        self.assertTrue(wizard.can_publish)
        self.assertEqual(
            before, (self.count('stock.location'), self.count('maintenance.equipment'), self.count('mrp.workcenter'))
        )
        self.assertEqual(wizard.state, 'preview')

    def test_ac50_plan_create_update_archive(self):
        slot_a = self.rack('AA-R1', bays=2, levels=1)
        placement = self.make_placement(code='TQM-1')
        self.publish()
        passport2 = self.env['f3d.equipment.passport'].create(
            {'role': 'other_machine', 'manufacturer': "Т", 'model': "Інший"}
        )
        variant2 = self.env['f3d.equipment.variant'].create(
            {'passport_id': passport2.id, 'name': "В2", 'length_mm': 2000, 'width_mm': 1000, 'height_mm': 1500}
        )
        placement.variant_id = variant2  # змінене розміщення
        slot_a.unlink()  # видалене місце
        self.rack('BB-R1', bays=3, levels=1)  # новий ряд
        wizard = self.wizard()
        kinds = {}
        for line in wizard.line_ids:
            kinds.setdefault((line.kind, line.res_model), []).append(line.code)
        self.assertEqual(len(kinds[('create', 'stock.location')]), 3)
        self.assertEqual(kinds[('update', 'maintenance.equipment')], ['TQM-1'])
        self.assertEqual(sorted(kinds[('archive', 'stock.location')]), ['AA-R1-B01-L1', 'AA-R1-B02-L1'])
        self.assertTrue(all(not line.selected for line in wizard.line_ids if line.kind == 'archive'))

    # --- AC-51 / AC-52 -----------------------------------------------------------------------------
    def test_ac51_creates_72_locations(self):
        self.rack()
        before = self.count('stock.location')
        wizard = self.publish()
        self.assertEqual(self.count('stock.location'), before + 72)
        loc = self.env['stock.location'].search([('f3d_code', '=', 'TQ-R1-B01-L1')])
        self.assertEqual(
            (loc.barcode, loc.usage, loc.f3d_loc_kind, loc.f3d_capacity), ('TQ-R1-B01-L1', 'internal', 'pallet_cell', 3)
        )
        slot = self.env['f3d.slot'].search([('site_id', '=', self.site.id)])
        self.assertEqual((loc.location_id, loc.f3d_site_id, loc.f3d_slot_uid), (self.wh_fg, self.site, slot.uid))
        self.assertEqual(wizard.state, 'done')
        self.assertEqual(wizard.version_id.n, 1)
        self.assertEqual(wizard.version_id.created_count, 72)

    def test_ac52_matches_existing_by_barcode_no_duplicates(self):
        self.rack().parent_location_id = self.wh_stock
        existing = self.env['stock.location'].create(
            {'name': 'TQ-R1-B01-L4', 'barcode': 'TQ-R1-B01-L4', 'usage': 'internal', 'location_id': self.wh_stock.id}
        )
        before = self.count('stock.location')
        self.publish()
        self.assertEqual(self.count('stock.location'), before + 71)
        self.assertEqual(
            (existing.f3d_code, existing.f3d_site_id, existing.name), ('TQ-R1-B01-L4', self.site, 'TQ-R1-B01-L4')
        )
        self.assertEqual(existing.location_id, self.wh_stock)  # батьківська локація існуючого запису не змінюється
        plan = publish.build_plan(self.site)
        with self.assertRaises(publish.PublishError) as ctx:
            publish.apply_plan(self.site.with_user(self.u_manager), plan, (), '')
        self.assertEqual(ctx.exception.code, 'no_changes')
        self.assertEqual(self.count('stock.location'), before + 71)

    # --- AC-53 -------------------------------------------------------------------------------------
    def test_ac53_equipment_and_workcenter(self):
        placement = self.make_placement(code='TQM-9', x=20.0, y=10.0)
        existing_wc = self.env['mrp.workcenter'].create({'name': "Існуючий ЦП", 'code': 'TQM-9'})
        self.publish()
        eq = self.env['maintenance.equipment'].search([('f3d_code', '=', 'TQM-9')])
        self.assertEqual(len(eq), 1)
        self.assertEqual(
            (eq.f3d_passport_id, eq.f3d_site_id, eq.f3d_placement_uid), (self.passport, self.site, placement.uid)
        )
        zone = self.env['f3d.zone'].zone_at(20.0, 10.0, self.company)
        self.assertEqual(eq.f3d_zone_id, zone)
        self.assertEqual(placement.equipment_id, eq)
        self.assertEqual(placement.workcenter_id, existing_wc)  # збіг за code — не дублюється
        self.assertEqual(existing_wc.f3d_code, 'TQM-9')
        self.assertTrue(placement.published_at)
        self.assertEqual(self.env['mrp.workcenter'].search_count([('code', '=', 'TQM-9')]), 1)

    def test_ac53_existing_equipment_only_updated(self):
        existing = self.env['maintenance.equipment'].create({'name': "Старий", 'f3d_code': 'TQM-8'})
        before = self.count('maintenance.equipment')
        self.make_placement(code='TQM-8')
        self.publish()
        self.assertEqual(self.count('maintenance.equipment'), before)
        self.assertEqual(
            (existing.f3d_site_id, existing.f3d_passport_id, existing.name), (self.site, self.passport, "Старий")
        )

    # --- AC-54 -------------------------------------------------------------------------------------
    def test_ac54_archive_is_only_a_proposal(self):
        slot = self.rack('AR-R1', bays=2, levels=1)
        self.publish()
        foreign = self.env['stock.location'].create({'name': 'ЧУЖА-1', 'barcode': 'ЧУЖА-1', 'usage': 'internal'})
        slot.unlink()
        wizard = self.wizard()
        archive = wizard.line_ids.filtered(lambda r: r.kind == 'archive')
        self.assertEqual(sorted(archive.mapped('code')), ['AR-R1-B01-L1', 'AR-R1-B02-L1'])
        self.assertTrue(all(not r.selected for r in archive))
        self.assertNotIn(foreign.id, archive.mapped('res_id'))
        wizard.action_confirm()
        locs = self.env['stock.location'].search([('f3d_code', 'like', 'AR-R1-%')])
        self.assertEqual(len(locs), 2)
        self.assertTrue(all(locs.mapped('active')))  # без галочки — лишається активним
        # повторно: відмітити одну пропозицію
        self.site.sudo().write({'draft_rev': self.site.draft_rev + 1})  # імітація правки чернетки
        wizard = self.wizard()
        wizard.line_ids.filtered(lambda r: r.code == 'AR-R1-B01-L1').selected = True
        wizard.action_confirm()
        self.assertFalse(
            self.env['stock.location']
            .with_context(active_test=False)
            .search([('f3d_code', '=', 'AR-R1-B01-L1')])
            .active
        )
        self.assertTrue(self.env['stock.location'].search([('f3d_code', '=', 'AR-R1-B02-L1')]).active)
        self.assertTrue(
            self.env['stock.location']
            .with_context(active_test=False)
            .search([('f3d_code', '=', 'AR-R1-B01-L1')])
            .exists()
        )

    def test_ac54_stock_blocks_archive(self):
        slot = self.rack('BL-R1', bays=1, levels=1)
        self.publish()
        loc = self.env['stock.location'].search([('f3d_code', '=', 'BL-R1-B01-L1')])
        product = self.env['product.product'].create({'name': "Тестовий товар", 'is_storable': True})
        self.env['stock.quant']._update_available_quantity(product, loc, 12.0)
        slot.unlink()
        wizard = self.wizard()
        line = wizard.line_ids.filtered(lambda r: r.kind == 'archive')
        self.assertTrue(line.blocked)
        self.assertIn("Є залишки", line.blocked_reason)
        line.selected = True  # навіть із галочкою заблокований запис не архівується
        wizard.action_confirm()
        self.assertTrue(loc.active)

    # --- AC-55, AC-56 ------------------------------------------------------------------------------
    def test_ac55_stop_valve(self):
        self.rack(bays=2, levels=1)
        self.env['ir.config_parameter'].sudo().set_param('factory3d.constructor.publish_enabled', 'False')
        wizard = self.wizard()
        self.assertFalse(wizard.can_publish)
        before = self.count('stock.location')
        with self.assertRaises(publish.PublishError) as ctx:
            wizard.action_confirm()
        self.assertEqual(ctx.exception.code, 'disabled')
        self.assertEqual(self.count('stock.location'), before)

    def test_ac56_rights(self):
        self.rack(bays=2, levels=1)
        from odoo.exceptions import AccessError

        for user in (self.u_tech, self.u_store, self.u_eng):
            with self.subTest(user=user.login):
                with self.assertRaises(AccessError):
                    self.site.with_user(user).action_publish_wizard()
                with self.assertRaises(publish.PublishError) as ctx:
                    publish.apply_plan(self.site.with_user(user), publish.build_plan(self.site), (), '')
                self.assertEqual(ctx.exception.code, 'rights')
        self.publish()  # менеджер — успіх

    # --- AC-57 -------------------------------------------------------------------------------------
    def test_ac57_rollback_on_failure(self):
        self.rack(bays=20, levels=2)
        StockLocation = type(self.env['stock.location'])
        original = StockLocation.create

        def failing_create(self_, vals_list):
            original(self_, vals_list[:39])
            raise ValueError("штучна помилка на 40-й локації")

        before = (self.count('stock.location'), self.count('f3d.layout.version'))
        plan = publish.build_plan(self.site)
        with (
            patch.object(StockLocation, 'create', failing_create),
            mute_logger('odoo.addons.factory3d_constructor.services.publish'),
        ):
            with self.assertRaises(publish.PublishError) as ctx:
                publish.apply_plan(self.site.with_user(self.u_manager), plan, (), '')
        self.assertEqual(ctx.exception.code, 'rollback')
        self.assertEqual((self.count('stock.location'), self.count('f3d.layout.version')), before)
        self.assertFalse(self.env['stock.location'].search([('f3d_site_id', '=', self.site.id)]))
        self.assertFalse(self.site.active_version_id)

    # --- AC-06 -------------------------------------------------------------------------------------
    def test_ac06_same_prefix_on_two_sites(self):
        site2 = (
            self.env['f3d.site']
            .with_context(f3d_blank=True)
            .create({'name': "Друга", 'code': 'TS2', 'default_parent_location_id': self.wh_stock.id})
        )
        layer2 = site2.layer_ids.filtered(lambda r: r.kind == 'storage')
        self.make_slot(prefix='AA', bays=2, levels=1)
        self.env['f3d.slot'].create(
            {
                'layer_id': layer2.id,
                'template': 'pallet_rack',
                'code_prefix': 'AA',
                'x_m': 30.0,
                'y_m': 10.0,
                'params': {'bays': 2, 'levels': 1},
                'parent_location_id': self.wh_fg.id,
            }
        )
        self.publish()
        plan = publish.build_plan(site2)
        conflicts = [i for i in plan['issues'] if i['check'] == 'conflict' and i['severity'] == 'block']
        self.assertTrue(conflicts)
        self.assertIn("зайнятий записом площадки", conflicts[0]['message'])
        with self.assertRaises(publish.PublishError) as ctx:
            publish.apply_plan(site2.with_user(self.u_manager), plan, (), '')
        self.assertEqual(ctx.exception.code, 'conflict_codes')

    # --- AC-30 -------------------------------------------------------------------------------------
    def test_ac30_modes_in_publication(self):
        generic = self.env.ref('factory3d_constructor.variant_generic_panel')
        self.make_placement(kind='yard', code='AA-1', x=10.0, y=10.0, variant=generic)
        self.make_placement(kind='yard', code='AA-2', x=10.4, y=10.0, variant=generic)
        collide = self.site.check_config_ids.filtered(lambda c: c.check_key == 'collide')
        for key in ('fits', 'service_free', 'utility_reach'):
            self.site.check_config_ids.filtered(lambda c, k=key: c.check_key == k).enabled = False
        collide.mode = 'block'
        with self.assertRaises(publish.PublishError) as ctx:
            publish.apply_plan(self.site.with_user(self.u_manager), publish.build_plan(self.site), (), '')
        self.assertEqual(ctx.exception.code, 'blocked')
        self.assertFalse(self.site.version_ids)
        collide.mode = 'warn'
        wizard = self.publish()
        self.assertTrue(any(i['check'] == 'collide' for i in wizard.version_id.report['warnings']))
        collide.enabled = False
        self.assertFalse([i for i in publish.build_plan(self.site)['issues'] if i['check'] == 'collide'])

    # --- продуктивність (§13.4) -----------------------------------------------------------------------
    def test_perf_publish_360_cells(self):
        import time

        for i in range(1, 6):
            self.make_slot(prefix='PF-R%d' % i, x=30.0, y=2.0 + 2.2 * i, bays=18, levels=4)
        started = time.time()
        wizard = self.wizard()
        self.assertEqual(wizard.n_create, 360)
        self.assertEqual(wizard.n_block, 0)
        wizard.action_confirm()
        self.assertLess(time.time() - started, 20)
        self.assertEqual(self.env['stock.location'].search_count([('f3d_site_id', '=', self.site.id)]), 360)

    def test_unticked_create_line_is_skipped(self):
        self.rack('UT-R1', bays=2, levels=1)
        wizard = self.wizard()
        skipped = wizard.line_ids.filtered(lambda r: r.code == 'UT-R1-B02-L1')
        skipped.selected = False
        wizard.action_confirm()
        codes = self.env['stock.location'].search([('f3d_site_id', '=', self.site.id)]).mapped('f3d_code')
        self.assertEqual(sorted(codes), ['UT-R1-B01-L1'])
