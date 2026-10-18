from datetime import timedelta

from psycopg2 import IntegrityError

from odoo import Command, fields
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import F3DConstructorCase

NEW_MODELS = [
    'td.slot.type',
    'td.slot.preset',
    'td.putaway.rule',
    'td.replenish.rule',
    'td.publish.op',
    'td.layout.variant',
    'td.comment',
    'td.zone.lock',
]
# MERGE.md §3.3: нові поля наявних моделей
EXTENDED_FIELDS = {
    'td.site': [
        'warehouse_id', 'addr', 'loc_tree', 'depth_mode', 'sprinkler_height_m', 'aisle_tech', 'parse_rules',
        'active_variant_id', 'wizard_state', 'odoo_baseline_id', 'publish_copy_ack',
    ],  # fmt: skip
    'td.layer': ['items'],
    'td.slot': [
        'type_id', 'storage_category_id', 'removal_strategy_id', 'function_id', 'attr_ids', 'temp_min_c', 'temp_max_c',
        'tech', 'addr', 'depth_mode',
    ],  # fmt: skip
    'stock.location': ['td_row', 'td_bay', 'td_level', 'td_pos'],
    'td.layout.version': ['kind', 'variant_id', 'rolled_back_at', 'rolled_back_by_id', 'op_ids', 'metrics'],
    'td.publish.wizard.line': ['depends_code', 'scope_uid', 'before'],
    'td.term': ['color', 'value'],
}
# MERGE.md §3.4: поля нових моделей
NEW_FIELDS = {
    'td.slot.type': [
        'code', 'ref', 'name', 'description', 'group', 'template', 'shape', 'params', 'relevance', 'loc_kind',
        'is_custom', 'company_id', 'sequence', 'active',
    ],  # fmt: skip
    'td.slot.preset': ['name', 'type_id', 'kind', 'data', 'company_id', 'active'],
    'td.putaway.rule': [
        'site_id', 'uid', 'product_id', 'category_id', 'package_type_ids', 'in_location_id', 'out_code',
        'out_location_id', 'sublocation', 'storage_category_id', 'sequence', 'odoo_rule_id', 'deleted', 'company_id',
        'active',
    ],  # fmt: skip
    'td.replenish.rule': [
        'site_id', 'uid', 'product_id', 'cell_code', 'location_id', 'min_qty', 'max_qty', 'odoo_orderpoint_id',
        'deleted', 'company_id', 'active',
    ],  # fmt: skip
    'td.publish.op': ['version_id', 'seq', 'op', 'res_model', 'res_id', 'code', 'before', 'after', 'rolled_back'],
    'td.layout.variant': [
        'site_id', 'name', 'sequence', 'snapshot_id', 'base_version_id', 'is_training', 'metrics', 'company_id',
        'active',
    ],  # fmt: skip
    'td.comment': [
        'site_id', 'target_kind', 'target_uid', 'target_label', 'kind', 'state', 'text', 'author_id', 'resolved_by_id',
        'resolved_at', 'company_id', 'active',
    ],  # fmt: skip
    'td.zone.lock': ['site_id', 'zone_uid', 'user_id', 'expires_at', 'company_id'],
}
PARAMS = {
    'lock_ttl_s': '300',
    'lock_heartbeat_s': '60',
    'variants_max': '12',
    'versions_keep': '50',
    'stock_days': '90',
    'labels_max': '5000',
}


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestSkeletonModels(F3DConstructorCase):
    """W0-B: модели и поля MERGE.md §3.3–3.4 создаются без бизнес-логики; параметры, меню, представления."""

    def test_fields_exist(self):
        for model, names in {**EXTENDED_FIELDS, **NEW_FIELDS}.items():
            fields_ = self.env[model]._fields
            missing = [name for name in names if name not in fields_]
            self.assertFalse(missing, "%s: немає полів %s" % (model, missing))

    def test_defaults_of_existing_models(self):
        site, layer = self.site, self.layers['storage']
        self.assertEqual((site.loc_tree, site.depth_mode), ('flat', 'level'))
        self.assertFalse(site.addr or site.parse_rules or site.wizard_state)  # порожній JSON читається як False
        self.assertEqual((site.sprinkler_height_m, site.publish_copy_ack), (0.0, False))
        self.assertFalse(site.warehouse_id or site.active_variant_id or site.odoo_baseline_id)
        self.assertFalse(layer.items)
        slot = self.make_slot()
        self.assertFalse(slot.type_id or slot.storage_category_id or slot.removal_strategy_id or slot.function_id)
        self.assertFalse(slot.addr or slot.depth_mode or slot.tech or slot.attr_ids)
        self.assertGreater(slot.cell_count, 0)  # комірки на льоту не зачеплені новими полями (R-01)
        location = self.env['stock.location'].create({'name': 'TD-R', 'usage': 'internal', 'td_row': 3, 'td_pos': 2})
        self.assertEqual((location.td_row, location.td_bay, location.td_level, location.td_pos), (3, 0, 0, 2))

    def test_site_new_fields_roundtrip(self):
        warehouse = self.env['stock.warehouse'].search([('company_id', '=', self.company.id)], limit=1)
        self.site.write(
            {
                'warehouse_id': warehouse.id,
                'addr': {'tpl': '{row}-{bay}'},
                'loc_tree': 'row',
                'depth_mode': 'cell',
                'sprinkler_height_m': 6.5,
                'aisle_tech': 'reach_truck',
                'parse_rules': {'sep': '-'},
                'wizard_state': {'step': 2},
                'publish_copy_ack': True,
            }
        )
        self.site.invalidate_recordset()
        self.assertEqual((self.site.warehouse_id, self.site.loc_tree, self.site.depth_mode), (warehouse, 'row', 'cell'))
        self.assertEqual(self.site.addr['tpl'], '{row}-{bay}')  # R-22 (S1): нормалізовано з умовчаннями
        self.assertEqual(self.site.sprinkler_height_m, 6.5)

    def test_term_new_types_and_fields(self):
        Term = self.env['td.term']
        func = Term.create({'term_type': 'zone_function', 'key': 'dock', 'name': "Док", 'color': '#3366cc'})
        attr = Term.create({'term_type': 'zone_attr', 'key': 'cold', 'name': "Холод", 'value': '+2…+8'})
        self.assertEqual((func.color, attr.value), ('#3366cc', '+2…+8'))
        slot = self.make_slot(prefix='TQ-Z1')
        slot.write({'function_id': func.id, 'attr_ids': [Command.set(attr.ids)], 'temp_min_c': 2.0, 'temp_max_c': 8.0})
        self.assertEqual((slot.function_id, slot.attr_ids, slot.temp_max_c), (func, attr, 8.0))

    def test_check_config_new_keys(self):
        selection = dict(self.env['td.check.config']._fields['check_key'].selection)
        new_keys = ['inside', 'aisle_width', 'height', 'cell_load', 'putaway_fit', 'code_conflict']
        self.assertEqual(len(selection), 13)
        self.assertTrue(set(new_keys) <= set(selection))
        for key in new_keys:
            cfg = self.env['td.check.config'].create({'site_id': self.site.id, 'check_key': key, 'mode': 'warn'})
            self.assertEqual((cfg.check_key, cfg.params or {}), (key, {}))
        self.assertEqual(len(self.site.check_config_ids), 13)

    def test_new_models_create(self):
        env, site = self.env, self.site
        stype = env['td.slot.type'].create(
            {'code': 'R01', 'ref': 'R01', 'name': "Фронтальний", 'template': 'pallet_rack', 'params': {'levels': 4}}
        )
        self.assertEqual((stype.group, stype.relevance, stype.is_custom, stype.active), ('rack', 0, False, True))
        # UNIQUE (code, company)
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.cr.savepoint():
            env['td.slot.type'].create({'code': 'R01', 'name': "Дубль"})
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.cr.savepoint():  # relevance 0…2
            env['td.slot.type'].create({'code': 'R99', 'name': "Погана важливість", 'relevance': 3})
        other = env['td.slot.type'].create({'code': 'R01', 'name': "Власний", 'company_id': self.company.id})
        self.assertTrue(other)  # той самий ключ в іншій «компанії» дозволено
        slot = self.make_slot(prefix='TQ-T1')
        slot.type_id = stype
        self.assertEqual(slot.type_id.code, 'R01')
        preset = env['td.slot.preset'].create(
            {
                'name': "Ряд 4 яруси",
                'type_id': stype.id,
                'data': {'slot': {'template': 'pallet_rack', 'params': {'levels': 4}}},
            }
        )
        self.assertEqual((preset.kind, preset.company_id), ('row', self.company))

        product = env['product.product'].create({'name': "Тестовий товар"})
        draft_rev = site.draft_rev
        putaway = env['td.putaway.rule'].create(
            {'site_id': site.id, 'product_id': product.id, 'out_code': 'TQ-R1-B01-L1', 'in_location_id': self.wh_fg.id}
        )
        replenish = env['td.replenish.rule'].create(
            {'site_id': site.id, 'product_id': product.id, 'cell_code': 'TQ-R1-B01-L1', 'min_qty': 2, 'max_qty': 10}
        )
        self.assertEqual(site.draft_rev, draft_rev + 2)  # чернетки на td.draft.mixin: лічильник R-21
        self.assertTrue(putaway.uid and replenish.uid and putaway.uid != replenish.uid)
        self.assertEqual((putaway.sublocation, putaway.deleted, putaway.company_id), ('no', False, self.company))
        putaway.unlink()
        self.assertEqual(site.draft_rev, draft_rev + 3)

        version = env['td.layout.version'].create({'site_id': site.id, 'n': 1})
        self.assertEqual((version.kind, version.op_ids), ('publish', env['td.publish.op']))
        self.assertFalse(version.metrics)
        op = env['td.publish.op'].create(
            {
                'version_id': version.id,
                'seq': 1,
                'op': 'create',
                'res_model': 'stock.location',
                'res_id': self.wh_fg.id,
                'code': 'FG',
                'before': {},
                'after': {'name': 'FG'},
            }
        )
        self.assertEqual((version.op_ids, op.rolled_back), (op, False))
        variant = env['td.layout.variant'].create(
            {'site_id': site.id, 'name': "Варіант А", 'base_version_id': version.id}
        )
        site.active_variant_id = variant
        version.variant_id = variant
        self.assertEqual((site.active_variant_id, variant.company_id), (variant, self.company))
        self.assertFalse(variant.is_training)
        comment = env['td.comment'].create({'site_id': site.id, 'target_uid': slot.uid, 'text': "Перевірити висоту"})
        self.assertEqual((comment.kind, comment.state, comment.author_id), ('note', 'open', env.user))
        lock = env['td.zone.lock'].create(
            {'site_id': site.id, 'zone_uid': slot.uid, 'expires_at': fields.Datetime.now() + timedelta(seconds=300)}
        )
        self.assertEqual((lock.user_id, lock.company_id), (env.user, self.company))
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'), self.cr.savepoint():  # одна оренда на зону
            env['td.zone.lock'].create(
                {'site_id': site.id, 'zone_uid': slot.uid, 'expires_at': fields.Datetime.now()}
            )

    def test_variant_removal_cleans_links(self):
        variant = self.env['td.layout.variant'].create({'site_id': self.site.id, 'name': "Тимчасовий"})
        self.site.active_variant_id = variant
        variant.unlink()
        self.assertFalse(self.site.active_variant_id)

    def test_publish_wizard_line_extension(self):
        Line = self.env['td.publish.wizard.line']
        kinds = dict(Line._fields['kind'].selection)
        models_ = dict(Line._fields['res_model'].selection)
        self.assertTrue({'create', 'update', 'archive', 'move', 'rename', 'attrs'} <= set(kinds))
        self.assertTrue({'stock.warehouse.orderpoint', 'stock.putaway.rule', 'stock.location'} <= set(models_))
        wizard = self.env['td.publish.wizard'].create({'site_id': self.site.id})
        line = Line.create(
            {
                'wizard_id': wizard.id,
                'kind': 'move',
                'res_model': 'stock.putaway.rule',
                'code': 'TQ-R1',
                'depends_code': 'TQ',
                'scope_uid': 'abc',
                'before': {'location_id': 1},
            }
        )
        self.assertEqual((line.depends_code, line.scope_uid, line.before), ('TQ', 'abc', {'location_id': 1}))

    def test_params_menus_actions_views(self):
        get = self.env['ir.config_parameter'].sudo().get_param
        for key, value in PARAMS.items():
            self.assertEqual(get('td.constructor.' + key), value, key)
        menus = [
            'menu_td_slot_type', 'menu_td_slot_preset', 'menu_td_putaway_rule', 'menu_td_replenish_rule',
            'menu_td_publish_op', 'menu_td_layout_variant', 'menu_td_comment', 'menu_td_zone_lock',
        ]  # fmt: skip
        for name in menus:
            menu = self.env.ref('td_constructor.' + name)
            self.assertTrue(menu.action, name)
        for model in NEW_MODELS:
            views = self.env[model].get_views([(False, 'list'), (False, 'form')])
            self.assertEqual(set(views['views']), {'list', 'form'}, model)
