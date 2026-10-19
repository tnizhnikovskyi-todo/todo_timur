from unittest.mock import MagicMock, patch

from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import file_open

from ..models.td_access_event import F3dAccessEvent
from ..models.telemetry_bridge import F3dAccessTelemetry
from ..tools import params as P
from .common import AccessCase, FakeBioStar


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestSettings(AccessCase):

    def _settings(self, **vals):
        """Налаштування від адміністратора системи (execute() вимагає is_admin; поля — група F ⊂ system)."""
        return self.env['res.config.settings'].with_user(self.env.ref('base.user_admin')).create(vals)

    def test_params_roundtrip(self):  # AC-54
        self._settings(td_access_page_size=300, td_access_write_enabled=True,
                       td_access_visitor_user_prefix='VV-').execute()
        self.assertEqual(P.get_int(self.env, 'page_size', 500, 1, 2000), 300)
        self.assertTrue(P.get_flag(self.env, 'write_enabled'))
        self.assertEqual(P.get_str(self.env, 'visitor_user_prefix'), 'VV-')
        self._settings(td_access_write_enabled=False, td_access_overlap_s=0).execute()
        self.assertFalse(P.get_flag(self.env, 'write_enabled'))
        self.assertEqual(P.get_int(self.env, 'overlap_s', 120, 0, 3600), 0)

    def test_ranges(self):  # AC-54
        for field, bad in (('td_access_page_size', 3000), ('td_access_page_size', 0), ('td_access_overlap_s', 4000),
                           ('td_access_max_shift_h', 25), ('td_access_keep_days', 4000)):
            with self.subTest(field=field, bad=bad), self.assertRaisesRegex(ValidationError, 'допустимо'):
                self._settings(**{field: bad}).execute()
        for field, bad in (('td_access_visitor_user_prefix', 'TOO-LONG-PREFIX'),
                           ('td_access_visitor_user_group_id', '12a')):
            with self.subTest(field=field), self.assertRaises(ValidationError):
                self._settings(**{field: bad}).execute()

    def test_password_groups(self):  # AC-54, ТБ-02
        fields_admin = self.env['res.config.settings'].with_user(self.user_admin).fields_get()
        self.assertNotIn('td_access_biostar_password', fields_admin)
        fields_sys = self.env['res.config.settings'].with_user(self.env.ref('base.user_admin')).fields_get()
        self.assertIn('td_access_biostar_password', fields_sys)
        self.assertEqual(self.env['res.config.settings'].with_user(self.user_f3d_admin).fields_get().keys()
                         & {'td_access_biostar_password'}, {'td_access_biostar_password'})

    def test_read_disabled(self):  # AC-55
        P.set_param(self.env, 'read_enabled', 'False')
        fake = FakeBioStar()
        Server = self.env['td.access.server']
        with self.patch_client(fake):
            Server._cron_poll()
            Server._cron_sync_users()
            Server._cron_sync_devices()
            self.env['td.access.event']._cron_housekeeping()
        self.assertEqual(fake.calls, [])
        server = self.server.with_user(self.user_admin)
        with self.patch_client(fake):
            for action in (server.action_poll_now, server.action_sync_users):
                with self.assertRaisesRegex(UserError, 'вимкнено стоп-краном td.access.read_enabled'):
                    action()
        self.assertEqual(fake.calls, [])

    def test_neutralize_sql(self):  # AC-57
        self.server.sudo().write({'session_id': 's1', 'state': 'online'})
        card = self.env['td.access.card'].create({
            'number': '777', 'server_id': self.server.id, 'holder_type': 'employee', 'employee_id': self.emp_a.id})
        card.sudo().write({'sync_state': 'pending', 'pending_op': 'issue'})
        P.set_param(self.env, 'read_enabled', 'True')
        P.set_param(self.env, 'write_enabled', 'True')
        P.set_param(self.env, 'biostar_password', 'S3cr3t!')
        self.env.flush_all()
        with file_open('td_access/data/neutralize.sql') as fh:
            self.env.cr.execute(fh.read())
        self.env.invalidate_all()
        crons = self.env['ir.cron'].with_context(active_test=False).search([
            ('id', 'in', self.env['ir.model.data'].search([
                ('module', '=', 'td_access'), ('model', '=', 'ir.cron')]).mapped('res_id'))])
        self.assertEqual(len(crons), 6)
        self.assertFalse(any(crons.mapped('active')))
        self.assertEqual(P.get_str(self.env, 'read_enabled'), 'False')
        self.assertEqual(P.get_str(self.env, 'write_enabled'), 'False')
        self.assertEqual(P.get_str(self.env, 'biostar_password', 'ABSENT'), 'ABSENT')
        server = self.server.sudo()
        self.assertEqual((server.session_id, server.state), (False, 'offline'))
        self.assertEqual(card.sudo().sync_state, 'local')
        fake = FakeBioStar()
        with self.patch_client(fake):
            self.env['td.access.server']._cron_poll()
        self.assertEqual(fake.calls, [])

    def _three_events(self):
        return [self.prow(1, '2026-10-12T03:52:00.00Z', 4102, 'TSTA1', tna='1'),
                self.prow(2, '2026-10-12T03:53:00.00Z', 4102, 'TSTB2', where='elec'),
                self.prow(3, '2026-10-12T03:54:00.00Z', 4102, 'TSTA1', where='elec')]

    def test_telemetry_publish(self):  # AC-53
        fake_signal = MagicMock()
        fake_signal._td_ingest.return_value = {'accepted': 4, 'rejected': []}
        with patch.object(F3dAccessTelemetry, '_td_signal_model', return_value=fake_signal):
            self.poll('2026-10-12 04:00:00', FakeBioStar(events=self._three_events()))
        fake_signal._td_ingest.assert_called_once()
        readings = fake_signal._td_ingest.call_args.args[0]
        self.assertEqual(fake_signal._td_ingest.call_args.kwargs, {'src': 'module'})
        self.assertEqual({r['code'] for r in readings}, {
            'access/readers/ACR-IN/last_event', 'access/readers/ACR-ELEC/last_event',
            'access/turnstiles/TURNSTILES/on_site', 'access/events'})
        self.assertFalse(any('TSTA1' in str(r.get('text', '')) for r in readings))
        by_code = {r['code']: r for r in readings}
        self.assertEqual(by_code['access/readers/ACR-ELEC/last_event']['text'], '4102 DOOR-ELEC')
        self.assertEqual(by_code['access/events']['value'], 3.0)
        self.assertEqual(by_code['access/events']['text'], 'pass:3 denied:0 door:0')

    def test_telemetry_off(self):  # AC-53
        fake_signal = MagicMock()
        with patch.object(F3dAccessTelemetry, '_td_signal_model', return_value=fake_signal):
            P.set_param(self.env, 'publish_signals', 'False')
            self.poll('2026-10-12 04:00:00', FakeBioStar(events=self._three_events()))
            P.set_param(self.env, 'publish_signals', 'True')
            self.poll('2026-10-12 04:00:00', FakeBioStar(events=[]))
        fake_signal._td_ingest.assert_not_called()
        with patch.object(F3dAccessTelemetry, '_td_signal_model', return_value=None):
            self.poll('2026-10-12 04:10:00', FakeBioStar(events=[self.prow(9, '2026-10-12T04:05:00.00Z', 4102,
                                                                           'TSTA1', tna='2')]))
        self.assertIsNone(self.env['td.access.telemetry']._td_publish(self.server, self.env['td.access.event']))

    def test_telemetry_failure_isolated(self):  # R-18
        fake_signal = MagicMock()
        fake_signal._td_ingest.side_effect = RuntimeError('boom')
        with patch.object(F3dAccessTelemetry, '_td_signal_model', return_value=fake_signal), \
                self.assertLogs('odoo.addons.td_access.models.td_access_server', 'WARNING'):
            res = self.poll('2026-10-12 04:00:00', FakeBioStar(events=self._three_events()))
        self.assertEqual(res['new'], 3)
        self.assertTrue(F3dAccessEvent)
