# Part of td_genset (ToDo). Власник файлу: W0 «Каркас».
"""Димовий тест каркаса: установка, дані, групи, ACL, меню й подання, cron, bus, мок ретранслятора,
наявність і виклик інтерфейсів SPEC 9 (= ТР А.11).

Тести мають лишатися зеленими після наповнення потоками: нейтральні результати перевіряються лише для
методів, чий докстринг ще містить «Заглушка W0» (реалізуючи метод, потік прибирає цю позначку).
"""
import inspect
import json
from datetime import date, datetime, timedelta

import pytz
import requests

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from ..models.genset_reading import READING_FIELD_MAP
from ..models.genset_schedule import kyiv_localize
from .common import BASE_URL, HOSTID, TOKEN, TdGensetCase, snapshot

STUB_MARK = 'Заглушка W0'
IMPLEMENTED = object()
MODULE = 'odoo.addons.td_genset.models.'

# XML id з SPEC 6 / BUILD_PLAN W0
SPEC_XMLIDS = [
    'module_category_td_genset', 'group_user', 'group_admin', 'group_tech',
    'cron_pull_readings', 'cron_commands', 'cron_scheduler', 'cron_cleanup',
    'seq_canister', 'seq_command', 'seq_refuel',
    'mt_alarm', 'mt_command', 'mt_event', 'activity_refuel', 'activity_check',
    'equipment_category_genset', 'maintenance_team_genset',
    'controller_hgm6120n', 'controller_hgm6110n',
    'config_main', 'level_1', 'level_2', 'level_3',
    'export_reading_all',
]

