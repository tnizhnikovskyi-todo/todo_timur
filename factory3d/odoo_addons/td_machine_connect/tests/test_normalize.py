"""AC-01…AC-03: нормалізація стану (R-01)."""

from datetime import datetime, timedelta

from odoo.tests import BaseCase, tagged

from ..tools import states
from .common import F3DMachineCase

LOGGER = "odoo.addons.td_machine_connect"


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestNormalize(F3DMachineCase):
    def test_examples_r01(self):
        cases = [
            ("opcua", {"state": "WORKING", "mode": "AUTOMATIC", "alarm": False}, "working"),
            ("opcua", {"state": "READY", "mode": "SETUP", "alarm": False}, "setup"),
            ("opcua", {"state": "READY", "mode": "AUTOMATIC", "alarm": False}, "idle"),
            ("opcua", {"state": "ERROR", "mode": "AUTOMATIC", "alarm": True}, "fault"),
            ("opcua", {"state": "OFFLINE", "mode": "SLEEP", "alarm": False}, "off"),
            ("opcua", {"state": "READY", "mode": "AUTOMATIC", "alarm": True}, "fault"),
            ("opcua", {"state": "STANDBY", "mode": "SLEEP", "alarm": False}, "idle"),
            ("io", {"state": "run", "alarm": False}, "working"),
            ("io", {"state": "run", "alarm": True}, "fault"),
            ("io", {"state": "stop", "alarm": False}, "idle"),
            ("opcua", {"state": "WORKING", "mode": "AUTOMATIC", "alarm": False, "bad": True}, "nodata"),
        ]
        for protocol, raw, expected in cases:
            with self.subTest(protocol=protocol, raw=raw):
                self.assertEqual(states.normalize(protocol, raw), expected)
        self.assertEqual(states.normalize("opcua", {"state": None}), "nodata")
        self.assertEqual(states.normalize("manual", {"state": "run"}), "nodata")

    def test_unknown_text_nodata_warns_once(self):
        states._warned.clear()
        raw = {"state": "FOO", "mode": "AUTOMATIC", "alarm": False}
        t0 = datetime(2026, 10, 12, 7, 0)
        with self.assertLogs(LOGGER, "WARNING"):
            self.assertEqual(states.normalize("opcua", raw, key="UA-T", now=t0), "nodata")
        with self.assertNoLogs(LOGGER, "WARNING"):
            self.assertEqual(states.normalize("opcua", raw, key="UA-T", now=t0 + timedelta(minutes=30)), "nodata")
        with self.assertLogs(LOGGER, "WARNING"):
            states.normalize("opcua", raw, key="UA-T", now=t0 + timedelta(hours=1))

    def test_io_alarm_wins(self):
        m = self.m_io
        self.feed(self.io(m, "10:00:00", run=True) + self.io(m, "10:00:00", alarm=True))
        self.assertEqual(m.state, "fault")
        self.assertEqual(m.raw_state, "run")
        self.assertTrue(m.raw_alarm)


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestParseTs(BaseCase):
    def test_parse_ts(self):
        self.assertEqual(states.parse_ts("2026-10-12T09:55:00+03:00"), datetime(2026, 10, 12, 6, 55))
        self.assertEqual(states.parse_ts("2026-10-12T06:55:00Z"), datetime(2026, 10, 12, 6, 55))
        self.assertEqual(states.parse_ts(datetime(2026, 10, 12, 6, 55)), datetime(2026, 10, 12, 6, 55))
        self.assertIsNone(states.parse_ts("не дата"))
