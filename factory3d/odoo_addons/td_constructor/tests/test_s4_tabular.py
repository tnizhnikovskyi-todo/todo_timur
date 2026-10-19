import base64
import io
import json
from pathlib import Path
from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from ..services import tabular
from ..services.registry import RENDERERS
from . import golden_s4
from .common import PASSWORD, F3DConstructorCase, F3DConstructorHttpCase

FIXTURES = Path(__file__).resolve().parents[1] / 'static' / 'tests' / 'fixtures'
ROUNDTRIP = [
    ['Full Location Name', 'Location Type', 'Barcode', 'Parent Location', 'Quantity'],
    ['WH/Stock/A-01-01-1', 'Internal Location', 'A-01-01-1', 'WH/Stock', 12.5],
    ['WH/Stock/Зона «Б» & Ко', 'Internal Location', '007', 'WH/Stock', ''],
    ['WH/Stock/нотатка\nз перенесенням', 'View', '', 'WH/Stock', 0],
]


def b64(data):
    return base64.b64encode(data).decode()


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s4")
class TestS4Tabular(F3DConstructorCase):
    """S4, F11: розбір CSV/XLSX сервером (API-20), створення XLSX (API-19 table_xlsx), сумісність з ядром JS."""

    # --- CSV ---------------------------------------------------------------------------------------------
    def test_csv_delimiters_quotes_bom_and_cp1251(self):
        text = 'name;note\r\nA-01;"каже ""привіт"", а потім;"\r\nB-02;"рядок1\nрядок2"\r\nC-03;\r\n'
        res = tabular.parse_table('x.csv', ('﻿' + text).encode('utf-8'))
        self.assertEqual((res['format'], res['encoding'], res['delimiter']), ('csv', 'utf-8', ';'))
        self.assertEqual(
            res['rows'],
            [['name', 'note'], ['A-01', 'каже "привіт", а потім;'], ['B-02', 'рядок1\nрядок2'], ['C-03', '']],
        )
        for delim in (',', '\t'):
            rows = tabular.parse_table('x.csv', text.replace(';', delim).encode())['rows']
            self.assertEqual(rows[1][0], 'A-01', repr(delim))
        win = tabular.parse_table('y.csv', 'Назва;B\nПолиця;1\n'.encode('cp1251'))
        self.assertEqual((win['encoding'], win['rows']), ('windows-1251', [['Назва', 'B'], ['Полиця', '1']]))
        # порожній хвіст і вирівнювання ширини (як trimRows у JS)
        ragged = tabular.parse_table('z.csv', b'a,b,c\n1\n\n,,\n')['rows']
        self.assertEqual(ragged, [['a', 'b', 'c'], ['1', '', '']])

    def test_csv_limits_and_errors(self):
        with self.assertRaises(ValidationError):
            tabular.parse_table('x.csv', b'')
        with patch.object(tabular, 'MAX_BYTES', 10), self.assertRaises(ValidationError):
            tabular.parse_table('x.csv', b'a,b\n' * 5)
        res = tabular.parse_table('x.csv', b'a\n1\n2\n3\n', max_rows=2)
        self.assertEqual((res['rows'], res['truncated']), ([['a'], ['1']], True))

    # --- XLSX --------------------------------------------------------------------------------------------
    def test_xlsx_written_by_python_roundtrips_without_loss(self):
        rows = [
            ['name', 'barcode', 'qty', 'flag'],
            ['Полиця «Брак» & <т>', '007', 12.5, True],
            ['рядок1\nрядок2', '0001234567890', 3, ''],
            ['', '', '', ''],
        ]
        data = tabular.table_xlsx(rows, 'Локації')
        self.assertEqual(data[:2], b'PK')
        res = tabular.parse_table('x.xlsx', data)
        self.assertEqual((res['format'], res['sheets'], res['sheet']), ('xlsx', ['Локації'], 'Локації'))
        self.assertEqual(res['rows'], rows[:3], "нулі на початку лишилися рядком, 3 — числом, порожній хвіст зник")
        self.assertIsInstance(res['rows'][2][2], int)
        self.assertEqual(tabular.table_xlsx(rows, 'Локації'), data, "файл детермінований")
        with self.assertRaises(ValidationError):
            tabular.parse_table('x.xlsx', data, sheet='Немає такого')
        with self.assertRaises(ValidationError):
            tabular.parse_table('x.xlsx', data, sheet=3)
        with self.assertRaises(ValidationError):
            tabular.parse_table('bad.xlsx', 'PK\x03\x04 not a zip'.encode())

    def test_xlsx_golden_files_python_and_js(self):
        """s4_python.xlsx пише Python (xlsxwriter, актуальність — тут), s4_roundtrip.xlsx пише ядро JS (openpyxl читає
        його тут)."""
        path = FIXTURES / golden_s4.NAME
        self.assertEqual(
            path.read_bytes(), golden_s4.build(), "s4_python.xlsx застарів: python3 tests/golden_s4.py --write"
        )
        res = tabular.parse_table(path.name, path.read_bytes())
        self.assertEqual(res['sheets'], ['Локації', 'Другий'])
        self.assertEqual(res['rows'], golden_s4.FIRST[:3] + [golden_s4.FIRST[3]])
        second = tabular.parse_table(path.name, path.read_bytes(), sheet='Другий')
        self.assertEqual(second['rows'], golden_s4.SECOND)
        js = tabular.parse_table('s4_roundtrip.xlsx', (FIXTURES / 's4_roundtrip.xlsx').read_bytes())
        self.assertEqual((js['sheet'], js['rows']), ('Локації', ROUNDTRIP), "XLSX ядра JS читає openpyxl без втрат")

    def test_renderer_registered_and_payload_checks(self):
        self.assertIn('table_xlsx', RENDERERS.keys())
        name, mime, content = RENDERERS.get('table_xlsx')(
            self.env, {'rows': [['a', 1]], 'filename': 'Мої локації 1', 'sheet': 'А/Б'}
        )
        self.assertEqual(name, 'Мої_локації_1.xlsx')
        self.assertIn('spreadsheetml', mime)
        back = tabular.parse_table(name, content)
        self.assertEqual((back['sheet'], back['rows']), ('А Б', [['a', 1]]))
        with self.assertRaises(ValidationError):
            RENDERERS.get('table_xlsx')(self.env, {'rows': 'не список'})
        with self.assertRaises(ValidationError):
            tabular.decode_payload('***')
        with self.assertRaises(ValidationError):
            tabular.table_xlsx([['x'] * 300])
        self.assertEqual(tabular.parse_table('e.xlsx', tabular.table_xlsx([[None, '']]))['rows'], [])


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s4")
class TestS4TabularApi(F3DConstructorHttpCase):
    """API-20 `/parse/table` і API-19 `/render/table_xlsx`: JSON-RPC, права, помилки."""

    def test_parse_table_route(self):
        self.authenticate(self.u_plain.login, PASSWORD)
        res = self.rpc(
            '/f3d/constructor/parse/table',
            site_id=self.site.id,
            filename='a.csv',
            content=b64('x;y\nПолиця;7\n'.encode('cp1251')),
        )
        self.assertTrue(res['ok'], res)
        self.assertEqual(
            (res['format'], res['encoding'], res['rows']), ('csv', 'windows-1251', [['x', 'y'], ['Полиця', '7']])
        )
        xlsx = tabular.table_xlsx([['name', 'qty'], ['A', 5]])
        res = self.rpc('/f3d/constructor/parse/table', filename='a.xlsx', content=b64(xlsx), sheet=0)
        self.assertEqual((res['ok'], res['sheet'], res['rows']), (True, 'Локації', [['name', 'qty'], ['A', 5]]))
        bad = self.rpc('/f3d/constructor/parse/table', filename='a.xlsx', content='***')
        self.assertEqual((bad['ok'], bad['code']), (False, 'validation'))
        empty = self.rpc('/f3d/constructor/parse/table', filename='a.xlsx')
        self.assertEqual((empty['ok'], empty['code']), (False, 'validation'))
        missing = self.rpc('/f3d/constructor/parse/table', filename='a.xlsx', content=b64(xlsx), sheet='Немає')
        self.assertEqual((missing['ok'], missing['code']), (False, 'validation'))

    def test_parse_table_requires_view_group(self):
        outsider = (
            self.env['res.users']
            .with_context(no_reset_password=True)
            .create(
                {
                    'name': 'outsider',
                    'login': 'f3d_outsider',
                    'password': PASSWORD,
                    'group_ids': [(6, 0, [self.env.ref('base.group_user').id])],
                }
            )
        )
        self.authenticate(outsider.login, PASSWORD)
        res = self.rpc('/f3d/constructor/parse/table', filename='a.csv', content=b64(b'a\n1\n'))
        self.assertEqual((res['ok'], res['code']), (False, 'rights'))

    def test_render_table_xlsx_route_roundtrip(self):
        self.authenticate(self.u_tech.login, PASSWORD)
        rows = [['name', 'location_id', 'usage', 'barcode', 'posx'], ['A-01-01-1', 'WH/Stock', 'internal', '007', 1]]
        res = self.rpc('/f3d/constructor/render/table_xlsx', rows=rows, sheet='Локації', filename='TST')
        self.assertTrue(res['ok'], res)
        self.assertEqual(res['filename'], 'TST.xlsx')
        back = tabular.parse_table(res['filename'], base64.b64decode(res['content']))
        self.assertEqual(back['rows'], rows)
        bad = self.rpc('/f3d/constructor/render/table_xlsx', rows='x')
        self.assertEqual((bad['ok'], bad['code']), (False, 'validation'))
        self.assertTrue(json.dumps(res) and io.BytesIO(base64.b64decode(res['content'])).read(2) == b'PK')
