import hashlib
from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time
from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import F3DTelemetryCase

TAGS = ("post_install", "-at_install", "f3d", "f3d_telemetry")
NOW = "2026-10-14 08:00:00"


def _msg(ctx):
    return ctx.exception.args[0]


@tagged(*TAGS)
class TestToken(F3DTelemetryCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_telemetry_fixtures()

    def _generate(self):
        return self.col.with_user(self.user_admin).action_generate_token()

    def test_generate_token(self):
        res = self._generate()
        self.assertEqual(res["type"], "ir.actions.act_window")
        self.assertEqual(res["res_model"], "f3d.collector.token.wizard")
        self.assertEqual(res["target"], "new")
        token = res["context"]["default_token"]
        self.assertGreaterEqual(len(token), 43)
        col = self.col.with_user(self.user_admin)
        self.assertEqual(col.token_hash, hashlib.sha256(token.encode()).hexdigest())
        self.assertEqual(col.token_hint, token[-4:])
        self.assertTrue(col.token_set_at)
        bodies = " ".join(self.col.message_ids.mapped("body"))
        self.assertIn("Видано новий токен (…%s)" % token[-4:], bodies)
        self.assertNotIn(token, bodies)
        self.assertEqual(self.env["f3d.collector"]._authenticate(token), self.col)

    def test_generate_requires_admin(self):
        with self.assertRaises(AccessError):
            self.col.with_user(self.user_manager).action_generate_token()

    def test_authenticate_cases(self):
        token = self._generate()["context"]["default_token"]
        Col = self.env["f3d.collector"]
        for case in (token + "x", "", "a" * 257, None):
            with self.subTest(case=case):
                self.assertFalse(Col._authenticate(case))

    def test_inactive_collector(self):
        token = self._generate()["context"]["default_token"]
        self.col.active = False
        self.assertFalse(self.env["f3d.collector"]._authenticate(token))

    def test_regenerate_invalidates(self):
        old = self._generate()["context"]["default_token"]
        new = self._generate()["context"]["default_token"]
        Col = self.env["f3d.collector"]
        self.assertFalse(Col._authenticate(old))
        self.assertEqual(Col._authenticate(new), self.col)

    def test_revoke(self):
        token = self._generate()["context"]["default_token"]
        self.col.with_user(self.user_admin).action_revoke_token()
        col = self.col.with_user(self.user_admin)
        self.assertFalse(col.token_hash)
        self.assertFalse(col.token_hint)
        self.assertFalse(self.env["f3d.collector"]._authenticate(token))
        self.assertIn("Токен відкликано", " ".join(self.col.message_ids.mapped("body")))


@tagged(*TAGS)
class TestCollectorConstraints(F3DTelemetryCase):
    def _create(self, code, **kw):
        return self.env["f3d.collector"].create({"code": code, "name": code, **kw})

    def test_code_valid(self):
        for code in ("COL-MAIN-T", "C1", "COL-2-YARD"):
            with self.subTest(code=code):
                self.assertEqual(self._create(code).code, code)

    def test_code_invalid(self):
        for code in ("col-main", "COL_MAIN", "-COL", "COL MAIN", "A" * 33):
            with self.subTest(code=code), self.assertRaises(ValidationError) as ctx:
                self._create(code)
            self.assertIn("Код колектора: великі латинські літери, цифри, дефіс (напр. COL-MAIN).", _msg(ctx))

    def test_code_unique(self):
        self._create("COL-MAIN-T")
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.cr.savepoint():
            self._create("COL-MAIN-T")

    def test_interval_checks(self):
        col = self._create("COL-INT-T")
        for field, value in (
            ("push_max", 2001),
            ("push_interval_s", 0),
            ("push_interval_s", 61),
            ("status_interval_s", 9),
            ("config_poll_s", 9),
        ):
            with self.subTest(field=field, value=value):
                with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.cr.savepoint():
                    col.write({field: value})

    def test_defaults(self):
        col = self._create("COL-DEF-T")
        self.assertEqual(
            (col.state, col.push_interval_s, col.push_max, col.status_interval_s, col.config_poll_s),
            ("never", 5, 1000, 60, 60),
        )


@tagged(*TAGS)
class TestCollectorOffline(F3DTelemetryCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_telemetry_fixtures()

    def _prepare(self, age):
        now = fields.Datetime.now()
        self.set_sql(self.col, state="online", last_seen=now - timedelta(seconds=age))
        self.set_sql(self.col2, state="online", last_seen=now)
        self.set_sql(self.src_mb, state="online")
        self.set_sql(self.src_mqtt, state="error")
        self.set_sql(self.src_other, state="online")
        self.set_sql(self.sig_press, status="ok", last_ts=now)
        self.set_sql(self.sig_foreign, status="ok", last_ts=now)

    def test_offline_after_3_intervals(self):
        with freeze_time(NOW):
            self._prepare(181)
            self.env["f3d.signal"]._cron_stale()
            self.assertEqual(self.col.state, "offline")
            self.assertEqual((self.src_mb.state, self.src_mqtt.state), ("offline", "offline"))
            self.assertEqual(self.sig_press.status, "stale")
            self.assertEqual(self.col2.state, "online")
            self.assertEqual(self.src_other.state, "online")
            self.assertEqual(self.sig_foreign.status, "ok")

    def test_online_within_window(self):
        with freeze_time(NOW):
            self._prepare(179)
            self.env["f3d.signal"]._cron_stale()
            self.assertEqual(self.col.state, "online")
            self.assertEqual(self.sig_press.status, "ok")


@tagged(*TAGS)
class TestConfigPayload(F3DTelemetryCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_telemetry_fixtures()

    def test_payload_and_etag(self):
        body = self.col._config_payload()
        codes = [s["code"] for s in body["sources"]]
        self.assertIn("MB-T-U70", codes)
        self.assertNotIn("MB-T-OLD", codes)
        self.assertNotIn("MB-T2", codes)
        mb = next(s for s in body["sources"] if s["code"] == "MB-T-U70")
        sig_codes = [s["code"] for s in mb["signals"]]
        self.assertIn(self.sig_press.code, sig_codes)
        self.assertNotIn(self.sig_noaddr.code, sig_codes)
        self.assertNotIn(self.sig_old.code, sig_codes)
        self.assertEqual(len(body["etag"]), 64)
        self.assertEqual(self.col.config_etag, body["etag"])
        self.assertEqual(self.col._config_payload()["etag"], body["etag"])
        self.assertEqual(self.col._etag(), body["etag"])
        self.sig_press.write({"period_s": 20})
        self.assertFalse(self.col.config_etag)
        self.assertNotEqual(self.col._config_payload()["etag"], body["etag"])
        self.assertTrue(body["read_enabled"])
        self.assertFalse(body["write_enabled"])

    def test_rate_check(self):
        with freeze_time(NOW):
            for _i in range(60):
                self.assertTrue(self.col._rate_check())
            self.assertFalse(self.col._rate_check())
        with freeze_time("2026-10-14 08:01:01"):
            self.assertTrue(self.col._rate_check())


@tagged(*TAGS)
class TestCollectorTouchThrottle(F3DTelemetryCase):
    """DEC-19: `_touch` не пише рядок колектора на кожен запит (спільний рядок → deadlock/serialization)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_telemetry_fixtures()

    def _at(self, sec):
        return freeze_time(fields.Datetime.to_datetime(NOW) + timedelta(seconds=sec))

    def _touch(self, sec, ip="10.0.0.1", **kw):
        """Повертає кількість `write` на колекторі за виклик `_touch`."""
        writes = []
        orig = self.registry["f3d.collector"].write

        def spy(rec, vals):
            writes.append(set(vals))
            return orig(rec, vals)

        with self._at(sec), patch.object(self.registry["f3d.collector"], "write", spy):
            self.col._touch(ip, **kw)
        return writes

    def test_first_touch_writes_once(self):
        writes = self._touch(0, version="1.2", pushed=True)
        self.assertEqual(len(writes), 1)
        self.assertEqual(self.col.state, "online")
        self.assertEqual((self.col.last_ip, self.col.version), ("10.0.0.1", "1.2"))
        self.assertEqual(self.col.last_seen, fields.Datetime.to_datetime(NOW))
        self.assertEqual(self.col.last_push_at, fields.Datetime.to_datetime(NOW))

    def test_touch_within_interval_skipped(self):
        self._touch(0, pushed=True)
        for sec in (1, 10, 29):
            self.assertEqual(self._touch(sec, pushed=True), [], "sec=%s" % sec)
        self.assertEqual(self.col.last_seen, fields.Datetime.to_datetime(NOW))
        self.assertEqual(self.col.last_push_at, fields.Datetime.to_datetime(NOW))

    def test_touch_after_interval_written(self):
        self._touch(0)
        self.assertEqual(len(self._touch(30, pushed=True)), 1)
        later = fields.Datetime.to_datetime(NOW) + timedelta(seconds=30)
        self.assertEqual((self.col.last_seen, self.col.last_push_at), (later, later))

    def test_changes_written_immediately(self):
        self._touch(0, version="1.0")
        self.assertEqual(len(self._touch(1, ip="10.0.0.2")), 1)  # IP
        self.assertEqual(len(self._touch(2, ip="10.0.0.2", version="1.1")), 1)  # версія
        self.assertEqual(self._touch(3, ip="10.0.0.2", version="1.1"), [])
        self.env.flush_all()
        self.set_sql(self.col, state="offline")  # крон `_cron_offline`
        self.assertEqual(len(self._touch(4, ip="10.0.0.2", version="1.1")), 1)
        self.assertEqual(self.col.state, "online")

    def test_interval_capped_by_status_interval(self):
        """Офлайн-крон = 3·status_interval_s: при status_interval_s = 10 інтервал запису — 10 с, а не 30."""
        self.col.status_interval_s = 10
        self._touch(0)
        self.assertEqual(self._touch(9), [])
        self.assertEqual(len(self._touch(10)), 1)

    def test_interval_parameter(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("factory3d.telemetry.touch_interval_s", "0")
        self._touch(0)
        self.assertEqual(len(self._touch(1)), 1)
        icp.set_param("factory3d.telemetry.touch_interval_s", "garbage")
        self.assertEqual(self._touch(2), [])  # некоректне значення → 30 с
