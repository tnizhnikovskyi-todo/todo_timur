"""API-09 (multipart: завантаження моделі варіанта) і API-10 (GET файла моделі)."""

import json
import logging

from psycopg2 import errors as pg_errors

from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request

from ..models.f3d_equipment_variant import F3dModelError, SERVER_CONVERT_FORMATS, model_extension

_logger = logging.getLogger(__name__)

TECHNOLOGIST = 'factory3d_constructor.group_f3d_constructor_technologist'
HTTP_CODES = {
    'rights': 403,
    'too_large': 413,
    'unsupported_format': 400,
    'bad_glb': 400,
    'not_found': 404,
    'validation': 400,
    'busy': 409,
}


def _json(data, status=200):
    return request.make_json_response(data, status=status)


def _error(code, message):
    return _json({'ok': False, 'code': code, 'message': message}, HTTP_CODES.get(code, 400))


class F3dModelController(http.Controller):
    @http.route('/f3d/constructor/model/upload', type='http', auth='user', methods=['POST'], csrf=True)
    def upload(self, variant_id=None, meta=None, original=None, glb=None, **kw):
        env = request.env
        if not env.user.has_group(TECHNOLOGIST):
            return _error('rights', "Завантажувати моделі може технолог або менеджер конструктора.")
        try:
            variant = env['f3d.equipment.variant'].browse(int(variant_id)).exists()
        except (TypeError, ValueError):
            variant = None
        if not variant:
            return _error('not_found', "Варіант не знайдено.")
        try:
            variant.check_access('write')
        except AccessError as exc:
            return _error('rights', str(exc))
        max_mb, _tri, _enabled = variant._f3d_params()
        limit = int(max_mb * 1048576)
        files = {}
        for key, storage in (('original', original), ('glb', glb)):
            if storage is None or not getattr(storage, 'filename', None):
                continue
            raw = storage.read(limit + 1)
            if len(raw) > limit:
                return _error('too_large', "Файл більший за %g МБ" % max_mb)
            files[key] = (storage.filename, raw)
        if 'original' not in files:
            return _error('validation', "Не передано файл оригіналу (original).")
        try:
            client_meta = json.loads(meta) if meta else {}
        except ValueError:
            client_meta = {}
        try:
            with env.cr.savepoint():
                env.cr.execute("SELECT id FROM f3d_equipment_variant WHERE id = %s FOR UPDATE NOWAIT", (variant.id,))
        except pg_errors.LockNotAvailable:
            return _error('busy', "Завантаження для цього варіанта вже виконується.")
        name, raw = files['original']
        ext = model_extension(name)
        try:
            with env.cr.savepoint():
                if ext in SERVER_CONVERT_FORMATS:
                    variant._f3d_set_model(
                        original=files['original'],
                        glb=files.get('glb'),
                        meta=client_meta,
                        status='ok' if 'glb' in files else 'pending_conversion',
                        message="" if 'glb' in files else "Очікує перетворення",
                    )
                    if 'glb' not in files:
                        variant._f3d_convert_model()
                else:
                    glb_file = files.get('glb') or ((name, raw) if ext == 'glb' else None)
                    if glb_file is None and ext in ('gltf', 'obj', 'mtl', 'fbx', 'stl', '3mf', 'dae'):
                        raise F3dModelError(
                            'bad_glb',
                            "Потрібен GLB, створений у браузері: перетворення цього формату виконується у віджеті.",
                        )
                    variant._f3d_set_model(original=files['original'], glb=glb_file, meta=client_meta, status='ok')
        except F3dModelError as exc:
            env.invalidate_all()
            return _error(exc.code, str(exc))
        variant = env['f3d.equipment.variant'].browse(variant.id)
        return _json(
            {
                'ok': True,
                'status': variant.model_status,
                'meta': variant.model_meta or {},
                'glb_url': '/f3d/constructor/model/%d/glb' % variant.id if variant.model_glb_id else None,
                'original_url': '/f3d/constructor/model/%d/original' % variant.id
                if variant.model_original_id
                else None,
                'message': (variant.model_meta or {}).get('message') or '',
            }
        )

    @http.route('/f3d/constructor/model/<int:variant_id>/<string:kind>', type='http', auth='user', methods=['GET'])
    def download(self, variant_id, kind, **kw):
        if kind not in ('glb', 'original'):
            raise request.not_found()
        variant = request.env['f3d.equipment.variant'].browse(variant_id).exists()
        if not variant:
            raise request.not_found()
        try:
            variant.check_access('read')
        except AccessError:
            return request.make_response("Forbidden", status=403)
        attachment = (variant.model_glb_id if kind == 'glb' else variant.model_original_id).sudo()
        if not attachment:
            raise request.not_found()
        etag = '"%s"' % (attachment.checksum or attachment.id)
        if request.httprequest.headers.get('If-None-Match') == etag:
            return request.make_response("", status=304, headers=[('ETag', etag)])
        data = attachment.raw or b''
        content_type = 'model/gltf-binary' if kind == 'glb' else 'application/octet-stream'
        return request.make_response(
            data,
            headers=[
                ('Content-Type', content_type),
                ('Content-Length', str(len(data))),
                ('ETag', etag),
                ('Cache-Control', 'private, max-age=3600'),
                ('X-Content-Type-Options', 'nosniff'),
            ],
        )
