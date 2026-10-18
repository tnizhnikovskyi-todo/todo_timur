import base64
import io
import json
import zipfile
from pathlib import Path

from PyPDF2 import PdfReader
from PIL import Image

from odoo import Command
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from ..services import labels
from ..services.registry import RENDERERS
from .common import PASSWORD, F3DConstructorCase, F3DConstructorHttpCase

FIXTURE = Path(__file__).resolve().parents[1] / 'static' / 'tests' / 'fixtures' / 's3_barcode_golden.json'
ROUTE = '/f3d/constructor/render/labels_pdf'


def make_payload(count=3, fmt='pdf', **extra):
    """70×36 мм на A4: сітка 3×8, поля по центру (як `pageGeometry` ядра)."""
    payload = {
        'format': fmt,
        'font': 'cyr',
        'kind': 'code128',
        'page': {'w': 210, 'h': 297},
        'grid': {'cols': 3, 'rows': 8, 'x0': 0, 'y0': 4.5, 'w': 70, 'h': 36, 'gx': 0, 'gy': 0},
        'skip': 0,
        'labels': [
            {'code': 'PLT-%02dA' % i, 'lines': ['Зона A · Ряд %d' % i], 'arrow': 'up' if i % 2 else None}
            for i in range(count)
        ],
    }
    payload.update(extra)
    return payload


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s3")
class TestS3Labels(F3DConstructorCase):
    """F05: сервіс етикеток — Code128/QR як у ядрі (золота фікстура), валідація, розкладка, PDF і PNG."""

    def test_golden_barcodes_match_core(self):
        golden = json.loads(FIXTURE.read_text(encoding='utf-8'))
        self.assertEqual(list(labels.C128), golden['patterns'])
        for item in golden['code128']:
            self.assertEqual(labels.code128_values(item['text']), item['values'], item['text'])
            self.assertEqual(labels.code128_modules(item['text']), item['modules'], item['text'])
        for item in golden['qr']:
            self.assertEqual(labels.qr_rows(item['text'], item['ecc'], item['mask']), item['rows'], item['text'][:20])

    def test_code128_rules(self):
        self.assertEqual(labels.code128_values('123456')[0], labels.START_C)
        self.assertEqual(labels.code128_values('PLT-01A')[0], labels.START_B)
        with self.assertRaises(ValidationError):
            labels.code128_values('Зона-1')
        with self.assertRaises(ValidationError):
            labels.code128_values('')
        self.assertEqual(labels.kind_for('Зона-1', 'code128'), 'qr', "не-ASCII → QR")
        self.assertEqual(labels.kind_for('PLT-01A', 'code128'), 'code128')

    def test_payload_validation(self):
        bad = {
            'не-об\'єкт': [],
            'порожньо': make_payload(0),
            'формат': make_payload(format='gif'),
            'шрифт': make_payload(font='comic'),
            'штрихкод': make_payload(kind='aztec'),
            'сітка': make_payload(grid={'cols': 0, 'rows': 8, 'x0': 0, 'y0': 0, 'w': 70, 'h': 36}),
            'аркуш': make_payload(page={'w': 5, 'h': 297}),
            'стрілка': make_payload(labels=[{'code': 'A', 'lines': [], 'arrow': 'left'}]),
            'код': make_payload(labels=[{'code': '', 'lines': []}]),
            'рядки': make_payload(labels=[{'code': 'A', 'lines': ['x'] * 9}]),
            'довгий': make_payload(labels=[{'code': 'A', 'lines': ['x' * 200]}]),
        }
        for name, payload in bad.items():
            with self.assertRaises(ValidationError, msg=name):
                labels.parse_payload(payload, 5000)
        with self.assertRaises(ValidationError):
            labels.parse_payload(make_payload(6), 5)  # понад labels_max
        spec = labels.parse_payload(make_payload(2), 5000)
        self.assertEqual((spec['cols'], spec['rows'], spec['w'], spec['h']), (3, 8, 70.0, 36.0))

    def test_paginate_skip_first(self):
        spec = labels.parse_payload(make_payload(30), 5000)
        self.assertEqual([len(p) for p in labels.paginate(spec)], [24, 6])
        spec = labels.parse_payload(make_payload(30, skip=10), 5000)
        pages = labels.paginate(spec)
        self.assertEqual([len(p) for p in pages], [14, 16])
        _label, x, y = pages[0][0]
        self.assertEqual((x, y), (70.0, 4.5 + 3 * 36.0), "перша етикетка після пропуску 10 — рядок 4, колонка 2")

    def test_pdf_pages_and_text(self):
        spec = labels.parse_payload(make_payload(30), 5000)
        pdf = labels.render_pdf(spec)
        self.assertTrue(pdf.startswith(b'%PDF'))
        reader = PdfReader(io.BytesIO(pdf))
        self.assertEqual(len(reader.pages), 2)
        box = reader.pages[0].mediabox
        self.assertAlmostEqual(float(box.width), 210 * 72 / 25.4, delta=0.5)
        self.assertAlmostEqual(float(box.height), 297 * 72 / 25.4, delta=0.5)
        self.assertIn(b'NotoSans-Regular', pdf, "кирилицю малює вбудований шрифт")
        text = reader.pages[0].extract_text()
        self.assertIn('PLT-01A', text.replace(' ', ''))
        self.assertIn('Зона A', text, "кирилиця витягується з PDF")

    def test_pdf_latin_font_and_qr(self):
        spec = labels.parse_payload(make_payload(3, font='latin', kind='qr'), 5000)
        pdf = labels.render_pdf(spec)
        self.assertNotIn(b'NotoSans', pdf)
        self.assertEqual(len(PdfReader(io.BytesIO(pdf)).pages), 1)

    def test_png_single_and_multi_page(self):
        name, data = labels.render_png(labels.parse_payload(make_payload(3, fmt='png'), 5000), dpi=100)
        self.assertEqual(name, 'labels_1.png')
        self.assertEqual(data[1:4], b'PNG')
        image = Image.open(io.BytesIO(data))
        self.assertEqual(image.size, (round(210 / 25.4 * 100), round(297 / 25.4 * 100)))
        self.assertTrue(
            any(px != (255, 255, 255) for px in list(image.convert('RGB').getdata())[::97]), "аркуш не порожній"
        )
        name, data = labels.render_png(labels.parse_payload(make_payload(30, fmt='png'), 5000), dpi=50)
        self.assertEqual(name, 'labels_png.zip')
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            self.assertEqual(archive.namelist(), ['labels_1.png', 'labels_2.png'])

    def test_png_page_limit(self):
        spec = labels.parse_payload(make_payload(24 * (labels.MAX_PNG_PAGES + 1), fmt='png'), 5000)
        with self.assertRaises(ValidationError):
            labels.render_png(spec, dpi=20)

    def test_renderer_registered_and_rights(self):
        self.assertIs(RENDERERS.get('labels_pdf'), labels.render_labels)
        filename, mimetype, content = RENDERERS.get('labels_pdf')(self.env, make_payload(2))
        self.assertEqual((filename, mimetype), ('labels.pdf', 'application/pdf'))
        self.assertTrue(content.startswith(b'%PDF'))
        filename, mimetype, content = RENDERERS.get('labels_pdf')(self.env, make_payload(2, fmt='png'))
        self.assertEqual((filename, mimetype), ('labels_1.png', 'image/png'))
        outsider = (
            self.env['res.users']
            .with_context(no_reset_password=True)
            .create(
                {
                    'name': 'Без групи',
                    'login': 'f3d_outsider',
                    'email': 'f3d_outsider@example.com',
                    'group_ids': [Command.set([self.env.ref('base.group_user').id])],
                }
            )
        )
        with self.assertRaises(AccessError):
            RENDERERS.get('labels_pdf')(self.env(user=outsider), make_payload(1))

    def test_labels_max_parameter(self):
        self.env['ir.config_parameter'].sudo().set_param('td.constructor.labels_max', '5')
        with self.assertRaises(ValidationError):
            RENDERERS.get('labels_pdf')(self.env, make_payload(6))
        self.assertTrue(RENDERERS.get('labels_pdf')(self.env, make_payload(5))[2].startswith(b'%PDF'))


