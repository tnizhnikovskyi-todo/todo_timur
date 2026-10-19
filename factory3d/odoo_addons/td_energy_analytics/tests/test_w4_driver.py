"""W4-A: драйвери нормалізації (AC-03, AC-05, AC-06, AC-07)."""

from datetime import timedelta

from psycopg2 import IntegrityError

from odoo.exceptions import AccessError
from odoo.tools import mute_logger

from odoo.addons.td_energy.tools import dates
from odoo.tests import tagged

from .common import TAGS, TODAY, TestW4Common

DAY = TODAY - timedelta(days=1)  # вчора: 2026-10-16


@tagged(*TAGS)
class TestW4Driver(TestW4Common):
    def _move(self, product, qty, state="done", production=True, when=None):
        d0, _d1 = dates.local_day_bounds(DAY)
        when = when or d0 + timedelta(hours=10)
        mo = self.env["mrp.production"].create({"product_id": product.id, "product_qty": qty}) if production else None
        stock, customers = self.env.ref("stock.stock_location_stock"), self.env.ref("stock.stock_location_customers")
        move = self.env["stock.move"].create(
            {
                "product_id": product.id, "product_uom_qty": qty, "product_uom": product.uom_id.id,
                "location_id": stock.id, "location_dest_id": customers.id, "production_id": mo.id if mo else False,
            }
        )  # fmt: skip
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE stock_move SET quantity = %s, state = %s, date = %s WHERE id = %s", (qty, state, when, move.id)
        )
        move.invalidate_recordset()
        return move

    def _signal(self, code="ventilation/totals/outdoor_c"):
        return self.env["td.signal"].search([("code", "=", code)], limit=1) or self.env["td.signal"].create(
            {"code": code, "name": code, "kind": "gauge", "unit": "°C", "period_s": 60, "module": "energy"}
        )

    def _hours(self, signal, day, temps):
        d0 = dates.local_day_bounds(day)[0]
        self.env["td.reading.hour"].create(
            [
                {
                    "signal_id": signal.id,
                    "hour": d0 + timedelta(hours=i),
                    "v_avg": t,
                    "v_min": t,
                    "v_max": t,
                    "v_count": 6,
                }
                for i, t in enumerate(temps)
            ]
        )

    def test_ac03_drivers_data(self):
        self.assertEqual((self.plate.source_kind, self.plate.uom), ("mrp_area", "м²"))
        self.assertEqual((self.hdd.source_kind, self.hdd.uom, self.hdd.base_temp_c), ("weather_hdd", "°C·доба", 18.0))
        self.assertEqual(self.hdd.temp_signal_code, "ventilation/totals/outdoor_c")
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.Driver.create({"code": "hdd", "name": "Дубль", "source_kind": "manual"})
        self._driver_value("plate_m2", DAY, 10.0)
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.DriverValue.create({"driver_id": self.plate.id, "day": DAY, "value": 5.0, "quality": "manual"})

    def test_ac05_plate_from_mrp(self):
        self.env.cr.execute("UPDATE product_template SET td_plate_area_m2 = 0")
        self._cron_values_noop = self.Driver._cron_values()
        self.assertFalse(self.DriverValue.search([("driver_id", "=", self.plate.id)]), "немає продуктів із площею")
        p1, p2, p3 = (self._product("DRV-A", 3.1), self._product("DRV-B", 8.4), self._product("DRV-C", 1.0))
        self._move(p1, 10)
        self._move(p2, 5)
        self._move(p3, 20)
        self._move(p1, 100, state="draft")  # не done
        self._move(p1, 100, production=False)  # без МО
        d0, _d1 = dates.local_day_bounds(DAY)
        self._move(p1, 100, when=d0 - timedelta(hours=1))  # поза добою
        self.Driver._cron_values()
        value = self.DriverValue.search([("driver_id", "=", self.plate.id), ("day", "=", DAY)])
        self.assertEqual(len(value), 1)
        self.assertAlmostEqual(value.value, 93.0, places=3)
        self.assertEqual((value.quality, value.source_note), ("estimated", "MRP"))
        self.Driver._cron_values()
        self.assertEqual(self.DriverValue.search_count([("driver_id", "=", self.plate.id), ("day", "=", DAY)]), 1)

    def test_ac06_hdd(self):
        signal = self._signal()
        self._hours(signal, DAY, [6.0, 8.0] * 12)  # середнє 7,0
        self.Driver._cron_values()
        value = self.DriverValue.search([("driver_id", "=", self.hdd.id), ("day", "=", DAY)])
        self.assertAlmostEqual(value.value, 11.0)
        self.assertEqual(value.quality, "measured")
        # тепло: T_mean > 18 → hdd = 0
        day2 = DAY - timedelta(days=1)
        self._hours(signal, day2, [20.0] * 24)
        self.Driver._cron_values()
        self.assertEqual(self.DriverValue.search([("driver_id", "=", self.hdd.id), ("day", "=", day2)]).value, 0.0)
        # < 18 годин — немає рядка; сирі показання ≥ 50 — є
        day3 = DAY - timedelta(days=2)
        self._hours(signal, day3, [5.0] * 10)
        self.Driver._cron_values()
        self.assertFalse(self.DriverValue.search([("driver_id", "=", self.hdd.id), ("day", "=", day3)]))
        d0 = dates.local_day_bounds(day3)[0]
        self.env["td.reading"].create(
            [{"signal_id": signal.id, "ts": d0 + timedelta(minutes=10 * i), "value": 3.0} for i in range(60)]
        )
        self.env.cr.execute(
            "DELETE FROM td_reading_hour WHERE signal_id = %s AND hour >= %s AND hour < %s",
            (signal.id, d0, d0 + timedelta(days=1)),
        )
        self.Driver._cron_values()
        self.assertAlmostEqual(
            self.DriverValue.search([("driver_id", "=", self.hdd.id), ("day", "=", day3)]).value, 15.0
        )

    def test_ac07_manual_driver(self):
        manual = self.Driver.create({"code": "units", "name": "Одиниці", "source_kind": "manual", "uom": "шт"})
        value = self.DriverValue.with_user(self.u_eng).create({"driver_id": manual.id, "day": DAY, "value": 12.0})
        self.assertEqual(value.quality, "manual")
        with self.assertRaises(AccessError):
            self.DriverValue.with_user(self.u_view).create(
                {"driver_id": manual.id, "day": DAY - timedelta(days=1), "value": 1}
            )
        # ручне значення не перезаписується кроном
        self.hdd.base_temp_c = 18.0
        self.assertEqual(self.DriverValue.get_series("units", DAY, DAY), {DAY.isoformat(): 12.0})
        self.assertEqual(self.DriverValue.with_user(self.u_view).get_series("units", DAY, DAY), {DAY.isoformat(): 12.0})
