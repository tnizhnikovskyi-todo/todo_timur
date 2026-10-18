"""API-01…04, 07, 10, 11, 12 (§7). Спільна логіка винесена в методи `serve_*`, щоб кіоск (API-09) викликав їх
з `request.env` користувача кіоска."""
import base64
import gzip
import json
import logging
import re

from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request

from ..models.viewer_provider_maintenance import GROUP_KIOSK, plan_error
from ..tools import dates, loc_history, payload as payload_tools, static_data
from ..tools.cycle_check import check

_logger = logging.getLogger(__name__)

# сегменти через «/» (назви документів `WH/MO/00231`) не починаються з «.», тож `..`, `../x`, `/x`, `x//y` не проходять (V-2)
CODE_RE = re.compile(r"^(?=.{1,64}\Z)[A-Za-z0-9_\-][A-Za-z0-9_.\-]*(?:/[A-Za-z0-9_\-][A-Za-z0-9_.\-]*)*\Z")
SECTION_RE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
DATE_RE = re.compile(r"^\d{4}-\d\d-\d\d$")
SINCE_RE = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(\.\d+)?Z?$")
MAX_CODES = 200
GROUP_USER = "factory3d_base.group_f3d_user"
GROUP_STOCK = "stock.group_stock_user"
GROUP_MANAGER = "factory3d_base.group_f3d_manager"
GROUP_ADMIN = "factory3d_base.group_f3d_admin"
JSON_CT = "application/json; charset=utf-8"


class BadRequest(Exception):
    pass


def json_response(data, status=200, headers=None, gzip_ok=False, cache="no-store"):
    body = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    hdrs = {"Content-Type": JSON_CT, "Cache-Control": cache}
    hdrs.update(headers or {})
    if gzip_ok and len(body) > 1024 and "gzip" in (request.httprequest.headers.get("Accept-Encoding") or ""):
        body = gzip.compress(body, 5)
        hdrs["Content-Encoding"] = "gzip"
        hdrs["Vary"] = "Accept-Encoding"
    return request.make_response(body, headers=list(hdrs.items()), status=status)


def error(code, message, status):
    return json_response({"error": {"code": code, "message": message}}, status=status)


def bad_request(message="Невалідний параметр"):
    return error("bad_request", message, 400)


def forbidden(message="Немає доступу до переглядача «Завод 3D»"):
    return error("forbidden", message, 403)


def parse_codes(value, limit=MAX_CODES):
    if value is None or value == "":
        return None
    codes = value.split(",")
    if len(codes) > limit or not all(CODE_RE.match(c) for c in codes):
        raise BadRequest("codes")
    return set(codes)


def parse_flag(value, name):
    if value is None or value == "":
        return False
    if value not in ("0", "1"):
        raise BadRequest(name)
    return value == "1"


def etag_matches(header, etag):
    if not header:
        return False
    tags = [t.strip() for t in header.split(",")]
    return any(t in ('"%s"' % etag, 'W/"%s"' % etag, "*") for t in tags)


