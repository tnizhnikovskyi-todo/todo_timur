from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from ..tools import address as address_tools
from .common import MQTT_PARAMS, F3DTelemetryCase

TAGS = ("post_install", "-at_install", "f3d", "f3d_telemetry")

VALID_PARAMS = {
    "modbus_tcp": {"host": "iot-sim", "port": 502, "unit": 70, "timeout_s": 3, "retries": 2, "max_block": 100},
    "mqtt": MQTT_PARAMS,
    "http_push": {
        "routes": ["lpr"],
        "allow_ips": ["iot-sim"],
        "token_ref": "F3D_HTTP_PUSH_TOKEN_LPR",
        "secret_ref": "F3D_HTTP_PUSH_SECRET_LPR",
    },
    "bacnet_ip": {
        "host": "iot-sim",
        "port": 47808,
        "device": 140,
        "network": 2,
        "timeout_s": 5,
        "rpm": True,
        "rpm_max": 50,
        "cov_lifetime_s": 300,
    },
    "opcua": {"endpoint": "opc.tcp://iot-sim:4840/f3d/", "security_mode": "None"},
    "helvarnet": {"host": "iot-sim", "port": 50000, "protocol": "tcp"},
    "sics": {"host": "iot-sim", "port": 4001},
    "rest_vendor": {"base_url": "http://iot-sim:8082", "auth": "api_key", "key_ref": "F3D_WOODSTORE_KEY"},
}
MB = VALID_PARAMS["modbus_tcp"]
INVALID_PARAMS = [
    ("modbus_tcp", {"port": 502}, "host"),
    ("modbus_tcp", {**MB, "port": 0}, "port"),
    ("modbus_tcp", {**MB, "port": 65536}, "port"),
    ("modbus_tcp", {**MB, "unit": 0}, "unit"),
    ("modbus_tcp", {**MB, "unit": 248}, "unit"),
    ("mqtt", {**MQTT_PARAMS, "topics": []}, "topics"),
    ("mqtt", {**MQTT_PARAMS, "topics": ["f3d/#/x"]}, "topics"),
    ("mqtt", {**MQTT_PARAMS, "password": "x"}, "секрети не зберігаються в Odoo — використайте password_ref"),
    ("http_push", {"routes": ["Lpr"]}, "routes"),
    ("bacnet_ip", {"host": "iot-sim", "device": 4194303}, "device"),
    ("opcua", {"endpoint": "http://x"}, "endpoint"),
    ("rest_vendor", {"base_url": "ftp://x"}, "base_url"),
    ("modbus_tcp", [1], "параметри мають бути об"),
]


def _msg(ctx):
    return ctx.exception.args[0]


