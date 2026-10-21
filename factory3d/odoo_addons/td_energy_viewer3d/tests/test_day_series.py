"""R-59 (SPEC 8.4.5): добові серії енергії для 3D — `tools/day_series.build`, маршрути `…/energy/day`, права на ₴.
AC-294…AC-296. Фікстура: доба суботи 2026-10-17 (UTC+3), вводи PM-Q1/PM-Q2 з двома цінами, споживач SAW-1,
СЕС SUN-1."""

from datetime import date, datetime, timedelta

from odoo.tests import HttpCase, tagged

from odoo.addons.td_viewer3d.controllers import kiosk as kiosk_ctrl

from ..tools import day_series
from .common import TAGS, LayerCase

DAY = date(2026, 10, 17)
MIDNIGHT = datetime(2026, 10, 16, 21, 0)  # 00:00 Київ у UTC (EEST, UTC+3)
SLOT_0700 = 28  # 07:00 = слот 28


class DayCase(LayerCase):
    def setUp(self):
        super().setUp()
        self.slots = list(range(SLOT_0700, SLOT_0700 + 8))  # 07:00–09:00
        for s in self.slots:
            ts = MIDNIGHT + timedelta(minutes=15 * s)
            price = 8.4 if s < SLOT_0700 + 4 else 4.2  # дві зони: до 08:00 дорожче
            self.interval("PM-Q1", ts, 50.0, price=price)
            self.interval("PM-Q2", ts, 25.0, kwh_export=5.0, price=price)
            self.interval("PM-SAW-1", ts, 3.0 + (s - SLOT_0700))
            self.interval("SUN-1", ts, 10.0)
        self.env["td.energy.interval"].flush_model()

    def series(self, with_cost=True, day=DAY):
        return day_series.build(self.env, day, with_cost)


