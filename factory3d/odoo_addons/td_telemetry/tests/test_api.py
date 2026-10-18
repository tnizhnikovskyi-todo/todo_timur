import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from odoo import fields
from odoo.addons.td_telemetry.models.push_handler import F3dPushHandler
from odoo.exceptions import ValidationError
from odoo.modules.module import Manifest
from odoo.tests import tagged

from .common import F3DTelemetryHttpCase

TAGS = ("post_install", "-at_install", "f3d", "f3d_telemetry")
BASE = "/f3d/telemetry/"
CONFIG_KEYS = {"etag", "generated_at", "server_time", "read_enabled", "write_enabled", "collector", "params", "sources"}


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class ApiCase(F3DTelemetryHttpCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_telemetry_fixtures()

    def setUp(self):
        super().setUp()
        self.icp = self.env["ir.config_parameter"].sudo()

    def now(self, seconds=0):
        return fields.Datetime.now() + timedelta(seconds=seconds)

    def reading(self, sig, value=None, text=None, seconds=-5, q=None):
        res = {"code": sig.code, "ts": iso(self.now(seconds)), "value": value, "text": text, "q": q}
        return {k: v for k, v in res.items() if v is not None}

    def post(self, path, body, **kw):
        return self.api("POST", BASE + path, body, **kw)

    def get(self, path, **kw):
        return self.api("GET", BASE + path, **kw)

    def reload(self, *recs):
        self.env.invalidate_all()
        return recs


@tagged(*TAGS)
class TestConfig(ApiCase):
    def test_config_schema(self):
        status, body, headers = self.get("config")
        self.assertEqual(status, 200)
        self.assertIn("application/json", headers["Content-Type"])
        self.assertEqual(headers["Cache-Control"], "private, max-age=0")
        self.assertEqual(set(body), CONFIG_KEYS)
        self.assertEqual(headers["ETag"], '"%s"' % body["etag"])
        self.assertEqual(body["collector"]["code"], "COL-T")
        self.assertEqual(
            [s["code"] for s in body["sources"]], ["BAC-T-105", "BAC-T-200", "HTTP-T", "MB-T-U70", "MB-T-U84", "MQTT-T"]
        )
        codes = {sig["code"] for s in body["sources"] for sig in s["signals"]}
        self.assertNotIn(self.sig_flow.code, codes)
        self.assertNotIn(self.sig_noaddr.code, codes)
        self.assertNotIn(self.sig_old.code, codes)
        self.assertIn(self.sig_press.code, codes)

    def test_filters(self):
        _s, body, _h = self.get("config")
        codes = [s["code"] for s in body["sources"]]
        self.assertNotIn("MB-T-OLD", codes)
        self.assertNotIn("MB-T2", codes)

    def test_no_secrets(self):
        resp = self.url_open(BASE + "config", headers={"Authorization": "Bearer " + self.token})
        raw = resp.text
        self.assertIn("password_ref", raw)
        self.assertNotIn('"password"', raw)
        self.assertNotIn('"token"', raw)

    def test_source_disabled(self):
        self.src_mb.read_enabled = False
        _s, body, _h = self.get("config")
        src = next(s for s in body["sources"] if s["code"] == "MB-T-U70")
        self.assertFalse(src["read_enabled"])

    def test_global_disabled(self):
        self.icp.set_param("td.telemetry.read_enabled", "False")
        _s, body, _h = self.get("config")
        self.assertFalse(body["read_enabled"])
        self.assertFalse(any(s["read_enabled"] for s in body["sources"]))

    def test_etag_304(self):
        _s, body, _h = self.get("config")
        status, data, _h = self.get("config", headers={"If-None-Match": '"%s"' % body["etag"]})
        self.assertEqual(status, 304)
        self.assertIsNone(data)

    def test_etag_changes(self):
        _s, body1, _h = self.get("config")
        _s, body2, _h = self.get("config")
        self.assertEqual(body1["etag"], body2["etag"])
        self.sig_press.period_s = 20
        _s, body3, _h = self.get("config")
        self.assertNotEqual(body1["etag"], body3["etag"])
        _s, res, _h = self.post("push", {"collector": "COL-T", "readings": [self.reading(self.sig_press, 6.8)]})
        self.assertEqual(res["config_etag"], body3["etag"])


@tagged(*TAGS)
class TestAuth(ApiCase):
    def test_unauthorized(self):
        for token in (None, "wrong"):
            for method, path in (
                ("GET", "config"),
                ("POST", "push"),
                ("POST", "status"),
                ("POST", "event"),
                ("GET", "commands"),
                ("POST", "commands/result"),
            ):
                status, body, _h = self.api(method, BASE + path, {}, token=token)
                self.assertEqual(status, 401, path)
                self.assertEqual(body, {"error": {"code": "unauthorized", "message": "Невірний токен колектора"}})
        self.col.action_revoke_token()
        status, _b, _h = self.get("config")
        self.assertEqual(status, 401)

    def test_wrong_method_json_405(self):  # T-5: 405 у JSON-конверті, а не HTML Odoo
        for method, path, allow in (("GET", "push", "POST"), ("POST", "config", "GET"), ("POST", "health", "GET")):
            for token in (None, "default"):
                status, body, headers = self.api(method, BASE + path, {}, token=token)
                self.assertEqual(status, 405, path)
                self.assertEqual(body["error"]["code"], "method_not_allowed")
                self.assertEqual(headers["Allow"], allow)
                self.assertIn("application/json", headers["Content-Type"])

    def test_inactive_forbidden(self):
        self.col.active = False
        status, body, _h = self.get("config")
        self.assertEqual((status, body["error"]["code"]), (403, "forbidden"))

    def test_health(self):
        for token in (None, "wrong"):
            status, body, _h = self.get("health", token=token)
            self.assertEqual(status, 200)
            self.assertEqual(set(body), {"ok", "module", "version", "server_time"})
            self.assertEqual(body["version"], "19.0.1.1.0")

    def test_health_with_token(self):
        status, body, _h = self.get("health")
        self.assertEqual(status, 200)
        Signal = self.env["td.signal"]
        self.assertEqual(body["collector"]["code"], "COL-T")
        self.assertEqual(
            body["counts"],
            {
                "signals": Signal.search_count([]),
                "alarms": Signal.search_count([("status", "=", "alarm")]),
                "stale": Signal.search_count([("status", "=", "stale")]),
                "sources_online": self.env["td.source"].search_count([("state", "=", "online")]),
            },
        )

    def test_status(self):
        body = {
            "collector": "COL-T",
            "version": "0.1.0",
            "uptime_s": 86412,
            "ts": iso(self.now()),
            "buffer": {"rows": 0, "dropped_total": 0, "bytes": 24576},
            "plugins": [{"type": "modbus_tcp", "version": "0.1.0", "sources": 4}],
            "sources": [
                {"code": "MB-T-U70", "state": "online", "last_ok": iso(self.now()), "error": None},
                {"code": "MQTT-T", "state": "online", "error": None},
                {"code": "BAC-T-105", "state": "error", "error": "timeout password=secret123"},
                {"code": "NOPE", "state": "online"},
                {"code": "MB-T2", "state": "online"},
            ],
        }
        status, res, _h = self.post("status", body)
        self.assertEqual(status, 200)
        self.assertTrue(res["ok"])
        self.assertEqual(res["rejected"], ["NOPE", "MB-T2"])
        self.reload()
        self.assertEqual((self.col.version, self.col.uptime_s, self.col.buffer_rows), ("0.1.0", 86412, 0))
        self.assertEqual(self.col.plugins, body["plugins"])
        self.assertEqual(self.src_bac.state, "error")
        self.assertNotIn("secret123", self.src_bac.last_error)
        status, res, _h = self.post("status", {"sources": "x"})
        self.assertEqual((status, res["error"]["code"]), (400, "bad_schema"))


@tagged(*TAGS)
class TestPush(ApiCase):
    def packet(self):
        local = (self.now(-5) + timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S+03:00")
        return {
            "collector": "COL-T",
            "seq": 1,
            "readings": [
                self.reading(self.sig_press, 6.772, q="good"),
                {"code": self.sig_bat.code, "ts": local, "value": 23.6},
                self.reading(self.sig_flstate, text="busy"),
                self.reading(self.sig_water, 18642.37),
            ],
        }

    def test_push_ok(self):
        status, res, _h = self.post("push", self.packet())
        self.assertEqual(status, 200)
        self.assertEqual((res["accepted"], res["stored"], res["duplicates"], res["rejected"]), (4, 4, 0, []))
        self.assertEqual(len(res["changed"]), 4)
        self.assertEqual(res["alarms_opened"], 0)
        self.assertEqual(len(res["config_etag"]), 64)
        self.assertTrue(res["read_enabled"])
        self.assertTrue(res["server_time"].endswith("Z"))
        self.reload()
        self.assertEqual(self.sig_press.last_value, 6.772)
        self.assertEqual(self.sig_bat.status, "warn")
        self.assertEqual(self.sig_flstate.last_text, "busy")
        self.assertTrue(self.col.last_push_at and self.col.last_seen)
        self.assertEqual(self.col.state, "online")

    def test_push_bad_body(self):
        status, res, _h = self.post("push", None, raw="not json")
        self.assertEqual((status, res["error"]["code"]), (400, "bad_json"))
        status, res, _h = self.post("push", {"readings": {}})
        self.assertEqual((status, res["error"]["code"]), (400, "bad_schema"))
        many = [{"code": "a/b", "ts": iso(self.now())}] * 2001
        status, res, _h = self.post("push", {"readings": many})
        self.assertEqual((status, res["error"]["code"]), (413, "too_many_readings"))
        status, res, _h = self.post("push", {"readings": [], "pad": "x" * (1024 * 1024 + 10)})
        self.assertEqual((status, res["error"]["code"]), (413, "payload_too_large"))
        status, res, _h = self.post("push", {"collector": "COL-T2", "readings": []})
        self.assertEqual((status, res["error"]["code"]), (403, "collector_mismatch"))

    def test_push_element_rejects(self):
        now = self.now
        ok_ts = iso(now(-5))
        readings = [
            {"code": "equipment/XX/y", "ts": ok_ts, "value": 1},
            {"code": self.sig_foreign.code, "ts": ok_ts, "value": 1},
            {"code": self.sig_old.code, "ts": ok_ts, "value": 1},
            {"code": "Equipment/X", "ts": ok_ts, "value": 1},
            {"code": self.sig_press.code, "ts": "2026-10-14T06:10:00", "value": 1},
            {"code": self.sig_press.code, "ts": "abc", "value": 1},
            {"code": self.sig_press.code, "ts": iso(now(300)), "value": 1},
            {"code": self.sig_press.code, "ts": iso(now(-31 * 86400)), "value": 1},
            {"code": self.sig_press.code, "ts": ok_ts, "value": "abc"},
            {"code": self.sig_press.code, "ts": ok_ts, "value": float("nan")},
            {"code": self.sig_flstate.code, "ts": ok_ts, "text": "x" * 65},
            {"code": self.sig_press.code, "ts": ok_ts},
        ]
        status, res, _h = self.post("push", {"collector": "COL-T", "readings": readings})
        self.assertEqual(status, 200)
        self.assertEqual(res["accepted"], 0)
        self.assertEqual(
            [r["reason"] for r in res["rejected"]],
            [
                "unknown_code",
                "foreign_signal",
                "inactive",
                "bad_code_format",
                "ts_no_tz",
                "ts_invalid",
                "ts_future",
                "ts_too_old",
                "value_invalid",
                "value_invalid",
                "text_too_long",
                "missing_value",
            ],
        )
        self.assertEqual([r["i"] for r in res["rejected"]], list(range(12)))

    def test_gauge_ignores_text(self):  # T-5: value+text для числового сигналу — text не потрапляє в last_text
        item = self.reading(self.sig_press, 6.8, text="x")
        _s, res, _h = self.post("push", {"collector": "COL-T", "readings": [item]})
        self.assertEqual((res["accepted"], res["rejected"]), (1, []))
        self.reload()
        self.assertEqual(self.sig_press.last_value, 6.8)
        self.assertFalse(self.sig_press.last_text)

    def test_push_repeat(self):
        packet = self.packet()
        self.post("push", packet)
        self.reload()
        before = self.env["td.reading"].search_count([])
        last = self.sig_press.last_value
        status, res, _h = self.post("push", packet)
        self.assertEqual((status, res["stored"], res["duplicates"], res["changed"]), (200, 0, 4, []))
        self.reload()
        self.assertEqual(self.env["td.reading"].search_count([]), before)
        self.assertEqual(self.sig_press.last_value, last)

    def test_push_read_disabled_423(self):
        self.icp.set_param("td.telemetry.read_enabled", "False")
        status, res, _h = self.post("push", self.packet())
        self.assertEqual((status, res["error"]["code"]), (423, "read_disabled"))
        self.reload()
        self.assertFalse(self.sig_press.last_ts)
        status, res, _h = self.post("event", {"events": []})
        self.assertEqual(status, 423)

    def test_push_rate_limited_429(self):
        self.icp.set_param("td.telemetry.push_rate_per_min", "3")
        empty = {"collector": "COL-T", "readings": []}
        codes = [self.post("push", empty)[0] for _ in range(3)]
        self.assertEqual(codes, [200, 200, 200])
        status, res, headers = self.post("push", empty)
        self.assertEqual((status, res["error"]["code"], headers["Retry-After"]), (429, "rate_limited", "10"))
        # вікно минуло: пакети в журналі ліміту старші за 60 с (AC-41)
        self.env.cr.execute("UPDATE td_collector_push SET ts = ts - interval '61 seconds'")
        self.assertEqual(self.post("push", empty)[0], 200)


def _event(sig_provider="CAM-05", suffix="", seconds=-2, **extra):
    ms = int((datetime.now(timezone.utc) + timedelta(seconds=seconds)).timestamp() * 1000)
    payload = {
        "plateText": "AA4512KT",
        "carState": "new",
        "sensorProviderID": sig_provider,
        "capture_timestamp": str(ms),
        **extra,
    }
    return {
        "event_id": hashlib.sha256(("lpr" + json.dumps(payload) + suffix).encode()).hexdigest(),
        "route": "lpr",
        "ts": iso(datetime.now(timezone.utc)),
        "remote": "10.90.2.5",
        "headers": {"content-type": "application/json", "x-other": "dropped"},
        "payload": payload,
    }


@tagged(*TAGS)
class TestEvent(ApiCase):
    def test_event_ok(self):
        # без обробників маршруту: модулі на кшталт td_yard реєструють власні (`handled` залежить від них)
        with patch.object(F3dPushHandler, "_f3d_handler_models", return_value=[]):
            status, res, _h = self.post("event", {"collector": "COL-T", "events": [_event()]})
        self.assertEqual((status, res), (200, {"accepted": 1, "rejected": [], "handled": {}}))
        self.reload()
        ev = self.env["td.push.event"].search([("route", "=", "lpr")])
        self.assertEqual((len(ev), ev.signal_count, ev.remote, ev.collector_id), (1, 1, "10.90.2.5", self.col))
        self.assertEqual(ev.payload["plateText"], "AA4512KT")
        self.assertEqual(self.sig_plate.last_text, "AA4512KT")

    def test_event_duplicate(self):
        ev = _event()
        self.post("event", {"events": [ev]})
        _s, res, _h = self.post("event", {"events": [ev]})
        self.assertEqual(res["accepted"], 0)
        self.assertEqual(res["rejected"], [{"event_id": ev["event_id"], "reason": "duplicate"}])

    def test_event_bad(self):
        bad_route = dict(_event(), route="Lpr")
        bad_payload = dict(_event(suffix="b"), payload=[1])
        for ev in (bad_route, bad_payload):
            status, res, _h = self.post("event", {"events": [ev]})
            self.assertEqual((status, res["error"]["code"]), (400, "bad_schema"))

    def test_event_413_423(self):
        status, _r, _h = self.post("event", {"events": [_event(suffix=str(i)) for i in range(101)]})
        self.assertEqual(status, 413)
        self.icp.set_param("td.telemetry.read_enabled", "False")
        status, _r, _h = self.post("event", {"events": [_event()]})
        self.assertEqual(status, 423)


class CommandCase(ApiCase):
    def setUp(self):
        super().setUp()
        self.icp.set_param("td.telemetry.write_enabled", "True")
        self.src_bac.write_enabled = True
        self.src_other.write_enabled = True
        self.sig_valve.write_enabled = True
        self.sig_foreign.write_enabled = True

    def command(self, sig=None, **kw):
        return self.env["td.command"].create({"signal_id": (sig or self.sig_valve).id, "value": 80, **kw})


@tagged(*TAGS)
class TestCommandsApi(CommandCase):
    def test_commands_write_disabled(self):
        a = self.command()
        self.icp.set_param("td.telemetry.write_enabled", "False")
        _s, res, _h = self.get("commands")
        self.assertEqual(res, {"commands": [], "write_enabled": False})
        self.reload()
        self.assertEqual(a.state, "queued")

    def test_commands_handout(self):
        a = self.command()
        self.command(self.sig_foreign)
        self.command(expires_at=self.now(-10))
        _s, res, _h = self.get("commands")
        self.assertTrue(res["write_enabled"])
        self.assertEqual([c["id"] for c in res["commands"]], [a.id])
        self.assertEqual(res["commands"][0]["address"], self.sig_valve.address)
        self.assertEqual(res["commands"][0]["source"], "BAC-T-105")
        self.reload()
        self.assertEqual(a.state, "sent")
        self.assertTrue(a.sent_at)
        self.assertEqual(self.get("commands")[1]["commands"], [])
        self.command()
        self.command()
        self.assertEqual(len(self.api("GET", BASE + "commands?limit=1")[1]["commands"]), 1)

    def test_results(self):
        a, d = self.command(), self.command()
        (a | d).write({"state": "sent"})
        body = {
            "collector": "COL-T",
            "results": [
                {"id": a.id, "state": "done", "result": "written 80.0 @prio 8"},
                {"id": d.id, "state": "failed", "error": "WriteAccessDenied"},
            ],
        }
        _s, res, _h = self.post("commands/result", body)
        self.assertEqual(res, {"accepted": 2, "rejected": []})
        self.reload()
        self.assertEqual(
            (a.state, a.result, d.state, d.error), ("done", "written 80.0 @prio 8", "failed", "WriteAccessDenied")
        )
        self.assertTrue(a.done_at)
        self.assertTrue(any("Виконано: written 80.0 @prio 8" in (m.body or "") for m in a.message_ids))

    def test_results_repeat_and_errors(self):
        a = self.command()
        a.state = "sent"
        item = {"id": a.id, "state": "done", "result": "ok"}
        self.post("commands/result", {"results": [item]})
        _s, res, _h = self.post("commands/result", {"results": [item]})
        self.assertEqual((res["accepted"], [r["reason"] for r in res["rejected"]]), (0, ["already_done"]))
        queued, foreign = self.command(), self.command(self.sig_foreign)
        foreign.state = "sent"
        _s, res, _h = self.post(
            "commands/result",
            {
                "results": [
                    {"id": queued.id, "state": "done"},
                    {"id": foreign.id, "state": "done"},
                    {"id": 99999999, "state": "done"},
                ]
            },
        )
        self.assertEqual([r["reason"] for r in res["rejected"]], ["not_sent", "not_found", "not_found"])
        status, res, _h = self.post("commands/result", {"results": "x"})
        self.assertEqual((status, res["error"]["code"]), (400, "bad_schema"))


@tagged(*TAGS)
class TestIngestEntryPoint(ApiCase):
    def spy(self):
        model = type(self.env["td.signal"])
        return patch.object(model, "_f3d_ingest", autospec=True, side_effect=model._f3d_ingest)

    def test_push_goes_through_f3d_ingest(self):
        readings = [self.reading(self.sig_press, 6.8)]
        with self.spy() as spy:
            _s, res, _h = self.post("push", {"collector": "COL-T", "readings": readings})
        self.assertEqual(spy.call_count, 1)
        self.assertEqual(spy.call_args.args[1], readings)
        self.assertEqual(spy.call_args.kwargs["src"], "collector")
        self.assertEqual(spy.call_args.kwargs["collector"], self.col)
        self.assertEqual(res["changed"], [self.sig_press.code])

    def test_event_goes_through_f3d_ingest(self):
        with self.spy() as spy:
            self.post("event", {"events": [_event()]})
        self.assertEqual(spy.call_count, 1)
        self.assertEqual(spy.call_args.kwargs["src"], "collector")
        self.assertEqual(spy.call_args.kwargs["collector"], self.col)

    def test_rejected_push_no_ingest(self):
        self.icp.set_param("td.telemetry.push_rate_per_min", "1")
        with self.spy() as spy:
            self.post("push", {"readings": []})
            spy.reset_mock()
            self.assertEqual(self.post("push", {"readings": []})[0], 429)
            self.icp.set_param("td.telemetry.read_enabled", "False")
            self.assertEqual(self.post("push", {"readings": []})[0], 423)
        self.assertEqual(spy.call_count, 0)


@tagged(*TAGS)
class TestCommandPayload(CommandCase):
    def test_payload_create_and_validate(self):
        payload = {"method": "StoreAndStart", "job": "WO00013", "qty": 14}
        cmd = self.command(payload=payload)
        self.assertEqual((cmd.state, cmd.payload), ("queued", payload))
        self.assertEqual(json.loads(cmd.payload_text), payload)
        for bad in ([1], "x", {"k": "x" * 70000}):
            with self.assertRaises(ValidationError), self.env.cr.savepoint():
                self.command(payload=bad)

    def test_commands_payload_key(self):
        payload = {"method": "StoreAndStart", "job": "WO00013", "qty": 14}
        self.command(payload=payload)
        self.command()
        _s, res, _h = self.get("commands")
        self.assertEqual([c["payload"] for c in res["commands"]], [payload, None])

    def test_result_data_saved(self):
        cmd = self.command(payload={"method": "m"})
        cmd.state = "sent"
        item = {"id": cmd.id, "state": "done", "result": '{"ReturnStatus": 0}', "data": {"ReturnStatus": 0}}
        self.post("commands/result", {"results": [item]})
        self.reload()
        self.assertEqual((cmd.state, cmd.result_data), ("done", {"ReturnStatus": 0}))

    def test_result_data_bad_schema(self):
        cmd = self.command()
        cmd.state = "sent"
        for data in ("x", {"k": "x" * 70000}):
            status, res, _h = self.post("commands/result", {"results": [{"id": cmd.id, "state": "done", "data": data}]})
            self.assertEqual((status, res["error"]["code"]), (400, "bad_schema"))
        self.reload()
        self.assertEqual(cmd.state, "sent")
        self.assertEqual(Manifest.for_addon("td_telemetry")["version"], "19.0.1.1.0")


@tagged(*TAGS, "f3d_perf")
class TestPushPerf(ApiCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Signal = cls.env["td.signal"]
        cls.perf = [
            Signal.create(
                {
                    "code": "equipment/PERF-T/p%02d" % i,
                    "name": "perf %d" % i,
                    "kind": "gauge",
                    "unit": "бар",
                    "source_id": cls.src_mb.id,
                    "address": {"fc": 3, "addr": 4000 + i, "type": "u16"},
                    "origin": "manual",
                    "store_period_s": 0,
                }
            )
            for i in range(38)
        ]
        cls.sigs = cls.perf

    def batch(self, n, offset):
        base = self.now(-3000)
        return [
            {
                "code": self.sigs[i % len(self.sigs)].code,
                "ts": iso(base + timedelta(seconds=offset + i // 38)),
                "value": 5.0 + (i % 7) * 0.1,
            }
            for i in range(n)
        ]

    def test_push_1000_under_1s(self):
        durations = []
        for run in range(5):
            body = {"collector": "COL-T", "readings": self.batch(1000, run * 100)}
            self.icp.set_param("td.telemetry.push_rate_per_min", "1000")
            t0 = time.perf_counter()
            status, res, _h = self.post("push", body)
            durations.append(time.perf_counter() - t0)
            self.assertEqual(status, 200)
            self.assertEqual(res["rejected"], [])
        self.assertLess(sum(durations) / 5, 1.0)

    def test_no_n_plus_one(self):
        self.push(self.batch(38, 0))  # прогрів: статуси стабільні
        self.push(self.batch(100, 500))  # прогрів кешів ORM
        self.env.invalidate_all()
        counts = {}
        for n, offset in ((100, 1000), (1000, 2000), (100, 3000), (1000, 4000)):
            before = self.cr.sql_log_count
            self.push(self.batch(n, offset))
            counts.setdefault(n, []).append(self.cr.sql_log_count - before)
        self.assertLessEqual(abs(counts[1000][-1] - counts[100][-1]), 5, counts)
