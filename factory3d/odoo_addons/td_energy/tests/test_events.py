"""AC-33, AC-34, AC-36: журнал подій енергетики (R-13) і заявки за порогами (R-12)."""

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from odoo.addons.td_telemetry.tools.titles import fmt_num

from ..tools import dates
from .common import TAGS, F3DEnergyCase
from .test_counter import EnergyMixin


@tagged(*TAGS)
class TestEvents(EnergyMixin, F3DEnergyCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Event = cls.env["td.energy.event"]
        cls.Signal = cls.env["td.signal"]

    def put(self, code, value=None, text=None, seconds_ago=0):
        ts = fields.Datetime.now() - timedelta(seconds=seconds_ago)
        item = {"code": code, "ts": ts}
        if value is not None:
            item["value"] = value
        if text is not None:
            item["text"] = text
        self.Signal._f3d_ingest([item])

    def test_threshold_events(self):  # AC-33
        sig = self.Signal.search([("code", "=", "energy/transformers/T1/s_kva")])
        sig.write({"min_duration_s": 0})
        self.bind_equipment(sig.code, "T1")
        self.assertEqual((sig.warn_high, sig.alarm_high), (900, 1000))
        self.put(sig.code, 950, seconds_ago=30)
        self.put(sig.code, 1020, seconds_ago=20)
        self.put(sig.code, 880, seconds_ago=10)
        events = self.Event.search([("signal_id", "=", sig.id)], order="id")
        self.assertEqual([e.level for e in events], ["warn", "bad", "info"])
        self.assertEqual(events[0].text, "Перевантаження трансформатора T1: 950 кВА при номіналі 900")
        self.assertEqual(
            events[1].text,
            "Перевантаження трансформатора T1: %s кВА при номіналі %s" % (fmt_num(1020, 0), fmt_num(1000, 0)),
        )
        self.assertEqual(events[2].text, "%s: повернувся в норму (880 кВА)" % sig.name)
        self.assertTrue(
            self.env["maintenance.request"].search([("name", "=like", "Перевантаження трансформатора T1: 1%")])
        )

    def test_contract_power_request(self):  # AC-34
        self.bind_equipment("energy/totals/grid15_kw", "SWB-1")
        tariff = self.env.ref("td_energy.tariff_demo")
        tariff._f3d_apply_contract_thresholds()
        sig = self.Signal.search([("code", "=", "energy/totals/grid15_kw")])
        self.assertEqual((sig.warn_high, sig.alarm_high), (720.0, 800.0))
        self.put(sig.code, 812.4)
        self.assertEqual(sig.status, "alarm")
        request = self.env["maintenance.request"].search(
            [("name", "=", "Перевищення договірної потужності: 812,4 кВт при ліміті 800 кВт")]
        )
        self.assertEqual(len(request), 1)
        self.assertEqual(request.equipment_id.td_code, "SWB-1")

    def test_pfc_event(self):  # AC-36 (а)
        parent = self.env["td.energy.node"].search([("code", "=", "SEC-1")])
        node = self.env["td.energy.node"].create(
            {"code": "PFC-T", "name": "PFC-T", "kind": "cell", "cell_type": "pfc", "parent_id": parent.id, "section": 1}
        )
        first = self.Event._f3d_pfc_event(node, 35, 70, 0.97)  # W1 D-09: крок ступеня — 35 квар
        self.assertEqual(first.text, "Компенсація секції 1: увімкнено ще один ступінь 35 квар, cos φ 0,97.")
        self.assertEqual((first.level, first.kind, first.code), ("info", "pfc", "PFC-T"))
        self.assertFalse(self.Event._f3d_pfc_event(node, 35, 70, 0.97))
        self.assertEqual(
            self.Event._f3d_pfc_event(node, 70, 35, 0.97).text,
            "Компенсація секції 1: вимкнено ступінь 35 квар, cos φ 0,97.",
        )
        self.assertEqual(
            self.Event._f3d_pfc_event(node, 0, 70, 0.95).text,
            "Компенсація секції 1: увімкнено 2 ступені (70 квар), cos φ 0,95.",
        )

    def test_machine_fault_event(self):  # AC-36 (б)
        meter = self.mk_meter("PM-CNC-T", with_power=True)
        meter.p_signal_id.write({"last_value": 0.7})
        state = self.mk_signal(
            "workcenters/CNC-T/machine_state", "state", "", states=["idle", "working", "fault"], module="telemetry"
        )
        self.put(state.code, text="working", seconds_ago=20)
        self.assertFalse(self.Event.search([("code", "=", "CNC-T")]))
        self.put(state.code, text="fault", seconds_ago=10)
        event = self.Event.search([("code", "=", "CNC-T")])
        self.assertEqual(event.text, "CNC-T: аварійна зупинка, споживання впало до 0,7 кВт.")
        self.assertEqual(event.level, "bad")

    def test_peak_event(self):  # AC-36 (в)
        m1, m2 = self.mk_meter("PM-F1-T", role="feeder"), self.mk_meter("PM-F2-T", role="feeder")
        now = fields.Datetime.now()
        today = dates.local_day(now)
        y0, _y1 = dates.local_day_bounds(today - timedelta(days=1))
        peak_slot = y0 + timedelta(hours=9, minutes=15)
        for k in range(96):
            slot = y0 + timedelta(minutes=15 * k)
            for meter in (m1, m2):
                self.mk_interval(meter, slot, 40.0 if slot == peak_slot else 10.0)
        Interval = self.env["td.energy.interval"]
        self.assertTrue(Interval._f3d_peak_event(now))
        event = self.Event.search([("kind", "=", "peak")])
        yesterday = today - timedelta(days=1)
        self.assertEqual(
            event.text,
            "Пік 15-хвилинної потужності за %s: 320 кВт о 09:15; ліміт договірної потужності (800 кВт) не перевищено."
            % yesterday.strftime("%d.%m"),
        )
        self.assertEqual((event.level, event.code), ("info", "SWB-1"))
        self.assertFalse(Interval._f3d_peak_event(now))  # одна подія за добу
        self.assertEqual(self.Event.search_count([("kind", "=", "peak")]), 1)

    def test_snapshot_ignores_internal_context(self):
        """Власні вкладення модуля (контекст f3d_energy_internal) не породжують подій повторно."""
        sig = self.Signal.search([("code", "=", "energy/transformers/T1/s_kva")])
        sig.write({"min_duration_s": 0})
        self.Signal.with_context(f3d_energy_internal=True)._f3d_ingest(
            [{"code": sig.code, "ts": fields.Datetime.now(), "value": 1500.0}]
        )
        self.assertFalse(self.Event.search([("signal_id", "=", sig.id)]))

    def test_on_ingest_db_error_propagates(self):  # O-2
        """Помилка БД рівня транзакції (serialization) не ковтається — ретрай приймання; інші — лише лог."""
        from unittest.mock import patch

        from psycopg2 import errors

        Event = self.env["td.energy.event"]
        with patch.object(type(Event), "_f3d_on_ingest_inner", side_effect=errors.SerializationFailure("x")):
            with self.assertRaises(errors.SerializationFailure):
                Event._f3d_on_ingest({}, [])
        with patch.object(type(Event), "_f3d_on_ingest_inner", side_effect=ValueError("x")):
            with self.assertLogs("odoo.addons.td_energy.models.td_energy_event", "ERROR"):
                Event._f3d_on_ingest({}, [])
