from odoo.tests import tagged
from odoo.tools import mute_logger

from ..services import capacity, checks, publish, snapshot, state as state_mod
from ..services.registry import CHECKS, PLAN_BUILDERS, SNAPSHOT_SECTIONS
from .common import F3DConstructorCase, F3DConstructorHttpCase, PASSWORD


class S2Mixin:
    """Помічники S2: план, застосування, пошук локацій, товар."""

    def plan(self):
        return publish.build_plan(self.site)

    def lines(self, plan, kind=None, model=publish.LOCATION):
        return [ln for ln in plan['lines'] if ln['res_model'] == model and (kind is None or ln['kind'] == kind)]

    def apply(self, plan=None, **kw):
        plan = plan or self.plan()
        return publish.apply_plan(self.site.with_user(self.u_manager), plan, kw.pop('archive_keys', ()), '', **kw)

    def loc(self, code, active_test=True):
        return self.env['stock.location'].with_context(active_test=active_test).search([('td_code', '=', code)])

    def product(self, name="Товар S2", **vals):
        return self.env['product.product'].create(dict({'name': name, 'is_storable': True}, **vals))

    def enable_check(self, key, mode='warn'):
        cfg = self.site.check_config_ids.filtered(lambda c: c.check_key == key)
        if cfg:
            cfg.write({'enabled': True, 'mode': mode})
        else:
            self.env['td.check.config'].create({'site_id': self.site.id, 'check_key': key, 'mode': mode})


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s2")
class TestS2Capacity(S2Mixin, F3DConstructorCase):
    """S2, F03: довідники зони, категорії зберігання, min/max (orderpoint), вага запасу (cell_load), знімок правил."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('td.constructor.publish_enabled', 'True')

    # --- довідники зони ---------------------------------------------------------------------------------
    def test_zone_terms_are_seeded_once(self):
        functions, attrs = capacity.ensure_zone_terms(self.env)
        self.assertEqual(len(functions), 10)
        self.assertEqual({a['key'] for a in attrs}, {'temp', 'hazmat', 'valuable', 'long'})
        self.assertTrue(all(f['color'].startswith('#') for f in functions))
        again, _attrs = capacity.ensure_zone_terms(self.env)
        self.assertEqual([f['id'] for f in again], [f['id'] for f in functions])  # повторно нічого не створює
        self.assertEqual(self.env['td.term'].search_count([('term_type', '=', 'zone_function')]), 10)

    # --- категорії зберігання -----------------------------------------------------------------------------
    def test_category_crud_and_validation(self):
        product = self.product()
        cat = capacity.save_category(
            self.env,
            self.company,
            {
                'name': "Палетна",
                'max_weight': 800,
                'allow_new_product': 'same',
                'capacity': [{'product_id': product.id, 'quantity': 12}],
            },
        )
        data = capacity.category_dict(cat)
        self.assertEqual((data['name'], data['max_weight'], data['allow_new_product']), ("Палетна", 800.0, 'same'))
        self.assertEqual([(c['product_id'], c['quantity']) for c in data['capacity']], [(product.id, 12.0)])
        capacity.save_category(self.env, self.company, {'name': "Палетна 2", 'max_weight': 900, 'capacity': []}, cat.id)
        self.assertEqual((cat.name, cat.max_weight, len(cat.capacity_ids)), ("Палетна 2", 900.0, 0))
        for bad in (
            {'name': ''},
            {'name': 'x', 'max_weight': -1},
            {'name': 'x', 'allow_new_product': 'nope'},
            {'name': 'x', 'capacity': [{'product_id': product.id, 'quantity': 0}]},
            {'name': 'x', 'capacity': [{'quantity': 1}]},
            {'name': 'x', 'capacity': [{'product_id': product.id, 'quantity': 1}] * 2},
        ):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                capacity.save_category(self.env, self.company, bad)
        capacity.delete_category(self.env, self.company, cat.id)
        self.assertFalse(cat.exists())

    def test_category_in_use_is_not_deleted(self):
        cat = capacity.save_category(self.env, self.company, {'name': "Зайнята"})
        slot = self.make_slot(prefix='CP-R1', bays=1, levels=1)
        slot.storage_category_id = cat
        with self.assertRaises(ValueError):
            capacity.delete_category(self.env, self.company, cat.id)
        slot.storage_category_id = False
        capacity.delete_category(self.env, self.company, cat.id)

    # --- min/max → stock.warehouse.orderpoint -------------------------------------------------------------------
    def rule(self, product, cell_code='CP-R1-B01-L1', **vals):
        return self.env['td.replenish.rule'].create(
            dict(
                {
                    'site_id': self.site.id,
                    'product_id': product.id,
                    'cell_code': cell_code,
                    'min_qty': 2,
                    'max_qty': 10,
                },
                **vals,
            )
        )

    def test_orderpoint_created_with_parent_cell_and_journal(self):
        slot = self.make_slot(prefix='CP-R1', bays=2, levels=1)
        product = self.product()
        rule = self.rule(product)
        plan = self.plan()
        line = self.lines(plan, 'create', publish.ORDERPOINT)[0]
        self.assertEqual((line['depends_code'], line['scope_uid']), ('CP-R1-B01-L1', slot.uid))
        self.assertEqual((line['vals']['product_min_qty'], line['vals']['product_max_qty']), (2, 10))
        # лише рядок правила без залежності: батьківська комірка додається сама
        chosen, _ = publish.select_lines(
            plan, excluded={(publish.LOCATION, 'CP-R1-B01-L1', 'create'), (publish.LOCATION, 'CP-R1-B02-L1', 'create')}
        )
        self.assertIn('CP-R1-B01-L1', [ln['code'] for ln in chosen])
        result = self.apply(plan)
        point = rule.odoo_orderpoint_id
        self.assertTrue(point and point.active)
        self.assertEqual(
            (point.product_id, point.location_id, point.product_min_qty, point.product_max_qty),
            (product, self.loc('CP-R1-B01-L1'), 2, 10),
        )
        ops = result['version'].op_ids.filtered(lambda o: o.res_model == publish.ORDERPOINT)
        self.assertEqual((ops.op, ops.res_id), ('create', point.id))
        self.assertIn(
            ('stock.warehouse.orderpoint', 'create'), [(c['model'], c.get('kind')) for c in result['created']]
        )
        self.assertEqual(self.plan()['lines'], [])  # ідемпотентно: правило вже в Odoo

    def test_orderpoint_update_delete_and_rollback(self):
        self.make_slot(prefix='CP-R1', bays=1, levels=1)
        product = self.product()
        rule = self.rule(product)
        first = self.apply()['version']
        point = rule.odoo_orderpoint_id
        rule.write({'min_qty': 1, 'max_qty': 20})
        attrs = self.lines(self.plan(), 'attrs', publish.ORDERPOINT)
        self.assertEqual(
            (attrs[0]['vals'], attrs[0]['before']),
            ({'product_min_qty': 1, 'product_max_qty': 20}, {'product_min_qty': 2, 'product_max_qty': 10}),
        )
        second = self.apply()['version']
        self.assertEqual((point.product_min_qty, point.product_max_qty), (1, 20))
        rule.deleted = True  # видалення правила = архів (явний намір, позначено за замовчуванням)
        archive = self.lines(self.plan(), 'archive', publish.ORDERPOINT)
        self.assertTrue(archive[0]['selected'] and archive[0]['extra']['explicit'])
        third = self.apply()['version']
        self.assertFalse(point.active)
        self.assertEqual(
            self.lines(self.plan(), None, publish.ORDERPOINT), []
        )  # архівне й видалене в чернетці — рядків немає
        # відкат у зворотному порядку повертає Odoo
        publish.rollback_version(self.site.with_user(self.u_manager), third)
        self.assertTrue(point.active)
        rule.deleted = False  # у чернетці правило знову діє
        publish.rollback_version(self.site.with_user(self.u_manager), second)
        self.assertEqual((point.product_min_qty, point.product_max_qty), (2, 10))
        publish.rollback_version(self.site.with_user(self.u_manager), first)
        self.assertFalse(point.active)
        self.assertFalse(rule.odoo_orderpoint_id)  # чернетка забула зв'язок
        # наступний план знову пропонує правило: наявне (архівне) відновлюється й зв'язується, а не дублюється
        plan = self.plan()
        line = self.lines(plan, 'attrs', publish.ORDERPOINT)[0]
        self.assertTrue(line['extra']['link'] and line['vals']['active'])
        before = self.env['stock.warehouse.orderpoint'].with_context(active_test=False).search_count([])
        self.apply(plan)
        self.assertEqual(
            self.env['stock.warehouse.orderpoint'].with_context(active_test=False).search_count([]), before
        )
        self.assertEqual(
            (rule.odoo_orderpoint_id, point.active, point.product_max_qty), (point, True, 20)
        )  # беруться значення чернетки

    def test_orderpoint_links_existing_and_blocks_unknown_target(self):
        self.make_slot(prefix='CP-R1', bays=1, levels=1)
        self.apply()
        loc = self.loc('CP-R1-B01-L1')
        product = self.product()
        existing = self.env['stock.warehouse.orderpoint'].create(
            {'product_id': product.id, 'location_id': loc.id, 'product_min_qty': 2, 'product_max_qty': 10}
        )
        rule = self.rule(product)
        line = self.lines(self.plan(), 'attrs', publish.ORDERPOINT)[0]
        self.assertEqual(
            (line['res_id'], line['vals'], line['changes']), (existing.id, {}, "зв'язати з наявним правилом")
        )
        self.apply()
        self.assertEqual(rule.odoo_orderpoint_id, existing)
        self.assertEqual(self.plan()['lines'], [])
        bad = self.rule(product, cell_code='НЕМА-ТАКОЇ')
        line = self.lines(self.plan(), 'create', publish.ORDERPOINT)[0]
        self.assertTrue(line['blocked'])
        self.assertIn("Не знайдено локацію", line['blocked_reason'])
        bad.unlink()

    def test_replenish_rule_validation(self):
        from odoo.exceptions import ValidationError

        product = self.product()
        with self.assertRaises(ValidationError), mute_logger('odoo.sql_db'):
            self.rule(product, min_qty=5, max_qty=1)
        with self.assertRaises(ValidationError):
            self.rule(product, min_qty=-1)

    # --- вага запасу -----------------------------------------------------------------------------------
    def test_cell_load_check_in_plan_and_pure(self):
        slot = self.make_slot(prefix='CP-R1', bays=1, levels=1, max_load_kg=100)
        self.apply()
        loc = self.loc('CP-R1-B01-L1')
        heavy = self.product("Важкий", weight=40)
        self.env['stock.quant']._update_available_quantity(heavy, loc, 3.0)  # 120 кг > 100 кг
        self.assertEqual(capacity.stock_loads(self.env, ['CP-R1-B01-L1', 'НЕМА'])['CP-R1-B01-L1']['weight_kg'], 120.0)
        # перевірку не налаштовано — у плані її немає
        self.assertFalse([i for i in self.plan()['issues'] if i['check'] == 'cell_load'])
        self.enable_check('cell_load', 'warn')
        slot.write({'note': "правка"})
        issues = [i for i in self.plan()['issues'] if i['check'] == 'cell_load']
        self.assertEqual((issues[0]['codes'], issues[0]['severity']), (['CP-R1-B01-L1'], 'warn'))
        self.assertIn("120", issues[0]['message'])
        # категорія зберігання задає ліміт, коли в комірці власного немає
        slot.params = dict(slot.params, max_load_kg=0)
        cat = capacity.save_category(self.env, self.company, {'name': "Легка", 'max_weight': 150})
        slot.storage_category_id = cat
        self.assertEqual(capacity.site_cell_limits(self.site)['CP-R1-B01-L1'], 150.0)
        self.assertFalse([i for i in self.plan()['issues'] if i['check'] == 'cell_load'])  # 120 < 150
        self.env['stock.quant']._update_available_quantity(heavy, loc, 1.0)  # 160 кг > 150 кг
        self.assertTrue([i for i in self.plan()['issues'] if i['check'] == 'cell_load'])
        # без даних (живий API-05) перевірка нічого не знаходить
        state_issues = checks.run_checks(
            state_mod.checks_state(self.site), [{'check': 'cell_load', 'enabled': True, 'mode': 'warn', 'params': {}}]
        )
        self.assertEqual(state_issues, [])
        self.assertIn('cell_load', CHECKS)

    # --- знімок -----------------------------------------------------------------------------------------
    def test_replenish_rules_are_part_of_snapshot_and_restore(self):
        self.make_slot(prefix='CP-R1', bays=1, levels=1)
        product = self.product()
        rule = self.rule(product)
        self.assertIn('replenish_rules', SNAPSHOT_SECTIONS)
        first = self.apply()['version']
        snap = snapshot.load_snapshot(first)
        self.assertEqual([r['min_qty'] for r in snap['sections']['replenish_rules']], [2.0])
        rule.write({'min_qty': 5, 'max_qty': 50})
        other = self.rule(product, cell_code='CP-R1-B01-L1X')
        snapshot.restore_draft(first)
        self.assertEqual((rule.min_qty, rule.max_qty), (2.0, 10.0))
        self.assertFalse(other.exists())  # без зв'язку з Odoo зникає
        self.assertIn('capacity', PLAN_BUILDERS)

    def test_linked_rule_missing_in_snapshot_is_marked_deleted(self):
        self.make_slot(prefix='CP-R1', bays=1, levels=1)
        first = self.apply()['version']  # у версії 1 правил немає
        rule = self.rule(self.product())
        self.apply()  # правило опубліковане: зв'язане з Odoo
        snapshot.restore_draft(first)
        self.assertTrue(rule.exists() and rule.deleted)  # зв'язане не зникає: план запропонує архів
        self.assertEqual(len(self.lines(self.plan(), 'archive', publish.ORDERPOINT)), 1)


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s2")
class TestS2StorageApi(S2Mixin, F3DConstructorHttpCase):
    """API-12: категорії зберігання й стратегії списання (прямий виклик менеджера з підтвердженням)."""

    def test_list_save_delete_and_rights(self):
        self.authenticate(self.u_tech.login, PASSWORD)
        res = self.rpc('/f3d/constructor/storage_categories')
        self.assertTrue(res['ok'])
        self.assertEqual((len(res['functions']), len(res['attrs'])), (10, 4))
        self.assertTrue(res['strategies'])
        self.assertEqual(self.rpc('/f3d/constructor/removal_strategies')['strategies'], res['strategies'])
        denied = self.rpc('/f3d/constructor/storage_categories', op='save', vals={'name': 'X'}, confirm=True)
        self.assertEqual(denied['code'], 'rights')
        self.authenticate(self.u_manager.login, PASSWORD)
        no_confirm = self.rpc('/f3d/constructor/storage_categories', op='save', vals={'name': 'X'})
        self.assertEqual(no_confirm['code'], 'validation')
        saved = self.rpc(
            '/f3d/constructor/storage_categories',
            op='save',
            vals={'name': "Зона А", 'max_weight': 500, 'allow_new_product': 'empty'},
            confirm=True,
        )
        self.assertTrue(saved['ok'], saved)
        cat_id = saved['category']['id']
        self.assertEqual((saved['category']['name'], saved['category']['company_id']), ("Зона А", self.company.id))
        bad = self.rpc(
            '/f3d/constructor/storage_categories', op='save', vals={'name': 'Y', 'max_weight': -5}, confirm=True
        )
        self.assertEqual(bad['code'], 'validation')
        listed = self.rpc('/f3d/constructor/storage_categories')
        self.assertIn(cat_id, [c['id'] for c in listed['categories']])
        self.assertEqual(
            self.rpc('/f3d/constructor/storage_categories', op='delete', id=999999, confirm=True)['code'], 'not_found'
        )
        done = self.rpc('/f3d/constructor/storage_categories', op='delete', id=cat_id, confirm=True)
        self.assertEqual((done['ok'], done['id']), (True, cat_id))
        self.assertEqual(self.rpc('/f3d/constructor/storage_categories', op='nope')['code'], 'validation')

    def test_loads_route(self):
        self.make_slot(prefix='CL-R1', bays=1, levels=1, max_load_kg=100)
        self.env['ir.config_parameter'].sudo().set_param('td.constructor.publish_enabled', 'True')
        publish.apply_plan(self.site.with_user(self.u_manager), publish.build_plan(self.site), (), '')
        loc = self.loc('CL-R1-B01-L1')
        self.env['stock.quant']._update_available_quantity(self.product("Кг", weight=10), loc, 4.0)
        self.authenticate(self.u_store.login, PASSWORD)
        res = self.rpc('/f3d/constructor/storage/loads', site_id=self.site.id)
        self.assertEqual((res['loads']['CL-R1-B01-L1']['weight_kg'], res['limits']['CL-R1-B01-L1']), (40.0, 100.0))
        self.assertEqual(
            self.rpc('/f3d/constructor/storage/loads', site_id=self.site.id, codes='x')['code'], 'validation'
        )