@tagged(*TAGS)
class TestDaySeries(DayCase):
    def test_shape_and_slots(self):  # AC-294
        s = self.series()
        self.assertEqual((s["schema"], s["day"], s["slot_min"]), (1, "2026-10-17", 15))
        self.assertEqual(len(s["grid"]["kwh"]), 96)
        self.assertEqual(len(s["consumers"]["SAW-1"]), 96)
        self.assertEqual(s["built_to"], SLOT_0700 + 7)
        self.assertEqual(s["grid"]["kwh"][SLOT_0700 - 1], 0)  # до 07:00 слотів немає
        self.assertEqual(s["grid"]["kwh"][SLOT_0700], 75.0)  # PM-Q1 + PM-Q2
        self.assertEqual(s["grid"]["export"][SLOT_0700], 5.0)
        self.assertEqual(s["gen"]["kwh"][SLOT_0700], 10.0)
        self.assertEqual(s["consumers"]["SAW-1"][SLOT_0700 + 3], 24.0)  # kw_avg = kwh × 4 (6 кВт·год → 24 кВт)

    def test_cost_is_incomer_kwh_times_zone_price(self):  # AC-294: вартість = Σ вводів × ціна зони
        s = self.series()
        self.assertEqual(s["grid"]["cost"][SLOT_0700], round(75.0 * 8.4, 2))
        self.assertEqual(s["grid"]["cost"][SLOT_0700 + 4], round(75.0 * 4.2, 2))
        expect = 4 * 75.0 * 8.4 + 4 * 75.0 * 4.2
        self.assertAlmostEqual(s["totals"]["cost"], expect, places=2)
        self.assertAlmostEqual(s["totals"]["kwh"], 8 * 75.0, places=3)
        self.assertAlmostEqual(s["totals"]["gen_kwh"], 80.0, places=3)
        # доба збігається із SQL-сумою, яку рахує td_energy_analytics (`td.energy.daily` plant: Σ cost, Σ kwh вводів)
        self.env.cr.execute(
            "SELECT SUM(cost), SUM(kwh) FROM td_energy_interval WHERE day = %s AND role = 'incomer'", (DAY,)
        )
        cost, kwh = self.env.cr.fetchone()
        self.assertAlmostEqual(s["totals"]["cost"], cost, places=2)
        self.assertAlmostEqual(s["totals"]["kwh"], kwh, places=3)

    def test_zonal_tariff_price_per_slot(self):  # AC-301: зонний тариф (ніч 0,5× / напівпік 1,0× / пік 1,5× від 8,4 ₴)
        """Стенд із зонним тарифом (td_live_production, LP-07): 15-хв інтервали, побудовані за ним (генератор історії
        бере ту саму ціну зони, що й побудова слотів), дають вартість слота за ціною ЗОНИ, а не плоскою 8,4."""
        company = self.env.company
        Tariff = self.env["td.energy.tariff"].sudo()
        Tariff.search([("company_id", "=", company.id), ("active", "=", True)]).write({"active": False})
        spans = (  # код, назва, ціна, [(з, до)] — як `td_live_production.tools.tariff.ZONES` від 8,4 ₴
            ("night", "Ніч", 4.2, ((0.0, 7.0), (23.0, 24.0))),
            ("half_peak", "Напівпік", 8.4, ((7.0, 8.0), (11.0, 20.0), (22.0, 23.0))),
            ("peak", "Пік", 12.6, ((8.0, 11.0), (20.0, 22.0))),
        )
        zones, seq = [], 10
        for code, name, price, hours in spans:
            for hour_from, hour_to in hours:
                zones.append(
                    (0, 0, {"sequence": seq, "name": name, "code": code, "price": price,
                            "hour_from": hour_from, "hour_to": hour_to})
                )  # fmt: skip
                seq += 10
        Tariff.create(
            {"name": "Зонний", "company_id": company.id, "currency_id": company.currency_id.id,
             "date_from": date(2026, 10, 1), "contract_kw": 800, "zone_ids": zones}
        )  # fmt: skip
        self.env["td.energy.interval"]._td_backfill(
            days=1,
            until=datetime(2026, 10, 18, 21, 0),
            with_balance=False,
            with_events=False,
            meters=["PM-Q1", "PM-Q2"],
        )
        s = self.series(day=date(2026, 10, 18))
        self.assertEqual(s["built_to"], 95)

        def zone_price(slot):
            return next(p for _c, _n, p, hrs in spans for a, b in hrs if a <= slot / 4 < b)

        for slot in range(96):
            kwh = s["grid"]["kwh"][slot]
            self.assertGreater(kwh, 0, slot)
            self.assertAlmostEqual(s["grid"]["cost"][slot], kwh * zone_price(slot), delta=0.02, msg=slot)
        by_zone = sum(s["grid"]["kwh"][k] * zone_price(k) for k in range(96))
        self.assertAlmostEqual(s["totals"]["cost"], by_zone, delta=1.0)
        self.assertNotAlmostEqual(s["totals"]["cost"], s["totals"]["kwh"] * 8.4, delta=10.0)  # не плоска ціна
        for slot, expect in ((4, 4.2), (36, 12.6), (48, 8.4), (84, 12.6)):  # 01:00 ніч, 09:00 пік, 12:00, 21:00 пік
            self.assertAlmostEqual(s["grid"]["cost"][slot] / s["grid"]["kwh"][slot], expect, delta=0.05)

    def test_peak_is_net_import(self):  # AC-294: пік — чистий імпорт вводів, кВт
        s = self.series()
        self.assertEqual(s["totals"]["peak_kw"], (75.0 - 5.0) * 4)
        self.assertGreaterEqual(s["totals"]["peak_slot"], SLOT_0700)
        self.assertEqual(s["contract_kw"], 800)  # договірна потужність демо-тарифу

    def test_no_cost_keys_without_right(self):  # AC-295
        s = self.series(with_cost=False)
        self.assertNotIn("cost", s["grid"])
        self.assertNotIn("cost", s["totals"])
        self.assertIs(s["cost"], False)
        self.assertNotIn("cost", str(s["totals"]))

    def test_cost_allowed_rules(self):  # AC-295: група вартості; киоск — лише за `kiosk_cost`
        self.assertTrue(day_series.cost_allowed(self.env(user=self.u_cost.id)))
        self.assertFalse(day_series.cost_allowed(self.env(user=self.u_viewer.id)))
        self.assertFalse(day_series.cost_allowed(self.env(user=self.u_cost.id), kiosk=True))  # киоск: AC-65
        self.env["ir.config_parameter"].sudo().set_param(day_series.KIOSK_COST_PARAM, "True")
        self.assertTrue(day_series.cost_allowed(self.env(user=self.u_viewer.id), kiosk=True))
        self.assertTrue(day_series.cost_allowed(self.env(user=self.u_viewer.id, context={"kiosk": True})))

    def test_empty_day(self):
        s = self.series(day=date(2026, 10, 10))
        self.assertEqual(s["built_to"], -1)
        self.assertEqual(s["totals"]["peak_slot"], -1)
        self.assertEqual(sum(s["grid"]["kwh"]), 0)
        self.assertEqual(s["consumers"], {})

    def test_dst_day_collision_is_summed(self):
        """Доба переходу на зимовий час (2026-10-25, 25 год): година 03:00–04:00 за місцевим часом повторюється; слот
        з однаковим місцевим часом сумується — доба не втрачає й не подвоює енергію."""
        base = datetime(2026, 10, 24, 21, 0)  # 00:00 Київ (UTC+3)
        for k in (0, 12, 16):  # 00:00; 00:00 UTC (03:00 EEST) і 01:00 UTC (03:00 EET) — обидва в слоті 12
            self.interval("PM-Q1", base + timedelta(minutes=15 * k), 10.0)
        s = self.series(day=date(2026, 10, 25))
        self.assertAlmostEqual(sum(s["grid"]["kwh"]), 30.0, places=3)
        self.assertEqual((s["grid"]["kwh"][0], s["grid"]["kwh"][12]), (10.0, 20.0))


