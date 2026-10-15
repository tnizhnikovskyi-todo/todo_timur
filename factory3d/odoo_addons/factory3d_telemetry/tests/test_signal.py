from datetime import datetime

from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import F3DTelemetryCase

TAGS = ("post_install", "-at_install", "f3d", "f3d_telemetry")


def _msg(ctx):
    return ctx.exception.args[0]


class SignalCase(F3DTelemetryCase):
    _counter = 0

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_telemetry_fixtures()

    def new_signal(self, source=None, address=None, user=None, code=None, **kw):
        type(self)._counter += 1
        Sig = self.env["f3d.signal"]
        if user:
            Sig = Sig.with_user(user)
        vals = {"code": code or "equipment/NEW-T/s%s" % self._counter, "name": "Новий", "kind": "gauge", **kw}
        if source:
            vals["source_id"] = source.id
        if address is not None:
            vals["address"] = address
        return Sig.create(vals)


@tagged(*TAGS)
class TestOrigin(SignalCase):
    def test_origin_selection(self):
        sel = self.env["f3d.signal"].fields_get(["origin"])["origin"]["selection"]
        self.assertEqual(
            sel,
            [
                ("sim_data", "Рівень 0 (макет)"),
                ("catalog", "Каталог емулятора"),
                ("manual", "Вручну"),
                ("module", "Дані модуля"),
            ],
        )
        self.assertEqual(self.new_signal(user=self.user_manager).origin, "manual")

    def test_origin_module_saved(self):
        self.assertEqual(self.new_signal(user=self.user_manager, origin="module").origin, "module")


@tagged(*TAGS)
class TestSicsSchema(SignalCase):
    def _sics(self, params):
        return self.env["f3d.source"].create(
            {"code": "SICS-T", "name": "SICS-T", "type": "sics", "collector_id": self.col.id, "params": params}
        )

    def test_sics_params_valid(self):
        self._sics(
            {
                "host": "iot-sim",
                "port": 4001,
                "mode": "stream",
                "period_s": 1,
                "timeout_s": 5,
                "unit": "kg",
                "dialect": "mt_sics",
                "reset_on_connect": True,
            }
        )
        self.assertTrue(self.env["f3d.source"].search([("code", "=", "SICS-T")]))

    def test_sics_minimal_valid(self):
        self.assertTrue(self._sics({"host": "iot-sim"}))

    def test_sics_params_invalid(self):
        for params in (
            {"host": "iot-sim", "mode": "push"},
            {"host": "iot-sim", "timeout_s": 31},
            {"host": "iot-sim", "unit": "oz"},
            {"host": "x", "foo": 1},
        ):
            with self.subTest(params=params), self.assertRaises(ValidationError) as ctx:
                self.env["f3d.source"].create(
                    {"code": "SICS-T", "name": "x", "type": "sics", "collector_id": self.col.id, "params": params}
                )
            msg = _msg(ctx)
            self.assertIn("Параметри джерела SICS-T:", msg)
        self.assertIn("foo: невідомий ключ (схема sics не допускає додаткових)", msg)

    def test_sics_address_valid(self):
        src = self._sics({"host": "iot-sim"})
        for addr in (
            {"field": "weight"},
            {"field": "stable", "cmd": "SI"},
            {"field": "weight", "write": {"cmd": "Z"}},
            {"field": "weight", "scale": 0.001},
        ):
            with self.subTest(addr=addr):
                self.assertTrue(self.new_signal(src, addr))

    def test_sics_address_invalid(self):
        src = self._sics({"host": "iot-sim"})
        for addr in (
            {"cmd": "SI"},
            {"field": "unit"},
            {"field": "weight", "cmd": "SIR"},
            {"field": "weight", "write": {"cmd": "TA"}},
            {"field": "weight", "x": 1},
        ):
            with self.subTest(addr=addr), self.assertRaises(ValidationError) as ctx:
                self.new_signal(src, addr)
            self.assertIn("Адреса сигналу", _msg(ctx))


