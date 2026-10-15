"""AC-17…AC-27, AC-67 (R-10…R-13, R-19, A-22): синхронізація станів із сигналами."""
from unittest import mock

from odoo.tests import tagged

from ..tools import states
from .common import FireCase

ACT_XMLID = 'factory3d_fire_safety.mail_act_fire_alarm'
SYNC_RUN = 'odoo.addons.factory3d_fire_safety.tools.sync.FireSync.run'


class SyncCase(FireCase):

    def activities(self, summary_prefix=None):
        act_type = self.env.ref(ACT_XMLID)
        acts = self.env['mail.activity'].search([
            ('activity_type_id', '=', act_type.id), ('res_model', '=', 'f3d.fire.panel'),
            ('res_id', '=', self.panel.id)])
        if summary_prefix:
            acts = acts.filtered(lambda a: (a.summary or '').startswith(summary_prefix))
        return acts

    def requests_for(self, code):
        sig = self.env['f3d.signal'].search([('code', '=', code)])
        return self.env['maintenance.request'].search([('f3d_signal_id', '=', sig.id)])


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestZones(SyncCase):

    def test_alarm_cycle(self):
        self.push_text('fire/totals/state', 'alarm', self.at(0))
        self.push_text('fire/groups/FA-CUT/state', 'alarm', self.at(0))
        self.assertEqual(self.z_cut.state, 'alarm')
        event = self.ev('alarm', object_code='FA-CUT')
        self.assertEqual(event.text, 'ТРИВОГА: зона FA-CUT (Розкрій)')
        acts = self.activities()
        self.assertEqual(acts.mapped('user_id'), self.guard1 | self.guard2)
        self.assertEqual(len(acts), 2)
        self.assertFalse(self.requests_for('fire/groups/FA-CUT/state'))
        self.push_text('fire/totals/state', 'quiet', self.at(10))
        self.push_text('fire/groups/FA-CUT/state', 'quiet', self.at(10))
        self.assertEqual(self.z_cut.state, 'normal')
        self.assertTrue(self.ev('reset', object_code='FA-CUT'))
        self.assertTrue(self.ev('reset', object_code='FACP-1'))
        self.assertFalse(self.activities())

    def test_states_table(self):
        table = {
            'quiet': ('normal', 'normal', False), 'pre-alarm': ('prealarm', 'prealarm', False),
            'alarm': ('alarm', 'alarm', False), 'fault': ('fault', 'fault', True),
            'fault-pre-alarm': ('prealarm', 'prealarm', False), 'fault-alarm': ('alarm', 'alarm', False),
            'not-ready': ('disabled', 'disabled', False), 'active': ('alarm', 'active', False),
            'tamper': ('fault', 'fault', True), 'test-alarm': ('test', 'test', False),
            'test-active': ('test', 'test', False), 'test-fault': ('test', 'test', False),
            'test-fault-alarm': ('test', 'test', False), 'holdup': ('alarm', 'alarm', False),
            'duress': ('alarm', 'alarm', False), 'tamper-alarm': ('alarm', 'alarm', False),
            'abnormal': ('fault', 'fault', True), 'emergency-power': ('fault', 'fault', True),
            'delayed': ('prealarm', 'prealarm', False), 'blocked': ('disabled', 'disabled', False),
            'local-alarm': ('prealarm', 'prealarm', False), 'general-alarm': ('alarm', 'alarm', False),
            'supervisory': ('fault', 'fault', True), 'test-supervisory': ('test', 'test', False)}
        self.assertEqual(len(table), 24)
        for text, (zone, device, fault) in table.items():
            self.assertEqual(states.ZONE_MAP[text], zone, text)
            self.assertEqual(states.DEVICE_MAP[text], device, text)
            self.assertEqual(text in states.FAULT_STATES, fault, text)
        self.assertEqual(states.zone_state('9'), 'test')
        self.assertEqual(states.zone_state('xyz'), 'unknown')
        self.assertEqual(states.device_state('7'), 'active')

    def test_loop_fault(self):
        self.push_text('fire/loops/2/state', 'on', self.at(0))
        self.assertEqual(self.loop2.state, 'fault')
        self.assertEqual(self.loop2.fault_since, self.at(0))
        self.assertEqual(self.ev('loop_fault').text, 'Несправність шлейфу 2 приладу FACP-1')
        self.push_text('fire/loops/2/state', 'off', self.at(10))
        self.assertEqual(self.loop2.state, 'ok')
        self.assertTrue(self.ev('loop_ok'))

    def test_stale_keeps_state(self):
        self.push_text('fire/groups/FA-EB/state', 'pre-alarm', self.at(0))
        self.assertEqual(self.z_eb.state, 'prealarm')
        sig = self.env['f3d.signal'].search([('code', '=', 'fire/groups/FA-EB/state')])
        sig.write({'status': 'stale'})
        self.sync(30)
        self.assertTrue(self.z_eb.stale)
        self.assertEqual(self.z_eb.state, 'prealarm')

    def test_unknown_text(self):
        self.push_text('fire/groups/FA-EB/state', 'xyz', self.at(0))
        self.assertEqual((self.z_eb.state, self.z_eb.raw_state), ('unknown', 'xyz'))
        self.assertFalse(self.ev('alarm', object_code='FA-EB'))

    def test_idempotent(self):
        self.push_text('fire/groups/FA-CUT/state', 'fault', self.at(0))
        self.push_text('fire/totals/state', 'quiet', self.at(0))
        self.sync()
        res = self.sync()
        self.assertEqual((res['changed'], res['events']), (0, 0))


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestPanel(SyncCase):

    def test_priority(self):
        self.push_text('fire/totals/state', 'quiet', self.at(0))
        self.push_text('fire/totals/system_state', 'normal', self.at(0))
        self.assertEqual(self.panel.state, 'normal')
        self.push_text('fire/totals/system_state', 'fault', self.at(10))
        self.assertEqual(self.panel.state, 'fault')
        self.assertEqual(self.panel.system_state, 3)
        self.push_text('fire/totals/state', 'test-alarm', self.at(20))
        self.push_text('fire/totals/system_state', 'test', self.at(20))
        self.assertEqual(self.panel.state, 'test')
        self.assertEqual(self.panel.raw_state, 'test-alarm')

    def test_state_text_plural(self):
        self.push_text('fire/totals/state', 'quiet', self.at(0))
        self.assertEqual(self.panel.comm, 'online')
        self.assertEqual(self.panel.state_text, 'Норма')
        devices = self.env['f3d.fire.device']
        seen = set()
        for dev in self.env['f3d.fire.device'].search([('type', 'in', ('smoke', 'multi', 'heat'))]):
            if dev.zone_id.id not in seen and len(seen) < 5:
                seen.add(dev.zone_id.id)
                devices |= dev
        devices[0].write({'dust_pct': 85, 'dust_ts': self.T0})
        self.assertEqual(self.panel.state_text, 'Норма, 1 попередження')
        devices.write({'dust_pct': 85, 'dust_ts': self.T0})
        self.assertEqual(self.panel.state_text, 'Норма, 5 попереджень')
        self.panel.comm = 'lost'
        self.assertEqual(self.panel.state_text, "Зв'язок із приладом втрачено")

    def test_read_disabled(self):
        self.env['ir.config_parameter'].sudo().set_param('factory3d.fire_safety.read_enabled', 'False')
        self.panel._cron_sync()
        self.assertEqual(self.panel.comm, 'off')
        self.assertEqual(self.panel.state_text, 'Обробка вимкнена')
        self.push_text('fire/groups/FA-CUT/state', 'alarm', self.at(0))
        self.assertEqual(self.z_cut.state, 'unknown')
        self.assertFalse(self.ev('alarm'))


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestDust(SyncCase):

    CODE = 'fire/groups/FA-FAC/dust'

    def test_dust_cycle(self):
        self.push_value(self.CODE, 82, self.at(0))
        self.assertEqual(self.dev_fac07.dust_state, 'warn')
        self.assertTrue(self.z_fac.warn)
        self.assertRegex(self.z_fac.warning, r'^Сповіщувач 2\.FAC\.07\b.*запиленість камери 82 % — очистити до кінця '
                         r'зміни, інакше прилад переведе його в несправність\.$')
        self.assertTrue(self.ev('dust_warn'))
        self.push_value(self.CODE, 90.1, self.at(60))
        self.assertEqual(self.dev_fac07.dust_state, 'alarm')
        self.assertTrue(self.ev('dust_alarm'))
        request = self.requests_for(self.CODE)
        self.assertEqual(len(request), 1)
        self.assertEqual(request.f3d_fire_device_id, self.dev_fac07)
        self.assertEqual(request.f3d_fire_zone_id, self.z_fac)
        self.assertEqual(request.maintenance_team_id, self.team)
        self.push_value(self.CODE, 79, self.at(120))
        self.assertEqual(self.dev_fac07.dust_state, 'ok')
        self.assertTrue(self.ev('dust_ok'))
        self.assertFalse(self.z_fac.warning)


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestComm(SyncCase):

    def test_comm_sequence(self):
        self.assertTrue(self.panel.first_sync)
        self.sync(0)
        self.assertEqual(self.panel.comm, 'lost')
        self.assertFalse(self.ev('comm_lost') | self.ev('comm_restored'))
        self.assertFalse(self.requests_for('fire/totals/state'))
        self.push_text('fire/totals/state', 'quiet', self.at(0))
        self.assertEqual(self.panel.comm, 'online')
        self.assertTrue(self.ev('comm_restored'))
        self.assertFalse(self.panel.first_sync)
        self.sync(100)
        self.assertEqual(self.panel.comm, 'stale')
        self.assertTrue(self.ev('comm_stale'))
        self.sync(185)
        self.assertEqual(self.panel.comm, 'lost')
        lost = self.ev('comm_lost')
        self.assertEqual(lost.text, "Зв'язок із приладом FACP-1 втрачено: немає даних з 10:00 (3 хв)")
        self.assertEqual(self.activities("Втрата зв'язку").mapped('user_id'), self.guard1 | self.guard2)
        request = self.env['maintenance.request'].search([('f3d_origin', '=', 'fire_comm')])
        self.assertEqual(len(request), 1)
        self.assertEqual(request.name, "Втрата зв'язку з приладом FACP-1: немає даних з 10:00 (3 хв)")
        self.assertEqual(lost.request_id, request)
        self.assertEqual(self.panel.comm_request_id, request)
        # відновлення й нова втрата при відкритій заявці
        self.push_value('fire/totals/alarms', 0, self.at(300))
        self.assertEqual(self.panel.comm, 'online')
        self.assertFalse(self.activities("Втрата зв'язку"))
        self.sync(600)
        self.assertEqual(self.panel.comm, 'lost')
        self.assertEqual(self.env['maintenance.request'].search_count([('f3d_origin', '=', 'fire_comm')]), 1)
        self.assertFalse(request.stage_id.done)


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestSystems(SyncCase):

    def test_spark(self):
        self.push_value('fire/spark/SPARK-1/count_today', 2, self.at(0))
        self.assertEqual(self.sys_spark.state, 'ok')
        self.assertEqual(self.sys_spark.count_today, 2)
        self.assertEqual(
            self.ev('spark').text,
            'Іскрогасіння: іскру виявлено на магістралі аспірації (2 шт.), гасіння спрацювало; за добу — 2.')
        self.push_value('fire/spark/SPARK-1/count_today', 0, self.at(10))
        self.assertEqual(self.sys_spark.count_today, 0)
        self.assertEqual(len(self.ev('spark')), 1)
        self.push_text('fire/spark/SPARK-1/fault', 'on', self.at(20))
        self.assertEqual(self.sys_spark.state, 'fault')
        self.assertTrue(self.ev('spark_fault'))
        self.push_text('fire/spark/SPARK-1/fault', 'off', self.at(30))
        self.push_text('fire/spark/SPARK-1/water_ok', 'low', self.at(40))
        self.assertEqual(self.sys_spark.state, 'fault')
        self.assertIn('немає тиску води', self.sys_spark.state_text)
        self.assertTrue(self.ev('spark_water_low'))
        self.assertTrue(self.ev('spark_fault_ok'))
        # усі сигнали stale → unknown, comm_lost (warn)
        self.env['f3d.signal'].search([('code', 'like', 'fire/spark/SPARK-1/%')]).write({'status': 'stale'})
        self.sync(500)
        self.assertEqual(self.sys_spark.state, 'unknown')
        self.assertTrue(self.sys_spark.stale)
        lost = self.ev('comm_lost', object_code='SPARK-1')
        self.assertEqual(lost.level, 'warn')
        self.assertFalse(self.env['maintenance.request'].search([('f3d_origin', '=', 'fire_comm')]))

    def test_smoke_sprinkler(self):
        self.push_text('fire/smoke/SMOKE-VENTS/state', 'open', self.at(0))
        self.assertEqual(self.sys_smoke.state, 'active')
        self.assertIn('(44 шт.)', self.ev('smoke_open').text)
        self.push_text('fire/smoke/SMOKE-CTRL/battery', 'battery', self.at(10))
        self.assertEqual(self.sys_smoke.state, 'battery')
        self.push_text('fire/smoke/SMOKE-CTRL/fault', 'fault', self.at(20))
        self.assertEqual(self.sys_smoke.state, 'fault')
        self.assertTrue(self.ev('smoke_fault'))
        self.assertTrue(self.ev('smoke_battery'))
        self.push_value('equipment/SPRINKLERS/pressure_bar', 6.2, self.at(30))
        self.assertEqual(self.sys_spr.state, 'low_pressure')
        self.assertEqual(self.ev('sprinkler_low').text, 'Спринклерна система: тиск 6,2 бар нижче норми 6,5 бар')
        self.push_value('equipment/SPRINKLERS/pressure_bar', 7.2, self.at(40))
        self.assertEqual(self.sys_spr.state, 'ok')
        self.assertTrue(self.ev('sprinkler_ok'))


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestIngestHook(SyncCase):

    def test_immediate_sync(self):
        res = self.push_text('fire/groups/FA-EB/state', 'fault', self.at(0))
        self.assertTrue(res['changed_codes'])
        self.assertEqual(self.z_eb.state, 'fault')
        self.assertTrue(self.ev('fault', object_code='FA-EB'))

    def test_non_fire_code_skipped(self):
        self.env['f3d.signal'].create({
            'code': 'equipment/COMPRESSOR/pressure_bar', 'name': 'Тиск компресора', 'kind': 'gauge',
            'module': 'telemetry'})
        with mock.patch(SYNC_RUN) as run:
            self.push_value('equipment/COMPRESSOR/pressure_bar', 7.0, self.at(0))
            run.assert_not_called()
            self.push_text('fire/groups/FA-EB/state', 'fault', self.at(10))
            run.assert_called_once()
            self.assertEqual(run.call_args.kwargs['codes'], ['fire/groups/FA-EB/state'])

    def test_sync_exception_isolated(self):
        with mock.patch(SYNC_RUN, side_effect=RuntimeError('boom')), self.assertLogs(
                'odoo.addons.factory3d_fire_safety.models.f3d_signal', 'ERROR') as logs:
            res = self.push_text('fire/groups/FA-EB/state', 'fault', self.at(0))
        self.assertIn('fire sync after ingest', logs.output[0])
        self.assertIn('changed_codes', res)
        self.assertEqual(self.z_eb.state, 'unknown')
        self.sync()
        self.assertEqual(self.z_eb.state, 'fault')


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestAlarmActivity(SyncCase):

    def test_activity_per_guard(self):
        self.push_text('fire/groups/FA-CUT/state', 'alarm', self.at(0))
        self.assertEqual(len(self.activities()), 2)
        self.push_text('fire/groups/FA-EB/state', 'alarm', self.at(10))
        self.assertEqual(len(self.activities()), 2)  # друга зона при відкритій активності — нових немає
        self.assertEqual(self.panel.alarm_activity_id.activity_type_id, self.env.ref(ACT_XMLID))

    def test_reset_closes(self):
        self.push_text('fire/groups/FA-CUT/state', 'alarm', self.at(0))
        self.push_text('fire/totals/state', 'alarm', self.at(0))
        self.assertEqual(len(self.activities()), 2)
        self.push_text('fire/groups/FA-CUT/state', 'quiet', self.at(30))
        self.push_text('fire/totals/state', 'quiet', self.at(30))
        self.assertFalse(self.activities())
        self.assertFalse(self.panel.alarm_activity_id)