# Модель → {метод: (файл-власник, сигнатура)} — SPEC 9 / ТР А.11
SPEC_METHODS = {
    'td.genset.relay.client': {
        '_base_url': ('relay_client', '(self)'),
        '_timeout': ('relay_client', '(self)'),
        '_headers': ('relay_client', '(self)'),
        '_request': ('relay_client', '(self, method, path, params=None, json=None)'),
        'status': ('relay_client', '(self)'),
        'device_status': ('relay_client', '(self, status, hostid)'),
        'latest': ('relay_client', '(self, hostid)'),
        'readings': ('relay_client', '(self, hostid, since, limit=500, raw=False)'),
        'post_command': ('relay_client', '(self, hostid, command, requested_by, source)'),
        'command': ('relay_client', '(self, relay_cmd_id)'),
        'commands': ('relay_client', '(self, since, limit=200)'),
    },
    'td.genset': {
        '_cron_pull_readings': ('genset_monitoring', '(self)'),
        '_apply_status': ('genset_monitoring', '(self, status)'),
        '_pull_readings_page': ('genset_monitoring', '(self, client)'),
        '_find_cursor_for_date': ('genset_monitoring', '(self, client, date)'),
        '_need_raw': ('genset_monitoring', '(self, status)'),
        '_apply_reading': ('genset_monitoring', '(self, reading)'),
        '_update_link_state': ('genset_monitoring', '(self, online, now=None)'),
        '_check_relay_health': ('genset_monitoring', '(self, status)'),
        '_finish_catchup': ('genset_monitoring', '(self, summary)'),
        'action_check_relay': ('genset_monitoring', '(self)'),
        'action_refresh': ('genset_monitoring', '(self)'),
        '_cron_scheduler': ('genset_scheduler', '(self)'),
        '_in_window': ('genset_scheduler', '(self, dt_kyiv)'),
        '_window_bounds': ('genset_scheduler', '(self, date_kyiv)'),
        '_next_transition': ('genset_scheduler', '(self, after_kyiv)'),
        '_follow_schedule': ('genset_scheduler', '(self, source, requested_by=None)'),
        '_timer_start': ('genset_scheduler', '(self, duration_min, user)'),
        '_timer_extend': ('genset_scheduler', '(self, minutes, user)'),
        '_timer_stop': ('genset_scheduler', '(self, user)'),
        '_test_start': ('genset_scheduler', '(self, mode, user)'),
        '_test_finish': ('genset_scheduler', '(self)'),
        '_compute_next_event_text': ('genset_scheduler', '(self)'),
        'action_open_command_wizard': ('genset_scheduler', '(self)'),
        'action_open_timer_wizard': ('genset_scheduler', '(self)'),
        'action_timer_extend_15': ('genset_scheduler', '(self)'),
        'action_timer_extend_30': ('genset_scheduler', '(self)'),
        'action_timer_extend_60': ('genset_scheduler', '(self)'),
        'action_timer_stop': ('genset_scheduler', '(self)'),
        'get_pult_state': ('genset_ui', '(self)'),
        '_compute_current_data_html': ('genset_ui', '(self)'),
        '_compute_timer_progress': ('genset_ui', '(self)'),
        '_compute_is_tech': ('genset_ui', '(self)'),
        '_compute_is_admin': ('genset_ui', '(self)'),
        '_check_fuel_stock': ('genset_fuel', '(self)'),
        '_fuel_stats': ('genset_fuel', '(self, days)'),
        '_liters_from_ohm': ('genset_fuel', '(self, ohm)'),
        '_compute_fuel_calibrated': ('genset_fuel', '(self)'),
        'action_recompute_liters': ('genset_fuel', '(self)'),
        '_ensure_equipment': ('genset_fuel', '(self)'),
        '_compute_maint': ('genset_fuel', '(self)'),
        '_check_maintenance': ('genset_fuel', '(self)'),
        '_notify_bus': ('genset', '(self, kind, payload=None)'),
        'action_open_readings': ('genset', '(self)'),
        'action_open_events': ('genset', '(self)'),
        'action_open_alarms': ('genset', '(self)'),
        'action_open_commands': ('genset', '(self)'),
        'action_open_maintenance': ('genset', '(self)'),
    },
    'td.genset.reading': {
        '_create_from_payload': ('genset_reading', '(self, genset, payloads)'),
        '_derive': ('genset_reading', '(self, values, genset)'),
        '_extract_sensor_ohms': ('genset_reading', '(self, payload)'),
        '_mark_journal': ('genset_reading', '(self, genset, slots)'),
        '_cron_cleanup': ('genset_reading', '(self)'),
    },
    'td.genset.event': {
        '_process_readings': ('genset_event', '(self, genset, readings)'),
        '_open': ('genset_event', '(self, genset, event_type, date_start, **vals)'),
        '_close': ('genset_event', '(self, event, date_end, **vals)'),
        '_detect_external_control': ('genset_event', '(self, genset, prev=None, cur=None, cloud=None)'),
    },
    'td.genset.alarm': {
        '_raise': ('genset_alarm', "(self, genset, code, level, name, description='', source=None, tech=False)"),
        '_clear': ('genset_alarm', "(self, genset, code, note='')"),
        '_can_ack': ('genset_alarm', '(self, user)'),
        'action_ack': ('genset_alarm', '(self)'),
        '_cron_escalate': ('genset_alarm', '(self)'),
        '_evaluate_current': ('genset_alarm', '(self, genset)'),
    },
    'td.genset.config': {
        'get': ('genset_config', '(self)'),
        '_quiet_now': ('genset_config', '(self, dt=None)'),
        '_quiet_end': ('genset_config', '(self, dt=None)'),
        'action_send_test_notification': ('genset_config', '(self)'),
    },
    'td.genset.command': {
        '_enqueue': ('genset_command', '(self, genset, command, source, requested_by, batch_key=None, '
                                       'late_transition_at=None, target_breaker_closed=None)'),
        '_enqueue_batch': ('genset_command', '(self, genset, commands, source, requested_by, late_transition_at=None)'),
        '_cron_process_commands': ('genset_command', '(self)'),
        '_step': ('genset_command', '(self)'),
        '_precheck': ('genset_command', '(self)'),
        '_check_confirmation': ('genset_command', '(self, reading)'),
        '_cancel_pending': ('genset_command',
                            "(self, genset, reason, sources=('schedule', 'timer', 'exception', 'test'))"),
        '_count_inflight': ('genset_command', '(self, genset)'),
    },
    'td.genset.fuel.move': {'_post': ('genset_fuel', '(self, kind, liters_delta, canister=None, genset=None, '
                                                     'refuel=None, **vals)')},
    'td.genset.refuel': {'_reconcile_pending': ('genset_fuel', '(self)')},
    'td.genset.canister': {'action_write_off': ('genset_fuel', '(self)')},
    'maintenance.request': {'_td_on_done': ('maintenance_ext', '(self)')},
    'ir.websocket': {'_build_bus_channel_list': ('ir_websocket', '(self, channels)')},
}


