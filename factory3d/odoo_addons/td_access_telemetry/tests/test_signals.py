import unittest
from datetime import timedelta

from freezegun import freeze_time

from odoo.tests import tagged
from odoo.fields import Datetime

from odoo.addons.factory3d_access.tests.common import AccessCase


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestAccessSignals(AccessCase):
    """AC-68: потребує встановленого factory3d_telemetry (міст ставиться автоматично)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        if 'f3d.signal' not in cls.env:
            raise unittest.SkipTest('factory3d_telemetry не встановлено')
        cls.Signal = cls.env['f3d.signal'].sudo().with_context(active_test=False)

    def _access_signals(self):
        return self.Signal.search([('code', '=like', 'access/%')])

    def test_bridge_installed_signals(self):
        bridge = self.env['ir.module.module'].sudo().search([('name', '=', 'factory3d_access_telemetry')])
        self.assertEqual(bridge.state, 'installed')
        signals = self._access_signals()
        self.assertEqual(len(signals), 7)
        by_code = {s.code: s for s in signals}
        for code in ('ACR-IN', 'ACR-ELEC', 'ACR-CHG', 'ACR-PAINT', 'ACR-SRV'):
            self.assertEqual(by_code['access/readers/%s/last_event' % code].kind, 'event')
        on_site = by_code['access/turnstiles/TURNSTILES/on_site']
        self.assertEqual((on_site.kind, on_site.unit), ('gauge', 'осіб'))
        self.assertEqual(by_code['access/events'].kind, 'event')
        for sig in signals:
            self.assertEqual((sig.module, sig.origin, sig.viewer_visible, sig.create_request, sig.period_s),
                             ('access', 'module', False, False, 60), sig.code)
            self.assertFalse(sig.source_id)

    def test_ensure_idempotent(self):
        self.assertEqual(self.env['f3d.access.telemetry']._f3d_ensure_signals(), {'created': 0, 'existing': 7})

    def test_new_device_signal(self):
        self.env['f3d.access.device'].sudo().create({
            'name': 'Тест', 'code': 'ACR-T9', 'server_id': self.server.id, 'biostar_id': '5399999'})
        self.assertTrue(self.Signal.search([('code', '=', 'access/readers/ACR-T9/last_event')]))

    def test_ingest_accepted(self):
        now = Datetime.now()
        res = self.env['f3d.signal'].sudo()._f3d_ingest(
            [{'code': 'access/turnstiles/TURNSTILES/on_site', 'ts': now, 'value': 35.0, 'q': 'good'}], src='module')
        self.assertEqual(res['accepted'], 1)
        self.assertEqual(res['rejected'], [])
        signal = self.Signal.search([('code', '=', 'access/turnstiles/TURNSTILES/on_site')])
        self.assertEqual(signal.last_value, 35)

    def test_no_stale_without_source(self):
        signal = self.Signal.search([('code', '=', 'access/events')])
        with freeze_time(Datetime.now() + timedelta(days=1)):
            self.env['f3d.signal']._cron_stale()
        self.assertNotEqual(signal.status, 'stale')
