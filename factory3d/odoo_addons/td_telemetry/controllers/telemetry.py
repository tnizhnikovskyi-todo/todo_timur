"""HTTP/JSON API колектора (SPEC §7, API-01…API-07).

Контролер лише автентифікує колектор, розбирає й перевіряє тіло; показання проходять через
`td.signal._td_ingest` (X-02), події — через `td.push.event._td_receive` (R-22).
"""

import hashlib
import json
import re
from datetime import timedelta

from odoo import SUPERUSER_ID, fields, http
from odoo.http import request
from odoo.modules.module import Manifest

from ..tools.ingest import parse_ts

MODULE = "td_telemetry"
BODY_MAX = 1024 * 1024
STATUS_MAX = 256 * 1024
RESULT_DATA_MAX = 65536
EVENT_ROUTE_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
EVENT_ID_RE = re.compile(r"^[0-9a-f]{64}$")
EVENT_HEADERS = ("content-type", "user-agent", "x-f3d-token-ok")
EVENT_PAYLOAD_MAX = 256 * 1024
NO_STORE = [("Cache-Control", "no-store")]


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ") if dt else None


def _json(data, status=200, headers=None):
    return request.make_json_response(data, headers=headers if headers is not None else NO_STORE, status=status)


def _error(status, code, message, headers=None):
    return _json({"error": {"code": code, "message": message}}, status, headers)


def _param_flag(env, key):
    return env["ir.config_parameter"].sudo().get_param("td.telemetry." + key, "False") in ("True", "true", "1")


class _Abort(Exception):
    def __init__(self, response):
        super().__init__("abort")
        self.response = response


