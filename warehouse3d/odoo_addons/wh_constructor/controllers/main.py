import functools
import json
import os

from odoo import http, release
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.http import request

# В Odoo 19 type='json' — устаревший псевдоним 'jsonrpc' (с предупреждением в логе), в 18 'jsonrpc' нет.
JSON = "jsonrpc" if release.version_info[0] >= 19 else "json"
BASE = "/wh_constructor"
APP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "app")
G_VIEW, G_DESIGN, G_APPLY = "wh_constructor.group_wh_view", "wh_constructor.group_wh_design", "wh_constructor.group_wh_apply"

NO_BUILD = (
    "<!doctype html><meta charset=utf-8><title>Конструктор складу</title>"
    "<p>Застосунок не зібрано. У каталозі warehouse3d/app виконайте <code>npm run build:odoo</code> "
    "(збірка потрапляє в static/app модуля wh_constructor).</p>"
)


def _read_index():
    """Текст собранного index.html или None, если сборки нет (отдельная функция — чтобы подменять в тестах)."""
    try:
        with open(os.path.join(APP_DIR, "index.html"), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None


def _rights(user):
    return {"view": user.has_group(G_VIEW), "design": user.has_group(G_DESIGN), "apply": user.has_group(G_APPLY)}


def _guard(func):
    """Отказ по правам и ошибки проверки — ответом {status}, а не JSON-RPC ошибкой."""
    @functools.wraps(func)
    def wrapper(*args, **kw):
        try:
            return func(*args, **kw)
        except AccessError as e:
            return {"status": "denied", "message": str(e)}
        except (ValidationError, UserError) as e:
            return {"status": "error", "message": str(e)}
    return wrapper


class WhConstructor(http.Controller):

    # ------------------------------------------------------------ приложение
    @http.route(["/wh_constructor/app", "/wh_constructor/app/"], type="http", auth="user")
    def app(self, **kw):
        user = request.env.user
        if not user.has_group(G_VIEW):
            return request.make_response("Немає права «Конструктор: перегляд».", headers=[("Content-Type", "text/plain; charset=utf-8")], status=403)
        html = _read_index()
        if html is None:
            return request.make_response(NO_BUILD, headers=[("Content-Type", "text/html; charset=utf-8")], status=404)
        # относительные пути сборки (base "./") разрешаем от каталога статики; конфиг сообщает приложению, что оно в Odoo
        cfg = json.dumps({"api": BASE + "/api", "db": request.db}).replace("<", "\\u003c")
        inject = f'<base href="{BASE}/static/app/"><script>window.__WH_ODOO__={cfg};</script>'
        html = html.replace("<head>", "<head>" + inject, 1) if "<head>" in html else inject + html
        return request.make_response(html, headers=[("Content-Type", "text/html; charset=utf-8"), ("Cache-Control", "no-store")])

    # ------------------------------------------------------------ пользователь
    @http.route(BASE + "/api/me", type=JSON, auth="user")
    def me(self, **kw):
        user = request.env.user
        return {"uid": user.id, "name": user.name, "company_id": request.env.company.id, "company": request.env.company.name, "rights": _rights(user)}

    # ------------------------------------------------------------ проекты
    @http.route(BASE + "/api/projects", type=JSON, auth="user")
    @_guard
    def projects(self, **kw):
        return {"status": "ok", "projects": request.env["wh.project"].api_list()}

    @http.route(BASE + "/api/project/load", type=JSON, auth="user")
    @_guard
    def project_load(self, key=None, **kw):
        return {"status": "ok", **request.env["wh.project"].api_load(key)}

    @http.route(BASE + "/api/project/save", type=JSON, auth="user")
    @_guard
    def project_save(self, key=None, data=None, name=None, base_rev=None, commit=True, comment=None, **kw):
        return request.env["wh.project"].api_save(key, data, name=name, base_rev=base_rev, commit=bool(commit), comment=comment)

    @http.route(BASE + "/api/project/delete", type=JSON, auth="user")
    @_guard
    def project_delete(self, key=None, **kw):
        return request.env["wh.project"].api_delete(key)

    @http.route(BASE + "/api/project/versions", type=JSON, auth="user")
    @_guard
    def project_versions(self, key=None, **kw):
        return {"status": "ok", "versions": request.env["wh.project"].api_versions(key)}

    @http.route(BASE + "/api/project/restore", type=JSON, auth="user")
    @_guard
    def project_restore(self, key=None, version_id=None, base_rev=None, **kw):
        return request.env["wh.project"].api_restore(key, version_id, base_rev=base_rev)

    # ------------------------------------------------------------ блокировки зон
    @http.route(BASE + "/api/lock/acquire", type=JSON, auth="user")
    @_guard
    def lock_acquire(self, key=None, warehouse=None, zone=None, warehouse_code=None, **kw):
        return request.env["wh.zone.lock"].api_acquire(key, warehouse, zone, warehouse_code=warehouse_code)

    @http.route(BASE + "/api/lock/release", type=JSON, auth="user")
    @_guard
    def lock_release(self, key=None, warehouse=None, zone=None, **kw):
        return request.env["wh.zone.lock"].api_release(key, warehouse_key=warehouse, zone_key=zone)

    @http.route(BASE + "/api/lock/list", type=JSON, auth="user")
    @_guard
    def lock_list(self, key=None, **kw):
        return {"status": "ok", "locks": request.env["wh.zone.lock"].api_list(key)}
