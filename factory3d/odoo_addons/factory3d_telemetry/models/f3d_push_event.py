import logging
import math
import re
from datetime import datetime, timedelta, timezone

from odoo import api, fields, models

from ..tools.ingest import parse_ts

_logger = logging.getLogger(__name__)

FUTURE_S = 60
PATH_STEP_RE = re.compile(r"\.([A-Za-z_][A-Za-z0-9_\-]*)|\[([0-9]+)\]")


def jsonpath(path, data):
    """Мінімальний JSONPath ($.a.b[0]), як у валідаторі адреси; відсутній вузол -> None."""
    if not isinstance(path, str) or not path.startswith("$"):
        return None
    node = data
    for key, idx in PATH_STEP_RE.findall(path):
        if idx:
            if not isinstance(node, list) or int(idx) >= len(node):
                return None
            node = node[int(idx)]
        else:
            if not isinstance(node, dict) or key not in node:
                return None
            node = node[key]
    return node


def _device_ts(raw):
    """Час пристрою (ISO із зоною або епоха с/мс) -> naive UTC або None."""
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, str):
        s = raw.strip()
        try:
            raw = float(s)
        except ValueError:
            ts, reason = parse_ts(s)
            return None if reason else ts
    if isinstance(raw, (int, float)):
        if not math.isfinite(raw) or raw < 0:
            return None
        sec = raw / 1000.0 if raw > 1e11 else float(raw)
        try:
            return datetime.fromtimestamp(sec, tz=timezone.utc).replace(tzinfo=None)
        except (OverflowError, OSError, ValueError):
            return None
    return None


class F3dPushEvent(models.Model):
    _name = "f3d.push.event"
    _description = "Телеметрія: подія HTTP push"
    _order = "ts desc"
    _log_access = False

    event_id = fields.Char(string="Ідентифікатор події", size=64, required=True, index=True)
    route = fields.Char(string="Маршрут", size=32, required=True, index=True)
    ts = fields.Datetime(string="Час події", required=True, index=True)
    collector_id = fields.Many2one("f3d.collector", string="Колектор", ondelete="set null")
    remote = fields.Char(string="Відправник", size=64)
    payload = fields.Json(string="Тіло події")
    handled_by = fields.Char(string="Обробники", size=256)
    error = fields.Char(string="Помилка", size=512)
    signal_count = fields.Integer(string="Показань")

    _f3d_push_event_uniq = models.Constraint("UNIQUE(event_id)", "Подія з таким ідентифікатором уже є.")

    @api.model
    def _f3d_receive(self, events, collector):
        """R-22: журнал, обробники M-11 і показання сигналів `http_push` для пакета подій API-05."""
        received_at = fields.Datetime.now()
        Handler = self.env["f3d.push.handler"]
        accepted, rejected, handled = 0, [], {}
        for ev in events:
            event_id = ev["event_id"]
            if self.sudo().search_count([("event_id", "=", event_id)]):
                rejected.append({"event_id": event_id, "reason": "duplicate"})
                continue
            route, payload = ev["route"], ev["payload"]
            if isinstance(ev["ts"], datetime):
                ts = ev["ts"].replace(tzinfo=None)
            else:
                ts = _device_ts(ev["ts"]) or received_at
            remote = ev.get("remote")
            event = {
                "event_id": event_id,
                "route": route,
                "ts": ts,
                "remote": remote,
                "headers": ev.get("headers") or {},
                "payload": payload,
            }
            names = Handler._f3d_handler_models(route)
            errors = []
            for name in names:
                try:
                    with self.env.cr.savepoint():
                        self.env[name]._f3d_handle_push(route, event)
                except Exception as e:  # noqa: BLE001 — обробники ізольовані (M-11)
                    _logger.exception("f3d push handler %s failed for route %s", name, route)
                    errors.append("%s: %s" % (type(e).__name__, e))
            readings = self._f3d_event_readings(route, payload, collector, received_at)
            count = 0
            if readings:
                res = (
                    self.env["f3d.signal"]
                    .sudo()
                    .with_context(f3d_received_at=received_at)
                    ._f3d_ingest(readings, src="collector", collector=collector)
                )
                count = len(readings) - len(res["rejected"])
            self.sudo().create(
                {
                    "event_id": event_id,
                    "route": route,
                    "ts": ts,
                    "collector_id": collector.id,
                    "remote": (remote or "")[:64] or False,
                    "payload": payload,
                    "handled_by": ",".join(names)[:256] or False,
                    "error": "; ".join(errors)[:512] or False,
                    "signal_count": count,
                }
            )
            accepted += 1
            if names:
                handled[route] = sorted(set(handled.get(route, [])) | set(names))
        return {"accepted": accepted, "rejected": rejected, "handled": handled}

    @api.model
    def _f3d_event_readings(self, route, payload, collector, received_at):
        """Показання сигналів `http_push` колектора, чий `address.route/match` підходить події (R-22, X-63)."""
        keep_days = int(self.env["ir.config_parameter"].sudo().get_param("factory3d.telemetry.keep_days", "30") or 30)
        signals = (
            self.env["f3d.signal"]
            .sudo()
            .search(
                [
                    ("source_id.type", "=", "http_push"),
                    ("source_id.collector_id", "=", collector.id),
                    ("active", "=", True),
                ]
            )
        )
        readings = []
        for sig in signals:
            addr = sig.address or {}
            if addr.get("route") != route:
                continue
            if not all(payload.get(k) == v for k, v in (addr.get("match") or {}).items()):
                continue
            val = jsonpath(addr.get("path"), payload)
            if val is None:
                continue
            reading = {"code": sig.code, "q": "good"}
            if sig.kind in ("gauge", "counter"):
                if isinstance(val, (bool, int, float)):
                    val = float(val)
                elif isinstance(val, str):
                    try:
                        val = float(val.strip())
                    except ValueError:
                        continue
                else:
                    continue
                if not math.isfinite(val):
                    continue
                reading["value"] = (val * float(addr.get("scale", 1.0)) + float(addr.get("offset", 0.0))) * sig.scale
            elif sig.kind == "event":
                reading.update(value=1.0, text=str(val)[:64])
            else:
                reading["text"] = str(val)[:64]
            ts = None
            if addr.get("ts_path"):
                ts = _device_ts(jsonpath(addr["ts_path"], payload))
                if ts is not None and (
                    ts > received_at + timedelta(seconds=FUTURE_S) or ts < received_at - timedelta(days=keep_days)
                ):
                    ts = None
                if ts is None:
                    reading["q"] = "uncertain"
            reading["ts"] = ts or received_at
            readings.append(reading)
        return readings
