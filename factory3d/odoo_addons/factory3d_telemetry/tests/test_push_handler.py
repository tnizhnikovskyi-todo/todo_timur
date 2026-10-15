import hashlib
from datetime import datetime
from unittest.mock import Mock, patch

from freezegun import freeze_time

from odoo.addons.factory3d_telemetry.models.push_handler import F3dPushHandler
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import F3DTelemetryCase

TAGS = ('post_install', '-at_install', 'f3d', 'f3d_telemetry')
FREEZE = '2026-10-14 05:15:10'
CAPTURE_MS = 1791954905507
CAPTURE = datetime(2026, 10, 14, 5, 15, 5, 507000)


def event(n=1, provider='CAM-05', capture=CAPTURE_MS, **payload):
    body = {"plateText": "AA4512KT", "carState": "new", "sensorProviderID": provider,
            "capture_timestamp": str(capture), **payload}
    return {"event_id": hashlib.sha256(str(n).encode()).hexdigest(), "route": "lpr",
            "ts": "2026-10-14T05:15:05.507Z", "remote": "10.90.2.5",
            "headers": {"content-type": "application/json"}, "payload": body}


@tagged(*TAGS)
class TestDispatch(F3DTelemetryCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_telemetry_fixtures()

    def setUp(self):
        super().setUp()
        frozen = freeze_time(FREEZE)
        frozen.start()
        self.addCleanup(frozen.stop)
        self.Event = self.env['f3d.push.event']

    def receive(self, events, models=None, handle=None):
        handle = handle or Mock()
        with patch.object(F3dPushHandler, '_f3d_handler_models', return_value=models or []), \
                patch.object(F3dPushHandler, '_f3d_handle_push', handle), \
                mute_logger('odoo.addons.factory3d_telemetry.models.f3d_push_event'):
            res = self.Event._f3d_receive(events, self.col)
        return res, handle

    def test_handler_called(self):
        res, handle = self.receive([event()], ['f3d.push.handler'])
        handle.assert_called_once()
        route, ev = handle.call_args.args
        self.assertEqual(route, 'lpr')
        self.assertEqual(set(ev), {'event_id', 'route', 'ts', 'remote', 'headers', 'payload'})
        self.assertEqual(ev['ts'], CAPTURE)
        self.assertEqual(res['handled'], {'lpr': ['f3d.push.handler']})
        rec = self.Event.search([('event_id', '=', event()['event_id'])])
        self.assertEqual(rec.handled_by, 'f3d.push.handler')

    def test_signal_reading_from_event(self):
        res, _h = self.receive([event()], ['f3d.push.handler'])
        self.assertEqual(res['accepted'], 1)
        reading = self.env['f3d.reading'].search([('signal_id', '=', self.sig_plate.id)])
        self.assertEqual((reading.text, reading.ts, reading.received_at), ('AA4512KT', CAPTURE,
                                                                          datetime(2026, 10, 14, 5, 15, 10)))
        self.assertEqual(self.Event.search([]).signal_count, 1)

    def test_match_mismatch(self):
        self.receive([event(provider='CAM-06')])
        self.assertFalse(self.env['f3d.reading'].search_count([('signal_id', '=', self.sig_plate.id)]))
        self.assertEqual(self.Event.search([]).signal_count, 0)

    def test_handler_exception_isolated(self):
        handle = Mock(side_effect=[ValueError('boom'), None])
        _res, handle = self.receive([event()], ['f3d.push.handler', 'f3d.push.handler'], handle)
        self.assertEqual(handle.call_count, 2)
        rec = self.Event.search([])
        self.assertIn('ValueError: boom', rec.error)
        self.assertEqual(self.sig_plate.last_text, 'AA4512KT')

    def test_numeric_scale_address_and_signal(self):
        sig = self.env['f3d.signal'].create({
            'code': 'yard/lpr/CAM-T/conf', 'name': 'conf', 'kind': 'gauge', 'source_id': self.src_http.id,
            'scale': 2.0, 'origin': 'manual',
            'address': {"route": "lpr", "match": {"sensorProviderID": "CAM-05"}, "path": "$.confidence",
                        "scale": 0.01}})
        self.receive([event(1, confidence=87)])
        self.assertAlmostEqual(sig.last_value, 1.74)
        sig.address = dict(sig.address, offset=0.1)
        with freeze_time('2026-10-14 05:15:20'):
            self.receive([event(2, confidence=87)])
        self.assertAlmostEqual(sig.last_value, 1.94)
        with freeze_time('2026-10-14 05:15:30'):
            self.receive([event(3, confidence='abc', plateText=None)])
        self.assertAlmostEqual(sig.last_value, 1.94)
        self.assertEqual(self.Event.search([('event_id', '=', event(3)['event_id'])]).signal_count, 0)

    def test_received_at_and_ts_fallback(self):
        self.receive([event(capture=CAPTURE_MS + 120000)])
        reading = self.env['f3d.reading'].search([('signal_id', '=', self.sig_plate.id)])
        received = datetime(2026, 10, 14, 5, 15, 10)
        self.assertEqual((reading.ts, reading.received_at, reading.quality), (received, received, 'uncertain'))