@tagged(*TAGS)
class TestCode(SignalCase):
    def test_valid_codes(self):
        for code in (
            "equipment/FL-C1-T/battery",
            "ventilation/units/RV-05-T/filter_dp_pa",
            "infra/WATER-T/m3_total",
            "energy/consumers/SAW-T/p_now",
        ):
            with self.subTest(code=code):
                self.assertTrue(self.new_signal(user=self.user_manager, code=code + ".new"))

    def test_invalid_codes(self):
        self.cr.execute("SELECT count(*) FROM f3d_signal")
        before = self.cr.fetchone()[0]
        for code in (
            "Equipment/FL-T/x",
            "equipment",
            "energy//x",
            "equipment/FL T/x",
            "equipment/FL-T/",
            "equipment/FL-T/x;DROP TABLE f3d_signal",
            "equipment/FL-T/x'--",
            "equipment/" + "a" * 119,
        ):
            with self.subTest(code=code), self.assertRaises(ValidationError) as ctx:
                self.new_signal(user=self.user_manager, code=code)
            self.assertIn("Код сигналу", _msg(ctx))
        self.cr.execute("SELECT count(*) FROM f3d_signal")
        self.assertEqual(self.cr.fetchone()[0], before)

    def test_unique_code(self):
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.cr.savepoint():
            self.new_signal(code=self.sig_press.code)


@tagged(*TAGS)
class TestAddress(SignalCase):
    def _bad(self, src, addr, needle):
        with self.subTest(addr=addr), self.assertRaises(ValidationError) as ctx:
            self.new_signal(src, addr)
        msg = _msg(ctx)
        self.assertIn("Адреса сигналу", msg)
        self.assertIn(needle, msg)

    def _ok(self, src, addr):
        with self.subTest(addr=addr):
            sig = self.new_signal(src, addr)
            self.assertEqual(sig.address, addr)

    def test_modbus(self):
        base = {"fc": 3, "addr": 3001}
        self._ok(self.src_mb, {"fc": 3, "addr": 3001, "type": "u16", "scale": 0.001})
        self._ok(self.src_mb, {**base, "write": {"fc": 5, "addr": 16, "pulse_ms": 1500}})
        self._ok(self.src_mb, {**base, "write": {"fc": 5, "addr": 20}})
        for addr, needle in (
            ({"fc": 7, "addr": 1}, "fc"),
            ({"fc": 3, "addr": -1}, "addr"),
            ({"fc": 3, "addr": 65536}, "addr"),
            ({**base, "type": "u128"}, "type"),
            ({**base, "wordorder": "middle"}, "wordorder"),
            ({**base, "count": 0}, "count"),
            ({**base, "agg": "median"}, "agg"),
            ({"fc": 3, "states": [{"addr": 0, "eq": 1}]}, "states[0].text"),
            ({**base, "write": {"fc": 5, "addr": 16, "pulse_ms": 99}}, "pulse_ms"),
            ({**base, "write": {"fc": 5, "addr": 16, "pulse_ms": 10001}}, "pulse_ms"),
            ({**base, "write": {"fc": 16, "addr": 16, "pulse_ms": 1500}}, "pulse_ms"),
        ):
            self._bad(self.src_mb, addr, needle)

    def test_mqtt(self):
        self._ok(self.src_mqtt, {"topic": "f3d/mobile/FL-C1-T/telemetry", "path": "$.battery_pct"})
        for addr, needle in (
            ({"topic": "f3d/x", "path": "$.a;drop"}, "path"),
            ({"topic": "f3d/x", "path": "battery_pct"}, "path"),
            ({"topic": "f3d/x", "path": "$..x"}, "path"),
            ({"topic": "f3d/mobile/+/telemetry", "path": "$.a"}, "topic"),
        ):
            self._bad(self.src_mqtt, addr, needle)

    def test_bacnet(self):
        for addr in (
            {"object": "AI", "instance": 4},
            {"object": "analog-input", "instance": 4},
            {"object": "PIV", "instance": 1},
            {"object": "positive-integer-value", "instance": 1},
        ):
            self._ok(self.src_bac, addr)
        for addr, needle in (
            ({"object": "XX", "instance": 1}, "object"),
            ({"object": "AI", "instance": 4194303}, "instance"),
            ({"object": "AI", "instance": 1, "priority": 0}, "priority"),
            ({"object": "AI", "instance": 1, "priority": 17}, "priority"),
        ):
            self._bad(self.src_bac, addr, needle)

    def test_http_push(self):
        self._bad(self.src_http, {"route": "Lpr", "path": "$.a"}, "route")
        self._bad(self.src_http, {"route": "lpr", "path": "$.a", "match": [1]}, "match")

    def test_no_source_not_validated(self):
        self.assertEqual(self.new_signal(None, {"any": 1}).address, {"any": 1})

    def test_not_object(self):
        self._bad(self.src_mb, [1, 2], "адреса має бути об'єктом JSON")

    def test_address_text(self):
        with self.assertRaises(ValidationError):
            self.new_signal(self.src_mb, address_text="{bad")
        sig = self.new_signal(self.src_mb, address_text='{"fc": 3, "addr": 5}')
        self.assertEqual(sig.address, {"fc": 3, "addr": 5})


