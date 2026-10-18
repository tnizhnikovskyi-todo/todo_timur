from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo.addons.td_telemetry.tests.common import F3DTelemetryCase
from odoo.tests import tagged

TAGS = ("post_install", "-at_install", "f3d", "f3d_telemetry_viewer")
FREEZE = "2026-10-14 06:11:00"


class ProviderCase(F3DTelemetryCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_telemetry_fixtures()
        cls.sig_vac = cls.env["td.signal"].create(
            {
                "code": "equipment/GANTRY-T/vacuum_kpa",
                "name": "Вакуум",
                "kind": "gauge",
                "unit": "кПа",
                "source_id": cls.src_mb.id,
                "address": {"fc": 3, "addr": 3050, "type": "i16"},
                "origin": "manual",
            }
        )
        cls.provider = cls.env["td.viewer.provider.telemetry"]

    def setUp(self):
        super().setUp()
        frozen = freeze_time(FREEZE)
        frozen.start()
        self.addCleanup(frozen.stop)

    def fill(self):
        self.push(
            [
                self.rd(self.sig_bat, 23.6, at=0),
                self.rd(self.sig_flstate, text="charging", at=0),
                self.rd(self.sig_hours, 17846.6, at=0),
                self.rd(self.sig_press, 6.772, at=600),
                self.rd(self.sig_vac, -71.9, at=0),
                self.rd(self.sig_water, 18642.37, at=0),
                self.rd(self.sig_flx, 1.0, at=0),
            ]
        )


@tagged(*TAGS)
class TestCollect(ProviderCase):
    def payload(self):
        return {
            "equipment": {
                "FL-C1-T": {"battery": 0.5, "state": "idle", "hours": 0},
                "COMPRESSOR-T": {"pressure_bar": 0, "hours": 0},
                "GANTRY-T": {"vacuum_kpa": 0},
            },
            "infra": {"totals": {"pv_now": 12.5, "chp_kw": 397.3}},
            "energy": {"totals": {}},
            "meta": {},
        }

    def test_values_and_meta(self):
        self.fill()
        payload = self.payload()
        self.provider._f3d_viewer_collect(payload, {})
        eq = payload["equipment"]
        self.assertEqual(eq["FL-C1-T"]["battery"], 0.236)
        self.assertEqual(eq["FL-C1-T"]["state"], "charging")
        self.assertEqual(eq["FL-C1-T"]["hours"], 0)  # sig_fl2_hours — інше обладнання, без показань
        self.assertEqual(eq["COMPRESSOR-T"]["hours"], 17846.6)
        self.assertEqual(eq["COMPRESSOR-T"]["pressure_bar"], 6.77)
        self.assertEqual(eq["GANTRY-T"]["vacuum_kpa"], -71.9)
        self.assertEqual(payload["energy"]["totals"], {"pv_kw": 12.5, "chp_kw": 397.3})
        visible = self.env["td.signal"].search_count(
            [("active", "=", True), ("viewer_visible", "=", True), ("status", "!=", "unknown")]
        )
        self.assertEqual(
            payload["meta"]["iot"],
            {
                "source": "телеметрія (td_telemetry)",
                "signals": visible,
                "alarms": 0,
                "stale": 0,
                "updated": "2026-10-14 09:10",
            },
        )

    def test_missing_node_skipped(self):
        self.fill()
        payload = self.payload()
        self.provider._f3d_viewer_collect(payload, {})
        self.assertNotIn("WATER-T", payload["infra"])
        self.assertEqual(set(payload["infra"]), {"totals"})

    def test_invisible_and_unknown_skipped(self):
        self.fill()
        payload = self.payload()
        payload["equipment"]["FL-C1-T"]["x"] = "orig"
        self.provider._f3d_viewer_collect(payload, {})
        self.assertEqual(payload["equipment"]["FL-C1-T"]["x"], "orig")
        self.assertEqual(self.sig_fl2_hours.status, "unknown")
        self.assertNotIn("FL-2-T", payload["equipment"])

    def test_provider_sequence(self):
        self.assertEqual(self.provider._f3d_sequence, 95)
        self.assertEqual(self.provider._f3d_sections, ())


@tagged(*TAGS)
class TestDelta(ProviderCase):
    def test_delta(self):
        self.fill()
        patch_ = {}
        ctx = {"changes": {"td.signal": {"equipment/FL-C1-T/battery", "equipment/FL-C1-T/x"}}}
        self.provider._f3d_viewer_delta(patch_, ctx)
        self.assertEqual(patch_["signals"], [{"path": "equipment/FL-C1-T/battery", "value": 0.236}])
        self.assertIn("iot", patch_["meta"])

    def test_empty_changes(self):
        self.fill()
        patch_ = {}
        self.provider._f3d_viewer_delta(patch_, {"changes": {}})
        self.assertEqual(patch_, {})

    def test_bus_models(self):
        self.assertEqual(self.provider._f3d_viewer_bus_models(), ["td.signal"])


@tagged(*TAGS)
class TestBus(ProviderCase):
    def test_debounce_10s(self):
        if "td.viewer.event" not in self.env:
            self.skipTest("td_viewer3d не встановлено: немає td.viewer.event")
        Event = type(self.env["td.viewer.event"])
        with patch.object(Event, "_notify") as notify:
            for at, value in ((0, 50), (5, 49), (10, 48)):
                with freeze_time(self.T0 + timedelta(seconds=at)):
                    self.push([self.rd(self.sig_bat, value, at=at)])
            sent = [call.args[1] for call in notify.call_args_list]
        self.assertEqual(sent, [[self.sig_bat.code], [self.sig_bat.code]])

    def test_state_change_immediate(self):
        if "td.viewer.event" not in self.env:
            self.skipTest("td_viewer3d не встановлено: немає td.viewer.event")
        Event = type(self.env["td.viewer.event"])
        with patch.object(Event, "_notify") as notify:
            for at, text in ((0, "busy"), (3, "charging")):
                with freeze_time(self.T0 + timedelta(seconds=at)):
                    self.push([self.rd(self.sig_flstate, text=text, at=at)])
        self.assertEqual(notify.call_count, 2)

    def test_ingest_without_viewer(self):
        res = self.push([self.rd(self.sig_bat, 50, at=0)])
        self.assertEqual(res["rejected"], [])
