"""W1-A: AC-137…AC-139, AC-141 — повірка лічильників, сигнали W1, пороги cos φ, події PFC."""

from datetime import date, timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import tagged

from .. import hooks
from .common import TAGS, TestW1Common

W1_CODES = (
    ["energy/cells/QS/state"]
    + ["energy/cells/PFC-%d/%s" % (n, s) for n in (1, 2) for s in ("q_kvar", "steps_on", "steps_total", "fault_step")]
    + ["energy/sections/S%d/%s" % (n, s) for n in (1, 2) for s in ("cos_phi", "p_kw", "q_kvar")]
)


@tagged(*TAGS)
class TestW1Signals(TestW1Common):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Signal = cls.env["td.signal"]

    def test_verification_cron(self):  # AC-137
        meter = self.Meter.search([("code", "=", "PM-QF-2")])
        meter.write({"next_verification": date(2026, 11, 6)})  # today = 17.10 → через 20 діб
        self.Meter._cron_verification()
        self.Meter._cron_verification()
        events = self.Event.search([("code", "=", "VERIFY-PM-QF-2")])
        self.assertEqual(len(events), 1)
        self.assertEqual((events.level, events.kind, events.state), ("warn", "meter", "active"))
        self.assertEqual(events.title, "Повірка лічильника PM-QF-2")
        self.assertEqual(events.detail, "до 06.11.2026. Заплануйте повірку.")
        meter.write({"next_verification": date(2026, 10, 1)})
        self.Meter._cron_verification()
        self.assertEqual((events.level, len(self.Event.search([("code", "=", "VERIFY-PM-QF-2")]))), ("bad", 1))
        self.assertIn("прострочена з 01.10.2026", events.text)
        meter.write({"last_verification": date(2026, 10, 17), "next_verification": date(2027, 10, 17)})
        self.Meter._cron_verification()
        self.assertEqual(events.state, "resolved")
        old = self.Event._td_log("warn", "trip", "QF-2", "Спрацював захист QF-2", ts=self.now - timedelta(hours=30))
        self.Meter._cron_verification()
        self.assertEqual(old.state, "resolved")  # R-25: trip старший за 24 год

    def test_w1_signals_exist(self):  # AC-138
        signals = self.Signal.search([("code", "in", W1_CODES)])
        self.assertEqual(len(signals), 15)
        self.assertTrue(all(s.module == "energy" for s in signals))
        source = self.env["td.source"].search([("code", "=", "MB-U73-SWB-CTRL")])
        self.assertEqual((source.params["unit"], source.params["host"], source.params["port"]), (73, "iot-sim", 502))
        foreign = self.env["ir.model.data"].search(
            [("module", "=", "td_energy_resources"), ("model", "=", "td.signal")]
        )
        self.assertEqual(  # сигнали td_energy_resources (+10) рахуються окремо
            self.Signal.search_count([("module", "=", "energy"), ("id", "not in", foreign.mapped("res_id"))]), 312
        )
        self.assertEqual(hooks._ensure_w1_signals(self.env), {"sources": 0, "signals": 0})
        qs = self.Signal.search([("code", "=", "energy/cells/QS/state")])
        self.assertEqual(qs.states, ["open", "closed"])
        qs.unlink()
        self.assertEqual(hooks._ensure_w1_signals(self.env), {"sources": 0, "signals": 1})
        fault = self.Signal.search([("code", "=", "energy/cells/PFC-2/fault_step")])
        self.assertEqual((fault.alarm_high, fault.min_duration_s), (0.5, 60))

    def test_cos_thresholds(self):  # AC-139
        codes = ["energy/totals/cos_phi", "energy/sections/S1/cos_phi", "energy/sections/S2/cos_phi"]
        self.Signal.search([("code", "=", codes[0])]).write({"warn_low": 0.95})
        settings = self.env["res.config.settings"].create({})
        settings.write({"td_energy_cos_phi_warn": 0.93, "td_energy_cos_phi_alarm": 0.91})
        settings.set_values()
        for sig in self.Signal.search([("code", "in", codes)]):
            self.assertEqual(
                (sig.warn_low, sig.alarm_low, sig.warn_low_on, sig.alarm_low_on), (0.93, 0.91, True, True), sig.code
            )
        with self.assertRaisesRegex(ValidationError, "Пороги cos φ: тривога < попередження ≤ ціль ≤ 1."):
            settings.write({"td_energy_cos_phi_alarm": 0.94})
        self.env["ir.config_parameter"].sudo().set_param("td.energy.cos_phi_warn", "0.92")
        self.env["ir.config_parameter"].sudo().set_param("td.energy.cos_phi_alarm", "0.90")
        self.Signal.search([("code", "=", codes[0])]).write({"warn_low": 0.95})
        hooks._migrate_w1(self.env)  # міграція застосовує пороги на існуючій БД
        self.assertEqual(self.Signal.search([("code", "=", codes[0])]).warn_low, 0.92)

    def test_pfc_fault_event_and_request(self):  # AC-141
        sig = self.Signal.search([("code", "=", "energy/cells/PFC-2/fault_step")])
        equipment = self.env["maintenance.equipment"].create({"name": "PFC-2 (тест)"})
        sig.write({"equipment_id": equipment.id, "min_duration_s": 0})
        now = fields.Datetime.now()
        self.fresh("energy/sections/S2/cos_phi", 0.88)
        self.Signal._td_ingest([{"code": sig.code, "ts": now - timedelta(seconds=20), "value": 0}])
        self.Signal._td_ingest([{"code": sig.code, "ts": now - timedelta(seconds=10), "value": 3}])
        self.Signal._td_ingest([{"code": sig.code, "ts": now - timedelta(seconds=5), "value": 3}])
        events = self.Event.search([("kind", "=", "pfc"), ("code", "=", "PFC-2")])
        self.assertEqual(len(events), 1)
        self.assertEqual(
            (events.level, events.title, events.state), ("warn", "PFC-2: ступінь 3 не вмикається", "active")
        )
        self.assertFalse(self.Event.search([("kind", "=", "threshold"), ("signal_id", "=", sig.id)]))
        request = self.env["maintenance.request"].search([("name", "=", "PFC-2: ступінь 3 не вмикається")])
        self.assertEqual(len(request), 1)
        self.fresh("energy/sections/S2/cos_phi", 0.88)
        self.Signal._td_ingest([{"code": sig.code, "ts": now - timedelta(seconds=2), "value": 0}])
        self.assertEqual(events.state, "active")  # cos φ секції ще нижче 0,92
        self.fresh("energy/sections/S2/cos_phi", 0.95)
        self.Signal._td_ingest([{"code": sig.code, "ts": now, "value": 3}])
        self.Signal._td_ingest([{"code": sig.code, "ts": now + timedelta(seconds=2), "value": 0}])
        self.assertEqual(events.state, "resolved")
