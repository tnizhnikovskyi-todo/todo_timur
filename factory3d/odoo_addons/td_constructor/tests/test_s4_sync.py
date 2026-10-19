import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from odoo import Command
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from ..services import odoo_sync
from .common import PASSWORD, F3DConstructorCase, F3DConstructorHttpCase

FACTORY3D = Path(__file__).resolve().parents[3]
SCRIPT = FACTORY3D / 'tools' / 's4_feed_import.mjs'
LOCATIONS = '/f3d/constructor/odoo/locations'
RULES = '/f3d/constructor/odoo/rules'
MASK4 = '{зона:a}-{ряд}-{секція}-{ярус}'


def loc(id_, code, name=None, parent='WH/Stock', active=True, parent_id=None):
    return {'id': id_, 'code': code, 'name': name or code, 'parent': parent, 'parent_id': parent_id, 'active': active}


class StructureFixture:
    """Склад WH/Stock: зона A (view) з коміркамиA-рр-сс-я, буфер (view) із двома місцями, локації без правила й без
    зони, залишки."""

    @classmethod
    def _structure_setup(cls):
        env = cls.env
        Loc = env['stock.location']

        def make(name, parent, usage='internal', **vals):
            return Loc.create({'name': name, 'usage': usage, 'location_id': parent.id, **vals})

        cls.zone_a = make('Зона A', cls.wh_stock, 'view')
        cls.cells = {}
        for row in (1, 2):
            for bay in (1, 2, 3):
                for level in (1, 2):
                    code = 'A-%02d-%02d-%d' % (row, bay, level)
                    cls.cells[code] = make(code, cls.zone_a, barcode=code)
        cls.buffer = make('Буфер', cls.wh_stock, 'view')
        cls.spots = {code: make(code, cls.buffer, barcode=code) for code in ('BUF-1', 'BUF-2')}
        cls.brak = make('Брак', cls.wh_stock)  # без штрихкоду: код = ім'я
        cls.archived = make('A-09-09-9', cls.zone_a, barcode='A-09-09-9')
        cls.archived.active = False
        cls.product = env['product.product'].create({'name': "Плита ДСП", 'default_code': 'DSP', 'is_storable': True})
        env['stock.quant'].sudo()._update_available_quantity(cls.product, cls.cells['A-01-01-1'], 7.0)
        env['stock.quant'].sudo()._update_available_quantity(cls.product, cls.brak, 3.0)

    def feed(self, **kw):
        return odoo_sync.locations_feed(self.env, self.site, **kw)

    def by_code(self, feed=None):
        return {row['code']: row for row in (feed or self.feed())['locations']}


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s4")
class TestS4Schema(F3DConstructorCase):
    """Схема `site.parse_rules` (R-22) і порівняння стрічок — без вмісту БД."""

    def test_normalize_parse_rules(self):
        self.assertEqual(odoo_sync.normalize_parse_rules(False), {})
        self.assertEqual(odoo_sync.normalize_parse_rules({}), {})
        out = odoo_sync.normalize_parse_rules(
            {
                'rules': [
                    {'id': 'a', 'mask': MASK4, 'type': 'pallet_rack', 'junk': 1},
                    {'mode': 'regex', 'regex': r'^(?<row>\d+)-(?<bay>\d+)$', 'type': 'невідомий', 'enabled': False},
                ],
                'tray': [
                    {
                        'code': 'Брак',
                        'name': 'Брак',
                        'parent': 'WH/Stock',
                        'usage': 'internal',
                        'reason': 'no_rule',
                        'x': 1,
                    },
                    {'name': 'без коду'},
                ],
                'tray_more': 5,
            }
        )
        self.assertEqual(out['v'], 1)
        self.assertEqual(
            out['rules'][0], {'id': 'a', 'mode': 'mask', 'type': 'pallet_rack', 'enabled': True, 'mask': MASK4}
        )
        self.assertEqual(
            (out['rules'][1]['id'], out['rules'][1]['type'], out['rules'][1]['enabled']), ('r2', 'auto', False)
        )
        self.assertEqual(
            out['tray'],
            [{'code': 'Брак', 'name': 'Брак', 'parent': 'WH/Stock', 'usage': 'internal', 'reason': 'no_rule'}],
        )
        self.assertEqual(out['tray_more'], 5)

    def test_normalize_parse_rules_errors(self):
        norm = odoo_sync.normalize_parse_rules
        for bad in (
            'рядок',
            {'rules': 'x'},
            {'rules': [{'mask': ''}]},
            {'rules': [{'mask': '{фрукт}-{ряд}'}]},
            {'rules': [{'mask': '{ряд'}]},
            {'rules': [{'mode': 'regex', 'regex': '('}]},
            {'rules': [{'mode': 'regex', 'regex': ''}]},
            {'rules': [{'mask': '{ряд}'}] * 31},
            {'rules': [5]},
            {'tray': 'x'},
        ):
            with self.assertRaises(ValidationError, msg=repr(bad)):
                norm(bad)
        with self.assertRaises(ValidationError):
            norm({'tray': [{'code': 'X'}] * 5001})

    def test_diff_feeds(self):
        old = [loc(1, 'A-1'), loc(2, 'A-2'), loc(3, 'A-3'), loc(4, 'A-4'), loc(5, 'A-5')]
        new = [
            loc(1, 'A-1'),
            loc(2, 'A-2', 'Нова назва'),
            loc(3, 'A-3', parent='WH/Stock/Інший', parent_id=77),
            loc(4, 'A-4', active=False),
            loc(6, 'A-6'),
            loc(5, 'A-5X'),
        ]
        diff = odoo_sync.diff_feeds(old, new)
        self.assertEqual(sorted(x['code'] for x in diff['appeared']), ['A-5X', 'A-6'])
        self.assertEqual(
            sorted(x['code'] for x in diff['disappeared']), ['A-4', 'A-5'], "неактивне й зміна коду — «зникло»"
        )
        self.assertEqual(diff['renamed'], [{'id': 2, 'code': 'A-2', 'old': 'A-2', 'new': 'Нова назва'}])
        self.assertEqual(
            diff['moved'],
            [{'id': 3, 'code': 'A-3', 'old_parent': 'WH/Stock', 'new_parent': 'WH/Stock/Інший', 'new_parent_id': 77}],
        )
        same = odoo_sync.diff_feeds(old, old)
        self.assertEqual(same, {'appeared': [], 'disappeared': [], 'renamed': [], 'moved': []})
        # без id — за кодом
        by_code = odoo_sync.diff_feeds(
            [{'code': 'X', 'name': 'X', 'parent': 'P'}], [{'code': 'X', 'name': 'Y', 'parent': 'P'}]
        )
        self.assertEqual(by_code['renamed'], [{'id': None, 'code': 'X', 'old': 'X', 'new': 'Y'}])


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s4")
class TestS4Feed(StructureFixture, F3DConstructorCase):
    """API-16: стрічка локацій складу (з вкладеними, залишками), порівняння з базою, оновлення бази."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._structure_setup()

    def test_feed_content_and_filters(self):
        feed = self.feed()
        self.assertEqual(feed['root'], 'WH/Stock')
        self.assertEqual(feed['warehouse']['code'], 'WH')
        rows = self.by_code(feed)
        self.assertTrue({'Зона A', 'Буфер', 'Брак', 'A-01-01-1', 'BUF-2', 'FG'} <= set(rows))
        self.assertEqual(rows['A-01-01-1']['parent'], 'Зона A', "повна назва view-локації в Odoo — лише її ім'я")
        self.assertEqual(rows['A-01-01-1']['parent_id'], self.zone_a.id)
        self.assertEqual((rows['A-01-01-1']['usage'], rows['A-01-01-1']['barcode']), ('internal', 'A-01-01-1'))
        self.assertEqual(rows['Зона A']['usage'], 'view', "структура (вигляд) теж у стрічці")
        self.assertEqual(rows['Брак']['code'], 'Брак', "без штрихкоду код = ім'я")
        self.assertEqual(rows['A-01-01-1']['qty'], 7.0)
        self.assertEqual(rows['Брак']['qty'], 3.0)
        self.assertEqual(rows['A-01-02-1']['qty'], 0.0)
        self.assertNotIn('A-09-09-9', rows, "архівна локація відсутня")
        self.assertTrue(all(row['usage'] in ('internal', 'view') for row in feed['locations']))
        root = next(row for row in feed['locations'] if row['id'] == self.wh_stock.id)
        self.assertEqual(
            (root['usage'], root['parent_id'] in {r['id'] for r in feed['locations']}),
            ('internal', False),
            "корінь стрічки — батьківська локація площадки",
        )
        self.assertEqual(sum(1 for r in feed['locations'] if r['code'].startswith('A-')), 12)

    def test_feed_td_code_wins_and_batches(self):
        self.cells['A-01-01-1'].td_code = 'TD-CODE'
        self.assertIn('TD-CODE', self.by_code())
        page = self.feed(limit=5)
        self.assertEqual((len(page['locations']), page['truncated']), (5, True))
        seen = list(page['locations'])
        while page['truncated']:
            page = self.feed(offset=page['next'], limit=5)
            seen.extend(page['locations'])
        self.assertEqual(len(seen), self.feed()['total'])
        self.assertEqual(len({row['id'] for row in seen}), len(seen), "без повторів між партіями")

    def test_other_warehouse_and_missing_warehouse(self):
        wh2 = self.env['stock.warehouse'].create({'name': 'Другий', 'code': 'W2'})
        feed = self.feed(warehouse_id=wh2.id)
        self.assertEqual((feed['warehouse']['code'], feed['root']), ('W2', wh2.lot_stock_id.complete_name))
        with self.assertRaises(UserError):
            self.feed(warehouse_id=999999)

    def test_sync_baseline_and_diff(self):
        first = odoo_sync.sync(self.env, self.site)
        self.assertEqual(first['baseline'], 'created')
        self.assertEqual(first['diff'], {'appeared': [], 'disappeared': [], 'renamed': [], 'moved': []})
        self.assertTrue(self.site.odoo_baseline_id, "база порівняння — вкладення площадки")
        self.assertNotIn('locations', first['feed'], "у відповіді sync немає великого списку")
        again = odoo_sync.sync(self.env, self.site)
        self.assertEqual(again['baseline'], 'existing')
        self.assertEqual(again['diff']['appeared'] + again['diff']['renamed'], [])
        self.cells['A-01-01-1'].name = 'Нова назва'  # штрихкод лишився — код той самий
        self.cells['A-01-01-2'].location_id = self.buffer
        self.cells['A-01-02-1'].active = False
        new = self.env['stock.location'].create(
            {'name': 'A-09-01-1', 'usage': 'internal', 'location_id': self.zone_a.id, 'barcode': 'A-09-01-1'}
        )
        diff = odoo_sync.sync(self.env, self.site)['diff']
        self.assertEqual([x['code'] for x in diff['appeared']], ['A-09-01-1'])
        self.assertEqual(diff['appeared'][0]['id'], new.id)
        self.assertEqual([x['code'] for x in diff['disappeared']], ['A-01-02-1'])
        self.assertEqual(
            [(x['code'], x['old'], x['new']) for x in diff['renamed']], [('A-01-01-1', 'A-01-01-1', 'Нова назва')]
        )
        self.assertEqual(
            [(x['code'], x['new_parent'], x['new_parent_id']) for x in diff['moved']],
            [('A-01-01-2', 'Буфер', self.buffer.id)],
        )
        odoo_sync.save_baseline(self.site, odoo_sync.full_feed(self.env, self.site)['locations'])
        self.assertEqual(
            odoo_sync.sync(self.env, self.site)['diff'], {'appeared': [], 'disappeared': [], 'renamed': [], 'moved': []}
        )
        self.assertEqual(
            self.env['ir.attachment']
            .sudo()
            .search_count(
                [('res_model', '=', 'td.site'), ('res_id', '=', self.site.id), ('name', '=', odoo_sync.BASELINE_NAME)]
            ),
            1,
            "одне вкладення, оновлюється",
        )

    def test_structure_imports_into_project_with_addressing_s1(self):
        """Критерій S4: структура складу з Odoo → проєкт ядром; коди розібрано за шаблоном адресації S1; нерозібране — в
        лоток."""
        node = shutil.which('node')
        if not node or not SCRIPT.is_file():
            self.skipTest("немає node або tools/s4_feed_import.mjs")
        feed = self.feed()
        payload = {'locations': feed['locations'], 'addr': {'tpl': '{zone} {row} {bay} {level}'}, 'rules': []}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'feed.json'
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
            proc = subprocess.run(
                [node, str(SCRIPT), str(path)], cwd=FACTORY3D, capture_output=True, text=True, timeout=120, check=False
            )
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        res = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertTrue(res['ok'], res['reason'])
        expected = sorted(list(self.cells) + list(self.spots))
        self.assertEqual(res['codes'], expected, "коди комірок проєкту = коди локацій Odoo")
        tray = dict(res['tray'])
        self.assertEqual(
            (tray.get('Брак'), tray.get('FG')), ('no_rule', 'no_rule'), "без правила й без зони-родителя — лоток"
        )
        self.assertEqual(
            sorted(res['zones']), ['Зона A', 'Зона BUF'], "шаблон читає BUF-1 як зона BUF, ряд 1 → місце на підлозі"
        )
        self.assertEqual(res['stats']['skipped_usage'], 0)
        self.assertGreaterEqual(res['stats']['rules'].get('addr', 0), 12, "розібрано шаблоном адресації площадки")
        # те саме через правило-маску без власної адресації площадки
        payload.update(addr=None, rules=[{'id': 'm', 'mode': 'mask', 'mask': MASK4, 'type': 'auto', 'enabled': True}])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'feed.json'
            path.write_text(json.dumps(payload, ensure_ascii=False), encoding='utf-8')
            proc = subprocess.run(
                [node, str(SCRIPT), str(path)], cwd=FACTORY3D, capture_output=True, text=True, timeout=120, check=False
            )
        res2 = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertEqual(res2['codes'], expected)
        self.assertEqual(res2['stats']['rules'], {'m': 12})
        self.assertEqual(
            sorted(res2['zones']), ['Буфер', 'Зона A'], "без шаблону BUF-1 — місце на підлозі в зоні-родителі «Буфер»"
        )


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s4")
class TestS4Api(StructureFixture, F3DConstructorHttpCase):
    """JSON-RPC: `/odoo/locations` (feed, sync, baseline) і `/odoo/rules` — права, помилки, запис правил і лотка."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._structure_setup()

    def test_locations_feed_route_and_rights(self):
        self.authenticate(self.u_plain.login, PASSWORD)
        res = self.rpc(LOCATIONS, site_id=self.site.id)
        self.assertTrue(res['ok'], res)
        self.assertEqual(res['feed']['root'], 'WH/Stock')
        self.assertTrue(any(r['code'] == 'A-01-01-1' for r in res['feed']['locations']))
        self.assertEqual(self.rpc(LOCATIONS, site_id=self.site.id, op='зайве')['code'], 'validation')
        self.assertEqual(self.rpc(LOCATIONS, site_id=0)['code'], 'not_found')
        self.assertEqual(self.rpc(LOCATIONS, site_id=self.site.id, offset='x')['code'], 'validation')
        self.assertEqual(self.rpc(LOCATIONS, site_id=self.site.id, warehouse_id='ab')['code'], 'validation')
        small = self.rpc(LOCATIONS, site_id=self.site.id, limit=3)
        self.assertEqual((len(small['feed']['locations']), small['feed']['truncated']), (3, True))
        outsider = (
            self.env['res.users']
            .with_context(no_reset_password=True)
            .create(
                {
                    'name': 'out',
                    'login': 'f3d_out4',
                    'password': PASSWORD,
                    'group_ids': [Command.set([self.env.ref('base.group_user').id])],
                }
            )
        )
        self.authenticate(outsider.login, PASSWORD)
        self.assertEqual(self.rpc(LOCATIONS, site_id=self.site.id)['code'], 'rights')

    def test_sync_and_baseline_route(self):
        self.authenticate(self.u_tech.login, PASSWORD)
        first = self.rpc(LOCATIONS, site_id=self.site.id, op='sync')
        self.assertEqual((first['ok'], first['baseline']), (True, 'created'))
        self.cells['A-01-01-1'].name = 'Перейменовано'
        diff = self.rpc(LOCATIONS, site_id=self.site.id, op='sync')['diff']
        self.assertEqual([x['code'] for x in diff['renamed']], ['A-01-01-1'])
        self.authenticate(self.u_plain.login, PASSWORD)
        self.site.sudo().odoo_baseline_id.unlink()
        viewer = self.rpc(LOCATIONS, site_id=self.site.id, op='sync')
        self.assertEqual((viewer['ok'], viewer['baseline']), (True, 'missing'), "читач бази не створює")
        self.assertFalse(self.site.sudo().odoo_baseline_id)
        denied = self.rpc(LOCATIONS, site_id=self.site.id, op='baseline')
        self.assertEqual(denied['code'], 'rights', "базу змінює менеджер чи проєктувальник шару")
        self.authenticate(self.u_manager.login, PASSWORD)
        self.assertTrue(self.rpc(LOCATIONS, site_id=self.site.id, op='baseline')['ok'])
        self.assertEqual(self.rpc(LOCATIONS, site_id=self.site.id, op='sync')['diff']['renamed'], [])

    def test_rules_route_saves_rules_and_tray(self):
        self.authenticate(self.u_manager.login, PASSWORD)
        rev0 = self.site.draft_rev
        value = {
            'v': 1,
            'rules': [{'id': 'm', 'mode': 'mask', 'mask': MASK4, 'type': 'auto', 'enabled': True}],
            'tray': [{'code': 'Брак', 'name': 'Брак', 'parent': 'WH/Stock', 'usage': 'internal', 'reason': 'no_rule'}],
        }
        res = self.rpc(RULES, site_id=self.site.id, parse_rules=value)
        self.assertTrue(res['ok'], res)
        self.assertEqual(res['rev'], rev0 + 1)
        self.site.invalidate_recordset()
        self.assertEqual(self.site.parse_rules, value)
        loaded = self.rpc('/f3d/constructor/load', site_id=self.site.id)
        self.assertEqual(loaded['site']['parse_rules'], value, "load віддає правила й лоток")
        bad = self.rpc(RULES, site_id=self.site.id, parse_rules={'rules': [{'mask': '{фрукт}'}]})
        self.assertEqual((bad['ok'], bad['code']), (False, 'validation'))
        self.assertEqual(self.site.parse_rules, value, "помилка нічого не змінила")
        cleared = self.rpc(RULES, site_id=self.site.id, parse_rules={})
        self.assertTrue(cleared['ok'])
        self.site.invalidate_recordset()
        self.assertFalse(self.site.parse_rules)

    def test_rules_route_rights(self):
        self.authenticate(self.u_plain.login, PASSWORD)
        res = self.rpc(RULES, site_id=self.site.id, parse_rules={'rules': []})
        self.assertEqual((res['ok'], res['code']), (False, 'rights'))
        self.authenticate(self.u_manager.login, PASSWORD)
        self.assertEqual(self.rpc(RULES, site_id=0, parse_rules={})['code'], 'not_found')