@tagged(*TAGS)
class TestDaySeriesHttp(HttpCase, DayCase):
    def setUp(self):
        super().setUp()
        kiosk_ctrl.reset_rate_limit()
        self.addCleanup(kiosk_ctrl.reset_rate_limit)
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("td.viewer.kiosk_enabled", "True")
        self.token = icp.get_param("td.viewer.kiosk_token")

    def test_user_route(self):  # AC-296
        self.authenticate("w1_cost", "w1_cost")
        res = self.url_open("/f3d/viewer/energy/day?day=2026-10-17")
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data["day"], "2026-10-17")
        self.assertIn("cost", data["grid"])
        self.assertEqual(data["totals"]["kwh"], 600.0)
        self.assertEqual(self.url_open("/f3d/viewer/energy/day?day=bad").status_code, 400)
        self.assertEqual(self.url_open("/f3d/viewer/energy/day?day=2026-02-31").status_code, 400)

    def test_user_without_cost_right(self):  # AC-295
        self.authenticate("en_viewer", "en_viewer")  # group_td_user без group_td_energy_cost
        data = self.url_open("/f3d/viewer/energy/day?day=2026-10-17").json()
        self.assertNotIn("cost", data["grid"])
        self.assertTrue(data["consumers"])  # кВт споживачів — як і живий payload

    def test_user_without_viewer_group(self):  # AC-296: без group_td_user — 403
        self.authenticate("w1_plain", "w1_plain")
        self.assertEqual(self.url_open("/f3d/viewer/energy/day").status_code, 403)

    def test_kiosk_route(self):  # AC-296: токен, без вартості; `kiosk_cost` вмикає її
        base = "/f3d/kiosk/%s/energy/day?day=2026-10-17" % self.token
        res = self.url_open(base)
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("Set-Cookie", res.headers)
        data = res.json()
        self.assertNotIn("cost", data["grid"])
        self.assertTrue(data["consumers"])
        for bad in ("deadbeef", "0" * 32, "%00"):
            self.assertEqual(self.url_open("/f3d/kiosk/%s/energy/day" % bad, allow_redirects=False).status_code, 404)
        self.env["ir.config_parameter"].sudo().set_param(day_series.KIOSK_COST_PARAM, "True")
        data = self.url_open(base).json()
        self.assertAlmostEqual(data["totals"]["cost"], 4 * 75.0 * 8.4 + 4 * 75.0 * 4.2, places=2)
        self.env["ir.config_parameter"].sudo().set_param("td.viewer.kiosk_enabled", "False")
        self.assertEqual(self.url_open(base, allow_redirects=False).status_code, 404)