class F3dViewerController(http.Controller):

    # --- спільна логіка (використовує і кіоск) -----------------------------

    @staticmethod
    def serve_static():
        body, body_gz, sha1 = static_data.static_body()
        headers = {"ETag": '"%s"' % sha1, "Content-Type": JSON_CT, "Cache-Control": "private, max-age=3600",
                   "Vary": "Accept-Encoding"}
        if etag_matches(request.httprequest.headers.get("If-None-Match"), sha1):
            return request.make_response(b"", headers=list(headers.items()), status=304)
        if "gzip" in (request.httprequest.headers.get("Accept-Encoding") or ""):
            body = body_gz
            headers["Content-Encoding"] = "gzip"
        return request.make_response(body, headers=list(headers.items()))

    @staticmethod
    def serve_data(kw, kiosk=False):
        try:
            full = parse_flag(kw.get("full"), "full")
            lite = parse_flag(kw.get("lite"), "lite")
            codes = parse_codes(kw.get("codes"))
            sections = None
            if kw.get("sections"):
                sections = set(kw["sections"].split(","))
                if not all(SECTION_RE.match(s) for s in sections):
                    raise BadRequest("sections")
        except BadRequest as e:
            return bad_request("Невалідний параметр: %s" % e)
        try:
            data = payload_tools.PayloadBuilder(
                request.env, full=full, lite=lite, kiosk=kiosk, sections=sections, codes=codes).build()
        except Exception:  # noqa: BLE001
            _logger.exception("збирач payload впав")
            return error("payload_failed", "Не вдалося зібрати дані переглядача", 500)
        return json_response(data, gzip_ok=True)

    @staticmethod
    def serve_delta(kw, kiosk=False):
        try:
            since = kw.get("since")
            if not since or not SINCE_RE.match(since):
                raise BadRequest("since")
            codes = parse_codes(kw.get("codes"))
            lite = parse_flag(kw.get("lite"), "lite")
            since_dt = dates.parse_iso_utc(since)
        except (BadRequest, ValueError) as e:
            return bad_request("Невалідний параметр: %s" % e)
        try:
            data = payload_tools.DeltaBuilder(request.env, since_dt, codes=codes, lite=lite, kiosk=kiosk).build()
        except Exception:  # noqa: BLE001
            _logger.exception("збирач дельти впав")
            return error("payload_failed", "Не вдалося зібрати дельту", 500)
        return json_response(data, gzip_ok=True)

    @staticmethod
    def serve_loc(code):
        """API-12: історія комірки. Код невалідний -> 400, коду немає в базі -> 404, немає прав на склад -> 403."""
        if not CODE_RE.match(code or ""):
            return bad_request("Невалідний параметр: code")
        env = request.env
        if not (env.user.has_group(GROUP_STOCK) and loc_history.accessible(env)):
            return forbidden("Немає доступу до залишків і переміщень складу")
        loc = env["stock.location"].search_f3d(code)
        if not loc:
            return error("not_found", "Комірку не знайдено", 404)
        try:
            data = loc_history.build(env, loc, code)
        except Exception:  # noqa: BLE001
            _logger.exception("історія комірки %s: збирач впав", code)
            return error("payload_failed", "Не вдалося зібрати історію комірки", 500)
        return json_response(data, gzip_ok=True)

    @staticmethod
    def serve_manifest():
        body, sha1 = static_data.parts_manifest()
        headers = {"ETag": '"%s"' % sha1, "Content-Type": JSON_CT, "Cache-Control": "private, max-age=3600"}
        if etag_matches(request.httprequest.headers.get("If-None-Match"), sha1):
            return request.make_response(b"", headers=list(headers.items()), status=304)
        return request.make_response(body, headers=list(headers.items()))

    # --- маршрути ----------------------------------------------------------

    @staticmethod
    def _allowed():
        return request.env.user.has_group(GROUP_USER)

    @http.route("/f3d/viewer/static", type="http", auth="user", methods=["GET"])
    def static(self, **kw):
        if not self._allowed():
            return forbidden()
        return self.serve_static()

    @http.route("/f3d/viewer/data", type="http", auth="user", methods=["GET"])
    def data(self, **kw):
        if not self._allowed():
            return forbidden()
        return self.serve_data(kw)

    @http.route("/f3d/viewer/delta", type="http", auth="user", methods=["GET"])
    def delta(self, **kw):
        if not self._allowed():
            return forbidden()
        return self.serve_delta(kw)

    @http.route("/f3d/viewer/resolve", type="http", auth="user", methods=["GET"])
    def resolve(self, **kw):
        if not self._allowed():
            return forbidden()
        code, name = kw.get("code"), kw.get("name")
        if bool(code) == bool(name):
            return bad_request("Потрібен рівно один параметр: code або name")
        if (code or name) and not CODE_RE.match(code or name):
            return bad_request("Невалідний параметр: code/name")
        try:
            codes = parse_codes(kw.get("codes"))  # коди дочірніх об'єктів (комірки стелажа), ≤ MAX_CODES
        except BadRequest as e:
            return bad_request("Невалідний параметр: %s" % e)
        if codes and not code:
            return bad_request("Параметр codes потребує code")
        return json_response(payload_tools.resolve(request.env, code=code, name=name, codes=sorted(codes or ())))

    @http.route("/f3d/viewer/loc/<path:code>", type="http", auth="user", methods=["GET"])
    def loc(self, code, **kw):
        if not self._allowed():
            return forbidden()
        return self.serve_loc(code)

    @http.route("/f3d/viewer/parts/manifest.json", type="http", auth="user", methods=["GET"])
    def parts_manifest(self, **kw):
        if not self._allowed():
            return forbidden()
        return self.serve_manifest()

    @http.route("/f3d/viewer/cycle_check", type="jsonrpc", auth="user", methods=["POST"])
    def cycle_check(self, as_user=None, **kw):
        env = request.env
        if not env.user.has_group(GROUP_MANAGER):
            raise AccessError("Перевірка циклу доступна лише менеджеру «Завод 3D».")
        if as_user:
            if not env.user.has_group(GROUP_ADMIN):
                raise AccessError("Вказати іншого користувача може лише адміністратор «Завод 3D».")
            env = env(user=int(as_user))
        data = payload_tools.PayloadBuilder(env, full=True).build()
        for key in ("pickings", "sale_orders", "quality_checks", "productions"):
            data.setdefault(key, [])
        for key in ("locations", "workorders"):
            data.setdefault(key, {})
        issues = check(data)
        if issues:
            return {"ok": False, "issues": issues, "count": len(issues)}
        return {"ok": True, "issues": []}

    @http.route("/f3d/viewer/maintenance/plan", type="jsonrpc", auth="user", methods=["POST"])
    def maintenance_plan(self, code=None, equipment_id=None, **kw):
        """API-11: «Запланувати ТО». jsonrpc (JSON-тіло, без CSRF-токена), помилки — у тілі `{ok:false,status,error}`."""
        if request.env.user.has_group(GROUP_KIOSK):
            return plan_error(403, "kiosk", "Екран цеху не може створювати заявки на обслуговування.")
        if not self._allowed():
            return plan_error(403, "forbidden", "Немає доступу до переглядача «Завод 3D»")
        if (code is None) == (equipment_id is None):
            return plan_error(400, "bad_request", "Потрібен рівно один параметр: code або equipment_id")
        if code is not None and not (isinstance(code, str) and CODE_RE.match(code)):
            return plan_error(400, "bad_request", "Невалідний параметр: code")
        if equipment_id is not None and (isinstance(equipment_id, bool) or not isinstance(equipment_id, int)
                                         or not 0 < equipment_id < 2 ** 31):
            return plan_error(400, "bad_request", "Невалідний параметр: equipment_id")
        return request.env["f3d.viewer.provider.maintenance"]._f3d_plan_maintenance(
            code=code, equipment_id=equipment_id)

    # --- знімки (API-05, API-06) -------------------------------------------

    @staticmethod
    def serve_snapshots(kw):
        date = kw.get("date") or dates.today(request.env)
        if not DATE_RE.match(date):
            return bad_request("Невалідний параметр: date")
        snaps = request.env["f3d.viewer.snapshot"].search([("shift_date", "=", date)], order="ts asc, id asc")
        items = [{"id": s.id, "ts": dates.local(s.ts), "kind": s.kind, "size_kb": s.size_kb, "note": s.note or None}
                 for s in snaps]
        return json_response({"date": date, "snapshots": items, "mode": "snapshots" if len(items) >= 3 else "plan"})

    @staticmethod
    def serve_snapshot(snapshot_id):
        """`snapshot_id` приходить рядком: нечисловий id → 404 JSON (а не редирект маршрутизатора, V-3)."""
        raw_id = str(snapshot_id)
        sid = int(raw_id) if raw_id.isascii() and raw_id.isdigit() and len(raw_id) <= 9 else 0
        snap = request.env["f3d.viewer.snapshot"].search([("id", "=", sid)], limit=1)
        if not snap:
            return error("not_found", "Знімок не знайдено", 404)
        raw = base64.b64decode(snap.payload_file or b"")
        headers = {"Content-Type": JSON_CT, "Cache-Control": "private, max-age=3600", "Vary": "Accept-Encoding"}
        if "gzip" in (request.httprequest.headers.get("Accept-Encoding") or ""):
            headers["Content-Encoding"] = "gzip"
            body = raw
        else:
            body = gzip.decompress(raw)
        return request.make_response(body, headers=list(headers.items()))

    @http.route("/f3d/viewer/snapshots", type="http", auth="user", methods=["GET"])
    def snapshots(self, **kw):
        if not self._allowed():
            return forbidden()
        return self.serve_snapshots(kw)

    @http.route("/f3d/viewer/snapshot/<string:snapshot_id>", type="http", auth="user", methods=["GET"])
    def snapshot(self, snapshot_id, **kw):
        if not self._allowed():
            return forbidden()
        return self.serve_snapshot(snapshot_id)
