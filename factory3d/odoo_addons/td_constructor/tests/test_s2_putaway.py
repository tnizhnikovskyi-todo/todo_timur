from odoo.tests import tagged

from ..services import capacity, checks, publish, putaway, snapshot, state as state_mod
from ..services.registry import CHECKS, PLAN_BUILDERS, SNAPSHOT_SECTIONS
from .common import F3DConstructorCase, F3DConstructorHttpCase, PASSWORD
from .test_s2_capacity import S2Mixin


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s2")
class TestS2Putaway(S2Mixin, F3DConstructorCase):
    """S2, F04: правила розміщення → stock.putaway.rule, «куди покладе Odoo», «чи вміститься» (putaway_fit)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('td.constructor.publish_enabled', 'True')

    def rule(self, product=None, out_code='PW-R1-B01-L1', **vals):
        data = {'site_id': self.site.id, 'out_code': out_code, 'in_location_id': self.wh_stock.id}
        if product is not False:
            data['product_id'] = (product or self.product()).id
        return self.env['td.putaway.rule'].create(dict(data, **vals))

    # --- план і застосування ----------------------------------------------------------------------------
    def test_rule_to_unpublished_cell_depends_on_its_creation(self):
        slot = self.make_slot(prefix='PW-R1', bays=2, levels=1)
        product = self.product()
        rule = self.rule(product, sequence=5)
        plan = self.plan()
        line = self.lines(plan, 'create', publish.PUTAWAY)[0]
        self.assertEqual((line['depends_code'], line['scope_uid']), ('PW-R1-B01-L1', slot.uid))
        self.assertEqual(
            (line['vals']['product_id'], line['vals']['location_in_id'], line['vals']['sequence']),
            (product.id, self.wh_stock.id, 5),
        )
        self.assertNotIn('location_out_id', line['vals'])  # ціль ще не існує: id підставить застосування
        result = self.apply(plan)
        odoo_rule = rule.odoo_rule_id
        self.assertEqual(
            (odoo_rule.product_id, odoo_rule.location_in_id, odoo_rule.location_out_id),
            (product, self.wh_stock, self.loc('PW-R1-B01-L1')),
        )
        self.assertEqual((odoo_rule.sequence, odoo_rule.sublocation, odoo_rule.company_id), (5, 'no', self.company))
        ops = result['version'].op_ids.filtered(lambda o: o.res_model == publish.PUTAWAY)
        self.assertEqual((ops.op, ops.res_id), ('create', odoo_rule.id))
        self.assertEqual(self.plan()['lines'], [])  # ідемпотентно

    def test_rule_update_package_types_and_delete(self):
        self.make_slot(prefix='PW-R1', bays=2, levels=1)
        rule = self.rule()
        self.apply()
        odoo_rule = rule.odoo_rule_id
        pallet = self.env['stock.package.type'].create(
            {'name': "Палета S2", 'packaging_length': 1200, 'width': 800, 'height': 150}
        )
        rule.write({'package_type_ids': [(6, 0, pallet.ids)], 'sequence': 1, 'out_code': 'PW-R1-B02-L1'})
        attrs = self.lines(self.plan(), 'attrs', publish.PUTAWAY)[0]
        self.assertEqual(attrs['vals']['package_type_ids'], pallet.ids)
        self.assertEqual(attrs['vals']['location_out_id'], self.loc('PW-R1-B02-L1').id)
        self.assertIn("Палета S2", attrs['changes'])
        version = self.apply()['version']
        self.assertEqual(
            (odoo_rule.package_type_ids, odoo_rule.sequence, odoo_rule.location_out_id.td_code),
            (pallet, 1, 'PW-R1-B02-L1'),
        )
        self.assertEqual(self.plan()['lines'], [])
        # відкат повертає й набір упаковок
        publish.rollback_version(self.site.with_user(self.u_manager), version)
        self.assertEqual(
            (odoo_rule.package_type_ids.ids, odoo_rule.sequence, odoo_rule.location_out_id.td_code),
            ([], 10, 'PW-R1-B01-L1'),
        )
        rule.deleted = True
        archive = self.lines(self.plan(), 'archive', publish.PUTAWAY)
        self.assertTrue(archive[0]['selected'])
        self.apply()
        self.assertFalse(odoo_rule.active)

    def test_rule_links_identical_existing_odoo_rule(self):
        self.make_slot(prefix='PW-R1', bays=1, levels=1)
        self.apply()
        product = self.product()
        existing = self.env['stock.putaway.rule'].create(
            {
                'product_id': product.id,
                'location_in_id': self.wh_stock.id,
                'location_out_id': self.loc('PW-R1-B01-L1').id,
            }
        )
        rule = self.rule(product, sequence=existing.sequence)
        line = self.lines(self.plan(), 'attrs', publish.PUTAWAY)[0]
        self.assertEqual(
            (line['res_id'], line['vals'], line['changes']), (existing.id, {}, "зв'язати з наявним правилом")
        )
        before = self.env['stock.putaway.rule'].search_count([])
        self.apply()
        self.assertEqual((rule.odoo_rule_id, self.env['stock.putaway.rule'].search_count([])), (existing, before))

    def test_incomplete_rules_are_blocked_not_published(self):
        self.make_slot(prefix='PW-R1', bays=1, levels=1)
        self.rule(False)  # ні товару, ні категорії
        self.rule(self.product(), out_code='НЕМА-ТАКОЇ')
        plan = self.plan()
        blocked = self.lines(plan, 'create', publish.PUTAWAY)
        self.assertEqual(len(blocked), 2)
        self.assertTrue(all(ln['blocked'] for ln in blocked))
        self.assertEqual(
            {tuple(i['codes']) for i in plan['issues'] if "Правило розміщення" in i['message']},
            {('PW-R1-B01-L1',), ('НЕМА-ТАКОЇ',)},
        )
        before = self.env['stock.putaway.rule'].search_count([])
        self.apply(plan)
        self.assertEqual(self.env['stock.putaway.rule'].search_count([]), before)

    def test_closest_location_keeps_storage_category(self):
        self.make_slot(prefix='PW-R1', bays=2, levels=1)
        cat = capacity.save_category(self.env, self.company, {'name': "Палетна S2", 'max_weight': 900})
        self.rule(self.product(), out_code='PW-R1-B01-L1', sublocation='closest_location', storage_category_id=cat.id)
        line = self.lines(self.plan(), 'create', publish.PUTAWAY)[0]
        self.assertEqual(
            (line['vals']['sublocation'], line['vals']['storage_category_id']), ('closest_location', cat.id)
        )
        # без «найближчої» категорію не передаємо (Odoo її обнуляє)
        self.env['td.putaway.rule'].search([]).write({'sublocation': 'no'})
        self.assertFalse(self.lines(self.plan(), 'create', publish.PUTAWAY)[0]['vals']['storage_category_id'])

    # --- куди покладе Odoo ------------------------------------------------------------------------------
    def test_where_uses_only_applied_rules(self):
        self.make_slot(prefix='PW-R1', bays=2, levels=1)
        product = self.product(weight=5)
        rule = self.rule(product)
        stock = self.wh_stock
        first = putaway.where(self.env, self.site, product, 1, stock)
        self.assertFalse(first['moved'])  # правило лише в чернетці: Odoo про нього не знає
        self.apply()
        res = putaway.where(self.env, self.site, product, 1, stock)
        self.assertTrue(res['moved'])
        self.assertEqual(
            (res['location']['code'], res['location']['id']), ('PW-R1-B01-L1', rule.odoo_rule_id.location_out_id.id)
        )
        other = self.product("Інший")
        self.assertFalse(putaway.where(self.env, self.site, other, 1, stock)['moved'])

    # --- чи вміститься ------------------------------------------------------------------------------------
    def test_fit_problems_pure(self):
        cell = {'l': 2.7, 'w': 1.1, 'h': 1.5}
        self.assertEqual(putaway.fit_problems({'weight_kg': 100, 'volume_m3': 1.0}, cell, 1000), [])
        self.assertEqual(len(putaway.fit_problems({'weight_kg': 1500}, cell, 1000)), 1)
        self.assertEqual(len(putaway.fit_problems({'volume_m3': 5.0}, cell, 1000)), 1)
        self.assertEqual(putaway.fit_problems({}, cell, 0), [])  # невідоме пропускається
        self.assertEqual(putaway.fit_problems({'weight_kg': 5000}, cell, 0), [])  # межа ваги невідома
        # упаковка: габарити з поворотом (2.5×1.0×1.4 вміщується, 3.0×1.0×1.0 — ні), вага упаковки проти межі
        fits = {'packages': [{'name': 'А', 'dims_m': [1.4, 2.5, 1.0], 'max_weight_kg': 800}]}
        self.assertEqual(putaway.fit_problems(fits, cell, 1000), [])
        long = {'packages': [{'name': 'Б', 'dims_m': [3.0, 1.0, 1.0], 'max_weight_kg': 1200}]}
        self.assertEqual(len(putaway.fit_problems(long, cell, 1000)), 2)

    def prepare_fit_rules(self):
        self.make_slot(prefix='PW-R1', bays=2, levels=1, max_load_kg=1000)
        heavy = self.product("Важкий", weight=1500, volume=9.0)
        ok = self.product("Звичайний", weight=20, volume=0.5)
        pallet = self.env['stock.package.type'].create(
            {'name': "Довга", 'packaging_length': 3500, 'width': 800, 'height': 800, 'max_weight': 300}
        )
        bad = self.rule(heavy, out_code='PW-R1-B01-L1')
        fine = self.rule(ok, out_code='PW-R1-B02-L1')
        packed = self.rule(ok, out_code='PW-R1-B02-L1', package_type_ids=[(6, 0, pallet.ids)])
        return bad, fine, packed

    def test_rule_fit_inputs_check_and_plan_issue(self):
        bad, fine, packed = self.prepare_fit_rules()
        inputs = {i['uid']: i for i in putaway.rule_fit_inputs(self.site)}
        self.assertEqual(inputs[bad.uid]['weight_kg'], 1500)
        for got, want in zip(inputs[packed.uid]['packages'][0]['dims_m'], [3.5, 0.8, 0.8], strict=True):
            self.assertAlmostEqual(got, want)
        fit = putaway.fit_rules(self.site)
        self.assertEqual(set(fit), {bad.uid, packed.uid})
        self.assertEqual({r['code'] for r in fit[bad.uid]}, {'PW-R1-B01-L1'})
        self.assertEqual(len(fit[bad.uid]), 2)  # вага й об'єм
        # перевірка не налаштована — зауважень у плані немає; налаштована — «Правило: не вміститься»
        self.assertFalse([i for i in self.plan()['issues'] if i['check'] == 'putaway_fit'])
        self.enable_check('putaway_fit', 'warn')
        issues = [i for i in self.plan()['issues'] if i['check'] == 'putaway_fit']
        self.assertEqual(len(issues), 3)
        self.assertTrue(all("не вміститься" in i['message'] and i['severity'] == 'warn' for i in issues))
        self.enable_check('putaway_fit', 'block')
        with self.assertRaises(publish.PublishError) as ctx:
            self.apply()
        self.assertEqual(ctx.exception.code, 'blocked')
        # живий API-05 даних БД не має
        self.assertEqual(
            checks.run_checks(
                state_mod.checks_state(self.site),
                [{'check': 'putaway_fit', 'enabled': True, 'mode': 'warn', 'params': {}}],
            ),
            [],
        )
        self.assertIn('putaway_fit', CHECKS)

    def test_item_units_follow_odoo_configuration(self):
        product = self.product(weight=10, volume=2.0)
        self.assertEqual(putaway.item_of(self.env, product, self.env['stock.package.type'])['weight_kg'], 10)
        self.env['ir.config_parameter'].sudo().set_param('product.weight_in_lbs', '1')
        self.assertAlmostEqual(
            putaway.item_of(self.env, product, self.env['stock.package.type'])['weight_kg'], 4.5359237, places=5
        )

    # --- код-конфлікт як перевірка ---------------------------------------------------------------------------
    def test_code_conflict_check_with_data(self):
        self.make_slot(prefix='PW-R1', bays=2, levels=1)
        self.env['stock.location'].create({'name': 'Зайнята', 'barcode': 'PW-R1-B01-L1', 'usage': 'customer'})
        self.enable_check('code_conflict', 'warn')
        scene = capacity.plan_check_scene(self.site, {})
        codes = [c for slot in scene.slots.values() for c in scene.slot_cells(slot)]
        scene.extra = {'code_states': publish.code_states(self.env, self.site, codes)}
        config = {'check': 'code_conflict', 'enabled': True, 'mode': 'block', 'params': {}}
        issues = publish.check_code_conflict(scene, config, 0.001)
        self.assertEqual([(i['codes'], i['severity']) for i in issues], [(['PW-R1-B01-L1'], 'block')])
        self.assertEqual(publish.check_code_conflict(capacity.plan_check_scene(self.site, {}), config, 0.001), [])
        self.assertIn('code_conflict', CHECKS)
        # у плані зауваження про зайнятий штрихкод слідує налаштуванню: блокує, коли режим block
        self.enable_check('code_conflict', 'block')
        plan = self.plan()
        self.assertTrue([i for i in plan['issues'] if i['check'] == 'code_conflict' and i['severity'] == 'block'])
        with self.assertRaises(publish.PublishError):
            self.apply(plan)

    # --- знімок ---------------------------------------------------------------------------------------------
    def test_putaway_rules_are_part_of_snapshot_and_restore(self):
        self.make_slot(prefix='PW-R1', bays=1, levels=1)
        self.assertIn('putaway_rules', SNAPSHOT_SECTIONS)
        self.assertIn('putaway', PLAN_BUILDERS)
        pallet = self.env['stock.package.type'].create({'name': "Палета снимка"})
        rule = self.rule(package_type_ids=[(6, 0, pallet.ids)])
        first = self.apply()['version']
        snap = snapshot.load_snapshot(first)
        item = snap['sections']['putaway_rules'][0]
        self.assertEqual(
            (item['uid'], item['package_type_ids'], item['out_code']), (rule.uid, pallet.ids, 'PW-R1-B01-L1')
        )
        rule.write({'sequence': 99, 'package_type_ids': [(5, 0, 0)]})
        extra = self.rule(out_code='PW-R1-B01-L1')
        snapshot.restore_draft(first)
        self.assertEqual((rule.sequence, rule.package_type_ids), (10, pallet))
        self.assertFalse(extra.exists())
        self.assertEqual(rule.odoo_rule_id.sequence, 10)  # зв'язок із Odoo зберігається


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s2")
class TestS2PutawayApi(S2Mixin, F3DConstructorHttpCase):
    """API-15: `where` і `fit`."""

    def test_where_and_fit_routes(self):
        self.env['ir.config_parameter'].sudo().set_param('td.constructor.publish_enabled', 'True')
        self.make_slot(prefix='PA-R1', bays=2, levels=1, max_load_kg=1000)
        product = self.product(weight=1200, volume=1.0)
        rule = self.env['td.putaway.rule'].create(
            {
                'site_id': self.site.id,
                'product_id': product.id,
                'out_code': 'PA-R1-B01-L1',
                'in_location_id': self.wh_stock.id,
            }
        )
        self.authenticate(self.u_store.login, PASSWORD)
        none = self.rpc(
            '/f3d/constructor/putaway/where', site_id=self.site.id, product_id=product.id, location_id=self.wh_stock.id
        )
        self.assertEqual((none['ok'], none['moved'], none['estimate']), (True, False, False))
        publish.apply_plan(self.site.with_user(self.u_manager), publish.build_plan(self.site), (), '')
        res = self.rpc(
            '/f3d/constructor/putaway/where', site_id=self.site.id, product_id=product.id, location_id=self.wh_stock.id
        )
        self.assertEqual((res['moved'], res['location']['code']), (True, 'PA-R1-B01-L1'))
        res = self.rpc(
            '/f3d/constructor/putaway/where', site_id=self.site.id, product_id=product.id, location_code='НЕМА'
        )
        self.assertEqual(res['code'], 'not_found')
        self.assertEqual(
            self.rpc('/f3d/constructor/putaway/where', site_id=self.site.id, product_id=0)['code'], 'validation'
        )
        self.assertEqual(
            self.rpc('/f3d/constructor/putaway/where', site_id=99999, product_id=product.id)['code'], 'not_found'
        )
        fit = self.rpc('/f3d/constructor/putaway/fit', site_id=self.site.id)
        self.assertEqual(list(fit['rules']), [rule.uid])
        self.assertIn("1200", fit['rules'][rule.uid][0]['reason'])
        items = self.rpc(
            '/f3d/constructor/putaway/fit', site_id=self.site.id, product_id=product.id, codes=['PA-R1-B01-L1', 'НЕМА']
        )
        self.assertEqual(list(items['items']), ['PA-R1-B01-L1'])
        self.assertTrue(items['items']['PA-R1-B01-L1'])
        self.assertEqual(
            self.rpc('/f3d/constructor/putaway/fit', site_id=self.site.id, product_id=product.id, codes='x')['code'],
            'validation',
        )
        self.assertEqual(
            self.rpc('/f3d/constructor/putaway/fit', site_id=self.site.id, codes=['A'])['code'], 'validation'
        )