class F3dTelemetryController(http.Controller):
    # --- спільне --------------------------------------------------------------------------------------
    def _authenticate(self):
        """Колектор за Bearer-токеном; `_Abort` з 401/403."""
        header = request.httprequest.headers.get("Authorization", "")
        token = header[7:].strip() if header[:7].lower() == "bearer " else ""
        Collector = request.env["td.collector"].sudo()
        collector = Collector._authenticate(token)
        if not collector:
            if token and len(token) <= 256:
                digest = hashlib.sha256(token.encode()).hexdigest()
                inactive = Collector.with_context(active_test=False).search(
                    [("active", "=", False), ("token_hash", "=", digest)], limit=1
                )
                if inactive:
                    raise _Abort(_error(403, "forbidden", "Колектор вимкнено"))
            raise _Abort(_error(401, "unauthorized", "Невірний токен колектора"))
        env = request.env(user=SUPERUSER_ID, context=dict(request.env.context, f3d_collector_id=collector.id, tz="UTC"))
        return collector.with_env(env), env

    def _body(self, limit=BODY_MAX):
        req = request.httprequest
        if (req.content_length or 0) > limit:
            raise _Abort(_error(413, "payload_too_large", "Тіло запиту завелике"))
        raw = req.get_data()
        if len(raw) > limit:
            raise _Abort(_error(413, "payload_too_large", "Тіло запиту завелике"))
        try:
            body = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            raise _Abort(_error(400, "bad_json", "Тіло запиту не є коректним JSON")) from None
        if not isinstance(body, dict):
            raise _Abort(_error(400, "bad_schema", "Тіло запиту має бути JSON-об'єктом"))
        return body

    def _check_collector(self, body, collector):
        name = body.get("collector")
        if name is not None and name != collector.code:
            raise _Abort(_error(403, "collector_mismatch", "Код колектора не збігається з токеном"))

    def _read_enabled_or_423(self, env):
        if not _param_flag(env, "read_enabled"):
            raise _Abort(_error(423, "read_disabled", "Приймання показань вимкнено"))

    def _flags(self, collector, env):
        return {
            "config_etag": collector._etag(),
            "read_enabled": _param_flag(env, "read_enabled"),
            "write_enabled": _param_flag(env, "write_enabled"),
            "server_time": _iso(fields.Datetime.now()),
        }

    def _method_denied(self, method):
        """Невірний HTTP-метод → 405 у JSON-конверті (SPEC §7: усі помилки — JSON), а не HTML Odoo."""
        actual = request.httprequest.method
        if actual == method or (method == "GET" and actual == "HEAD"):
            return None
        return _error(405, "method_not_allowed", "Дозволено лише %s" % method, NO_STORE + [("Allow", method)])

    def _guard(self, fn, method):
        denied = self._method_denied(method)
        if denied:
            return denied
        try:
            return fn()
        except _Abort as e:
            return e.response

    # --- API-01 ---------------------------------------------------------------------------------------
    @http.route("/f3d/telemetry/config", type="http", auth="public", csrf=False)
    def config(self, **kw):
        def run():
            collector, _env = self._authenticate()
            collector._touch(request.httprequest.remote_addr)
            body = collector._config_payload()
            etag = body["etag"]
            headers = [("Cache-Control", "private, max-age=0"), ("ETag", '"%s"' % etag)]
            inm = request.httprequest.headers.get("If-None-Match", "")
            if inm and etag in [p.strip().removeprefix("W/").strip('"') for p in inm.split(",")]:
                return request.make_response(b"", headers=headers, status=304)
            return _json(body, 200, headers)

        return self._guard(run, "GET")

    # --- API-02 ---------------------------------------------------------------------------------------
    @http.route("/f3d/telemetry/push", type="http", auth="public", csrf=False)
    def push(self, **kw):
        def run():
            collector, env = self._authenticate()
            self._read_enabled_or_423(env)
            body = self._body()
            readings = body.get("readings")
            if not isinstance(readings, list):
                return _error(400, "bad_schema", "readings має бути списком")
            limit = int(env["ir.config_parameter"].sudo().get_param("td.telemetry.push_max_readings", "2000"))
            if len(readings) > limit:
                return _error(413, "too_many_readings", "Забагато показань у пакеті")
            self._check_collector(body, collector)
            if not collector._rate_check():
                return _error(429, "rate_limited", "Забагато пакетів за хвилину", NO_STORE + [("Retry-After", "10")])
            collector._touch(request.httprequest.remote_addr, pushed=True)
            res = env["td.signal"].sudo()._td_ingest(readings, src="collector", collector=collector)
            return _json(
                {
                    "accepted": res["accepted"],
                    "stored": res["stored"],
                    "duplicates": res["duplicates"],
                    "rejected": res["rejected"],
                    "changed": res["changed_codes"],
                    "alarms_opened": res["alarms_opened"],
                    **self._flags(collector, env),
                }
            )

        return self._guard(run, "POST")

    # --- API-03 ---------------------------------------------------------------------------------------
    @http.route("/f3d/telemetry/status", type="http", auth="public", csrf=False)
    def status(self, **kw):
        def run():
            collector, env = self._authenticate()
            body = self._body(STATUS_MAX)
            self._check_collector(body, collector)
            sources = body.get("sources", [])
            if not isinstance(sources, list) or any(not isinstance(s, dict) for s in sources):
                return _error(400, "bad_schema", "sources має бути списком об'єктів")
            if len(sources) > 500:
                return _error(413, "payload_too_large", "Забагато джерел у звіті")
            collector._touch(request.httprequest.remote_addr, version=str(body.get("version") or "")[:64] or None)
            vals = {}
            uptime = body.get("uptime_s")
            if isinstance(uptime, int) and not isinstance(uptime, bool):
                vals["uptime_s"] = uptime
            buf = body.get("buffer")
            if isinstance(buf, dict):
                for key, field in (("rows", "buffer_rows"), ("dropped_total", "buffer_dropped")):
                    if isinstance(buf.get(key), int) and not isinstance(buf.get(key), bool):
                        vals[field] = buf[key]
            if isinstance(body.get("plugins"), list):
                vals["plugins"] = body["plugins"]
            if vals:
                collector.sudo().with_context(mail_notrack=True).write(vals)
            own = {s.code: s for s in collector.sudo().with_context(active_test=False).source_ids}
            rejected = []
            for item in sources:
                src = own.get(item.get("code"))
                if src:
                    src._apply_status(item)
                else:
                    rejected.append(item.get("code"))
            return _json({"ok": True, "rejected": rejected, **self._flags(collector, env)})

        return self._guard(run, "POST")

    # --- API-04 ---------------------------------------------------------------------------------------
    @http.route("/f3d/telemetry/health", type="http", auth="public", csrf=False)
    def health(self, **kw):
        denied = self._method_denied("GET")
        if denied:
            return denied
        env = request.env
        data = {"ok": True, "module": MODULE, "server_time": _iso(fields.Datetime.now())}
        try:
            manifest = Manifest.for_addon(MODULE)
            data["version"] = manifest["version"] if manifest else ""
        except Exception:  # noqa: BLE001
            data["version"] = ""
        header = request.httprequest.headers.get("Authorization", "")
        token = header[7:].strip() if header[:7].lower() == "bearer " else ""
        collector = env["td.collector"].sudo()._authenticate(token)
        if collector:
            su = env(user=SUPERUSER_ID)
            Signal = su["td.signal"]
            data["collector"] = {
                "code": collector.code,
                "state": collector.state,
                "last_seen": _iso(collector.last_seen),
            }
            data["counts"] = {
                "signals": Signal.search_count([]),
                "alarms": Signal.search_count([("status", "=", "alarm")]),
                "stale": Signal.search_count([("status", "=", "stale")]),
                "sources_online": su["td.source"].search_count([("state", "=", "online")]),
            }
        return _json(data)

    # --- API-05 ---------------------------------------------------------------------------------------
    @http.route("/f3d/telemetry/event", type="http", auth="public", csrf=False)
    def event(self, **kw):
        def run():
            collector, env = self._authenticate()
            self._read_enabled_or_423(env)
            body = self._body()
            self._check_collector(body, collector)
            events = body.get("events")
            if not isinstance(events, list):
                return _error(400, "bad_schema", "events має бути списком")
            if len(events) > 100:
                return _error(413, "payload_too_large", "Забагато подій у пакеті")
            clean = []
            for ev in events:
                item = self._event_item(ev)
                if item is None:
                    return _error(400, "bad_schema", "Невалідна подія у пакеті")
                clean.append(item)
            collector._touch(request.httprequest.remote_addr)
            res = env["td.push.event"]._td_receive(clean, collector)
            return _json(res)

        return self._guard(run, "POST")

    @staticmethod
    def _event_item(ev):
        if not isinstance(ev, dict):
            return None
        event_id, route, payload = ev.get("event_id"), ev.get("route"), ev.get("payload")
        if not (isinstance(event_id, str) and EVENT_ID_RE.match(event_id)):
            return None
        if not (isinstance(route, str) and EVENT_ROUTE_RE.match(route)) or not isinstance(payload, dict):
            return None
        if len(json.dumps(payload).encode()) > EVENT_PAYLOAD_MAX:
            return None
        ts, reason = parse_ts(ev.get("ts"))
        if reason:
            return None
        remote = ev.get("remote")
        headers = ev.get("headers")
        headers = {k: v for k, v in headers.items() if k in EVENT_HEADERS} if isinstance(headers, dict) else {}
        return {
            "event_id": event_id,
            "route": route,
            "ts": ts,
            "payload": payload,
            "headers": headers,
            "remote": remote if isinstance(remote, str) else None,
        }

    # --- API-06 ---------------------------------------------------------------------------------------
    @http.route("/f3d/telemetry/commands", type="http", auth="public", csrf=False)
    def commands(self, **kw):
        def run():
            collector, env = self._authenticate()
            write_on = _param_flag(env, "write_enabled")
            if not write_on:
                return _json({"commands": [], "write_enabled": False})
            try:
                limit = min(max(int(request.httprequest.args.get("limit", 50)), 1), 100)
            except ValueError:
                limit = 50
            now = fields.Datetime.now()
            cmds = env["td.command"].search(
                [
                    ("state", "=", "queued"),
                    ("collector_id", "=", collector.id),
                    ("expires_at", ">", now),
                    ("signal_id.write_enabled", "=", True),
                    ("source_id.write_enabled", "=", True),
                ],
                order="requested_at, id",
                limit=limit,
            )
            out = [
                {
                    "id": c.id,
                    "code": c.signal_id.code,
                    "source": c.source_id.code,
                    "value": c.value,
                    "text": c.text or None,
                    "payload": c.payload or None,
                    "requested_at": _iso(c.requested_at),
                    "expires_at": _iso(c.expires_at),
                    "address": c.signal_id.address or {},
                }
                for c in cmds
            ]
            cmds.with_context(mail_notrack=True).write({"state": "sent", "sent_at": now})
            return _json({"write_enabled": True, "server_time": _iso(now), "commands": out})

        return self._guard(run, "GET")

    # --- API-07 ---------------------------------------------------------------------------------------
    @http.route("/f3d/telemetry/commands/result", type="http", auth="public", csrf=False)
    def commands_result(self, **kw):
        def run():
            collector, env = self._authenticate()
            body = self._body()
            self._check_collector(body, collector)
            results = body.get("results")
            if not isinstance(results, list):
                return _error(400, "bad_schema", "results має бути списком")
            for item in results:
                rid = item.get("id") if isinstance(item, dict) else None
                if not isinstance(rid, int) or isinstance(rid, bool):
                    return _error(400, "bad_schema", "Невалідний елемент results")
                data = item.get("data")
                if data is not None and (
                    not isinstance(data, dict) or len(json.dumps(data, ensure_ascii=False).encode()) > RESULT_DATA_MAX
                ):
                    return _error(400, "bad_schema", "data має бути об'єктом ≤ 64 КБ")
            Command = env["td.command"]
            accepted, rejected = 0, []
            for item in results:
                cmd = Command.browse(item["id"]).exists()
                if not cmd or cmd.collector_id != collector:
                    rejected.append({"id": item["id"], "reason": "not_found"})
                elif cmd.state in ("done", "failed"):
                    rejected.append({"id": item["id"], "reason": "already_done"})
                elif cmd.state != "sent":
                    rejected.append({"id": item["id"], "reason": "not_sent"})
                elif item.get("state") not in ("done", "failed"):
                    rejected.append({"id": item["id"], "reason": "bad_state"})
                else:
                    self._apply_result(cmd, item)
                    accepted += 1
            return _json({"accepted": accepted, "rejected": rejected})

        return self._guard(run, "POST")

    @staticmethod
    def _apply_result(cmd, item):
        done_at, reason = parse_ts(item.get("ts"))
        now = fields.Datetime.now()
        if reason or done_at > now + timedelta(seconds=60):
            done_at = now
        result, error = item.get("result"), item.get("error")
        if result is not None and not isinstance(result, str):
            result = json.dumps(result, ensure_ascii=False)
        vals = {
            "state": item["state"],
            "done_at": done_at,
            "result": result or False,
            "error": str(error)[:512] if error else False,
        }
        if item.get("data") is not None:
            vals["result_data"] = item["data"]
        cmd = cmd.with_context(mail_notrack=True)
        cmd.write(vals)
        if item["state"] == "done":
            cmd.message_post(body="Виконано: %s" % (result or ""), subtype_xmlid="mail.mt_note")
        else:
            cmd.message_post(body="Помилка: %s" % (error or ""), subtype_xmlid="mail.mt_note")
