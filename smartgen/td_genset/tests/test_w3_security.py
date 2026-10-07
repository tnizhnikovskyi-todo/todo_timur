# Part of td_genset (ToDo). Власник файлу: W3.
"""ACL/AccessError для С/А, налаштування, експорт, токен (AC-24, AC-55, AC-56, AC-57, AC-59).

Матриця прав (ТР 2.5, AC-56): С — таймер; А — + розклад і заправка; Т — усе. Для кожного забороненого елемента
кнопка прихована в поданні (``groups=``), а прямий виклик (ORM від імені користувача або справжній JSON-RPC)
повертає помилку доступу без змін у базі.
"""
from datetime import datetime

from lxml import etree

from odoo.exceptions import AccessError
from odoo.tests import HttpCase, tagged
from odoo.tools import mute_logger

from .common import TdGensetCase


def _arch(env, model, view_type='form'):
    return etree.fromstring(env[model].get_views([(False, view_type)])['views'][view_type]['arch'])


@tagged('standard', 'at_install')
class TestW3Security(TdGensetCase):

    # ------------------------------------------------------------------ AC-56: матриця через ORM
    def test_ac56_rights_matrix(self):
        """AC-56: С — таймер; А — + розклад, дні-винятки, каністри, місця; Т — усе. Заборонене — AccessError,
        записів не додається."""
        genset = self.genset
        schedule_vals = {'genset_id': genset.id, 'dayofweek': '2', 'time_start': 8.0, 'time_end': 9.0}
        exception_vals = {'genset_id': genset.id, 'date': '2027-01-05', 'action': 'skip'}
        # Таймер «Робота поза графіком» — усі три ролі (майстер відкривається і створюється)
        for user in (self.user_s, self.user_a, self.user_t):
            action = genset.with_user(user).action_open_timer_wizard()
            self.assertEqual(action['res_model'], 'td.genset.timer.wizard')
            self.env['td.genset.timer.wizard'].with_user(user).create({'genset_id': genset.id, 'hours': 1})
        # Розклад і дні-винятки — А/Т
        counts = (self.env['td.genset.schedule'].search_count([]), self.env['td.genset.schedule.exception'].search_count([]))
        with self.assertRaises(AccessError):
            self.env['td.genset.schedule'].with_user(self.user_s).create(schedule_vals)
        with self.assertRaises(AccessError):
            self.env['td.genset.schedule.exception'].with_user(self.user_s).create(exception_vals)
        self.assertEqual(counts, (self.env['td.genset.schedule'].search_count([]),
                                  self.env['td.genset.schedule.exception'].search_count([])))
        self.env['td.genset.schedule'].with_user(self.user_a).create(schedule_vals)
        self.env['td.genset.schedule.exception'].with_user(self.user_a).create(exception_vals)
        # Заправка: місця, каністри, майстри заправки і надходження — А/Т
        with self.assertRaises(AccessError):
            self.env['td.genset.storage.location'].with_user(self.user_s).create({'name': 'Щитова (С)'})
        location = self.env['td.genset.storage.location'].with_user(self.user_a).create({'name': 'Щитова (А)'})
        with self.assertRaises(AccessError):
            self.env['td.genset.canister'].with_user(self.user_s).create({'location_id': location.id, 'volume_l': 20})
        self.env['td.genset.canister'].with_user(self.user_a).create({'location_id': location.id, 'volume_l': 20})
        for model in ('td.genset.refuel.wizard', 'td.genset.fuel.receipt.wizard'):
            with self.assertRaises(AccessError):
                self.env[model].with_user(self.user_s).check_access('create')
            self.env[model].with_user(self.user_a).check_access('create')
        # Пульт і автомати — лише Т (AC-24): майстер команди і запис команди
        for user in (self.user_s, self.user_a):
            with self.assertRaises(AccessError):
                genset.with_user(user).with_context(default_command='auto').action_open_command_wizard()
            with self.assertRaises(AccessError):
                self.env['td.genset.command.wizard'].with_user(user).create({'genset_id': genset.id, 'command': 'auto'})
        self.env['td.genset.command.wizard'].with_user(self.user_t).check_access('create')
        commands = self.env['td.genset.command'].search_count([])
        for user in (self.user_s, self.user_a, self.user_t):
            with self.assertRaises(AccessError):
                self.env['td.genset.command'].with_user(user).create({'genset_id': genset.id, 'command': 'auto',
                                                                      'source': 'button'})
        self.assertEqual(self.env['td.genset.command'].search_count([]), commands, 'AC-24: команда не створюється')
        # Калібрування датчика, генератор, налаштування — лише Т
        with self.assertRaises(AccessError):
            self.env['td.genset.fuel.calibration'].with_user(self.user_a).create(
                {'genset_id': genset.id, 'ohm': 50.0, 'liters': 40.0})
        self.env['td.genset.fuel.calibration'].with_user(self.user_t).create(
            {'genset_id': genset.id, 'ohm': 50.0, 'liters': 40.0})
        for user in (self.user_s, self.user_a):
            with self.assertRaises(AccessError):
                genset.with_user(user).write({'tank_volume_l': 100.0})
            with self.assertRaises(AccessError):
                genset.with_user(user).action_check_relay()
            with self.assertRaises(AccessError):
                genset.with_user(user).action_recompute_liters()
            with self.assertRaises(AccessError):
                genset.with_user(user).read(['commands_allowed'])
        self.assertEqual(genset.tank_volume_l, 145.0)
        genset.with_user(self.user_t).write({'tank_volume_l': 150.0})
        self.assertTrue(genset.with_user(self.user_t).read(['commands_allowed'])[0]['commands_allowed'])
        # Перегляд — усім: картка, пульт, показання, події, налаштування
        for user in (self.user_s, self.user_a, self.user_t):
            state = genset.with_user(user).get_pult_state()
            self.assertIn('buttons', state)
            genset.with_user(user).read(['name', 'current_data_html', 'alarm_recipients_text', 'retry_rule_text'])
            self.config.with_user(user).read(['retry_every_min', 'level_ids'])

    def test_ac56_buttons_hidden_by_group(self):
        """AC-56/AC-24: заборонені кнопки й поля відсутні в поданні (``groups=``), дозволені — є."""
        expectations = {
            # (кнопка/поле, xpath) → хто бачить
            ('check_relay', "//button[@name='action_check_relay']"): {'t'},
            ('recompute', "//button[@name='action_recompute_liters']"): {'t'},
            ('commands_allowed', "//field[@name='commands_allowed']"): {'t'},
            ('refuel', "//button[@string='Заправити генератор']"): {'a', 't'},
            ('receipt', "//button[@string='Надходження палива']"): {'a', 't'},
            ('timer', "//button[@name='action_open_timer_wizard']"): {'s', 'a', 't'},
            ('timer_stop', "//button[@name='action_timer_stop']"): {'s', 'a', 't'},
            ('pult', "//widget[@name='td_genset_pult']"): {'s', 'a', 't'},
        }
        users = {'s': self.user_s, 'a': self.user_a, 't': self.user_t}
        for key, user in users.items():
            arch = _arch(self.env(user=user), 'td.genset')
            for (name, xpath), allowed in expectations.items():
                self.assertEqual(bool(arch.xpath(xpath)), key in allowed, '%s для %s' % (name, user.login))
        # Каністри: кнопки майстрів у шапці kanban/list — лише А/Т
        for key, user in users.items():
            for view_type in ('kanban', 'list'):
                arch = _arch(self.env(user=user), 'td.genset.canister', view_type)
                self.assertEqual(bool(arch.xpath("//header/button")), key in ('a', 't'), '%s %s' % (view_type, key))
        # Розклад і калібрування на картці — readonly за роллю (is_admin / is_tech)
        arch = _arch(self.env(user=self.user_t), 'td.genset')
        self.assertEqual(arch.xpath("//field[@name='schedule_line_ids']")[0].get('readonly'), 'not is_admin')
        self.assertEqual(arch.xpath("//field[@name='exception_ids']")[0].get('readonly'), 'not is_admin')
        self.assertEqual(arch.xpath("//field[@name='fuel_calibration_ids']")[0].get('readonly'), 'not is_tech')
        self.assertFalse(self.genset.with_user(self.user_s).is_admin)
        self.assertTrue(self.genset.with_user(self.user_a).is_admin)
        self.assertFalse(self.genset.with_user(self.user_a).is_tech)
        self.assertTrue(self.genset.with_user(self.user_t).is_tech)

    # ------------------------------------------------------------------ AC-55: налаштування модуля
    def test_ac55_config_readonly_for_non_tech(self):
        """AC-55: С бачить налаштування лише для читання (банер, readonly, без кнопки тестового сповіщення),
        запис від С/А — помилка доступу; Т змінює повтор 2/10 → 3/12."""
        arch = _arch(self.env(user=self.user_s), 'td.genset.config')
        banner = arch.xpath("//div[contains(@class, 'alert') and @invisible='is_tech']")
        self.assertTrue(banner)
        self.assertIn('Лише перегляд: налаштування змінює тех. адміністратор.', ' '.join(banner[0].itertext()))
        self.assertFalse(arch.xpath("//button[@name='action_send_test_notification']"))
        editable = [node.get('name') for node in arch.xpath("//field") if node.get('name') not in ('is_tech',)
                    and node.getparent().tag != 'list' and node.get('readonly') != 'not is_tech'
                    and not node.xpath("ancestor::list")]
        self.assertFalse(editable, 'поля без readonly="not is_tech": %s' % editable)
        self.assertFalse(self.config.with_user(self.user_s).is_tech)
        for user in (self.user_s, self.user_a):
            with self.assertRaises(AccessError):
                self.config.with_user(user).write({'retry_every_min': 3, 'retry_window_min': 12})
            with self.assertRaises(AccessError):
                self.config.level_ids[:1].with_user(user).write({'delay_min': 0, 'name': 'X'})
        self.assertEqual((self.config.retry_every_min, self.config.retry_window_min), (2, 10))
        arch_t = _arch(self.env(user=self.user_t), 'td.genset.config')
        self.assertTrue(arch_t.xpath("//button[@name='action_send_test_notification']"))
        self.config.with_user(self.user_t).write({'retry_every_min': 3, 'retry_window_min': 12})
        self.assertEqual((self.config.retry_every_min, self.config.retry_window_min), (3, 12))
        # правило повторів на картці бере нові значення
        self.genset.invalidate_recordset(['retry_rule_text'])
        self.assertIn('повтор кожні 3 хв протягом 12 хв', self.genset.retry_rule_text)

    # ------------------------------------------------------------------ AC-59: експорт
    def test_ac59_export_template_all_values(self):
        """AC-59: шаблон «Генератори: усі значення» — кожне значення знімка окремою колонкою з українськими
        назвами й одиницями: паливо в L і %, оми датчиків, джерело літрів, «Інші значення (JSON)»; Співробітник
        експортує список «Показання»."""
        template = self.env.ref('td_genset.export_reading_all')
        names = template.export_fields.mapped('name')
        for name in ('fuel_liters', 'fuel_level', 'fuel_source', 'fuel_sensor_ohm', 'water_temp_sensor_ohm',
                     'oil_pressure_sensor_ohm', 'values_extra_text', 'mains_normal', 'gen_on_load', 'genset_status'):
            self.assertIn(name, names)
        fields_info = self.env['td.genset.reading'].with_user(self.user_s).fields_get(names, ['string'])
        self.assertEqual(fields_info['fuel_liters']['string'], 'Паливо, L')
        self.assertEqual(fields_info['fuel_level']['string'], 'Рівень палива, %')
        self.assertEqual(fields_info['fuel_sensor_ohm']['string'], 'Опір датчика рівня палива, Ом')
        self.assertEqual(fields_info['values_extra_text']['string'], 'Інші значення (JSON)')
        for name in names:
            label = fields_info[name]['string']
            self.assertTrue(label and not label.isascii(), '%s: підпис «%s» не український' % (name, label))
        # Odoo 18: експорт вимагає «Доступ до експорту» (base.group_allow_export) — групи модуля його не дають
        # (відкрите питання у звіті W3); без групи — відмова для будь-якої моделі.
        self.user_s.groups_id = [(4, self.env.ref('base.group_allow_export').id)]
        reading = self.env['td.genset.reading'].create({
            'genset_id': self.genset.id, 'relay_id': 501, 'ts': datetime(2026, 10, 7, 9, 0), 'fuel_level': 40.0,
            'fuel_sensor_ohm': 95.5, 'water_temp_sensor_ohm': 515.4, 'mains_normal': True,
            'values_extra': {'new_key': 7},
        })
        rows = reading.with_user(self.user_s).export_data(names)['datas']
        row = dict(zip(names, rows[0]))
        self.assertEqual(row['fuel_level'], 40.0)
        self.assertEqual(row['fuel_liters'], 58.0)  # 40 % × 145 L, без калібрування
        self.assertEqual(row['fuel_sensor_ohm'], 95.5)
        self.assertEqual(row['water_temp_sensor_ohm'], 515.4)
        self.assertIs(row['mains_normal'], True)
        self.assertIn('new_key', row['values_extra_text'])

    # ------------------------------------------------------------------ AC-57/AC-01: токен у Налаштуваннях
    def test_ac57_settings_token_never_returned(self):
        """AC-01/AC-57: токен не повертається у форму налаштувань (лише «встановлено»); порожнє поле не
        затирає збережений токен; нове значення — зберігається."""
        icp = self.env['ir.config_parameter'].sudo()
        token = icp.get_param('td_genset.relay_token')
        self.assertTrue(token)
        settings = self.env['res.config.settings'].create({})
        self.assertFalse(settings.td_genset_relay_token)
        self.assertTrue(settings.td_genset_relay_token_set)
        self.assertNotIn(token, str(settings.read()))
        settings.execute()
        self.assertEqual(icp.get_param('td_genset.relay_token'), token)
        self.env['res.config.settings'].create({'td_genset_relay_token': ' new-token-0123 '}).execute()
        self.assertEqual(icp.get_param('td_genset.relay_token'), 'new-token-0123')
        arch = _arch(self.env, 'res.config.settings')
        token_node = arch.xpath("//field[@name='td_genset_relay_token']")[0]
        self.assertEqual(token_node.get('password'), 'True')
        self.assertTrue(arch.xpath("//app[@name='td_genset']"))
        # блок «Генератори» лише для системного адміністратора
        view = self.env.ref('td_genset.res_config_settings_view_form_td_genset')
        app = etree.fromstring(view.arch).xpath("//app[@name='td_genset']")[0]
        self.assertEqual(app.get('groups'), 'base.group_system')


