"""API-08, API-09 (§7): кіоск цеху — сторінка і дані за токеном, без сесії.

Усі перевірки токена однакові: вимкнений кіоск і невірний токен дають однакову відповідь `404`. Далі середовище
запиту перемикається на технічного користувача `user_kiosk` (`ctx.kiosk=True`) і викликається та сама логіка, що в
API-01…07 (`serve_*` з `controllers/viewer.py`). Рейт-лимит — у пам'яті воркера (AC-48)."""

import collections
import hmac
import json
import re
import threading
import time

from markupsafe import Markup

from odoo import http
from odoo.http import request

from .viewer import CODE_RE, F3dViewerController

PREFIX = "td.viewer."
RATE_LIMIT = 10  # запитів
RATE_WINDOW_S = 1.0  # за вікно
MAX_TRACKED_IPS = 2048
TAB_RE = re.compile(r"^[a-z_]{1,32}$")
WALL_THEMES = ("dark", "light")
WALL_KEY_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
WALL_SLIDES = ("overview", "kpi", "events", "orders")  # умовчання, якщо параметр порожній
WALL_SLIDE_S = 20
LAYERS_RE = re.compile(r"^[A-Za-z0-9_,\-]{1,200}$")
_hits = {}  # ip -> deque міток часу
_hits_lock = threading.Lock()
_now = time.monotonic  # підміняється в тестах


def rate_limited(ip):
    """True, якщо з цього IP вже було RATE_LIMIT запитів за останню секунду (мітка поточного не додається)."""
    now = _now()
    with _hits_lock:
        if len(_hits) > MAX_TRACKED_IPS:
            for key in [k for k, q in _hits.items() if not q or now - q[-1] > RATE_WINDOW_S]:
                del _hits[key]
        stamps = _hits.setdefault(ip, collections.deque())
        while stamps and now - stamps[0] > RATE_WINDOW_S:
            stamps.popleft()
        if len(stamps) >= RATE_LIMIT:
            return True
        stamps.append(now)
        return False


def reset_rate_limit():
    with _hits_lock:
        _hits.clear()


def _not_found():
    return request.make_response(b"", status=404)


