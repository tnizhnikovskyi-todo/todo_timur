from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import PASSWORD, F3DConstructorHttpCase

ROW = {'slot': {'template': 'pallet_rack', 'params': {'bays': 5, 'levels': 3}, 'rotation': 450, 'type_code': 'r01'}}
GROUP = {
    'slots': [
        {'template': 'pallet_rack', 'params': {'bays': 2}, 'rotation': 0, 'dx': 0, 'dy': 0, 'prefix': 'A1'},
        {'template': 'floor_spot', 'params': {'length': 2.0}, 'rotation': 90, 'dx': 5.5, 'dy': -3},
    ]
}


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s1")
class TestLibraryApi(F3DConstructorHttpCase):
    """API-11 `/library`: типи й пресети, права (перегляд / проєктування / менеджер), компанії (F08, F09-06/07)."""

    URL = '/f3d/constructor/library'

    def login(self, user):
        self.authenticate(user.login, PASSWORD)

    def call(self, **params):
        return self.rpc(self.URL, **params)

    def test_list_for_viewer_and_load(self):
        self.login(self.u_plain)
        res = self.call(op='list')
        self.assertTrue(res['ok'], res)
        self.assertEqual(len(res['types']), 50)
        self.assertEqual(res['presets'], [])
        self.assertEqual(
            {'id', 'code', 'ref', 'name', 'group', 'template', 'shape', 'params', 'relevance', 'is_custom'}
            - set(res['types'][0]),
            set(),
        )
        load = self.rpc('/f3d/constructor/load', site_id=self.site.id)
        self.assertEqual(len(load['types']), 50)  # той самий склад у API-03

    def test_viewer_cannot_write(self):
        self.login(self.u_plain)
        for kind, vals in (
            ('type', {'code': 'v1', 'name': "V", 'group': 'rack', 'template': 'shelf'}),
            ('preset', {'name': "P", 'kind': 'row', 'data': ROW}),
        ):
            res = self.call(op='save', kind=kind, vals=vals)
            self.assertEqual((res['ok'], res['code']), (False, 'rights'), kind)
        self.assertEqual(self.call(op='delete', kind='type', id=1)['code'], 'rights')

    def test_designer_type_lifecycle(self):
        self.login(self.u_tech)
        vals = {
            'code': 'tech_t1',
            'name': "Стелаж технолога",
            'group': 'rack',
            'template': 'pallet_rack',
            'params': {'bays': 4, 'deep': 2},
            'shape': 'rack',
            'description': "Мій",
        }
        res = self.call(op='save', kind='type', vals=vals)
        self.assertTrue(res['ok'], res)
        rec = res['record']
        self.assertTrue(rec['is_custom'])
        self.assertEqual(rec['company_id'], self.company.id)
        self.assertEqual((rec['params']['deep'], rec['shape']), (2, 'rack'))
        res = self.call(op='save', kind='type', id=rec['id'], vals={'name': "Інша назва", 'params': {'bays': 5}})
        self.assertTrue(res['ok'], res)
        self.assertEqual((res['record']['name'], res['record']['code']), ("Інша назва", 'tech_t1'))
        self.assertEqual(
            self.call(op='save', kind='type', id=rec['id'], vals={'code': 'new'})['code'], 'validation'
        )  # ключ стабільний
        # чужі й службові поля, хибні дані
        self.assertEqual(
            self.call(op='save', kind='type', vals=dict(vals, code='t2', company_id=5))['code'], 'validation'
        )
        self.assertEqual(
            self.call(op='save', kind='type', vals=dict(vals, code='t3', params={'bays': 0}))['code'], 'validation'
        )
        with mute_logger('odoo.sql_db'):  # дубль ключа
            res = self.call(op='save', kind='type', vals=dict(vals, code='tech_t1'))
        self.assertEqual(res['code'], 'validation')
        self.assertEqual(self.call(op='save', kind='type', vals='x')['code'], 'validation')
        self.assertEqual(self.call(op='save', kind='nope', vals={})['code'], 'validation')
        self.assertEqual(self.call(op='frob')['code'], 'validation')
        # каталог змінює лише менеджер; видаляє лише менеджер
        catalog = self.env['td.slot.type'].search([('code', '=', 'r01')])
        self.assertEqual(self.call(op='save', kind='type', id=catalog.id, vals={'name': "Зламаний"})['code'], 'rights')
        self.assertEqual(self.call(op='delete', kind='type', id=rec['id'])['code'], 'rights')
        self.login(self.u_manager)
        self.assertEqual(
            self.call(op='delete', kind='type', id=catalog.id)['code'], 'validation'
        )  # тип каталогу не видаляється
        self.assertEqual(self.call(op='delete', kind='type', id=99999)['code'], 'not_found')
        used = self.make_slot(prefix='LB-1', bays=1, levels=1)
        used.type_id = self.env['td.slot.type'].browse(rec['id'])
        res = self.call(op='delete', kind='type', id=rec['id'])
        self.assertEqual((res['ok'], res['code']), (False, 'validation'))
        self.assertIn('використовується', res['message'])
        used.type_id = False
        self.assertTrue(self.call(op='delete', kind='type', id=rec['id'])['ok'])

    def test_presets_lifecycle_and_validation(self):
        self.login(self.u_store)
        res = self.call(op='save', kind='preset', vals={'name': "Ряд 5×3", 'kind': 'row', 'data': ROW})
        self.assertTrue(res['ok'], res)
        rec = res['record']
        self.assertEqual(rec['kind'], 'row')
        self.assertEqual(rec['company_id'], self.company.id)
        slot = rec['data']['slot']
        self.assertEqual(
            (slot['rotation'], slot['params']['bays'], slot['params']['levels'], slot['type_code']), (90, 5, 3, 'r01')
        )
        self.assertEqual(slot['params']['bay_width'], 2.7)  # параметри нормалізовано за генератором
        group = self.call(op='save', kind='preset', vals={'name': "Блок", 'kind': 'group', 'data': GROUP})
        self.assertTrue(group['ok'], group)
        self.assertEqual(group['record']['data']['slots'][1]['dx'], 5.5)
        section = self.call(
            op='save',
            kind='preset',
            vals={
                'name': "Секція",
                'kind': 'section',
                'data': {'slot': {'template': 'shelf', 'params': {'sections': 1}}},
            },
        )
        self.assertTrue(section['ok'], section)
        # оновлення
        res = self.call(op='save', kind='preset', id=rec['id'], vals={'name': "Ряд 5×3 (нове)"})
        self.assertEqual(res['record']['name'], "Ряд 5×3 (нове)")
        res = self.call(op='save', kind='preset', id=rec['id'], vals={'kind': 'group', 'data': GROUP})
        self.assertEqual(res['record']['kind'], 'group')
        listing = self.call(op='list')
        self.assertEqual(len(listing['presets']), 3)
        # хибні дані
        for kind, data in (
            ('row', {'slot': {'template': 'zone', 'params': {}}}),
            ('row', {'slot': {'template': 'pallet_rack', 'params': {'bays': 0}}}),
            ('section', {'slot': {'template': 'floor_spot', 'params': {}}}),
            ('group', {'slots': []}),
            ('group', {'slots': [{'template': 'floor_spot', 'params': {}}] * 201}),
            ('row', {'slot': {'template': 'pallet_rack', 'rotation': 'x'}}),
            ('row', {'slot': {'template': 'shelf', 'dx': 'x'}}),
            ('row', 'x'),
            ('nope', {}),
        ):
            res = self.call(op='save', kind='preset', vals={'name': "Хибний", 'kind': kind, 'data': data})
            self.assertEqual((res['ok'], res['code']), (False, 'validation'), (kind, data))
        self.assertEqual(
            self.call(op='save', kind='preset', vals={'name': "X", 'kind': 'row', 'data': ROW, 'active': False})[
                'code'
            ],
            'validation',
        )
        self.assertEqual(
            self.call(op='save', kind='preset', vals={'name': "X", 'kind': 'row', 'data': ROW, 'type_id': 99999})[
                'code'
            ],
            'validation',
        )
        # видаляє менеджер
        self.assertEqual(self.call(op='delete', kind='preset', id=rec['id'])['code'], 'rights')
        self.login(self.u_manager)
        self.assertTrue(self.call(op='delete', kind='preset', id=rec['id'])['ok'])
        self.assertEqual(self.call(op='delete', kind='preset', id=rec['id'])['code'], 'not_found')
        self.assertEqual(len(self.call(op='list')['presets']), 2)

    def test_company_isolation(self):
        company2 = self.env['res.company'].create({'name': "Друга компанія"})
        Type, Preset = self.env['td.slot.type'], self.env['td.slot.preset']
        Type.create(
            {
                'code': 'other_type',
                'name': "Чужий",
                'group': 'rack',
                'template': 'shelf',
                'is_custom': True,
                'company_id': company2.id,
            }
        )
        Preset.create({'name': "Чужий пресет", 'kind': 'row', 'data': ROW, 'company_id': company2.id})
        mine = self.env['td.slot.preset'].create(
            {'name': "Мій пресет", 'kind': 'row', 'data': ROW, 'company_id': self.company.id}
        )
        self.login(self.u_manager)
        res = self.call(op='list')
        self.assertNotIn('other_type', [t['code'] for t in res['types']])
        self.assertEqual([p['name'] for p in res['presets']], ["Мій пресет"])
        self.assertEqual(
            self.call(
                op='save',
                kind='preset',
                id=Preset.search([('name', '=', "Чужий пресет")]).id,
                vals={'name': "Зломлено"},
            )['code'],
            'not_found',
        )
        self.assertEqual(self.call(op='delete', kind='preset', id=mine.id)['ok'], True)
