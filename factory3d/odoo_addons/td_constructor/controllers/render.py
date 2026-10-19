"""API-19: JSON → файл (етикетки, таблиці, план, специфікація; F05, F11, F15).

Маршрути віддають файл через реєстр `services.registry.RENDERERS`: слайс реєструє `fn(env, payload) -> (filename,
mimetype, content)` зі свого файлу сервісу; без зареєстрованого рендерера — заглушка `not_implemented` (W0-B).
Відповідь `{ok: true, filename, mimetype, content: base64}`; помилки рендера — `validation` / `rights`."""

import base64

from odoo import http
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

from ..services.registry import RENDERERS
from .constructor import error_from_exception, fail
from .stub import not_implemented


def render_file(kind, payload):
    renderer = RENDERERS.get(kind)
    if renderer is None:
        return not_implemented('API-19')
    try:
        filename, mimetype, content = renderer(request.env, payload)
    except (AccessError, ValidationError, UserError) as exc:
        return fail(*error_from_exception(exc))
    return {'ok': True, 'filename': filename, 'mimetype': mimetype, 'content': base64.b64encode(content).decode()}


class TdRenderController(http.Controller):
    # --- API-19 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/render/labels_pdf', type='jsonrpc', auth='user', methods=['POST'])
    def render_labels_pdf(self, **kw):
        return render_file('labels_pdf', kw)

    @http.route('/f3d/constructor/render/table_xlsx', type='jsonrpc', auth='user', methods=['POST'])
    def render_table_xlsx(self, **kw):
        return render_file('table_xlsx', kw)

    @http.route('/f3d/constructor/render/plan_pdf', type='jsonrpc', auth='user', methods=['POST'])
    def render_plan_pdf(self, **kw):
        return render_file('plan_pdf', kw)

    @http.route('/f3d/constructor/render/spec_pdf', type='jsonrpc', auth='user', methods=['POST'])
    def render_spec_pdf(self, **kw):
        return render_file('spec_pdf', kw)
