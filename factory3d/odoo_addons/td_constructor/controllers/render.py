"""API-19: JSON → файл (етикетки, таблиці, план, специфікація; F05, F11, F15). Заглушки W0-B, наповнює слайс S3."""

from odoo import http

from .stub import not_implemented


class TdRenderController(http.Controller):
    # --- API-19 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/render/labels_pdf', type='jsonrpc', auth='user', methods=['POST'])
    def render_labels_pdf(self, **kw):
        return not_implemented('API-19')

    # --- API-19 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/render/table_xlsx', type='jsonrpc', auth='user', methods=['POST'])
    def render_table_xlsx(self, **kw):
        return not_implemented('API-19')

    # --- API-19 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/render/plan_pdf', type='jsonrpc', auth='user', methods=['POST'])
    def render_plan_pdf(self, **kw):
        return not_implemented('API-19')

    # --- API-19 ------------------------------------------------------------------------------------
    @http.route('/f3d/constructor/render/spec_pdf', type='jsonrpc', auth='user', methods=['POST'])
    def render_spec_pdf(self, **kw):
        return not_implemented('API-19')