@tagged(*TAGS)
class TestThresholdConstraints(SignalCase):
    def _bad(self, needle, **kw):
        with self.subTest(kw=kw), self.assertRaises(ValidationError) as ctx:
            self.new_signal(**kw)
        self.assertIn(needle, _msg(ctx))

    def test_low_order(self):
        self._bad(
            "«Тривога, нижче» має бути ≤ «Увага, нижче».",
            warn_low_on=True,
            alarm_low_on=True,
            warn_low=15,
            alarm_low=20,
        )

    def test_high_order(self):
        with self.assertRaises(ValidationError):
            self.new_signal(warn_high_on=True, alarm_high_on=True, warn_high=245, alarm_high=240)

    def test_low_lt_high(self):
        self._bad(
            "«Тривога, нижче» має бути < «Тривога, вище».",
            alarm_low_on=True,
            alarm_high_on=True,
            alarm_low=10,
            alarm_high=10,
        )

    def test_state_numeric(self):
        self._bad("Для стану задайте «Стани-тривоги», а не числові пороги.", kind="state", alarm_high_on=True)

    def test_derive_requires_counter(self):
        self._bad("Похідна «за годину» потребує лічильника-джерела.", derive_rule="rate_h")
        self._bad(
            "Похідна «за годину» потребує лічильника-джерела.", derive_rule="rate_h", derived_from_id=self.sig_press.id
        )

    def test_checks(self):
        for kw in ({"period_s": 0}, {"hysteresis": -1}):
            with (
                self.subTest(kw=kw),
                mute_logger("odoo.sql_db"),
                self.assertRaises(IntegrityError),
                self.cr.savepoint(),
            ):
                self.new_signal(**kw)

    def test_store_period_default(self):
        self.env["ir.config_parameter"].sudo().set_param("factory3d.telemetry.default_store_period_s", "120")
        self.assertEqual(self.new_signal().store_period_s, 120)


@tagged(*TAGS)
class TestWrite(SignalCase):
    def test_threshold_change_recomputes(self):
        now = fields.Datetime.now()
        req = self.env["maintenance.request"].create({"name": "Заявка", "equipment_id": self.eq_rv.id})
        self.set_sql(self.sig_rv, last_value=285, status="alarm", last_ts=now, maintenance_request_id=req.id)
        self.sig_rv.with_user(self.user_manager).write({"alarm_high": 300})
        self.assertEqual(self.sig_rv.status, "ok")
        self.assertGreaterEqual(self.sig_rv.status_since, now)
        self.assertIn("Стан:", self.sig_rv.message_ids[0].body)
        self.assertEqual(self.sig_rv.maintenance_request_id, req)

    def test_config_change_resets_etag(self):
        self.set_sql(self.col, config_etag="x")
        self.sig_rv.write({"period_s": 20})
        self.assertFalse(self.col.config_etag)

    def test_name_change_keeps_etag(self):
        self.set_sql(self.col, config_etag="x")
        self.sig_rv.write({"name": "Інша назва"})
        self.assertEqual(self.col.config_etag, "x")


@tagged(*TAGS)
class TestUnlink(SignalCase):
    def test_meter_signal_protected(self):
        self.eq_comp.write({"f3d_meter_signal_id": self.sig_hours.id, "f3d_meter_interval": 2000.0})
        with self.assertRaises(UserError) as ctx:
            self.sig_hours.unlink()
        self.assertIn("Сигнал використовується для ТО за лічильником на Компресорна станція.", _msg(ctx))

    def test_cascade_readings(self):
        sig = self.new_signal(self.src_mb, {"fc": 3, "addr": 9})
        Reading = self.env["f3d.reading"]
        for k in range(3):
            Reading.create({"signal_id": sig.id, "ts": datetime(2026, 10, 14, 6, k), "value": k})
        self.env["f3d.reading.hour"].create({"signal_id": sig.id, "hour": datetime(2026, 10, 14, 6)})
        sig_id = sig.id
        sig.unlink()
        self.assertEqual(Reading.search_count([("signal_id", "=", sig_id)]), 0)
        self.assertEqual(self.env["f3d.reading.hour"].search_count([("signal_id", "=", sig_id)]), 0)
