import json
from unittest.mock import patch

from odoo import http
from odoo.tests import tagged

from ..services import convert
from .common import F3DConstructorHttpCase, PASSWORD, make_glb

UPLOAD = '/f3d/constructor/model/upload'


@tagged("post_install", "-at_install", "f3d", "f3d_constructor")
class TestVariantModelApi(F3DConstructorHttpCase):
    """AC-33…AC-36, AC-40: API-09 (multipart), API-10 (GET), R-18…R-20."""

    def upload(self, user=None, variant=None, csrf=True, meta=None, **files):
        self.authenticate((user or self.u_tech).login, PASSWORD)
        data = {'variant_id': (variant or self.variant).id, 'meta': json.dumps(meta or {})}
        if csrf:
            data['csrf_token'] = http.Request.csrf_token(self)
        return self.url_open(UPLOAD, data=data, files={k: v for k, v in files.items()}, timeout=60)

    def attachments(self):
        return self.env['ir.attachment'].search_count([('res_model', '=', 'f3d.equipment.variant')])

    # --- AC-33 -------------------------------------------------------------------------------------
    def test_ac33_upload_glb_server_values_win(self):
        glb = make_glb(triangles=24, size=(1.0, 0.5, 2.0), pad_to=200 * 1024)
        before = self.attachments()
        resp = self.upload(original=('box.obj', b'o box\nv 0 0 0\n'), glb=('box.glb', glb),
                           meta={'triangles': 999, 'bbox_m': [9, 9, 9], 'units': 'mm', 'up_axis': 'z', 'warnings': []})
        self.assertEqual(resp.status_code, 200, resp.text)
        data = resp.json()
        self.assertEqual(data['status'], 'ok')
        self.assertEqual(data['meta']['triangles'], 24)          # значення клієнта (999) перезаписано
        self.assertEqual(data['meta']['bbox_m'], [1.0, 0.5, 2.0])
        self.assertEqual(data['meta']['size_mm'], {'x': 1000, 'y': 500, 'z': 2000})
        self.assertEqual((data['meta']['units'], data['meta']['up_axis'], data['meta']['format']), ('mm', 'z', 'obj'))
        self.assertEqual(self.attachments(), before + 2)
        self.variant.invalidate_recordset()
        self.assertEqual(self.variant.model_status, 'ok')
        got = self.url_open(data['glb_url'])
        self.assertEqual(got.status_code, 200)
        self.assertEqual(got.content, glb)
        self.assertEqual(got.headers['Content-Type'], 'model/gltf-binary')
        self.assertIn('private', got.headers['Cache-Control'])
        self.assertEqual(self.url_open(data['glb_url'], headers={'If-None-Match': got.headers['ETag']}).status_code, 304)
        orig = self.url_open(data['original_url'])
        self.assertEqual(orig.headers['Content-Type'], 'application/octet-stream')
        # заміна: старі вкладення видаляються
        self.upload(original=('box2.obj', b'o box\n'), glb=('box2.glb', make_glb(12)))
        self.assertEqual(self.attachments(), before + 2)

    def test_glb_original_used_as_preview(self):
        resp = self.upload(original=('part.glb', make_glb(6)))
        self.assertEqual(resp.json()['status'], 'ok')
        self.assertEqual(resp.json()['meta']['triangles'], 6)

    # --- AC-34 -------------------------------------------------------------------------------------
    def test_ac34_too_large(self):
        before = (self.attachments(), self.variant.model_status)
        resp = self.upload(original=('big.stl', b'0' * (21 * 1048576)))
        self.assertEqual(resp.status_code, 413)
        self.assertEqual(resp.json()['code'], 'too_large')
        self.assertIn("Файл більший за 20 МБ", resp.json()['message'])
        self.variant.invalidate_recordset()
        self.assertEqual((self.attachments(), self.variant.model_status), before)

    # --- AC-35 -------------------------------------------------------------------------------------
    def test_ac35_many_triangles_is_warning(self):
        resp = self.upload(original=('dense.glb', make_glb(triangles=60000)))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()['status'], 'ok')
        self.variant.invalidate_recordset()
        self.assertEqual(self.variant.model_meta['warnings'], ['triangles_over_limit'])
        self.assertEqual(self.variant.model_warning, "60 тис. трикутників при ліміті 50 тис.")

    # --- AC-36 -------------------------------------------------------------------------------------
    def test_ac36_step_pending_then_converted(self):
        with patch.dict(convert.CONVERTERS, {'step': (lambda: False, None), 'stp': (lambda: False, None)}):
            resp = self.upload(original=('part.step', b'ISO-10303-21;\nEND-ISO-10303-21;\n'))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.assertEqual(resp.json()['status'], 'pending_conversion')
        self.assertIn("Перетворення STEP/IFC на сервері недоступне", resp.json()['meta']['message'])
        self.variant.invalidate_recordset()
        self.assertEqual(self.variant.model_status, 'pending_conversion')
        self.assertTrue(self.variant.model_original_id)
        self.assertFalse(self.variant.model_glb_id)
        glb = make_glb(10)

        def run(in_path, out_path, timeout):
            with open(out_path, 'wb') as handle:
                handle.write(glb)

        with patch.dict(convert.CONVERTERS, {'step': (lambda: True, run)}):
            result = self.variant._f3d_convert_model()
        self.assertTrue(result['ok'], result)
        self.assertEqual(self.variant.model_status, 'ok')
        self.assertEqual(self.variant.model_meta['converted_by'], 'server')
        self.assertEqual(self.variant.model_meta['triangles'], 10)
        # .ifc / .iges: так само pending; повторна спроба з конвертером — ok
        resp = self.upload(original=('plan.iges', b'IGES'))
        self.assertEqual(resp.json()['status'], 'pending_conversion')
        self.variant.invalidate_recordset()
        with patch.dict(convert.CONVERTERS, {'iges': (lambda: True, run)}):
            self.variant.action_retry_convert()
        self.assertEqual(self.variant.model_status, 'ok')
        resp = self.upload(original=('building.ifc', b'ISO-10303-21;'))
        self.assertEqual(resp.json()['status'], 'pending_conversion')
        # вимкнений серверний конвертер
        self.env['ir.config_parameter'].sudo().set_param('factory3d.constructor.convert_server_enabled', 'False')
        self.variant.invalidate_recordset()
        result = self.variant._f3d_convert_model()
        self.assertEqual((result['ok'], result['status']), (False, 'pending_conversion'))
        self.assertIn("вимкнено", result['message'])

    def test_converter_failure_gives_error_status(self):
        self.variant._f3d_set_model(original=('p.step', b'x'), meta={}, status='pending_conversion')

        def boom(in_path, out_path, timeout):
            raise RuntimeError("зламано")

        with patch.dict(convert.CONVERTERS, {'step': (lambda: True, boom)}):
            result = self.variant._f3d_convert_model()
        self.assertEqual((result['ok'], result['status']), (False, 'error'))
        self.assertEqual(self.variant.model_status, 'error')
        self.assertIn("зламано", self.variant.model_meta['message'])

    # --- AC-40 і права -----------------------------------------------------------------------------
    def test_ac40_unsupported_format(self):
        resp = self.upload(original=('house.skp', b'SKP'))
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.json()['code'], 'unsupported_format')
        self.assertIn("Формат .skp не підтримується", resp.json()['message'])
        self.assertEqual(self.variant.model_status, 'none')

    def test_bad_glb_and_missing_pieces(self):
        resp = self.upload(original=('x.obj', b'o x'), glb=('x.glb', b'not a glb at all, sorry!!'))
        self.assertEqual((resp.status_code, resp.json()['code']), (400, 'bad_glb'))
        resp = self.upload(original=('x.obj', b'o x'))  # без GLB для формату, що перетворюється в браузері
        self.assertEqual(resp.json()['code'], 'bad_glb')
        resp = self.upload()
        self.assertEqual(resp.json()['code'], 'validation')

    def test_rights_and_csrf(self):
        for user in (self.u_store, self.u_eng, self.u_plain):
            resp = self.upload(user=user, original=('a.glb', make_glb(3)))
            self.assertEqual((resp.status_code, resp.json()['code']), (403, 'rights'), user.login)
        self.assertEqual(self.upload(user=self.u_manager, original=('a.glb', make_glb(3))).status_code, 200)
        resp = self.upload(csrf=False, original=('a.glb', make_glb(3)))
        self.assertEqual(resp.status_code, 400)  # без csrf_token
        self.authenticate(self.u_tech.login, PASSWORD)
        self.assertEqual(self.url_open(UPLOAD.replace('upload', '999999/glb')).status_code, 404)

    def test_filename_sanitized_and_clear_model(self):
        resp = self.upload(original=('../../etc/passwd.glb', make_glb(3)))
        self.assertEqual(resp.status_code, 200, resp.text)
        self.variant.invalidate_recordset()
        self.assertEqual(self.variant.model_original_id.name, 'passwd.glb')
        self.variant.with_user(self.u_tech).action_clear_model()
        self.assertEqual((self.variant.model_status, bool(self.variant.model_meta), bool(self.variant.model_glb_id)), ('none', False, False))