class F3dKioskController(http.Controller):
    @staticmethod
    def _token_ok(token):
        """kiosk_enabled і hmac.compare_digest(token, kiosk_token); без подробиць у відповіді."""
        params = request.env["ir.config_parameter"].sudo()
        enabled = (params.get_param(PREFIX + "kiosk_enabled") or "").lower() in ("true", "1")
        stored = params.get_param(PREFIX + "kiosk_token") or ""
        token = token or ""
        match = hmac.compare_digest(token.encode("utf-8"), stored.encode("utf-8")) if stored else False
        return enabled and match

    @staticmethod
    def _switch_to_kiosk_user():
        """Перемикає `request.env` на `user_kiosk` з `ctx.kiosk=True`; False, якщо користувача немає."""
        user = request.env.ref("td_viewer3d.user_kiosk", raise_if_not_found=False)
        if not user:
            return False
        context = {"kiosk": True, "tz": "Europe/Kyiv"}
        if request.env["res.lang"]._lang_get("uk_UA"):  # українська — лише якщо мову встановлено
            context["lang"] = "uk_UA"
        request.update_env(user=user.id, context=context)
        return True

    def _guard(self, token, limit=True):
        """None, якщо можна обслуговувати; інакше готова відповідь 404 / 429."""
        if not self._token_ok(token) or not self._switch_to_kiosk_user():
            return _not_found()
        if limit and rate_limited(request.httprequest.remote_addr or "-"):
            return request.make_response(b"", status=429, headers=[("Retry-After", "1")])
        return None

    @staticmethod
    def _page_params(kw):
        """Лише відомі параметри URL і лише валідні значення (жодного вільного тексту в HTML)."""
        params = {}
        for key, rx in (("tab", TAB_RE), ("mode", TAB_RE), ("code", CODE_RE), ("layers", LAYERS_RE)):
            value = kw.get(key)
            if value and rx.match(value):
                params[key] = value
        if kw.get("lite") in ("0", "1", "auto"):
            params["lite"] = kw["lite"] if kw["lite"] == "auto" else int(kw["lite"])
        if kw.get("ceiling") in ("0", "1"):
            params["ceiling"] = int(kw["ceiling"])  # 1 — показати стелю, 0 — сховати (у «стіні» за умовчанням сховано)
        if (kw.get("refresh") or "").isdigit() and 1 <= int(kw["refresh"]) <= 3600:
            params["refresh"] = int(kw["refresh"])
        if kw.get("wall") == "1":
            params["wall"] = True  # конфігурацію «стіни» підставляє `page()` з налаштувань
            if kw.get("theme") in WALL_THEMES:
                params["theme"] = kw["theme"]
        return params

    @staticmethod
    def _wall_config(theme=None):
        """Налаштування «стіни» (R-27): тривалість слайда, с, і ключі слайдів за порядком показу."""
        params = request.env["ir.config_parameter"].sudo()
        try:
            slide_s = int(params.get_param(PREFIX + "wall_slide_s") or WALL_SLIDE_S)
        except ValueError:
            slide_s = WALL_SLIDE_S
        if not 5 <= slide_s <= 300:
            slide_s = WALL_SLIDE_S
        raw = params.get_param(PREFIX + "wall_slides") or ""
        slides = [key for key in raw.replace(" ", "").split(",") if WALL_KEY_RE.match(key)] or list(WALL_SLIDES)
        return {"slide_s": slide_s, "slides": slides, "theme": theme or "dark"}

    # --- API-08 ------------------------------------------------------------

    @http.route(
        "/f3d/kiosk/<string:token>",
        type="http",
        auth="public",
        methods=["GET"],
        website=False,
        sitemap=False,
        csrf=False,
        save_session=False,
    )
    def page(self, token, **kw):
        if not self._token_ok(token):
            return _not_found()
        params = self._page_params(kw)
        if params.get("wall"):
            params["wall"] = self._wall_config(params.pop("theme", None))
        values = {
            "token": token,
            "params": params,
            "session_info_json": Markup(
                json.dumps({"db": request.db, "lang": "uk_UA", "user_context": {"tz": "Europe/Kyiv"}})
            ),
        }
        return request.render("td_viewer3d.kiosk_page", values)

    # --- API-09 ------------------------------------------------------------

    @http.route(
        "/f3d/kiosk/<string:token>/static", type="http", auth="public", methods=["GET"], csrf=False, save_session=False
    )
    def kiosk_static(self, token, **kw):
        return self._guard(token) or F3dViewerController.serve_static()

    @http.route(
        "/f3d/kiosk/<string:token>/data", type="http", auth="public", methods=["GET"], csrf=False, save_session=False
    )
    def kiosk_data(self, token, **kw):
        return self._guard(token) or F3dViewerController.serve_data(kw, kiosk=True)

    @http.route(
        "/f3d/kiosk/<string:token>/delta", type="http", auth="public", methods=["GET"], csrf=False, save_session=False
    )
    def kiosk_delta(self, token, **kw):
        return self._guard(token) or F3dViewerController.serve_delta(kw, kiosk=True)

    @http.route(
        "/f3d/kiosk/<string:token>/parts/manifest.json",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        save_session=False,
    )
    def kiosk_manifest(self, token, **kw):
        return self._guard(token) or F3dViewerController.serve_manifest()

    @http.route(
        "/f3d/kiosk/<string:token>/snapshots",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        save_session=False,
    )
    def kiosk_snapshots(self, token, **kw):
        return self._guard(token) or F3dViewerController.serve_snapshots(kw)

    @http.route(
        "/f3d/kiosk/<string:token>/snapshot/<string:snapshot_id>",
        type="http",
        auth="public",
        methods=["GET"],
        csrf=False,
        save_session=False,
    )
    def kiosk_snapshot(self, token, snapshot_id, **kw):
        return self._guard(token) or F3dViewerController.serve_snapshot(snapshot_id)
