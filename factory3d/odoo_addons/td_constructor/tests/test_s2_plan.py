from odoo.tests import tagged
from odoo.tools import mute_logger

from ..services import publish
from .common import F3DConstructorCase, F3DConstructorHttpCase, PASSWORD


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s2")
class TestS2Plan(F3DConstructorCase):
    """S2, F02: види рядків плану, залежності, частинами, зайнятий штрихкод, журнал і відкат (MERGE.md §2.6)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('td.constructor.publish_enabled', 'True')

    # --- помічники ---------------------------------------------------------------------------------
    def plan(self, site=None):
        return publish.build_plan(site or self.site)

    def lines(self, plan, kind=None, model=publish.LOCATION):
        return [ln for ln in plan['lines'] if ln['res_model'] == model and (kind is None or ln['kind'] == kind)]

    def apply(self, plan=None, **kw):
        plan = plan or self.plan()
        return publish.apply_plan(self.site.with_user(self.u_manager), plan, kw.pop('archive_keys', ()), '', **kw)

    def loc(self, code, active_test=True):
        return self.env['stock.location'].with_context(active_test=active_test).search([('td_code', '=', code)])

    def rack(self, prefix='SA-R1', bays=2, levels=1, **kw):
        return self.make_slot(prefix=prefix, bays=bays, levels=levels, **kw)

    # --- види рядків ---------------------------------------------------------------------------------
    def test_create_line_carries_address_parts_and_scope(self):
        slot = self.rack(bays=2, levels=2)
        plan = self.plan()
        creates = self.lines(plan, 'create')
        self.assertEqual(len(creates), 4)
        line = next(ln for ln in creates if ln['code'] == 'SA-R1-B02-L2')
        self.assertEqual((line['vals']['td_bay'], line['vals']['td_level']), (2, 2))
        self.assertEqual((line['scope_uid'], line['source_uid']), (slot.uid, slot.uid))
        self.assertEqual(plan['unchanged'], 0)
        self.apply(plan)
        rec = self.loc('SA-R1-B02-L2')
        self.assertEqual((rec.td_bay, rec.td_level), (2, 2))

    def test_update_is_split_into_move_rename_attrs(self):
        slot = self.rack(bays=1, levels=1)
        self.apply()
        rec = self.loc('SA-R1-B01-L1')
        other = self.env['stock.location'].create({'name': 'FG2', 'usage': 'internal', 'location_id': self.wh_stock.id})
        slot.parent_location_id = other  # перенесення
        slot.overrides = {'SA-R1-B01-L1': {'name': "Перша комірка", 'capacity': 7}}  # перейменування + атрибути
        plan = self.plan()
        self.assertEqual(
            sorted(ln['kind'] for ln in self.lines(plan) if ln['code'] == rec.td_code), ['attrs', 'move', 'rename']
        )
        move = self.lines(plan, 'move')[0]
        self.assertEqual((move['vals'], move['before']), ({'location_id': other.id}, {'location_id': self.wh_fg.id}))
        summary = publish.summary(plan)
        self.assertEqual((summary['update'], summary['move'], summary['rename'], summary['attrs']), (3, 1, 1, 1))
        result = self.apply(plan)
        self.assertEqual([(u['code'], u['kind']) for u in result['updated']].count(('SA-R1-B01-L1', 'move')), 1)
        rec.invalidate_recordset()
        self.assertEqual((rec.location_id, rec.name, rec.td_capacity), (other, "Перша комірка", 7))
        self.assertEqual(self.plan()['lines'], [])  # ідемпотентно: без змін — рядків немає

    def test_idempotent_publish_has_no_changes(self):
        self.rack(bays=2, levels=1)
        self.apply()
        plan = self.plan()
        self.assertEqual((plan['lines'], plan['unchanged']), ([], 2))
        with self.assertRaises(publish.PublishError) as ctx:
            self.apply(plan)
        self.assertEqual(ctx.exception.code, 'no_changes')

    def test_storage_category_and_removal_strategy_inherit_from_zone(self):
        cat = self.env['stock.storage.category'].create({'name': "Важка", 'max_weight': 500})
        strategy = self.env['product.removal'].search([], limit=1)
        self.make_slot(kind='yard', prefix='SA-Z', template='zone', polygon=[[0, 0], [60, 0], [60, 30], [0, 30]]).write(
            {'storage_category_id': cat.id, 'removal_strategy_id': strategy.id}
        )
        self.rack(bays=1, levels=1)
        plan = self.plan()
        line = self.lines(plan, 'create')[0]
        self.assertEqual(line['vals']['storage_category_id'], cat.id)
        self.assertEqual(line['vals']['removal_strategy_id'], strategy.id)
        self.assertTrue(line['extra']['zone_uid'])
        self.apply(plan)
        self.assertEqual(self.loc('SA-R1-B01-L1').storage_category_id, cat)
        own = self.env['stock.storage.category'].create({'name': "Своя", 'max_weight': 100})
        self.env['td.slot'].search(
            [('code_prefix', '=', 'SA-R1')]
        ).storage_category_id = own  # своя — важливіша за зону
        attrs = self.lines(self.plan(), 'attrs')
        self.assertEqual(attrs[0]['vals'], {'storage_category_id': own.id})

    def test_nested_zones_inherit_from_the_nearest_zone(self):
        outer_cat = self.env['stock.storage.category'].create({'name': "Зовнішня", 'max_weight': 900})
        inner_cat = self.env['stock.storage.category'].create({'name': "Внутрішня", 'max_weight': 300})
        strategy = self.env['product.removal'].search([], limit=1)
        self.make_slot(
            kind='yard', prefix='SA-ZO', template='zone', polygon=[[0, 0], [60, 0], [60, 30], [0, 30]]
        ).write({'storage_category_id': outer_cat.id, 'removal_strategy_id': strategy.id})
        self.make_slot(
            kind='yard', prefix='SA-ZI', template='zone', polygon=[[25, 5], [40, 5], [40, 15], [25, 15]]
        ).write({'storage_category_id': inner_cat.id})
        self.rack(bays=1, levels=1)  # стелаж (30; 10) — у внутрішній зоні
        line = self.lines(self.plan(), 'create')[0]
        self.assertEqual(line['vals']['storage_category_id'], inner_cat.id)  # ближча зона перекриває далеку
        self.assertEqual(line['vals']['removal_strategy_id'], strategy.id)  # що не задано — береться з далекої
        zone_uid = self.env['td.slot'].search([('code_prefix', '=', 'SA-ZI')]).uid
        self.assertEqual(line['extra']['zone_uid'], zone_uid)  # область — найближча зона

    # --- зайнятий штрихкод, залишки, переміщення ----------------------------------------------------------
    def test_barcode_held_by_non_internal_location_is_blocked(self):
        self.env['stock.location'].create({'name': 'Віртуальна', 'barcode': 'SA-R1-B01-L1', 'usage': 'view'})
        self.rack(bays=2, levels=1)
        plan = self.plan()
        busy = [ln for ln in plan['lines'] if ln['blocked']]
        self.assertEqual({ln['code'] for ln in busy}, {'SA-R1-B01-L1'})
        self.assertEqual(sorted(ln['kind'] for ln in busy), ['attrs', 'move'])
        self.assertIn('barcode_busy', busy[0]['extra']['flags'])
        self.assertTrue(any(i['check'] == 'code_conflict' for i in plan['issues']))
        self.apply(plan)  # заблокований рядок пропускається, решта публікується
        self.assertTrue(self.loc('SA-R1-B02-L1'))
        self.assertFalse(self.loc('SA-R1-B01-L1'))

    def test_code_states(self):
        self.rack(bays=1, levels=1)
        self.env['stock.location'].create({'name': 'Інша', 'barcode': 'BUSY-1', 'usage': 'customer'})
        self.env['stock.location'].create({'name': 'Своя', 'barcode': 'FREE-ISH', 'usage': 'internal'})
        states = publish.code_states(self.env, self.site, ['BUSY-1', 'FREE-ISH', 'NOPE', 'SA-R1-B01-L1'])
        self.assertEqual(states['BUSY-1']['state'], 'busy')
        self.assertEqual(states['FREE-ISH']['state'], 'match')
        self.assertEqual(states['NOPE']['state'], 'free')
        self.apply()
        self.assertEqual(publish.code_states(self.env, self.site, ['SA-R1-B01-L1'])['SA-R1-B01-L1']['state'], 'own')

    def test_archive_blocked_by_unfinished_moves(self):
        slot = self.rack(bays=1, levels=1)
        self.apply()
        loc = self.loc('SA-R1-B01-L1')
        product = self.env['product.product'].create({'name': "Тестовий", 'is_storable': True})
        self.env['stock.move'].create(
            {
                'product_id': product.id,
                'product_uom_qty': 2,
                'location_id': self.wh_stock.id,
                'location_dest_id': loc.id,
                'state': 'confirmed',
            }
        )
        slot.unlink()
        line = self.lines(self.plan(), 'archive')[0]
        self.assertTrue(line['blocked'])
        self.assertIn('moves', line['extra']['flags'])
        self.assertIn("переміщення", line['blocked_reason'])

    def test_move_of_location_with_stock_warns(self):
        slot = self.rack(bays=1, levels=1)
        self.apply()
        loc = self.loc('SA-R1-B01-L1')
        product = self.env['product.product'].create({'name': "Тестовий", 'is_storable': True})
        self.env['stock.quant']._update_available_quantity(product, loc, 5.0)
        slot.parent_location_id = self.wh_stock
        plan = self.plan()
        self.assertEqual(self.lines(plan, 'move')[0]['extra']['flags'], ['stock'])
        self.assertTrue(any("із залишком" in i['message'] for i in plan['issues'] if i['severity'] == 'warn'))

    # --- частинами й залежності -----------------------------------------------------------------------
    def test_scope_applies_one_row_only(self):
        a = self.rack('SA-A', bays=2, levels=1)
        self.rack('SA-B', bays=2, levels=1, x=30.0, y=15.0)
        plan = self.plan()
        self.assertEqual(len(self.lines(plan, 'create')), 4)
        result = self.apply(plan, scope={a.uid})
        self.assertEqual(sorted(c['code'] for c in result['created']), ['SA-A-B01-L1', 'SA-A-B02-L1'])
        self.assertFalse(self.loc('SA-B-B01-L1'))
        rest = self.plan()
        self.assertEqual([ln['code'] for ln in self.lines(rest, 'create')], ['SA-B-B01-L1', 'SA-B-B02-L1'])

    def test_row_tree_creates_parent_first_and_adds_it_automatically(self):
        self.site.loc_tree = 'row'
        a = self.rack('SA-R', bays=2, levels=1)
        plan = self.plan()
        creates = self.lines(plan, 'create')
        parent = next(ln for ln in creates if ln['extra'].get('virtual'))
        cells = [ln for ln in creates if not ln['extra'].get('virtual')]
        self.assertEqual((parent['code'], parent['vals']['usage']), ('SA-R', 'view'))
        self.assertTrue(all(ln['depends_code'] == 'SA-R' for ln in cells))
        self.assertEqual(
            {ln['vals']['name'] for ln in cells}, {'SA-R-B01-L1', 'SA-R-B02-L1'}
        )  # legacy: ім'я = повний код
        # знімаємо рядок батька: застосування додає його саме
        chosen, skipped = publish.select_lines(plan, excluded={(publish.LOCATION, 'SA-R', 'create')}, scope={a.uid})
        self.assertIn('SA-R', [ln['code'] for ln in chosen])
        self.apply(plan)
        row = self.loc('SA-R')
        self.assertEqual(self.loc('SA-R-B01-L1').location_id, row)
        self.assertEqual(row.location_id, self.wh_fg)
        self.assertEqual(self.plan()['lines'], [])

    def test_row_tree_follows_the_addressing_of_the_site(self):
        """Код ряду — слова адресації S1 без секції/ярусу: той самий префікс, що в кодах комірок (перегляд)."""
        from ..services import addr as addr_mod

        self.site.write({'loc_tree': 'row', 'addr': addr_mod.preset_addr('zone_row_bay_level')})
        slot = self.rack('SA-AD', bays=2, levels=2)
        plan = self.plan()
        creates = self.lines(plan, 'create')
        parent = next(ln for ln in creates if ln['extra'].get('virtual'))
        cells = [ln for ln in creates if not ln['extra'].get('virtual')]
        ctx = slot._f3d_addr_context()
        expected = addr_mod.render_code(
            ctx['addr'], {'prefix': slot.code_prefix, 'zone': ctx['zone'], 'row': ctx['row']}
        )
        self.assertEqual(parent['code'], expected)
        self.assertNotEqual(parent['code'], 'SA-AD')  # адресація, а не префікс місця
        preview = addr_mod.preview([c['code'] for c in cells], limit=10)
        sep = ctx['addr']['sep']
        self.assertTrue(all(code.startswith(parent['code'] + sep) for code in preview['first']))
        self.assertTrue(all(ln['depends_code'] == parent['code'] for ln in cells))
        # ім'я комірки — останній сегмент (F01-05), штрихкод — повний код, номери адреси розібрані з коду
        sample = next(ln for ln in cells if ln['vals']['td_bay'] == 2 and ln['vals']['td_level'] == 2)
        self.assertEqual(sample['vals']['name'], sample['code'].rsplit(sep, 1)[-1])
        self.assertEqual((sample['vals']['barcode'], sample['vals']['td_row']), (sample['code'], ctx['row']))
        self.apply(plan)
        row = self.loc(parent['code'])
        self.assertEqual(self.loc(sample['code']).location_id, row)
        self.assertEqual(self.plan()['lines'], [])

    def test_renumber_becomes_rename_when_the_addressing_changes(self):
        """Зміна адресації (S1) міняє коди, а не номери ряду/секції/ярусу: локації перейменовуються, не створюються."""
        from ..services import addr as addr_mod

        first = addr_mod.normalize_addr({'tpl': '{row} {bay} {level}', 'sep': '-'})
        self.site.write({'addr': first})
        slot = self.rack(bays=2, levels=1)
        plan = self.plan()
        old_codes = sorted(ln['code'] for ln in self.lines(plan, 'create'))
        self.assertEqual(self.lines(plan, 'create')[0]['vals']['td_row'], 1)
        self.apply(plan)
        wider = {'tpl': '{row} {bay} {level}', 'sep': '-', 'seg': {'row': {'width': 3}}}  # 01-01-1 → 001-01-1
        self.site.write({'addr': addr_mod.normalize_addr(wider)})
        plan = self.plan()
        rename = self.lines(plan, 'rename')
        self.assertEqual(len(rename), 2)
        self.assertEqual(sorted(ln['extra']['old_code'] for ln in rename), old_codes)
        self.assertEqual({ln['code'] for ln in rename}, {'0' + c for c in old_codes})
        self.assertFalse(self.lines(plan, 'create') or self.lines(plan, 'archive'))
        ids = {self.loc(c).id for c in old_codes}
        self.apply(plan)
        self.assertEqual({self.loc('0' + c).id for c in old_codes}, ids)  # ті самі записи Odoo
        self.assertEqual(self.plan()['lines'], [])
        self.assertTrue(slot.exists())

    # --- F03-05: прапорці місця (usage, replenish_location) --------------------------------------------
    def isolated_rack(self, **kw):
        """Стелаж у дереві без місця поповнення (типовий WH/Stock уже є таким, а вкладених Odoo не дозволяє)."""
        root = self.env['stock.location'].create({'name': 'Корінь без поповнення', 'usage': 'view'})
        slot = self.rack(**kw)
        slot.parent_location_id = root
        return slot, root

    def test_flags_from_cell_overrides_are_published(self):
        slot, _root = self.isolated_rack(bays=2, levels=1)
        slot.overrides = {'SA-R1-B01-L1': {'usage': 'view'}, 'SA-R1-B02-L1': {'replenish_location': True}}
        plan = self.plan()
        by = {ln['code']: ln['vals'] for ln in self.lines(plan, 'create')}
        self.assertEqual(by['SA-R1-B01-L1']['usage'], 'view')
        self.assertTrue(by['SA-R1-B02-L1']['replenish_location'])
        self.apply(plan)
        self.assertEqual(self.loc('SA-R1-B01-L1').usage, 'view')
        self.assertTrue(self.loc('SA-R1-B02-L1').replenish_location)
        self.assertEqual(self.plan()['lines'], [])  # ідемпотентно
        slot.overrides = {
            'SA-R1-B02-L1': {'replenish_location': False}
        }  # знімаємо прапорець; usage без ключа — як в Odoo
        attrs = self.lines(self.plan(), 'attrs')
        self.assertEqual([(ln['code'], ln['vals']) for ln in attrs], [('SA-R1-B02-L1', {'replenish_location': False})])

    def test_flag_rules_stock_view_and_nested_replenish(self):
        from odoo.exceptions import ValidationError

        slot, root = self.isolated_rack(bays=2, levels=1)
        self.apply()
        loc = self.loc('SA-R1-B01-L1')
        product = self.env['product.product'].create({'name': "Тестовий", 'is_storable': True})
        self.env['stock.quant']._update_available_quantity(product, loc, 2.0)
        slot.overrides = {'SA-R1-B01-L1': {'usage': 'view'}}
        line = self.lines(self.plan(), 'attrs')[0]
        self.assertTrue(line['blocked'])  # місце із залишком не стане view
        self.assertIn('stock', line['extra']['flags'])
        # вкладене місце поповнення заборонене: батько вже replenish
        root.replenish_location = True
        slot.overrides = {'SA-R1-B02-L1': {'replenish_location': True}}
        line = self.lines(self.plan(), 'attrs')[0]
        self.assertTrue(line['blocked'])
        self.assertIn('replenish_nested', line['extra']['flags'])
        root.replenish_location = False
        # неприпустиме значення відхиляється схемою overrides
        with self.assertRaises(ValidationError):
            slot.overrides = {'SA-R1-B01-L1': {'usage': 'customer'}}

    # --- журнал і відкат ------------------------------------------------------------------------------
    def test_journal_records_ops_with_before_after(self):
        slot = self.rack(bays=2, levels=1)
        self.make_placement(code='SA-M1')
        result = self.apply()
        version = result['version']
        ops = version.op_ids.sorted('seq')
        self.assertEqual(result['ops'], len(ops))
        self.assertEqual([op.seq for op in ops], list(range(1, len(ops) + 1)))
        self.assertEqual({op.op for op in ops}, {'create'})
        self.assertEqual({op.res_model for op in ops}, {'stock.location', 'maintenance.equipment', 'mrp.workcenter'})
        first = ops.filtered(lambda o: o.code == 'SA-R1-B01-L1')
        self.assertEqual((bool(first.before), first.after['td_capacity']), (False, 3.0))
        slot.overrides = {'SA-R1-B01-L1': {'capacity': 9}}
        second = self.apply()['version']
        op = second.op_ids
        self.assertEqual((op.op, op.before, op.after), ('attrs', {'td_capacity': 3.0}, {'td_capacity': 9.0}))

    def test_rollback_restores_odoo(self):
        slot = self.rack(bays=2, levels=1)
        placement = self.make_placement(code='SA-M2')
        before = self.env['stock.location'].with_context(active_test=False).search_count([])
        first = self.apply()['version']
        self.assertTrue(
            self.loc('SA-R1-B01-L1') and self.env['maintenance.equipment'].search([('td_code', '=', 'SA-M2')])
        )
        draft_rev = self.site.draft_rev
        res = publish.rollback_version(self.site.with_user(self.u_manager), first)
        self.assertEqual(res['reverted'], len(first.op_ids))
        self.assertFalse(self.loc('SA-R1-B01-L1'))  # створене пішло в архів
        self.assertTrue(self.loc('SA-R1-B01-L1', active_test=False))
        self.assertFalse(self.env['maintenance.equipment'].search([('td_code', '=', 'SA-M2')]))
        self.assertTrue(first.rolled_back_at and first.rolled_back_by_id == self.u_manager)
        self.assertTrue(all(first.op_ids.mapped('rolled_back')))
        self.assertEqual(self.site.draft_rev, draft_rev)  # чернетка не змінилась
        self.assertTrue(slot.exists() and placement.exists())
        self.assertEqual(
            self.env['stock.location'].with_context(active_test=False).search_count([]), before + 2
        )  # нових записів не з'явилось: лише архівовані створені
        with self.assertRaises(publish.PublishError) as ctx:  # вдруге не можна
            publish.rollback_version(self.site.with_user(self.u_manager), first)
        self.assertEqual(ctx.exception.code, 'rollback_blocked')
        # наступний план пропонує зміни знову: комірки відновлюються з архіву, обладнання створюється
        plan = self.plan()
        restore = [ln for ln in self.lines(plan, 'attrs') if ln['vals'].get('active')]
        self.assertEqual(sorted(ln['code'] for ln in restore), ['SA-R1-B01-L1', 'SA-R1-B02-L1'])
        again = self.apply(plan)['version']
        self.assertTrue(self.loc('SA-R1-B01-L1'))
        self.assertEqual(again.n, first.n + 1)

    def test_rollback_reverts_move_rename_attrs_and_archive(self):
        slot = self.rack(bays=2, levels=1)
        self.apply()
        a, b = self.loc('SA-R1-B01-L1'), self.loc('SA-R1-B02-L1')
        other = self.env['stock.location'].create({'name': 'FG3', 'usage': 'internal', 'location_id': self.wh_stock.id})
        slot.write(
            {
                'parent_location_id': other.id,
                'overrides': {'SA-R1-B01-L1': {'name': "Нове ім'я", 'capacity': 8}, 'SA-R1-B02-L1': {'disabled': True}},
            }
        )
        plan = self.plan()
        version = self.apply(plan, archive_keys={(publish.LOCATION, 'SA-R1-B02-L1')})['version']
        a.invalidate_recordset()
        self.assertEqual((a.location_id, a.name, a.td_capacity, b.active), (other, "Нове ім'я", 8.0, False))
        self.assertEqual({op.op for op in version.op_ids}, {'move', 'rename', 'attrs', 'archive'})
        publish.rollback_version(self.site.with_user(self.u_manager), version)
        a.invalidate_recordset()
        b.invalidate_recordset()
        self.assertEqual((a.location_id, a.name, a.td_capacity, b.active), (self.wh_fg, 'SA-R1-B01-L1', 3.0, True))

    def test_rollback_blocked_when_used_or_changed_or_later(self):
        self.rack(bays=1, levels=1)
        first = self.apply()['version']
        loc = self.loc('SA-R1-B01-L1')
        product = self.env['product.product'].create({'name': "Тестовий", 'is_storable': True})
        self.env['stock.quant']._update_available_quantity(product, loc, 3.0)
        problems = publish.rollback_problems(first)
        self.assertEqual(problems[0]['code'], 'SA-R1-B01-L1')
        self.assertIn("використано", problems[0]['reason'])
        with self.assertRaises(publish.PublishError) as ctx:
            publish.rollback_version(self.site.with_user(self.u_manager), first)
        self.assertEqual(ctx.exception.code, 'rollback_blocked')
        self.assertTrue(loc.active)  # нічого не змінено
        self.env['stock.quant']._update_available_quantity(product, loc, -3.0)  # залишок знято
        # пізніша публікація з тими самими кодами: спершу її
        self.env['td.slot'].search([('code_prefix', '=', 'SA-R1')]).overrides = {'SA-R1-B01-L1': {'capacity': 4}}
        second = self.apply()['version']
        self.assertIn("пізніша", publish.rollback_problems(first)[0]['reason'])
        # значення змінили в Odoo вручну — відкат не затирає чуже
        loc.td_capacity = 99
        self.assertEqual(publish.rollback_problems(second)[0]['reason'], "Запис змінено в Odoo після публікації")
        loc.td_capacity = 4
        publish.rollback_version(self.site.with_user(self.u_manager), second)
        self.assertEqual(loc.td_capacity, 3.0)
        self.assertEqual(publish.rollback_problems(first), [])

    def test_rollback_needs_manager(self):
        self.rack(bays=1, levels=1)
        version = self.apply()['version']
        from odoo.exceptions import AccessError

        with self.assertRaises(publish.PublishError) as ctx:
            publish.rollback_version(self.site.with_user(self.u_tech), version)
        self.assertEqual(ctx.exception.code, 'rights')
        with self.assertRaises(AccessError):
            version.with_user(self.u_tech).action_rollback()

    def test_rollback_is_atomic(self):
        from unittest.mock import patch

        self.rack(bays=3, levels=1)
        version = self.apply()['version']
        Loc = type(self.env['stock.location'])
        original = Loc.write
        calls = []

        def flaky(self_, vals):
            if vals == {'active': False} and self_._name == 'stock.location':
                calls.append(self_.td_code)
                if len(calls) == 2:
                    raise ValueError("штучна помилка")
            return original(self_, vals)

        with patch.object(Loc, 'write', flaky), mute_logger('odoo.addons.td_constructor.services.publish'):
            with self.assertRaises(publish.PublishError) as ctx:
                publish.rollback_version(self.site.with_user(self.u_manager), version)
        self.assertEqual(ctx.exception.code, 'rollback')
        self.assertEqual(len(self.loc('SA-R1-B01-L1') | self.loc('SA-R1-B02-L1') | self.loc('SA-R1-B03-L1')), 3)
        self.assertFalse(version.rolled_back_at)

    def test_publish_log_and_version_form(self):
        self.rack(bays=2, levels=1)
        version = self.apply()['version']
        log = publish.publish_log(self.site)
        self.assertEqual((log[0]['n'], log[0]['counts']['create'], log[0]['can_rollback']), (version.n, 2, True))
        version.invalidate_recordset()
        self.assertTrue(version.can_rollback)
        self.assertEqual(version.op_count, 2)
        res = version.with_user(self.u_manager).action_rollback()
        self.assertEqual(res['tag'], 'display_notification')
        version.invalidate_recordset()
        self.assertFalse(version.can_rollback)
        self.assertEqual(version.rollback_reason, "Версію вже відкочено")
        self.assertTrue(publish.publish_log(self.site)[0]['rolled_back'])

    # --- майстер ------------------------------------------------------------------------------------
    def test_wizard_pages_scope_select_all_and_apply(self):
        a = self.rack('SA-A', bays=2, levels=1)
        self.rack('SA-B', bays=1, levels=1, x=30.0, y=15.0)
        action = self.site.with_user(self.u_manager).action_publish_wizard()
        wizard = self.env['td.publish.wizard'].with_user(self.u_manager).browse(action['res_id'])
        self.assertEqual((wizard.n_create, wizard.n_move, wizard.n_rename, wizard.n_attrs), (3, 0, 0, 0))
        self.assertEqual(len(wizard.create_line_ids), 3)
        self.assertEqual(set(wizard.scope_slot_ids.mapped('code_prefix')), {'SA-A', 'SA-B'})
        wizard.scope_slot_id = a
        wizard.action_select_scope()
        self.assertEqual(sorted(wizard.line_ids.filtered('selected').mapped('code')), ['SA-A-B01-L1', 'SA-A-B02-L1'])
        wizard.action_select_none()
        self.assertFalse(wizard.line_ids.filtered('selected'))
        wizard.action_select_all()
        self.assertEqual(len(wizard.line_ids.filtered('selected')), 3)
        wizard.line_ids.filtered(lambda r: r.code == 'SA-B-B01-L1').selected = False
        wizard.action_confirm()
        self.assertEqual(
            sorted(self.env['stock.location'].search([('td_site_id', '=', self.site.id)]).mapped('td_code')),
            ['SA-A-B01-L1', 'SA-A-B02-L1'],
        )
        self.assertEqual(wizard.version_id.op_count, 2)

    def test_wizard_first_application_reminds_about_database_copy(self):
        self.rack(bays=1, levels=1)
        action = self.site.with_user(self.u_manager).action_publish_wizard()
        wizard = self.env['td.publish.wizard'].with_user(self.u_manager).browse(action['res_id'])
        self.assertTrue(wizard.copy_reminder)  # журнал порожній, нагадування не вимкнено
        wizard.copy_ack = True
        wizard.action_confirm()
        self.assertTrue(self.site.publish_copy_ack)
        self.rack('SA-R2', bays=1, levels=1, x=30.0, y=15.0)
        again = (
            self.env['td.publish.wizard']
            .with_user(self.u_manager)
            .browse(self.site.with_user(self.u_manager).action_publish_wizard()['res_id'])
        )
        self.assertFalse(again.copy_reminder)
        self.site.publish_copy_ack = False  # журнал уже не порожній — «перше застосування» минуло
        again._compute_copy_reminder()
        self.assertFalse(again.copy_reminder)

    def test_wizard_blocked_line_is_not_applicable(self):
        self.env['stock.location'].create({'name': 'Віртуальна', 'barcode': 'SA-R1-B01-L1', 'usage': 'view'})
        self.rack(bays=2, levels=1)
        action = self.site.with_user(self.u_manager).action_publish_wizard()
        wizard = self.env['td.publish.wizard'].with_user(self.u_manager).browse(action['res_id'])
        self.assertEqual((wizard.n_blocked, wizard.n_create), (2, 1))
        self.assertFalse(wizard.line_ids.filtered(lambda r: r.blocked and r.selected and False))
        wizard.action_confirm()
        self.assertTrue(self.loc('SA-R1-B02-L1'))
        self.assertFalse(self.loc('SA-R1-B01-L1'))


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s2")
class TestS2PlanApi(F3DConstructorHttpCase):
    """API-17 (зайнятість кодів) і API-18 (журнал, відкат)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['ir.config_parameter'].sudo().set_param('td.constructor.publish_enabled', 'True')

    def test_codes_check_and_log_and_rollback(self):
        self.make_slot(prefix='SA-API', bays=2, levels=1)
        self.env['stock.location'].create({'name': 'Зайнята', 'barcode': 'BUSY-X', 'usage': 'customer'})
        self.authenticate(self.u_manager.login, PASSWORD)
        res = self.rpc('/f3d/constructor/codes/check', site_id=self.site.id, codes=['BUSY-X', 'SA-API-B01-L1'])
        self.assertEqual(
            (res['ok'], res['codes']['BUSY-X']['state'], res['codes']['SA-API-B01-L1']['state']), (True, 'busy', 'free')
        )
        self.assertEqual(
            self.rpc('/f3d/constructor/codes/check', site_id=self.site.id, codes='x')['code'], 'validation'
        )
        self.assertEqual(self.rpc('/f3d/constructor/codes/check', site_id=999999, codes=[])['code'], 'not_found')
        pub = self.rpc('/f3d/constructor/publish', site_id=self.site.id, confirm=True)
        self.assertTrue(pub['ok'], pub)
        log = self.rpc('/f3d/constructor/publish/log', site_id=self.site.id, version_id=pub['version']['id'])
        self.assertTrue(log['ok'])
        self.assertEqual((log['versions'][0]['counts']['create'], log['versions'][0]['can_rollback']), (2, True))
        self.assertEqual(len(log['ops']), 2)
        self.assertEqual(
            self.rpc('/f3d/constructor/publish/rollback', site_id=self.site.id, version_id=pub['version']['id'])[
                'code'
            ],
            'validation',
        )  # без confirm
        done = self.rpc(
            '/f3d/constructor/publish/rollback', site_id=self.site.id, version_id=pub['version']['id'], confirm=True
        )
        self.assertEqual((done['ok'], done['reverted']), (True, 2))
        self.assertFalse(self.env['stock.location'].search([('td_code', '=', 'SA-API-B01-L1')]))
        again = self.rpc(
            '/f3d/constructor/publish/rollback', site_id=self.site.id, version_id=pub['version']['id'], confirm=True
        )
        self.assertEqual(again['code'], 'rollback_blocked')

    def test_publish_api_scope_and_excluded(self):
        a = self.make_slot(prefix='SA-SC', bays=2, levels=1)
        self.make_slot(prefix='SA-SD', bays=2, levels=1, x=30.0, y=15.0)
        self.authenticate(self.u_manager.login, PASSWORD)
        bad = self.rpc('/f3d/constructor/publish', site_id=self.site.id, confirm=True, scope='x')
        self.assertEqual(bad['code'], 'validation')
        bad = self.rpc('/f3d/constructor/publish', site_id=self.site.id, confirm=True, excluded=[['a']])
        self.assertEqual(bad['code'], 'validation')
        res = self.rpc(
            '/f3d/constructor/publish',
            site_id=self.site.id,
            confirm=True,
            scope=[a.uid],
            excluded=[['stock.location', 'SA-SC-B02-L1', 'create']],
        )
        self.assertTrue(res['ok'], res)
        self.assertEqual([c['code'] for c in res['created']], ['SA-SC-B01-L1'])
        self.assertEqual((res['ops'], res['skipped']), (1, []))
        self.assertFalse(self.env['stock.location'].search([('td_code', '=', 'SA-SD-B01-L1')]))

    def test_rollback_rights(self):
        self.make_slot(prefix='SA-RT', bays=1, levels=1)
        self.authenticate(self.u_manager.login, PASSWORD)
        pub = self.rpc('/f3d/constructor/publish', site_id=self.site.id, confirm=True)
        self.authenticate(self.u_tech.login, PASSWORD)
        res = self.rpc(
            '/f3d/constructor/publish/rollback', site_id=self.site.id, version_id=pub['version']['id'], confirm=True
        )
        self.assertEqual(res['code'], 'rights')
        log = self.rpc('/f3d/constructor/publish/log', site_id=self.site.id)
        self.assertEqual((log['ok'], log['can_rollback']), (True, False))