@tagged("post_install", "-at_install", "f3d", "f3d_constructor", "f3d_s3")
class TestS3LabelsApi(F3DConstructorHttpCase):
    """API-19 `labels_pdf`: JSON → файл (base64), помилки як `validation` / `rights`."""

    def test_route_returns_pdf_and_png(self):
        self.authenticate(self.u_plain.login, PASSWORD)
        res = self.rpc(ROUTE, site_id=self.site.id, **make_payload(4))
        self.assertTrue(res['ok'], res)
        self.assertEqual((res['filename'], res['mimetype']), ('labels.pdf', 'application/pdf'))
        self.assertTrue(base64.b64decode(res['content']).startswith(b'%PDF'))
        res = self.rpc(ROUTE, site_id=self.site.id, **make_payload(4, fmt='png'))
        self.assertTrue(res['ok'], res)
        self.assertEqual(res['mimetype'], 'image/png')
        self.assertEqual(base64.b64decode(res['content'])[1:4], b'PNG')

    def test_route_validation_error(self):
        self.authenticate(self.u_plain.login, PASSWORD)
        res = self.rpc(ROUTE, site_id=self.site.id, **make_payload(0))
        self.assertEqual((res['ok'], res['code']), (False, 'validation'))
        self.assertIn('Етикетки', res['message'])
