"""AC-41…AC-52, AC-78 (M-11, R-15…R-18): навчальна тривога."""
from types import SimpleNamespace
from unittest import mock

from freezegun import freeze_time

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from .common import FireCase


@tagged('post_install', '-at_install', 'f3d', 'f3d_fire')
class TestDrill(FireCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env['hr.attendance'].sudo().search([]).unlink()
        cls.env['f3d.fire.drill'].sudo().search([]).unlink()

    def setUp(self):
        super().setUp()
        # без factory3d_access: інакше його джерело (пріоритет 10) перекриває hr_attendance (AC-53)
        Base = type(self.env['f3d.fire.passage.source'])
        real = Base._f3d_source_names
        self.real_source_names = lambda: real(self.env['f3d.fire.passage.source'])
        patcher = mock.patch.object(
            Base, '_f3d_source_names',
            lambda model: [n for n in real(model) if n != 'f3d.fire.passage.source.access'])
        patcher.start()
        self.addCleanup(patcher.stop)

    def drill(self, **vals):
        vals.setdefault('zone_id', self.z_cnc.id)
        vals.setdefault('device_id', self.dev_cnc05.id)
        return self.new_drill(**vals)

    def start_at(self, drill, s=0):
        with freeze_time(self.at(s)):
            drill.action_start()
        return drill

    def log(self, etype, s, code='FA-CNC', **kw):
        return self.env['f3d.fire.event']._log(etype, code, self.at(s), 'Тест %s' % etype, **kw)

    # --- AC-41 -------------------------------------------------------------------------------------------
    def test_name_and_steps(self):
        d = self.drill()
        self.assertRegex(d.name, r'^DRILL/\d{4}/\d{4}$')
        self.assertEqual(len(d.step_ids), 8)
        steps = d.step_ids.sorted('sequence')
        self.assertEqual(steps[0].text, 'Сповіщувач 2.CNC.05 (%s): дим і тепло — тривога на приладі.' % self.z_cnc.name)
        sounders = self.env['f3d.fire.device'].search_count([('type', '=', 'sounder'), ('active', '=', True)])
        self.assertEqual(steps[1].text, 'Увімкнено %d сирен-маяків по всьому цеху.' % sounders)
        self.assertEqual(sounders, 41)

    # --- AC-42 -------------------------------------------------------------------------------------------
    def test_transitions(self):
        d = self.drill()
        with self.assertRaisesRegex(ValidationError, 'Вкажіть дату й час навчання'):
            d.action_plan()
        d.planned_ts = self.at(600)
        d.action_plan()
        self.assertEqual(d.state, 'planned')
        d2 = self.drill()
        self.start_at(d)
        self.assertEqual(d.state, 'running')
        with self.assertRaisesRegex(UserError, 'Уже триває навчання'):
            d2.action_start()
        with self.assertRaises(ValidationError):
            d2.sudo().write({'state': 'running'})
        with self.assertRaises(UserError):
            d.unlink()
        with freeze_time(self.at(30)):
            d.action_stop()
        self.assertEqual(d.state, 'evaluating')
        with self.assertRaisesRegex(UserError, 'Оберіть результат навчання'):
            d.action_close()
        d.result = 'ok'
        with self.assertRaisesRegex(UserError, 'Заповніть висновки'):
            d.action_close()
        d.conclusions = 'Усе гаразд'
        d.action_close()
        self.assertEqual(d.state, 'done')
        d2.action_cancel()
        self.assertEqual(d2.state, 'cancelled')
        d2.action_reset_draft()
        self.assertEqual(d2.state, 'draft')
        d2.unlink()

    # --- AC-43 -------------------------------------------------------------------------------------------
    def test_start_people(self):
        e = [self.make_employee('Людина %d' % i) for i in range(5)]
        for i in range(3):
            self.make_att(e[i], self.at(-3600))
        self.make_att(e[3], self.at(-7200), self.at(-3600))
        self.make_att(e[4], self.at(60))
        d = self.start_at(self.drill())
        self.assertEqual(d.on_site_count, 3)
        self.assertEqual(d.passage_source, 'hr_attendance')
        self.assertEqual(d.sudo().person_ids.mapped('seq'), [1, 2, 3])
        self.assertTrue(self.ev('drill_start', drill_id=d.id))

    # --- AC-44 -------------------------------------------------------------------------------------------
    def test_passages_rollcall_result(self):
        e = [self.make_employee('Людина %d' % i) for i in range(3)]
        atts = [self.make_att(x, self.at(-3600)) for x in e]
        d = self.start_at(self.drill())
        atts[0].check_out = self.at(95)
        atts[1].check_out = self.at(140)
        with freeze_time(self.at(150)):
            d._tick()
        persons = d.sudo().person_ids
        self.assertEqual(sorted(persons.mapped('exit_s')), [0, 95, 140])
        self.assertEqual(d.evacuated_count, 2)
        with freeze_time(self.at(200)):
            d.action_stop()
        self.assertEqual((d.evac_time_s, d.missing_count, d.result_suggested), (140, 1, 'failed'))
        wiz = self.env['f3d.fire.drill.rollcall.wizard'].with_user(self.d).with_context(
            default_drill_id=d.id).create({'drill_id': d.id})
        self.assertEqual(len(wiz.line_ids), 1)
        wiz.line_ids.present = True
        wiz.action_apply()
        self.assertEqual((d.present_count, d.missing_count, d.evac_pct, d.data_quality, d.result_suggested),
                         (1, 0, 100.0, 'partial', 'remarks'))
        d.write({'result': 'remarks', 'conclusions': 'Є зауваження'})
        d.action_close()
        self.assertEqual(d.state, 'done')

    def test_rollcall_only_after_stop(self):
        d = self.start_at(self.drill())
        wiz = self.env['f3d.fire.drill.rollcall.wizard'].create({'drill_id': d.id})
        with self.assertRaisesRegex(UserError, 'Перекличка'):
            wiz.action_apply()

    # --- AC-45 -------------------------------------------------------------------------------------------
    def test_auto_steps(self):
        pending = self.drill()
        with self.assertRaises(UserError):
            pending.step_ids[:1].action_done_now()
        d = self.start_at(self.drill(zone_id=self.z_cnc.id))
        zone_id = self.z_cnc.id
        self.log('test', 2, zone_id=zone_id)
        self.log('sounders_on', 4)
        self.log('smoke_open', 11)
        with freeze_time(self.at(12)):
            d._tick()
        by_key = {s.auto_key: s for s in d.step_ids}
        for key, fact in (('detector', 2), ('sounders', 4), ('smoke', 11)):
            self.assertTrue(by_key[key].done, key)
            self.assertEqual((by_key[key].t_fact_s, by_key[key].done_by), (fact, 'auto'))
        self.assertFalse(by_key['brigade'].done)
        self.assertEqual(d.steps_done, 3)

    def test_manual_step(self):
        d = self.start_at(self.drill())
        step = d.step_ids.filtered(lambda s: s.auto_key == 'brigade')
        with freeze_time(self.at(7)):
            step.action_done_now()
        self.assertEqual((step.done_by, step.t_fact_s), ('manual', 7))
        step.action_undo()
        self.assertFalse(step.done)

    # --- AC-46 -------------------------------------------------------------------------------------------
    def test_match_planned(self):
        planned = self.drill(planned_ts=self.at(600))
        planned.action_plan()
        with freeze_time(self.at(0)):
            self.z_cnc._set_state('test', 'test-alarm', self.at(0), self.dev_cnc05)
        self.assertEqual((planned.state, planned.start_ts), ('running', self.at(0)))

    def test_match_planned_other_zone(self):
        planned = self.drill(planned_ts=self.at(300), zone_id=self.z_cut.id, device_id=False)
        planned.action_plan()
        with freeze_time(self.at(0)):
            self.z_cnc._set_state('test', 'test-alarm', self.at(0), self.dev_cnc05)
        self.assertEqual((planned.state, planned.zone_id, planned.device_id),
                         ('running', self.z_cnc, self.dev_cnc05))

    def test_auto_create(self):
        with freeze_time(self.at(0)):
            self.z_cnc._set_state('test', 'test-alarm', self.at(0), self.dev_cnc05)
        d = self.env['f3d.fire.drill'].search([])
        self.assertEqual(len(d), 1)
        self.assertEqual((d.origin, d.title, d.state), ('panel', 'Тест приладу: %s' % self.z_cnc.name, 'running'))
        self.assertTrue(self.ev('drill_auto', drill_id=d.id))

    def test_no_auto_create(self):
        self.env['ir.config_parameter'].sudo().set_param('factory3d.fire_safety.drill_auto_create', 'False')
        with freeze_time(self.at(0)):
            self.z_cnc._set_state('test', 'test-alarm', self.at(0), self.dev_cnc05)
        self.assertEqual(self.env['f3d.fire.drill'].search_count([]), 0)

    # --- AC-47 -------------------------------------------------------------------------------------------
    def test_real_alarm(self):
        d = self.start_at(self.drill())
        with freeze_time(self.at(5)):
            self.z_cut._set_state('alarm', 'alarm', self.at(5), None)
        self.assertTrue(d.real_alarm)
        self.assertTrue(self.ev('drill_real_alarm', drill_id=d.id))
        self.assertTrue(self.env['mail.activity'].search_count([('user_id', 'in', (self.guard1 | self.guard2).ids)]))

    def test_real_alarm_without_drill(self):
        with freeze_time(self.at(5)):
            self.z_cut._set_state('alarm', 'alarm', self.at(5), None)
        self.assertEqual(self.env['f3d.fire.drill'].search_count([]), 0)

    # --- AC-48 -------------------------------------------------------------------------------------------
    def test_auto_stop(self):
        d = self.start_at(self.drill())
        self.log('test', 0, zone_id=self.z_cnc.id)
        self.log('test_end', 300, zone_id=self.z_cnc.id)
        with freeze_time(self.at(450)):
            d._tick()
        self.assertEqual((d.state, d.end_ts), ('evaluating', self.at(300)))
        self.assertTrue(self.ev('drill_end', drill_id=d.id))

    def test_tabletop_no_auto_stop(self):
        d = self.start_at(self.drill(mode='tabletop'))
        self.log('test', 0, zone_id=self.z_cnc.id)
        self.log('test_end', 300, zone_id=self.z_cnc.id)
        with freeze_time(self.at(450)):
            d._tick()
        self.assertEqual(d.state, 'running')

    # --- AC-49 -------------------------------------------------------------------------------------------
    def test_sim_unavailable(self):
        if 'f3d.sim.run' in self.env:
            self.skipTest('iot_sim встановлено')
        d = self.drill(mode='sim')
        self.assertFalse(d.sim_available)
        with self.assertRaisesRegex(UserError, 'Модуль емулятора не встановлено'):
            d.action_start_sim()

    def test_sim_bridge(self):
        if 'f3d.sim.run' not in self.env:
            self.skipTest('iot_sim не встановлено')
        d = self.drill(mode='sim')
        Drill = type(self.env['f3d.fire.drill'])
        run = SimpleNamespace(name='RUN/2026/0007', state='running', message='')
        with mock.patch.object(Drill, '_f3d_sim_create_run', return_value=run) as create:
            d.action_start_sim()
        self.assertEqual(create.call_args.args[1],
                         {'zone': 'FA-CNC', 'detector': '2.CNC.05', 'real': False, 'duration_s': 300})
        self.assertEqual((d.sim_run_ref, d.state), ('RUN/2026/0007', 'running'))
        d2 = self.drill(mode='sim')
        d.action_cancel()
        failed = SimpleNamespace(name='RUN/2026/0008', state='failed', message='збій')
        with mock.patch.object(Drill, '_f3d_sim_create_run', return_value=failed):
            with self.assertRaisesRegex(UserError, 'збій'):
                d2.action_start_sim()
        self.assertEqual(d2.state, 'draft')

    # --- AC-50 -------------------------------------------------------------------------------------------
    def test_privacy(self):
        emp = self.make_employee('Конфіденційний Тестович')
        self.make_att(emp, self.at(-3600))
        d = self.start_at(self.drill())
        with self.assertRaises(AccessError):
            self.env['f3d.fire.drill.person'].with_user(self.u).search([])
        self.assertEqual(len(self.env['f3d.fire.drill.person'].with_user(self.hr).search([])), 1)
        Report = self.env['ir.actions.report']
        html = Report._render_qweb_html('factory3d_fire_safety.report_f3d_fire_drill', d.ids)[0].decode()
        self.assertNotIn('Конфіденційний Тестович', html)
        d.print_names = True
        html = Report._render_qweb_html('factory3d_fire_safety.report_f3d_fire_drill', d.ids)[0].decode()
        self.assertIn('Конфіденційний Тестович', html)

    # --- AC-51 -------------------------------------------------------------------------------------------
    def test_report_drill(self):
        d = self.drill()
        html = self.env['ir.actions.report']._render_qweb_html(
            'factory3d_fire_safety.report_f3d_fire_drill', d.ids)[0].decode()
        self.assertIn(d.name, html)
        self.assertEqual(html.count('f3d-drill-step'), 8)
        self.assertIn('Персональний список не друкується', html)

    # --- AC-52 -------------------------------------------------------------------------------------------
    def test_cron_tick(self):
        Drill = self.env['f3d.fire.drill']
        Drill._cron_tick()  # без running — нічого
        d = self.start_at(self.drill())
        self.assertFalse(d.last_tick_ts)
        with freeze_time(self.at(10)), mock.patch.object(type(Drill), '_tick', autospec=True,
                                                          side_effect=lambda s: s.write({'last_tick_ts': self.at(10)})) as tick:
            Drill._cron_tick()
        self.assertEqual(tick.call_count, 1)
        self.assertEqual(d.last_tick_ts, self.at(10))

    def test_is_active_at(self):
        d = self.start_at(self.drill())
        Drill = self.env['f3d.fire.drill']
        self.assertTrue(Drill._f3d_is_active_at(self.at(100)))
        self.assertFalse(Drill._f3d_is_active_at(self.at(-1)))
        with freeze_time(self.at(330)):
            d.action_stop()
        self.assertTrue(Drill._f3d_is_active_at(self.at(180)))
        self.assertFalse(Drill._f3d_is_active_at(self.at(360)))

    # --- AC-78 -------------------------------------------------------------------------------------------
    def _machines_fixture(self, states):
        """states: {'WC-T1': ('fault', секунди_last_ts), ...} — сигнали CM-02 для РЦ зони FA-CNC."""
        zone = self.z_cnc.zone_id
        signals = {}
        for code, (text, s) in states.items():
            wc = self.env['mrp.workcenter'].search([('f3d_code', '=', code)]) or self.env['mrp.workcenter'].create(
                {'name': code, 'f3d_code': code, 'f3d_zone_id': zone.id})
            sig = self.env['f3d.signal'].create({
                'code': 'workcenters/%s/machine_state' % code, 'name': 'Стан %s' % code, 'kind': 'state',
                'module': 'telemetry'})
            sig.sudo().write({'last_text': text, 'last_ts': self.at(s)})
            signals[code] = sig
        return signals

    def test_auto_step_machines(self):
        signals = self._machines_fixture({'WC-T1': ('working', -10), 'WC-T2': ('idle', -600)})
        d = self.start_at(self.drill())
        step = d.step_ids.filtered(lambda s: s.auto_key == 'machines')
        with freeze_time(self.at(5)):
            d._tick()
        self.assertFalse(step.done)  # WC-T1 працює
        signals['WC-T1'].sudo().write({'last_text': 'fault', 'last_ts': self.at(20)})
        with freeze_time(self.at(25)):
            d._tick()
        self.assertEqual((step.done, step.done_by, step.t_fact_s), (True, 'auto', 20))

    def test_auto_step_machines_idle_before_start(self):
        self._machines_fixture({'WC-T1': ('idle', -900), 'WC-T2': ('idle', -600)})
        d = self.start_at(self.drill())
        step = d.step_ids.filtered(lambda s: s.auto_key == 'machines')
        with freeze_time(self.at(5)):
            d._tick()
        self.assertEqual((step.done, step.t_fact_s), (True, 0))

    def test_auto_step_machines_nodata(self):
        signals = self._machines_fixture({'WC-T1': ('nodata', -10)})
        d = self.start_at(self.drill())
        step = d.step_ids.filtered(lambda s: s.auto_key == 'machines')
        with freeze_time(self.at(5)):
            d._tick()
        self.assertFalse(step.done)
