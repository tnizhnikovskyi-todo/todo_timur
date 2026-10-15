from freezegun import freeze_time

from odoo.tests import tagged

from .test_rules_hvac import HvacRulesCase
from .test_rules_hvac import at as hat
from .test_rules_lighting import RulesCase, at


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestEnrichment(RulesCase):
    def _light_off_request(self):
        self.push(self.level.code, at(6, 55), 0)
        self.step(7, 5)
        return self.requests(self.check_sig)

    def test_light_off_title(self):
        req = self._light_off_request()
        zone = self.cut.zone_id.name
        self.assertEqual(
            req.name, "Освітлення LT-CUT (%s): вимкнено в робочий час — рівень 0 %% при нормі 500 лк" % zone
        )
        self.assertEqual((req.f3d_value, req.f3d_threshold), (0.0, 500.0))
        self.assertIn("Група DALI G:%d, щит LP-2; вимкнено з 14.10.2026 09:55." % self.cut.dali_group, req.description)
        self.assertEqual((req.f3d_bms_rule, req.f3d_bms_enriched), ("light_off", True))
        self.assertEqual(req.maintenance_type, "corrective")

    def test_idempotent(self):
        req = self._light_off_request()
        name = req.name
        for minute in (6, 20, 40):
            self.step(7, minute)
        self.assertEqual(self.requests(self.check_sig), req)
        self.assertEqual(req.name, name)
        self.assertEqual(req.description.count("Група DALI"), 1)

    def test_titles_table(self):
        self.push(self.level.code, at(7, 0), 60)
        self.step(7, 10)
        req = self.requests(self.check_sig)
        self.assertEqual(
            req.name,
            "Освітлення LT-CUT (%s): ≈ 305 лк при нормі 500 лк (рівень 60 %%)" % self.cut.zone_id.name,
        )
        self.assertEqual((req.f3d_value, req.f3d_threshold, req.f3d_bms_rule), (305.0, 500.0, "light_low"))

    def test_faults_description(self):
        with freeze_time(at(7, 30)):
            self.push(self.faulty.code, at(7, 1), text="1.2.1.5")
            self.push(self.faults.code, at(7, 2), 1)
        req = self.requests(self.faults)
        self.assertEqual(req.name, "Аварія світильників LT-CUT: несправних 1 шт. при нормі 0")
        self.assertEqual(req.f3d_bms_rule, "light_fault")
        with freeze_time(at(7, 31)):
            self.run_check()
        self.assertIn(
            "Несправні світильники: 1.2.1.5; щит LP-2, DALI-група G:%d." % self.cut.dali_group, req.description
        )
        with freeze_time(at(7, 40)):
            self.push(self.faults.code, at(7, 35), 0)
        self.assertEqual(self.faults.status, "ok")
        self.assertFalse(req.stage_id.done)


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestEnrichmentHvac(HvacRulesCase):
    def test_unit_off_and_cold(self):
        self.put(self.rv5, 6, 50, state="stopped", mode="ST", airflow=0.0)
        self.put(self.rv7, 6, 30, state="running", mode="AQ", indoor=15.5, airflow=8000.0)
        self.step(self.rv5, 7, 0)
        req = self.requests(self.rv5.check_signal_id)
        self.assertEqual(req.name, "Установка RV-05 (Склад плит): не працює в робочий час — режим «Очікування»")
        self.assertEqual((req.f3d_bms_rule, req.f3d_threshold), ("unit_off", 0.0))
        self.assertIn("Стан standby; з 14.10.2026 09:50.", req.description)
        req = self.requests(self.rv7.check_signal_id)
        self.assertIn("у зоні 15,5 °C при нормі від 16,0 °C", req.name)
        self.assertEqual((req.f3d_bms_rule, req.f3d_value, req.f3d_threshold), ("cold", 15.5, 16.0))

    def test_cold_off_hours_title(self):
        self.put(self.rv5, 19, 0, state="running", mode="AQ", indoor=9.0, airflow=8000.0)
        self.step(self.rv5, 19, 31)
        req = self.requests(self.rv5.check_signal_id)
        self.assertIn("у зоні 9,0 °C при нормі від 10,0 °C", req.name)

    def test_heat_deficit_title(self):
        sig = self._setup_deficit()
        for minute in (1, 31):
            with freeze_time(hat(7, minute)):
                self.run_check()
        req = self.requests(sig)
        self.assertEqual(req.name, "Котельня: дефіцит тепла 103 кВт (потреба 600 кВт, джерела 497 кВт)")
        self.assertEqual(req.f3d_bms_rule, "heat_deficit")


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestJournal(HvacRulesCase):
    def setUp(self):
        super().setUp()
        self.sig = self.define(
            "ventilation/units/RV-05/filter_dp_pa",
            "RV-05",
            alarm_high=250.0,
            alarm_high_on=True,
            hysteresis=5.0,
            decimals=0,
            unit="Па",
            alarm_title="Заміна фільтрів: перепад тиску {value} Па при нормі до {threshold}",
        )
        self.rv5.filter_signal_id = self.sig
        self.Dev = self.env["f3d.bms.deviation"]

    def feed(self, minute, value):
        with freeze_time(hat(7, minute)):
            self.push(self.sig.code, hat(7, minute), value)
            self.run_check()

    def test_open_update_close(self):
        self.feed(1, 285.2)
        ep = self.Dev.search([("signal_id", "=", self.sig.id)])
        self.assertEqual(len(ep), 1)
        self.assertEqual(
            (ep.rule, ep.object_kind, ep.object_code, ep.state), ("filter_supply", "unit", "RV-05", "open")
        )
        self.assertEqual((ep.value, ep.threshold, ep.unit), (285.2, 250.0, "Па"))
        self.assertEqual((ep.request_id, ep.zone_id), (self.requests(self.sig), self.zone_hvac))
        self.assertEqual(ep.started, hat(7, 1))
        self.feed(2, 300.0)
        self.assertEqual(ep.value, 300.0)
        self.feed(3, 290.0)
        self.assertEqual(ep.value, 300.0)  # найгірше
        self.feed(4, 244.0)
        self.assertEqual((ep.state, ep.ended), ("closed", hat(7, 4)))
        self.assertGreater(ep.duration_min, 0)

    def test_new_episode(self):
        self.feed(1, 285.2)
        self.feed(2, 240.0)
        self.feed(3, 290.0)
        self.assertEqual(self.Dev.search_count([("signal_id", "=", self.sig.id)]), 2)

    def test_cooldown_new_request(self):
        self.feed(1, 285.2)
        req = self.requests(self.sig)
        done = self.env["maintenance.stage"].search([("done", "=", True)], limit=1)
        with freeze_time(hat(7, 2)):
            req.stage_id = done
        self.feed(10, 290.0)  # менше за cooldown (3 600 с) — нової заявки немає
        self.assertEqual(self.requests(self.sig), req)
        ep = self.Dev.search([("signal_id", "=", self.sig.id), ("state", "=", "open")])
        self.assertEqual(ep.request_id, req)
        with freeze_time(hat(8, 3)):
            self.push(self.sig.code, hat(8, 3), 295.0)
            self.run_check()
        reqs = self.requests(self.sig)
        self.assertEqual(len(reqs), 2)
        self.assertEqual(ep.request_id, reqs - req)