@tagged('standard', 'at_install')
class TestW0Smoke(TdGensetCase):

    # ------------------------------------------------------------------ установка і дані
    def test_w0_install_xmlids(self):
        """Усі XML id SPEC 6 існують; singleton і 3 рівні ланцюжка; cron — OdooBot, code."""
        for xmlid in SPEC_XMLIDS:
            self.assertTrue(self.env.ref('td_genset.%s' % xmlid, raise_if_not_found=False), xmlid)
        self.assertEqual(self.env['td.genset.config'].search_count([]), 1)
        self.assertEqual(self.env['td.genset.config'].get(), self.config)
        self.assertEqual(len(self.config.level_ids), 3)
        self.assertEqual(self.config.level_ids.sorted('sequence').mapped('delay_min'), [0, 10, 30])
        self.assertEqual(self.config.maint_team_id, self.env.ref('td_genset.maintenance_team_genset'))
        self.assertEqual(self.config.raw_regs_mode, 'auto')
        self.assertFalse(self.env.ref('td_genset.controller_hgm6110n').has_mains_breaker)
        for xmlid in ('cron_pull_readings', 'cron_commands', 'cron_scheduler', 'cron_cleanup'):
            cron = self.env.ref('td_genset.%s' % xmlid)
            self.assertEqual(cron.user_id, self.env.ref('base.user_root'))
            self.assertEqual(cron.state, 'code')

    def test_w0_config_singleton(self):
        """Другий запис налаштувань заборонено; пороги ≥ 2 % бака; retry/test межі."""
        with self.assertRaises(ValidationError):
            self.env['td.genset.config'].create({})
        with self.assertRaises(ValidationError):
            self.config.retry_window_min = 1
        with self.assertRaises(ValidationError):
            self.config.drain_threshold_l = 1.0
        with self.assertRaises(ValidationError):
            self.config.test_minutes = 61

    def test_w0_groups(self):
        """group_user → group_admin → group_tech (+ maintenance manager) через implied_ids."""
        self.assertIn(self.env.ref('base.group_user'), self.group_user.implied_ids)
        self.assertIn(self.group_user, self.group_admin.implied_ids)
        self.assertIn(self.group_admin, self.group_tech.implied_ids)
        self.assertIn(self.env.ref('maintenance.group_equipment_manager'), self.group_tech.implied_ids)
        self.assertTrue(self.user_t.has_group('td_genset.group_user'))
        self.assertTrue(self.user_t.has_group('maintenance.group_equipment_manager'))
        self.assertFalse(self.user_s.has_group('td_genset.group_admin'))
        self.assertEqual(self.group_tech.category_id, self.env.ref('td_genset.module_category_td_genset'))

    def test_w0_access_rules(self):
        """ACL — 34 рядки (ТР А.10); кожна не абстрактна модель модуля має права."""
        acl_count = self.env['ir.model.data'].search_count([('module', '=', 'td_genset'), ('model', '=', 'ir.model.access')])
        self.assertEqual(acl_count, 34)
        own_models = [name for name, model in self.env.registry.items()
                      if name.startswith('td.genset') and not model._abstract]
        self.assertEqual(len(own_models), 19)  # 15 моделей + 4 майстри
        for name in own_models:
            self.assertTrue(self.env['ir.model.access'].search_count([('model_id.model', '=', name)]), name)

    # ------------------------------------------------------------------ меню і подання
    def test_w0_menus_and_views(self):
        """Кожен пункт меню модуля має дію, подання якої завантажуються (для тех. адміністратора)."""
        root = self.env.ref('td_genset.menu_root')
        menus = self.env['ir.ui.menu'].search([('id', 'child_of', root.id)])
        self.assertGreaterEqual(len(menus), 15)
        for menu in menus.filtered('action'):
            action = menu.action
            if action._name == 'ir.actions.server':
                result = action.with_user(self.user_s).run()
                self.assertEqual(result['res_model'], 'td.genset', menu.complete_name)
                continue
            if action._name != 'ir.actions.act_window' or action.res_model == 'res.users':
                continue
            user = self.user_t if action.res_model != 'res.config.settings' else self.env.ref('base.user_admin')
            view_types = [vt.strip() for vt in action.view_mode.split(',')]
            views = self.env[action.res_model].with_user(user).get_views(
                [(False, vt) for vt in view_types] + [(False, 'search')])
            self.assertTrue(views['views'], menu.complete_name)
        # форми майстрів
        for model in ('td.genset.command.wizard', 'td.genset.timer.wizard', 'td.genset.refuel.wizard',
                      'td.genset.fuel.receipt.wizard'):
            self.assertTrue(self.env[model].get_views([(False, 'form')])['views']['form']['arch'])

    def test_w0_main_menu_action(self):
        """«Генератор»: один генератор — його форма; кілька — список."""
        action = self.env['td.genset'].action_open_main()
        if self.env['td.genset'].search_count([]) == 1:
            self.assertEqual(action['res_id'], self.genset.id)
        self.env['td.genset'].create({'name': 'Другий', 'controller_model_id': self.controller_model.id,
                                      'power_kw': 10.0})
        action = self.env['td.genset'].action_open_main()
        self.assertFalse(action.get('res_id'))
        for method in ('action_open_readings', 'action_open_events', 'action_open_alarms', 'action_open_commands',
                       'action_open_maintenance'):
            result = getattr(self.genset, method)()
            self.assertEqual(result['type'], 'ir.actions.act_window', method)

    # ------------------------------------------------------------------ поля і обмеження
    def test_w0_genset_fields(self):
        """Поля SPEC 5.1 на td.genset, етап з genset_status, обмеження."""
        genset = self.genset
        for name in ('relay_hostid', 'commands_allowed', 'fuel_source', 'fuel_sensor_ohm', 'water_temp_sensor_ohm',
                     'oil_pressure_sensor_ohm', 'fuel_calibration_ids', 'fuel_calibrated', 'catchup_from_date',
                     'kpi_crank_battery_min_30d', 'fuel_cost_30d', 'open_alarm_codes', 'timer_progress',
                     'current_data_html', 'is_tech', 'is_admin', 'next_event_text', 'last_values_json'):
            self.assertIn(name, genset._fields)
        self.assertEqual(genset.tank_volume_l, 145.0)
        self.assertEqual(genset.catchup_from_date, date.today() - timedelta(days=30))
        self.assertEqual(genset.maint_first_hours, 30)
        for status, stage in (('0', 'standby'), ('3', 'start'), ('9', 'run'), ('14', 'stop')):
            genset.sudo().genset_status = status
            self.assertEqual(genset.genset_stage, stage)
        with self.assertRaises(ValidationError):
            genset.tank_volume_l = 0
        self.env['td.genset.fuel.calibration'].create({'genset_id': genset.id, 'ohm': 10.0, 'liters': 0.0})
        self.assertFalse(genset.fuel_calibrated)
        self.env['td.genset.fuel.calibration'].create({'genset_id': genset.id, 'ohm': 190.0, 'liters': 145.0})
        self.assertTrue(genset.fuel_calibrated)

    def test_w0_reading_map_and_export(self):
        """READING_FIELD_MAP: 123 ключі → поля; оми; шаблон експорту з усіма полями."""
        reading_model = self.env['td.genset.reading']
        self.assertEqual(len(READING_FIELD_MAP), 123)
        self.assertEqual(READING_FIELD_MAP['fuel_level_sensor_ohm'][0], 'fuel_sensor_ohm')
        for key, (field_name, field_type) in READING_FIELD_MAP.items():
            self.assertIn(field_name, reading_model._fields, key)
            self.assertEqual(reading_model._fields[field_name].type, field_type, key)
        self.assertTrue(set(snapshot()) - {'genset_status_text', 'remote_start_status_text', 'mains_status_text'}
                        <= set(READING_FIELD_MAP))
        export = self.env.ref('td_genset.export_reading_all')
        names = set(export.export_fields.mapped('name'))
        self.assertTrue({field for field, _type in READING_FIELD_MAP.values()} <= names)
        self.assertTrue({'values_extra_text', 'fuel_source', 'fuel_liters'} <= names)
        reading = reading_model.create({'genset_id': self.genset.id, 'relay_id': 1, 'ts': datetime(2026, 10, 7, 12, 0),
                                        'fuel_level': 50.0, 'run_hours': 10, 'run_minutes': 30,
                                        'values_extra': {'new_key': 1}})
        self.assertEqual(reading.fuel_liters, 72.0)
        self.assertEqual(reading.fuel_source, 'pct')
        self.assertAlmostEqual(reading.run_hours_total, 10.5)
        self.assertIn('new_key', reading.values_extra_text)
        with self.assertRaises(Exception), mute_logger('odoo.sql_db'), self.env.cr.savepoint():
            reading_model.create({'genset_id': self.genset.id, 'relay_id': 1, 'ts': datetime(2026, 10, 7, 12, 1)})

    def test_w0_schedule_and_kyiv(self):
        """Розклад: кінець > початок, без перетинів; kyiv_localize з DST (AC-37 — базово)."""
        schedule = self.env['td.genset.schedule']
        schedule.create({'genset_id': self.genset.id, 'dayofweek': '0', 'time_start': 8.0, 'time_end': 18.0})
        with self.assertRaises(ValidationError):
            schedule.create({'genset_id': self.genset.id, 'dayofweek': '0', 'time_start': 17.0, 'time_end': 19.0})
        with self.assertRaises(ValidationError):
            schedule.create({'genset_id': self.genset.id, 'dayofweek': '1', 'time_start': 10.0, 'time_end': 9.0})
        self.assertEqual(kyiv_localize(date(2026, 10, 7), 8.0), datetime(2026, 10, 7, 5, 0))
        self.assertEqual(kyiv_localize(date(2026, 3, 29), 3.5), datetime(2026, 3, 29, 1, 0))
        self.assertEqual(kyiv_localize(date(2026, 10, 25), 3.5), datetime(2026, 10, 25, 0, 30))

    # ------------------------------------------------------------------ cron, bus, websocket
    def test_w0_crons_succeed(self):
        """Усі 4 cron завершуються успішно (заглушки/реалізації не кидають винятків)."""
        for xmlid in ('cron_pull_readings', 'cron_commands', 'cron_scheduler', 'cron_cleanup'):
            self.assertTrue(self.env.ref('td_genset.%s' % xmlid).method_direct_trigger(), xmlid)

    def test_w0_notify_bus(self):
        """_notify_bus надсилає td_genset.update у канал запису (А.9); невідомий kind — помилка."""
        self.genset._notify_bus('reading', {'note': 'smoke'})
        self.env.cr.precommit.run()
        messages = self.env['bus.bus'].sudo().search([('channel', 'like', 'td.genset')], order='id desc', limit=1)
        self.assertTrue(messages)
        message = json.loads(messages.message)
        self.assertEqual(message['type'], 'td_genset.update')
        self.assertEqual(message['payload']['genset_id'], self.genset.id)
        self.assertEqual(message['payload']['kind'], 'reading')
        self.assertEqual(message['payload']['note'], 'smoke')
        with self.assertRaises(ValueError):
            self.genset._notify_bus('unknown')

    def test_w0_websocket_channels(self):
        """Канал td_genset_<id> → запис генератора, якщо є право читання; чужі рядки лишаються."""
        websocket = self.env['ir.websocket'].with_user(self.user_s)
        other, gensets = websocket._td_genset_bus_channels(
            ['broadcast', 'td_genset_%d' % self.genset.id, 'td_genset_999999999'])
        self.assertEqual(other, ['broadcast'])
        self.assertEqual(gensets, self.genset)

    # ------------------------------------------------------------------ права на кнопки
    def test_w0_button_access(self):
        """Кнопки пульта/налаштувань перевіряють групу в Python (AccessError для Співробітника)."""
        with self.assertRaises(AccessError):
            self.genset.with_user(self.user_s).action_open_command_wizard()
        with self.assertRaises(AccessError):
            self.genset.with_user(self.user_a).action_check_relay()
        action = self.genset.with_user(self.user_t).with_context(default_command='auto').action_open_command_wizard()
        self.assertEqual(action['res_model'], 'td.genset.command.wizard')
        self.assertEqual(action['context']['default_command'], 'auto')
        action = self.genset.with_user(self.user_s).action_open_timer_wizard()
        self.assertEqual(action['res_model'], 'td.genset.timer.wizard')
        with self.assertRaises(AccessError):
            self.env['td.genset'].with_user(self.user_s).create({'name': 'X', 'controller_model_id': self.controller_model.id,
                                                                 'power_kw': 1.0})
        state = self.genset.with_user(self.user_s).get_pult_state()
        for key in ('can_control', 'block_reason', 'buttons', 'breakers', 'gauges', 'status', 'feed', 'timer', 'test',
                    'server_now'):
            self.assertIn(key, state)

    # ------------------------------------------------------------------ інтерфейси SPEC 9
    def test_w0_spec9_methods_exist(self):
        """Кожен метод SPEC 9 є на моделі, визначений у файлі-власнику, з тією самою сигнатурою."""
        for model_name, methods in SPEC_METHODS.items():
            model_cls = type(self.env[model_name])
            for method, (owner, signature) in methods.items():
                func = getattr(model_cls, method, None)
                self.assertTrue(callable(func), '%s.%s' % (model_name, method))
                self.assertEqual(func.__module__, MODULE + owner, '%s.%s' % (model_name, method))
                self.assertEqual(str(inspect.signature(func)), signature, '%s.%s' % (model_name, method))
        self.assertIsInstance(self.env['td.genset.reading'].READING_FIELD_MAP, dict)
        self.assertEqual(str(inspect.signature(kyiv_localize)), '(date, float_time)')

    def _call_if_stub(self, record, method, *args, **kwargs):
        func = getattr(record, method)
        if STUB_MARK not in (func.__doc__ or ''):
            return IMPLEMENTED
        return func(*args, **kwargs)

    def test_w0_stubs_neutral(self):
        """Заглушки викликаються і повертають нейтральний результат (лише поки «Заглушка W0» у докстрингу)."""
        genset = self.genset
        client = self.env['td.genset.relay.client']
        status = self.relay.status_json()
        now = datetime(2026, 10, 7, 12, 0)
        kyiv_now = pytz.utc.localize(now).astimezone(pytz.timezone('Europe/Kyiv'))
        reading = self.env['td.genset.reading'].create({'genset_id': genset.id, 'relay_id': 99, 'ts': now})
        payload = {'id': 1, 'ts': 1791390868.86, 'time_utc': '2026-10-07T16:34:28Z', 'hostid': HOSTID,
                   'reason': 'interval', 'values': snapshot()}
        command = self.env['td.genset.command'].create({'genset_id': genset.id, 'command': 'auto', 'source': 'button'})
        alarm = self.env['td.genset.alarm'].create({'genset_id': genset.id, 'code': 'smoke', 'level': 'warn',
                                                    'name': 'Smoke'})
        location = self.env['td.genset.storage.location'].create({'name': 'Склад (smoke)'})
        canister = self.env['td.genset.canister'].create({'location_id': location.id, 'volume_l': 20.0, 'liters': 5.0})
        self.assertTrue(canister.name.startswith('К-'))
        user = self.user_t
        neutral = [
            (client, '_request', ('GET', '/status'), {}, (dict,)),
            (client, 'status', (), {}, (dict,)),
            (client, 'latest', (HOSTID,), {}, (type(None),)),
            (client, 'readings', (HOSTID, 0), {}, (tuple,)),
            (client, 'post_command', (HOSTID, 'auto', 'Smoke (res.users 2)', 'odoo:button'), {}, (dict,)),
            (client, 'command', (1,), {}, (dict,)),
            (client, 'commands', (0,), {}, (list,)),
            (genset, '_apply_status', (status,), {}, (type(None),)),
            (genset, '_pull_readings_page', (client,), {}, (int,)),
            (genset, '_find_cursor_for_date', (client, date(2026, 9, 7)), {}, (int,)),
            (genset, '_need_raw', (status,), {}, (bool,)),
            (genset, '_apply_reading', (reading,), {}, (type(None),)),
            (genset, '_update_link_state', (True,), {'now': now}, (type(None),)),
            (genset, '_check_relay_health', (status,), {}, (type(None),)),
            (genset, '_finish_catchup', ({'days': 0, 'readings': 0, 'events': 0},), {}, (type(None),)),
            (genset, '_in_window', (kyiv_now,), {}, (bool,)),
            (genset, '_window_bounds', (kyiv_now.date(),), {}, (list,)),
            (genset, '_next_transition', (kyiv_now,), {}, (type(None),)),
            (genset, '_follow_schedule', ('timer',), {}, (type(None),)),
            (genset, '_timer_start', (60, user), {}, (type(None),)),
            (genset, '_timer_extend', (15, user), {}, (type(None),)),
            (genset, '_timer_stop', (user,), {}, (type(None),)),
            (genset, '_test_start', ('load', user), {}, (type(None),)),
            (genset, '_test_finish', (), {}, (type(None),)),
            (genset, '_fuel_stats', (7,), {}, (dict,)),
            (genset, '_check_fuel_stock', (), {}, (type(None),)),
            (genset, '_liters_from_ohm', (100.0,), {}, (type(None),)),
            (genset, '_ensure_equipment', (), {}, (type(None),)),
            (genset, '_check_maintenance', (), {}, (type(None),)),
            (genset, 'action_recompute_liters', (), {}, (bool,)),
            (self.env['td.genset.reading'], '_create_from_payload', (genset, [payload]), {}, (type(reading),)),
            (self.env['td.genset.reading'], '_derive', (snapshot(), genset), {}, (dict,)),
            (self.env['td.genset.reading'], '_extract_sensor_ohms', (payload,), {}, (dict,)),
            (self.env['td.genset.reading'], '_mark_journal', (genset, set()), {}, (type(None),)),
            (self.env['td.genset.reading'], '_cron_cleanup', (), {}, (type(None),)),
            (self.env['td.genset.event'], '_process_readings', (genset, reading), {}, (type(None),)),
            (self.env['td.genset.event'], '_open', (genset, 'run', now), {}, (type(self.env['td.genset.event']),)),
            (self.env['td.genset.event'], '_close', (self.env['td.genset.event'], now), {}, (type(None),)),
            (self.env['td.genset.event'], '_detect_external_control', (genset,), {}, (type(None),)),
            (self.env['td.genset.alarm'], '_raise', (genset, 'smoke2', 'warn', 'Smoke 2'), {},
             (type(self.env['td.genset.alarm']),)),
            (self.env['td.genset.alarm'], '_clear', (genset, 'smoke2'), {}, (type(None),)),
            (alarm, 'action_ack', (), {}, (bool,)),
            (self.env['td.genset.alarm'], '_cron_escalate', (), {}, (type(None),)),
            (self.env['td.genset.alarm'], '_evaluate_current', (genset,), {}, (type(None),)),
            (self.config, '_quiet_now', (), {}, (bool,)),
            (self.config, '_quiet_end', (), {}, (type(None),)),
            (self.config, 'action_send_test_notification', (), {}, (bool,)),
            (self.env['td.genset.command'], '_enqueue', (genset, 'auto', 'button', user), {},
             (type(command),)),
            (self.env['td.genset.command'], '_enqueue_batch', (genset, ['manual', 'stop'], 'schedule', 'Odoo: розклад'),
             {}, (type(command),)),
            (command, '_step', (), {}, (type(None),)),
            (command, '_precheck', (), {}, (type(None),)),
            (command, '_check_confirmation', (reading,), {}, (bool,)),
            (self.env['td.genset.command'], '_cancel_pending', (genset, 'smoke'), {}, (type(None),)),
            (self.env['td.genset.fuel.move'], '_post', ('in', 10.0), {}, (type(self.env['td.genset.fuel.move']),)),
            (self.env['td.genset.refuel'], '_reconcile_pending', (), {}, (type(None),)),
            (canister, 'action_write_off', (), {}, (bool,)),
            (self.env['maintenance.request'], '_td_on_done', (), {}, (type(None),)),
        ]
        for record, method, args, kwargs, types in neutral:
            result = self._call_if_stub(record, method, *args, **kwargs)
            if result is not IMPLEMENTED:
                self.assertIsInstance(result, types, '%s.%s' % (record._name, method))
        self.assertEqual(self.env['td.genset.command']._count_inflight(genset), 0)
        self.assertEqual(client.device_status(status, HOSTID)['hostid'], HOSTID)
        self.assertIsNone(client.device_status(status, 'unknown'))
        self.assertEqual(client._base_url(), BASE_URL)
        self.assertEqual(client._timeout(), 20)
        self.assertEqual(client._headers()['Authorization'], 'Bearer %s' % TOKEN)

    # ------------------------------------------------------------------ мок ретранслятора
    def test_w0_relay_mock_formats(self):
        """RelayMock: /status, /readings (raw, 1.1.1), /latest, POST /commands, /commands/<id>, помилки, рестарт."""
        session = requests.Session()
        headers = {'Authorization': 'Bearer %s' % TOKEN}
        self.assertEqual(session.get(BASE_URL + '/status').status_code, 401)
        status = session.get(BASE_URL + '/status', headers=headers).json()
        self.assertEqual(status['devices'][0]['hostid'], HOSTID)
        self.assertTrue(status['devices'][0]['commands_ready'])
        latest = session.get(BASE_URL + '/latest', headers=headers)
        self.assertEqual((latest.status_code, latest.json()), (404, {'error': 'no readings yet'}))
        first = self.push_reading(snapshot(fuel_level=50, fuel_sensor_ohm=104.5))
        self.assertEqual(first['reason'], 'first')
        self.push_reading(None)
        page = session.get(BASE_URL + '/readings', params={'hostid': HOSTID, 'since': 0, 'limit': 500},
                           headers=headers).json()
        self.assertEqual([r['id'] for r in page['readings']], [1, 2])
        self.assertEqual(page['next_since'], 2)
        self.assertNotIn('regs', page['readings'][0])
        self.assertEqual(page['readings'][0]['values']['fuel_level_sensor_ohm'], 104.5)
        raw = session.get(BASE_URL + '/readings', params={'since': 1, 'raw': 1}, headers=headers).json()
        self.assertEqual(raw['readings'][0]['regs']['22'], 1045)
        self.assertEqual(len(raw['readings'][0]['regs']), 55)
        self.assertEqual(len(raw['readings'][0]['coils']), 80)
        self.relay.version = '1.1.1'
        old = session.get(BASE_URL + '/readings', params={'since': 0, 'raw': 1}, headers=headers).json()
        self.assertNotIn('fuel_level_sensor_ohm', old['readings'][0]['values'])
        self.assertEqual(old['readings'][0]['regs']['22'], 1045)
        self.assertEqual(session.get(BASE_URL + '/status', headers=headers).json()['relay']['version'], '1.1.1')
        empty = session.get(BASE_URL + '/readings', params={'since': 5}, headers=headers).json()
        self.assertEqual(empty, {'readings': [], 'next_since': 5})
        # команди: 201 → done → ефект + знімок change
        created = session.post(BASE_URL + '/commands', json={'command': 'manual', 'hostid': HOSTID,
                                                             'requested_by': 'Smoke', 'source': 'odoo:button'},
                               headers=headers)
        self.assertEqual(created.status_code, 201)
        self.assertEqual(created.json()['status'], 'queued')
        done = session.get(BASE_URL + '/commands/%d' % created.json()['id'], headers=headers).json()
        self.assertEqual(done['status'], 'done')
        self.assertEqual(self.relay.readings[-1]['values']['controller_mode'], 'manual')
        self.assertEqual(self.relay.readings[-1]['reason'], 'change')
        # контролер не виконує
        self.relay.controller_executes = False
        cmd_id = session.post(BASE_URL + '/commands', json={'command': 'auto'}, headers=headers).json()['id']
        session.get(BASE_URL + '/commands/%d' % cmd_id, headers=headers)
        self.assertEqual(self.relay.values['controller_mode'], 'manual')
        # помилки
        for code in (409, 403, 401, 500):
            self.relay.fail(code, path='/commands', method='POST', times=1)
            response = session.post(BASE_URL + '/commands', json={'command': 'auto'}, headers=headers)
            self.assertEqual(response.status_code, code)
            self.assertIn('error', response.json())
        self.relay.fail('timeout', times=1)
        with self.assertRaises(requests.exceptions.Timeout):
            session.get(BASE_URL + '/status', headers=headers)
        self.relay.fail(502, times=1)
        self.assertEqual(session.get(BASE_URL + '/status', headers=headers).status_code, 502)
        self.assertEqual(session.get(BASE_URL + '/commands/999', headers=headers).json(), {'error': 'no such command'})
        self.assertEqual(session.post(BASE_URL + '/commands', json={'command': 'fly'}, headers=headers).status_code, 400)
        # перезапуск ретранслятора
        self.relay.command_flow = 'queued'
        cmd_id = session.post(BASE_URL + '/commands', json={'command': 'stop'}, headers=headers).json()['id']
        self.relay.relay_restart()
        restarted = session.get(BASE_URL + '/commands/%d' % cmd_id, headers=headers).json()
        self.assertEqual((restarted['status'], restarted['error']), ('failed', 'relay restarted'))
        self.assertEqual(self.push_reading(None)['reason'], 'first')
        # черга ≤ 5
        for _i in range(5):
            session.post(BASE_URL + '/commands', json={'command': 'auto'}, headers=headers)
        full = session.post(BASE_URL + '/commands', json={'command': 'auto'}, headers=headers)
        self.assertEqual(full.json(), {'error': '5 commands already waiting for this modem'})
        self.assertTrue(all('headers' not in call for call in self.relay.calls))
        with self.assertRaises(AssertionError):
            session.get('https://example.invalid/api/v1/status')