class SourceCase(F3DTelemetryCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_telemetry_fixtures()

    def new_source(self, code, typ="modbus_tcp", params=None, user=None, **kw):
        Src = self.env["td.source"]
        if user:
            Src = Src.with_user(user)
        vals = {
            "code": code,
            "name": code,
            "type": typ,
            "collector_id": self.col.id,
            "params": VALID_PARAMS[typ] if params is None else params,
            **kw,
        }
        return Src.create(vals)


@tagged(*TAGS)
class TestParams(SourceCase):
    def test_valid_examples(self):
        for typ in VALID_PARAMS:
            with self.subTest(type=typ):
                src = self.new_source("EX-%s" % typ.upper().replace("_", "-"), typ, user=self.user_manager)
                self.assertEqual((src.state, src.read_enabled, src.write_enabled), ("unknown", True, False))

    def test_invalid_params(self):
        for i, (typ, params, needle) in enumerate(INVALID_PARAMS):
            with self.subTest(type=typ, needle=needle, i=i), self.assertRaises(ValidationError) as ctx:
                self.new_source("BAD-%s" % i, typ, params, user=self.user_manager)
            msg = _msg(ctx)
            self.assertTrue(msg.startswith("Параметри джерела BAD-%s:" % i), msg)
            self.assertIn(needle, msg)

    def test_code_format(self):
        for code in ("MB-U70.A", "HTTP-PUSH-T"):
            with self.subTest(code=code):
                typ = "http_push" if code.startswith("HTTP") else "modbus_tcp"
                self.assertTrue(self.new_source(code, typ, user=self.user_manager))
        with self.assertRaises(ValidationError) as ctx:
            self.new_source("mb-u70", user=self.user_manager)
        self.assertIn("Код джерела: великі латинські літери, цифри, дефіс, крапка.", _msg(ctx))


@tagged(*TAGS)
class TestSourceToggle(SourceCase):
    def _prepare(self):
        now = fields.Datetime.now()
        self.set_sql(self.src_mb, state="online")
        self.set_sql(self.sig_press, status="ok", last_ts=now)
        self.set_sql(self.col, config_etag="x")

    def test_disable_marks_stale(self):
        self._prepare()
        self.src_mb.with_user(self.user_manager).write({"read_enabled": False})
        self.assertEqual(self.src_mb.state, "disabled")
        self.assertEqual(self.sig_press.status, "stale")
        self.assertIn("Немає даних: disabled", self.sig_press.message_ids[0].body)
        self.assertFalse(self.col.config_etag)

    def test_status_keeps_disabled(self):
        self._prepare()
        self.src_mb.write({"read_enabled": False})
        self.src_mb._apply_status({"code": "MB-T-U70", "state": "online"})
        self.assertEqual(self.src_mb.state, "disabled")

    def test_reenable_unknown(self):
        self._prepare()
        self.src_mb.write({"read_enabled": False})
        self.src_mb.write({"read_enabled": True})
        self.assertEqual(self.src_mb.state, "unknown")
        self.assertEqual(self.sig_press.status, "stale")


@tagged(*TAGS)
class TestReadOnly(SourceCase):
    def test_source_write_forbidden(self):
        with self.assertRaises(ValidationError) as ctx:
            self.src_bac_ro.write({"write_enabled": True})
        self.assertIn("Джерело лише для читання (пожежна панель): запис заборонено.", _msg(ctx))

    def test_signal_write_forbidden(self):
        with self.assertRaises(ValidationError) as ctx:
            self.sig_fire.write({"write_enabled": True})
        self.assertIn("Запис у пожежну панель заборонено (D-07).", _msg(ctx))

    def test_type_change_with_signals(self):
        with self.assertRaises(ValidationError) as ctx:
            self.src_mb.write({"type": "mqtt"})
        self.assertIn("Тип джерела з сигналами змінити не можна — створіть нове джерело.", _msg(ctx))

    def test_type_change_empty(self):
        src = self.new_source("EMPTY-T")
        src.write({"type": "mqtt", "params": MQTT_PARAMS})
        self.assertEqual(src.type, "mqtt")


@tagged(*TAGS)
class TestApplyStatus(SourceCase):
    def _item(self, error):
        return {
            "code": "BAC-T-105",
            "state": "error",
            "last_ok": "2026-10-14T05:50:10Z",
            "error": error,
            "stats": {"polls": 120, "errors": 60},
        }

    def test_error_masked(self):
        self.set_sql(self.src_bac, state="online")
        self.set_sql(self.sig_rv, status="ok", last_ts=fields.Datetime.now())
        self.src_bac._apply_status(
            self._item("Who-Is: device 105 not found; url=http://u:password=Secr3t@x token=abc Bearer xyz")
        )
        src = self.src_bac
        self.assertEqual(src.state, "error")
        self.assertEqual(src.last_ok, datetime(2026, 10, 14, 5, 50, 10))
        for secret in ("Secr3t", "abc", "xyz"):
            self.assertNotIn(secret, src.last_error)
        for masked in ("password=***", "token=***", "Bearer ***"):
            self.assertIn(masked, src.last_error)
        self.assertEqual(src.error_count, 60)
        self.assertEqual(src.stats, {"polls": 120, "errors": 60})

    def test_unknown_state_keeps_last_error(self):  # T-5
        self.src_bac._apply_status(self._item("boom"))
        self.assertEqual(self.src_bac.last_error, "boom")
        self.src_bac._apply_status({"code": "BAC-T-105", "state": "bogus"})
        self.assertEqual(self.src_bac.last_error, "boom")
        self.src_bac._apply_status({"code": "BAC-T-105", "state": "online"})
        self.assertFalse(self.src_bac.last_error)

    def test_truncated_512(self):
        self.src_bac._apply_status(self._item("x" * 600))
        self.assertEqual(len(self.src_bac.last_error), 512)

    def test_signals_stale(self):
        self.set_sql(self.sig_rv, status="ok", last_ts=fields.Datetime.now())
        self.src_bac._apply_status(self._item("boom"))
        self.assertEqual(self.sig_rv.status, "stale")


@tagged(*TAGS)
class TestLocalSource(SourceCase):
    def _patch(self):
        return patch.object(type(self.env["td.source"]), "_f3d_local_types", lambda self: ["rest_vendor"])

    def _local(self):
        return (
            self.env["td.source"]
            .with_user(self.user_manager)
            .create(
                {
                    "code": "LOCAL-T",
                    "name": "LOCAL-T",
                    "type": "rest_vendor",
                    "params": {},
                    "module": "genset",
                    "period_s_default": 60,
                }
            )
        )

    def _local_signal(self, src, **kw):
        return self.env["td.signal"].create(
            {
                "code": "infra/genset/GENSET-T/fuel_pct",
                "name": "Паливо",
                "source_id": src.id,
                "address": "fuel_pct",
                "period_s": 100,
                **kw,
            }
        )

    def test_default_no_local_types(self):
        # базова реалізація (telemetry) повертає []; модулі-розширення (td_genset, td_energy…) дописують
        # свої типи через super(), тому перевіряємо саме її, а не результат усього ланцюжка
        Source = self.env["td.source"]
        base_impl = next(vars(c)["_f3d_local_types"] for c in reversed(type(Source).__mro__)
                         if "_f3d_local_types" in vars(c))
        self.assertEqual(base_impl(Source), [])
        self.assertEqual(address_tools.validate_params("td_genset", {}), ["type: невідомий тип джерела «td_genset»"])

    def test_validate_params_local(self):
        self.assertEqual(address_tools.validate_params("td_genset", {}, local_types=("td_genset",)), [])
        errors = address_tools.validate_params("td_genset", {"password": "x"}, local_types=("td_genset",))
        self.assertTrue(errors and "password" in errors[0])

    def test_local_without_collector(self):
        with self._patch():
            src = self._local()
            self.assertTrue(src.is_local)
            sig = self._local_signal(src)
            self.assertEqual(sig.address, "fuel_pct")

    def test_non_local_requires_collector(self):
        with self.assertRaises(ValidationError) as ctx:
            self._local()
        msg = _msg(ctx)
        self.assertTrue("вкажіть колектор" in msg or "base_url" in msg, msg)
        with self.assertRaises(ValidationError) as ctx:
            self.env["td.source"].create(
                {"code": "LOCAL-T", "name": "x", "type": "rest_vendor", "params": VALID_PARAMS["rest_vendor"]}
            )
        self.assertIn("Джерело LOCAL-T: вкажіть колектор.", _msg(ctx))

    def test_local_excluded_from_config_and_stale(self):
        with self._patch(), freeze_time("2026-10-14 08:00:00"):
            src = self._local()
            sig = self._local_signal(src)
            now = fields.Datetime.now()
            self.set_sql(sig, status="ok", last_ts=now - timedelta(hours=2))
            self.env["td.signal"]._cron_stale()
            self.assertEqual(sig.status, "ok")
            self.assertNotIn("LOCAL-T", [s["code"] for s in self.col._config_payload()["sources"]])

    def test_local_ingest_module_only(self):
        with self._patch(), freeze_time("2026-10-14 08:00:00"):
            sig = self._local_signal(self._local())
            res = self.env["td.signal"]._f3d_ingest([self.rd(sig, 75)], src="module")
            self.assertEqual(res["accepted"], 1)
            self.assertEqual(sig.last_value, 75)
            self.assertEqual(self.env["td.reading"].search([("signal_id", "=", sig.id)]).src, "module")
            res = self.push([self.rd(sig, 76, at=10)])
            self.assertEqual(res["rejected"][0]["reason"], "foreign_signal")

    def test_local_mark_stale_once(self):
        with self._patch():
            sig = self._local_signal(self._local())
            self.set_sql(sig, status="ok")
            before = len(sig.message_ids)
            sig._mark_stale("td_genset: немає свіжих даних")
            sig._mark_stale("td_genset: немає свіжих даних")
            self.assertEqual(sig.status, "stale")
            self.assertEqual(len(sig.message_ids), before + 1)

    def test_local_no_commands(self):
        with self._patch():
            src = self._local()
            sig = self._local_signal(src)
            self.set_sql(sig, write_enabled=True)
            self.set_sql(src, write_enabled=True)
            self.env["ir.config_parameter"].sudo().set_param("td.telemetry.write_enabled", "True")
            with self.assertRaises(UserError) as ctx:
                self.env["td.command"].with_user(self.user_manager).create({"signal_id": sig.id, "value": 1})
            self.assertIn("Джерело LOCAL-T без колектора: запис у пристрій неможливий.", _msg(ctx))

    def test_local_read_disabled(self):
        with self._patch():
            src = self._local()
            src.write({"read_enabled": False})
            self.assertEqual(src.state, "disabled")
