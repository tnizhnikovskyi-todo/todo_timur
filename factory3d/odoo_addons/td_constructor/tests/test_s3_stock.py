from datetime import timedelta

from odoo import Command, fields
from odoo.tests import tagged

from ..services import metrics
from .common import PASSWORD, F3DConstructorCase, F3DConstructorHttpCase

STATE = '/f3d/constructor/stock/state'
FIND = '/f3d/constructor/stock/find'


class StockFixture:
    """Три комірки площадки з залишками: категорія з ємністю товару, вага, без категорії; рух, правило поповнення."""

    @classmethod
    def _stock_setup(cls):
        env = cls.env
        Loc = env['stock.location']
        cls.product_a = env['product.product'].create(
            {'name': "Плита ДСП білий", 'default_code': 'DSP-W', 'is_storable': True, 'weight': 10.0}
        )
        cls.product_b = env['product.product'].create(
            {'name': "Фасад МДФ", 'default_code': 'MDF-F', 'is_storable': True, 'weight': 2.0}
        )
        cls.cat_qty = env['stock.storage.category'].create(
            {
                'name': "ДСП 20",
                'max_weight': 1000,
                'product_capacity_ids': [Command.create({'product_id': cls.product_a.id, 'quantity': 20})],
            }
        )
        cls.cat_weight = env['stock.storage.category'].create({'name': "Вага 100", 'max_weight': 100})

        def loc(code, **vals):
            return Loc.create(
                {
                    'name': code,
                    'usage': 'internal',
                    'location_id': cls.wh_stock.id,
                    'td_code': code,
                    'td_site_id': cls.site.id,
                    **vals,
                }
            )

        cls.l1 = loc('TST-R1-B01-L1', storage_category_id=cls.cat_qty.id)
        cls.l2 = loc('TST-R1-B01-L2', storage_category_id=cls.cat_weight.id)
        cls.l3 = loc('TST-R1-B02-L1')
        cls.l4 = loc('TST-R1-B02-L2', storage_category_id=cls.cat_qty.id)  # порожня, але з ємністю
        cls.foreign = Loc.create(
            {'name': 'ЧУЖА', 'usage': 'internal', 'location_id': cls.wh_stock.id, 'td_code': 'OTHER-1'}
        )
        Quant = env['stock.quant']
        old = fields.Datetime.now() - timedelta(days=200)
        lot_old = env['stock.lot'].create({'name': 'LOT-OLD', 'product_id': cls.product_a.id})
        lot_new = env['stock.lot'].create({'name': 'LOT-NEW', 'product_id': cls.product_a.id})
        Quant._update_available_quantity(cls.product_a, cls.l1, 10.0, lot_id=lot_old, in_date=old)
        Quant._update_available_quantity(
            cls.product_a, cls.l1, 5.0, lot_id=lot_new, in_date=fields.Datetime.now() - timedelta(days=5)
        )
        Quant._update_available_quantity(cls.product_a, cls.l2, 4.0)  # 4 × 10 кг = 40 кг із 100
        Quant._update_available_quantity(cls.product_a, cls.foreign, 99.0)
        Quant.search([('location_id', '=', cls.l1.id), ('lot_id', '=', lot_old.id)]).reserved_quantity = 3.0
        env['stock.warehouse.orderpoint'].create(
            {'product_id': cls.product_a.id, 'location_id': cls.l1.id, 'product_min_qty': 8.0, 'product_max_qty': 30.0}
        )
        # локація l3 наповнюється рухами: два за період і один старий (поза 90 днями)
        cls._done_move(cls.product_b, cls.l3, 4.0, days_ago=3)
        cls._done_move(cls.product_b, cls.l3, 3.0, days_ago=3)
        cls._done_move(cls.product_b, cls.l3, 2.0, days_ago=400)

    @classmethod
    def _done_move(cls, product, location, qty, days_ago):
        env = cls.env
        supplier = env.ref('stock.stock_location_suppliers')
        move = env['stock.move'].create(
            {
                'product_id': product.id,
                'product_uom_qty': qty,
                'product_uom': product.uom_id.id,
                'location_id': supplier.id,
                'location_dest_id': location.id,
            }
        )
        move._action_confirm()
        move._action_assign()
        move.move_line_ids.quantity = qty
        move.picked = True
        move._action_done()
        move.move_line_ids.write({'date': fields.Datetime.now() - timedelta(days=days_ago)})
        return move


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s3")
class TestS3StockState(StockFixture, F3DConstructorCase):
    """F06/F07: показники по кодах (API-13) — залишки, резерв, заповнення, вік, рух, min/max, пачки."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._stock_setup()

    def state(self, **kw):
        return metrics.stock_state(self.env, self.site, **kw)

    def test_aggregates_by_code(self):
        res = self.state()
        self.assertEqual(
            set(res['codes']),
            {'TST-R1-B01-L1', 'TST-R1-B01-L2', 'TST-R1-B02-L1', 'TST-R1-B02-L2'},
            "лише локації площадки",
        )
        self.assertFalse(res['demo'])
        self.assertEqual(res['days'], 90)
        c1 = res['codes']['TST-R1-B01-L1']
        self.assertEqual((c1['qty'], c1['reserved']), (15.0, 3.0))
        self.assertEqual(c1['top_product'], "Плита ДСП білий")
        self.assertEqual((c1['min'], c1['max']), (8.0, 30.0), "правило поповнення локації")
        self.assertEqual(c1['location_id'], self.l1.id)
        self.assertGreaterEqual(c1['age_days'], 199, "найстаріша партія — 200 днів")
        self.assertIsNotNone(c1['in_date'])
        self.assertEqual(c1['moves'], 0)
        c3 = res['codes']['TST-R1-B02-L1']
        self.assertEqual(
            (c3['qty'], c3['min'], c3['max'], c3['fill']), (9.0, None, None, None), "без правила й без категорії"
        )
        self.assertEqual(c3['moves'], 2, "два проведені рухи за 90 днів; старий (400 днів) не рахується")

    def test_fill_by_capacity_and_weight(self):
        res = self.state()['codes']
        self.assertEqual(res['TST-R1-B01-L1']['fill'], 0.75, "15 з 20 за ємністю товару")
        self.assertEqual(res['TST-R1-B01-L1']['capacity'], 20)
        self.assertEqual(res['TST-R1-B01-L2']['fill'], 0.4, "40 кг із 100 кг")
        self.assertEqual(res['TST-R1-B02-L2']['fill'], 0.0, "порожня комірка з ємністю = 0 %")
        self.assertEqual(res['TST-R1-B02-L2']['qty'], 0)
        self.assertIsNone(res['TST-R1-B02-L1']['fill'], "ємність не задано")

    def test_fill_uses_s2_capacity_service(self):
        """Вага й ліміт комірки — від сервісу ємності S2: max_load_kg комірки місця (а не лише категорія локації)."""
        slot = self.make_slot(prefix='TQ-R1', max_load_kg=500)
        code = slot._td_cells()[0]['code']
        loc = self.env['stock.location'].create(
            {
                'name': code,
                'usage': 'internal',
                'location_id': self.wh_stock.id,
                'td_code': code,
                'td_site_id': self.site.id,
            }
        )
        self.env['stock.quant']._update_available_quantity(self.product_a, loc, 10.0)  # 10 × 10 кг = 100 кг із 500
        res = self.state(codes=[code])['codes'][code]
        self.assertEqual(
            (res['fill'], res['capacity']), (0.2, 500.0), "ліміт — max_load_kg комірки від site_cell_limits"
        )
        self.assertEqual(metrics.cell_limits(self.site)[code], 500.0)
        self.env['ir.config_parameter'].sudo().set_param('product.weight_in_lbs', '1')
        res = self.state(codes=[code])['codes'][code]
        self.assertAlmostEqual(res['fill'], 0.2 * 0.45359237, places=3, msg="одиниці ваги Odoo (фунти) — як у S2")

    def test_codes_filter_and_unknown_code(self):
        res = self.state(codes=['TST-R1-B01-L2', 'OTHER-1', 'NOPE-1'])
        self.assertEqual(
            set(res['codes']), {'TST-R1-B01-L2'}, "чужа локація й невідомий код не потрапляють у відповідь"
        )
        self.assertFalse(res['truncated'])

    def test_period_parameter(self):
        self.assertEqual(self.state(days=5)['codes']['TST-R1-B02-L1']['moves'], 2)
        self.assertEqual(self.state(days=1)['codes']['TST-R1-B02-L1']['moves'], 0)
        self.env['ir.config_parameter'].sudo().set_param('td.constructor.stock_days', '30')
        self.assertEqual(metrics.stock_days(self.env), 30)
        self.assertEqual(self.state()['days'], 30)

    def test_batches(self):
        first = self.state(limit=2)
        self.assertEqual(list(first['codes']), ['TST-R1-B01-L1', 'TST-R1-B01-L2'])
        self.assertTrue(first['truncated'])
        self.assertEqual(first['next'], 2)
        second = self.state(offset=first['next'], limit=2)
        self.assertEqual(list(second['codes']), ['TST-R1-B02-L1', 'TST-R1-B02-L2'])

    def test_detail_for_card(self):
        res = self.state(codes=['TST-R1-B01-L1'], detail=True)
        detail = res['codes']['TST-R1-B01-L1']['detail']
        self.assertEqual(len(detail['rows']), 2, "два залишки: дві партії")
        self.assertEqual({r['ref'] for r in detail['rows']}, {'DSP-W'})
        self.assertEqual({r['lot']: r['qty'] for r in detail['rows']}, {'LOT-OLD': 10.0, 'LOT-NEW': 5.0})
        self.assertEqual(max(r['reserved'] for r in detail['rows']), 3.0)
        self.assertGreaterEqual(max(r['age_days'] for r in detail['rows']), 199)
        self.assertEqual(detail['category'], "ДСП 20")
        self.assertEqual(detail['record'], {'model': 'stock.location', 'id': self.l1.id})
        moves = self.state(codes=['TST-R1-B02-L1'], detail=True)['codes']['TST-R1-B02-L1']['detail']['moves']
        self.assertEqual(len(moves), 2)
        self.assertEqual(moves[0]['to'], 'TST-R1-B02-L1')
        self.assertEqual(moves[0]['product'], "Фасад МДФ")

    def test_find_all_words_in_one_quant(self):
        res = metrics.stock_find(self.env, self.site, "дсп білий")
        self.assertEqual([h['code'] for h in res['hits']], ['TST-R1-B01-L1', 'TST-R1-B01-L2'])
        self.assertEqual({i['ref'] for h in res['hits'] for i in h['items']}, {'DSP-W'})
        none = metrics.stock_find(self.env, self.site, "дсп фасад")
        self.assertEqual(none['hits'], [], "слова з різних залишків не з'єднуються")
        by_ref = metrics.stock_find(self.env, self.site, "mdf-f")
        self.assertEqual([h['code'] for h in by_ref['hits']], ['TST-R1-B02-L1'])
        self.assertEqual(metrics.stock_find(self.env, self.site, "   ")['hits'], [])

    def test_find_by_lot_and_package_modes(self):
        lot = self.env['stock.lot'].create({'name': 'LOT-777', 'product_id': self.product_b.id})
        self.env['stock.quant']._update_available_quantity(self.product_b, self.l4, 3.0, lot_id=lot)
        res = metrics.stock_find(self.env, self.site, "lot-777", mode='lot')
        self.assertEqual([h['code'] for h in res['hits']], ['TST-R1-B02-L2'])
        self.assertEqual(res['hits'][0]['items'][0]['lot'], 'LOT-777')
        self.assertEqual(metrics.stock_find(self.env, self.site, "lot-777", mode='product')['hits'], [])


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s3")
class TestS3StockApi(StockFixture, F3DConstructorHttpCase):
    """API-13/14: права (читає «Перегляд»), коди відповідей, перевірка вхідних даних."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._stock_setup()

    def test_state_route(self):
        self.authenticate(self.u_plain.login, PASSWORD)
        res = self.rpc(STATE, site_id=self.site.id)
        self.assertTrue(res['ok'], res)
        self.assertEqual(res['codes']['TST-R1-B01-L1']['qty'], 15.0)
        res = self.rpc(STATE, site_id=self.site.id, codes=['TST-R1-B01-L1'], detail=True)
        self.assertIn('rows', res['codes']['TST-R1-B01-L1']['detail'])
        res = self.rpc(STATE, site_id=self.site.id, codes=['TST-R1-B01-L1', 'TST-R1-B01-L2'] * 20, detail=True)
        self.assertNotIn('detail', res['codes']['TST-R1-B01-L1'], "подробиці лише для невеликого списку кодів")

    def test_state_validation_and_rights(self):
        self.authenticate(self.u_plain.login, PASSWORD)
        self.assertEqual(self.rpc(STATE, site_id=999999)['code'], 'not_found')
        self.assertEqual(self.rpc(STATE, site_id=self.site.id, codes='TST')['code'], 'validation')
        self.assertEqual(self.rpc(STATE, site_id=self.site.id, days=0 + 99999)['code'], 'validation')
        self.assertEqual(self.rpc(STATE, site_id=self.site.id, days='abc')['code'], 'validation')
        outsider = (
            self.env['res.users']
            .with_context(no_reset_password=True)
            .create(
                {
                    'name': 'Без групи',
                    'login': 'f3d_s3_out',
                    'password': PASSWORD,
                    'group_ids': [Command.set([self.env.ref('base.group_user').id])],
                }
            )
        )
        self.authenticate(outsider.login, PASSWORD)
        res = self.rpc(STATE, site_id=self.site.id)
        self.assertEqual((res['ok'], res['code']), (False, 'rights'))
        self.assertEqual(self.rpc(FIND, site_id=self.site.id, q='дсп')['code'], 'rights')

    def test_find_route(self):
        self.authenticate(self.u_tech.login, PASSWORD)
        res = self.rpc(FIND, site_id=self.site.id, q='дсп білий')
        self.assertTrue(res['ok'], res)
        self.assertEqual([h['code'] for h in res['hits']], ['TST-R1-B01-L1', 'TST-R1-B01-L2'])
        self.assertEqual(self.rpc(FIND, site_id=self.site.id, q='')['code'], 'validation')
        self.assertEqual(self.rpc(FIND, site_id=self.site.id, q='x', mode='bad')['code'], 'validation')
        self.assertEqual(self.rpc(FIND, site_id=self.site.id, q='x' * 300)['code'], 'validation')
