"""API-01: `GET /f3d/machine/cutmap/<id>/export` — одноразова видача списку деталей колектору (FR-35).

Одноразовий токен експорту — лише в заголовку `X-F3D-Token` (query `t` не приймається: URL потрапляє в access-log).
"""

import logging
import re

from odoo import SUPERUSER_ID, http
from odoo.http import request

from ..models.f3d_cut_map import MAX_EXPORT_LINES, CutExportError

_logger = logging.getLogger(__name__)

TOKEN_RE = re.compile(r"^[0-9a-f]{16}$")
BODY_MAX = 1024 * 1024
EXPORT_TOKEN_HEADER = "X-F3D-Token"
NO_STORE = [("Cache-Control", "no-store")]


def _error(status, code, message):
    return request.make_json_response({"error": {"code": code, "message": message}}, headers=NO_STORE, status=status)


class F3dCutMapController(http.Controller):
    @http.route("/f3d/machine/cutmap/<int:map_id>/export", type="http", auth="public", csrf=False, methods=["GET"])
    def cutmap_export(self, map_id, **_kw):
        header = request.httprequest.headers.get("Authorization", "")
        token = header[7:].strip() if header[:7].lower() == "bearer " else ""
        collector = request.env["f3d.collector"].sudo()._authenticate(token) if token and len(token) <= 256 else None
        # AC-67: токен колектора іншого (не власника джерела команд оптимізатора) → 401
        if not collector or collector != request.env["f3d.cut.map"].sudo()._f3d_export_collector():
            return _error(401, "unauthorized", "Невірний токен колектора")
        t = request.httprequest.headers.get(EXPORT_TOKEN_HEADER, "").strip()
        if not TOKEN_RE.match(t):
            return _error(400, "bad_token", "Невірний формат токена експорту (заголовок %s)" % EXPORT_TOKEN_HEADER)
        env = request.env(user=SUPERUSER_ID, context=dict(request.env.context, tz="UTC"))
        CutMap = env["f3d.cut.map"]
        try:
            cut_map = CutMap._f3d_check_export_token(map_id, t)
        except CutExportError as e:
            return _error(e.status, e.code, e.message)
        if env["f3d.cut.map.line"].search_count([("map_id", "=", cut_map.id)]) > MAX_EXPORT_LINES:
            cut_map.write({"state": "error", "error": "Забагато деталей для однієї карти", "export_token_hash": False})
            return _error(413, "too_large", "Забагато деталей для однієї карти")
        csv_text = (
            cut_map.csv_attachment_id.raw.decode("utf-8") if cut_map.csv_attachment_id else cut_map._f3d_csv_text()
        )
        body = {
            "map": cut_map.name,
            "external_ref": cut_map.production_id.name,
            "machine": cut_map.workcenter_id.f3d_code or "",
            "material": cut_map.material_product_id.default_code or "",
            "sheet": "%dx%dx%d" % (cut_map.sheet_length_mm, cut_map.sheet_width_mm, cut_map.thickness_mm),
            "priority": 5,
            "parts": cut_map.parts_count,
            "parts_csv": csv_text,
        }
        response = request.make_json_response(body, headers=NO_STORE, status=200)
        if len(response.get_data()) > BODY_MAX:
            cut_map.write({"state": "error", "error": "Забагато деталей для однієї карти", "export_token_hash": False})
            return _error(413, "too_large", "Забагато деталей для однієї карти")
        cut_map.write({"export_token_hash": False})
        cut_map.message_post(
            body="Список деталей забрав колектор %s" % collector.code,
            subtype_xmlid="mail.mt_note",
            author_id=env.ref("base.partner_root").id,
        )
        return response
