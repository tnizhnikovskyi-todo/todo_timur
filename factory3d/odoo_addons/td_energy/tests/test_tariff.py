"""AC-07…AC-10: зони й ціна тарифу, договірні пороги. AC-11 (слот без тарифу) — разом з R-04 (W2)."""

from datetime import datetime

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from ..tools import tariff as tariff_tools
from .common import TAGS, F3DEnergyCase


def zone(name, code, price, weekdays, hour_from, hour_to, sequence=10):
    return Command.create(
        {"name": name, "code": code, "price": price, "weekdays": weekdays, "hour_from": hour_from,
         "hour_to": hour_to, "sequence": sequence}
    )  # fmt: skip


@tagged(*TAGS)
class TestTariff(F3DEnergyCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Tariff = cls.env["f3d.energy.tariff"]
        cls.demo = cls.env.ref("factory3d_energy.tariff_demo")

    def day_night(self, **kw):
        vals = {
            "name": "День/ніч",
            "date_from": "2026-01-01",
            "zone_ids": [zone("День", "day", 9.6, "0123456", 7, 23), zone("Ніч", "night", 4.8, "0123456", 23, 7, 20)],
        }
        vals.update(kw)
        return self.Tariff.create(vals)

    def test_price_at(self):  # AC-07
        # 12.10.2026 — літній час Києва (UTC+3)
        for hour, minute, utc_hour, name, price in ((22, 45, 19, "День", 9.6), (23, 0, 20, "Ніч", 4.8),
                                                    (6, 45, 3, "Ніч", 4.8), (7, 0, 4, "День", 9.6)):  # fmt: skip
            dt = datetime(2026, 10, 12, utc_hour, minute)
            with self.subTest(local="%02d:%02d" % (hour, minute)):
                self.demo.active = False
                tariff = self.day_night()
                zone_, got = self.Tariff._f3d_price_at(dt)
                self.assertEqual((zone_.name, got), (name, price))
                self.assertEqual(zone_.tariff_id, tariff)
                tariff.unlink()
                self.demo.active = True
                zone_, got = self.Tariff._f3d_price_at(dt)
                self.assertEqual((zone_.name, got), ("Цілодобова", 8.4))

    def test_zone_validation(self):  # AC-08
        def create(zones):
            return self.Tariff.create({"name": "Т", "date_from": "2025-01-01", "date_to": "2025-12-31",
                                       "zone_ids": zones})  # fmt: skip

        with self.assertRaisesRegex(ValidationError, "нд о 00:00 не покрито"), self.env.cr.savepoint():
            create([zone("День", "day", 9.6, "012345", 7, 23), zone("Ніч", "night", 4.8, "012345", 23, 7)])
        with self.assertRaisesRegex(ValidationError, r"покрито двічі \(День, Пік\)"), self.env.cr.savepoint():
            create([zone("День", "day", 9.6, "0123456", 7, 23), zone("Пік", "peak", 12, "0123456", 18, 21, 15),
                    zone("Ніч", "night", 4.8, "0123456", 23, 7, 20)])  # fmt: skip
        with self.assertRaisesRegex(ValidationError, "нульову тривалість"), self.env.cr.savepoint():
            create([zone("День", "day", 9.6, "0123456", 7, 7)])
        with self.assertRaisesRegex(ValidationError, "Дні тижня"), self.env.cr.savepoint():
            create([zone("День", "day", 9.6, "0089", 0, 24)])
        with self.assertRaisesRegex(ValidationError, "від 0 до 24"), self.env.cr.savepoint():
            create([zone("День", "day", 9.6, "0123456", 0, 24.1)])

    def test_periods(self):  # AC-09
        flat = [zone("Ціла", "flat", 5, "0123456", 0, 24)]
        with self.assertRaisesRegex(ValidationError, "перетинається"), self.env.cr.savepoint():
            self.Tariff.create({"name": "Новий", "date_from": "2026-06-01", "zone_ids": flat})
        self.demo.date_to = "2026-05-31"
        second = self.Tariff.create({"name": "Новий", "date_from": "2026-06-01", "zone_ids": flat})
        self.assertEqual(self.Tariff._f3d_tariff_at(datetime(2026, 7, 1, 9, 0)), second)
        self.assertEqual(self.Tariff._f3d_tariff_at(datetime(2026, 5, 1, 9, 0)), self.demo)
        with self.assertRaisesRegex(ValidationError, "раніше"), self.env.cr.savepoint():
            second.date_to = "2026-01-01"

    def test_contract_thresholds(self):  # AC-10
        self.demo.write({"contract_kw": 900, "peak_warn_pct": 90})
        sig = self.env["f3d.signal"].search([("code", "=", "energy/totals/grid15_kw")])
        self.assertEqual((sig.warn_high, sig.alarm_high), (810, 900))
        self.assertTrue(sig.warn_high_on and sig.alarm_high_on)
        self.assertIn("договірної потужності", sig.alarm_title)
        self.assertEqual(sig.min_duration_s, 0)

    def test_zone_for_pure(self):  # R-05 п. 2 без ORM
        class Z:
            def __init__(self, weekdays, hour_from, hour_to, sequence=10):
                self.weekdays, self.hour_from, self.hour_to, self.sequence = weekdays, hour_from, hour_to, sequence

        night, day = Z("0123456", 23, 7), Z("0123456", 7, 23)
        local = tariff_tools.to_local(datetime(2026, 1, 12, 21, 0))  # 23:00 Київ (зима, UTC+2)
        self.assertIs(tariff_tools.zone_for(local, [day, night]), night)
        self.assertIsNone(tariff_tools.zone_for(local, [Z("1", 0, 24)]))
        self.assertIsNone(tariff_tools.check_coverage([day, night]))

    def test_tariff_without_zones_price_zero(self):
        self.demo.active = False
        self.Tariff.create({"name": "Порожній", "date_from": "2026-01-01"})
        zone_, price = self.Tariff._f3d_price_at(datetime(2026, 10, 12, 9, 0))
        self.assertEqual((bool(zone_), price), (False, 0.0))