@tagged('post_install', '-at_install')
class TestW3SecurityRpc(TdGensetCase, HttpCase):
    """AC-24/AC-56 через справжній JSON-RPC (/web/dataset/call_kw) від імені кожної ролі."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        for user in (cls.user_s, cls.user_a, cls.user_t):
            user.password = user.login

    def setUp(self):
        super().setUp()
        self.relay.stop()  # HttpCase/Chrome ходять через requests — мок ретранслятора тут не потрібен

    def _call(self, login, model, method, args, kwargs=None):
        self.authenticate(login, login)
        return self.make_jsonrpc_request('/web/dataset/call_kw/%s/%s' % (model, method), {
            'model': model, 'method': method, 'args': args, 'kwargs': kwargs or {},
        })

    @mute_logger('odoo.http')
    def test_ac24_ac56_rpc_by_role(self):
        """AC-24, AC-56: RPC-виклики пульта від С/А → помилка доступу, команда не створюється; Т — майстер команди;
        усі ролі читають стан пульта; заборонені записи — AccessError без змін у базі."""
        genset_id = self.genset.id
        commands = self.env['td.genset.command'].search_count([])
        for login in ('td_user_s', 'td_user_a'):
            with self.assertRaisesRegex(Exception, 'AccessError'):
                self._call(login, 'td.genset', 'action_open_command_wizard', [[genset_id]],
                           {'context': {'default_command': 'start'}})
            with self.assertRaisesRegex(Exception, 'AccessError'):
                self._call(login, 'td.genset.command.wizard', 'create', [{'genset_id': genset_id, 'command': 'stop'}])
            with self.assertRaisesRegex(Exception, 'AccessError'):
                self._call(login, 'td.genset', 'write', [[genset_id], {'relay_enabled': False}])
        with self.assertRaisesRegex(Exception, 'AccessError'):
            self._call('td_user_s', 'td.genset.schedule', 'create',
                       [{'genset_id': genset_id, 'dayofweek': '3', 'time_start': 8.0, 'time_end': 9.0}])
        with self.assertRaisesRegex(Exception, 'AccessError'):
            self._call('td_user_s', 'td.genset.config', 'write',
                       [[self.config.id], {'retry_every_min': 5, 'retry_window_min': 20}])
        self.assertEqual(self.env['td.genset.command'].search_count([]), commands)
        self.assertTrue(self.genset.relay_enabled)
        self.assertEqual(self.config.retry_every_min, 2)
        action = self._call('td_user_t', 'td.genset', 'action_open_command_wizard', [[genset_id]],
                            {'context': {'default_command': 'auto'}})
        self.assertEqual(action['res_model'], 'td.genset.command.wizard')
        self.assertEqual(action['context']['default_command'], 'auto')
        for login in ('td_user_s', 'td_user_a', 'td_user_t'):
            state = self._call(login, 'td.genset', 'get_pult_state', [[genset_id]])
            self.assertEqual(state['is_tech'], login == 'td_user_t')
            self.assertEqual(set(state['buttons']), {'auto', 'manual', 'start', 'stop', 'test'})
        # приватні методи через RPC недоступні
        with self.assertRaises(Exception):
            self._call('td_user_t', 'td.genset', '_td_pult_access', [[genset_id]])
