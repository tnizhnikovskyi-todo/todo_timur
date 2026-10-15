# Part of td_genset (ToDo). Підготовка до деплою на тестовий сервер (копія проду: Odoo 18 EE, 5 компаній) — 08.10.
"""Готовність до проду: безпечні значення за замовчуванням і стоп-крани, «Дозволити команди» з підтвердженням і
трекінгом, деінсталяція (токен не лишається) і нейтралізація копії бази, логи без спаму, мультикомпанійність,
самодостатні тексти сповіщень (push ``mail_mobile``), ретранслятор 1.1.1 (``raw=1``, ``command: null``).
"""
import logging
from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun import freeze_time
from lxml import etree

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.modules.module import get_manifest
from odoo.modules.neutralize import get_neutralization_queries
from odoo.tests import Form, tagged
from odoo.tools import html2plaintext

from .. import uninstall_hook
from ..models import td_logging
from .common import BASE_URL, TOKEN, TdGensetCase, snapshot

LOGGER = 'odoo.addons.td_genset'
NOW = datetime(2026, 10, 8, 9, 0, 0)          # 12:00 за Києвом
OTHER_HOSTID = '3130373031334717003D0099'
CRON_XMLIDS = ('cron_pull_readings', 'cron_commands', 'cron_scheduler', 'cron_cleanup', 'cron_recompute_liters')


@tagged('standard', 'at_install')
class TestW6ProdReadiness(TdGensetCase):

    # ------------------------------------------------------------------ помічники
    def _new_genset(self, user=None, **vals):
        return self.env['td.genset'].with_user(user or self.user_t).create(dict({
            'name': 'Садова вулиця', 'controller_model_id': self.controller_model.id, 'power_kw': 12.0,
            'relay_hostid': OTHER_HOSTID}, **vals))

    def _online(self, **values):
        """Знімок «зараз» і крок забору: генератор «Стенд» онлайн."""
        self.push_reading(snapshot(**values))
        self.run_pull()
        self.assertEqual(self.genset.link_state, 'online')

    def _posts(self):
        return [call for call in self.relay.calls if call['method'] == 'POST']

    def _form_arch(self, user, model='td.genset'):
        arch = self.env[model].with_user(user).get_views([(False, 'form')])['views']['form']['arch']
        return etree.fromstring(arch)

    @staticmethod
    def _records(logs, level):
        return [record for record in logs.records if record.levelno == level]

    # ------------------------------------------------------------------ стоп-крани і значення за замовчуванням
    def test_new_genset_is_safe_by_default(self):
        """Новий генератор: «Опитувати ретранслятор» і «Дозволити команди» вимкнено, розкладу, винятків, таймера й
        тесту немає, історія — з −30 днів; бак 145 L; «Читати сирі регістри» — «Автоматично». Порожній розклад
        з увімкненим опитуванням і командами не створює жодної команди."""
        genset = self._new_genset().sudo()
        self.assertFalse(genset.relay_enabled)
        self.assertFalse(genset.commands_allowed)
        self.assertEqual(genset.tank_volume_l, 145.0)
        self.assertFalse(genset.schedule_line_ids or genset.exception_ids)
        self.assertFalse(genset.timer_end or genset.test_end)
        self.assertEqual(genset.link_state, 'none')
        self.assertEqual(genset.catchup_from_date, fields.Date.context_today(genset) - timedelta(days=30))
        self.assertEqual(self.config.raw_regs_mode, 'auto')
        genset.write({'relay_enabled': True, 'commands_allowed': True})
        for moment in (NOW, NOW + timedelta(hours=6), NOW + timedelta(hours=12)):
            with freeze_time(moment):
                self.run_scheduler()
                self.run_commands()
        self.assertFalse(self.env['td.genset.command'].search([('genset_id', '=', genset.id)]))
        self.assertFalse(self._posts())

    def test_commands_allowed_button_confirm_tracking(self):
        """«Дозволити команди»: поки вимкнено — пульт записує «Не надіслано: команди вимкнено в Odoo» без POST, таймер
        не запускається (AC-66, див. також ``test_ac66_commands_disabled_in_odoo``). Кнопка — лише тех.
        адміністратору, у формі — з підтвердженням про справжній генератор; перемикач у формі лише показує стан.
        Увімкнення — трекінг поля від імені користувача і нотатка в чатері (хто/коли); «Заборонити команди» — одразу."""
        genset = self.genset
        genset.sudo().commands_allowed = False
        with freeze_time(NOW):
            self._online(controller_mode='auto')
            wizard = self.env['td.genset.command.wizard'].with_user(self.user_t).create(
                {'genset_id': genset.id, 'command': 'manual'})
            wizard.action_confirm()
            self.run_commands()
            command = self.env['td.genset.command'].search([('genset_id', '=', genset.id)])
            self.assertEqual((command.state, command.result_note),
                             ('disabled_odoo', 'Не надіслано: команди вимкнено в Odoo'))
            self.assertFalse(self._posts())
            with self.assertRaisesRegex(UserError, 'Команди вимкнено в Odoo'):
                genset.with_user(self.user_s)._timer_start(30, self.user_s)
            # кнопка — лише Т; поле теж недоступне С/А
            for user in (self.user_s, self.user_a):
                with self.assertRaises(AccessError):
                    genset.with_user(user).action_allow_commands()
                with self.assertRaises(AccessError):
                    genset.with_user(user).write({'commands_allowed': True})
            # форма: перемикач readonly, «Дозволити команди» з підтвердженням про справжній генератор
            arch = self._form_arch(self.user_t)
            [toggle] = arch.xpath("//field[@name='commands_allowed']")
            self.assertEqual(toggle.get('readonly'), '1')
            [allow] = arch.xpath("//button[@name='action_allow_commands']")
            self.assertIn('справжній генератор', allow.get('confirm'))
            self.assertIn('справжній генератор', allow.get('confirm-title'))
            [forbid] = arch.xpath("//button[@name='action_forbid_commands']")
            self.assertFalse(forbid.get('confirm'), 'стоп-кран спрацьовує без діалогу')
            for user in (self.user_s, self.user_a):
                self.assertFalse(self._form_arch(user).xpath("//button[@name='action_allow_commands']"))
            # увімкнення: трекінг від імені Т і нотатка в чатері (трекінг попередніх кроків тесту — окремо: у проді
            # кожна кнопка — своя транзакція)
            self.env.flush_all()
            self.env.cr.precommit.run()
            genset.with_user(self.user_t).action_allow_commands()
            self.env.flush_all()
            self.env.cr.precommit.run()
            self.assertTrue(genset.sudo().commands_allowed)
            tracking = self.env['mail.tracking.value'].sudo().search([
                ('field_id.name', '=', 'commands_allowed'), ('mail_message_id.model', '=', 'td.genset'),
                ('mail_message_id.res_id', '=', genset.id), ('new_value_integer', '=', 1)])
            self.assertEqual(len(tracking), 1)
            self.assertEqual((tracking.old_value_integer, tracking.new_value_integer), (0, 1))
            self.assertEqual(tracking.mail_message_id.author_id, self.user_t.partner_id)
            note = self.env['mail.message'].search([('model', '=', 'td.genset'), ('res_id', '=', genset.id),
                                                    ('body', 'ilike', 'Команди дозволено')])
            self.assertEqual(note.author_id, self.user_t.partner_id)
            self.assertIn(self.user_t.name, html2plaintext(note.body))
            # тепер та сама команда йде на ретранслятор
            self.env['td.genset.command.wizard'].with_user(self.user_t).create(
                {'genset_id': genset.id, 'command': 'manual'}).action_confirm()
            self.run_commands()
            self.assertEqual([call['json']['command'] for call in self._posts()], ['manual'])
            # стоп-кран: одразу, з нотаткою
            genset.with_user(self.user_t).action_forbid_commands()
            self.assertFalse(genset.sudo().commands_allowed)
            self.assertTrue(self.env['mail.message'].search_count([
                ('model', '=', 'td.genset'), ('res_id', '=', genset.id), ('body', 'ilike', 'Команди заборонено')]))

    # ------------------------------------------------------------------ деінсталяція і копія бази
    def test_uninstall_hook_removes_relay_parameters(self):
        """Деінсталяція: ``uninstall_hook`` (у маніфесті) видаляє ``td_genset.relay_token``, адресу й таймаут; інші
        параметри не чіпає (символ «_» у LIKE — не шаблон). Команда ТО «Генератори», на яку посилається заявка ТО,
        лишається звичайним записом (без xml id модуля), активності генераторів видаляються — деінсталяція без
        помилок ``violates foreign key constraint`` (повна деінсталяція перевірена ``button_immediate_uninstall``)."""
        self.assertEqual(get_manifest('td_genset').get('uninstall_hook'), 'uninstall_hook')
        icp = self.env['ir.config_parameter'].sudo()
        icp.set_param('tdXgenset.keep', 'x')
        self.assertEqual(icp.get_param('td_genset.relay_token'), TOKEN)
        genset = self.genset.sudo()
        genset.write({'run_hours_total': 40.0})
        genset._check_maintenance()             # заявка ТО (команда «Генератори») і активність «Термін ТО»
        team = self.env.ref('td_genset.maintenance_team_genset')
        self.assertTrue(self.env['maintenance.request'].search_count([('maintenance_team_id', '=', team.id)]))
        self.assertTrue(self.env['mail.activity'].search_count([('res_model', '=', 'td.genset')]))
        uninstall_hook(self.env)
        for key in ('td_genset.relay_token', 'td_genset.relay_url', 'td_genset.http_timeout'):
            self.assertFalse(icp.get_param(key), key)
        self.assertEqual(icp.get_param('tdXgenset.keep'), 'x')
        self.assertTrue(icp.get_param('database.uuid'))
        self.assertFalse(self.env['mail.activity'].search_count([('res_model', '=', 'td.genset')]))
        self.assertTrue(team.exists())
        self.assertFalse(self.env['ir.model.data'].search_count(
            [('module', '=', 'td_genset'), ('name', 'in', ('maintenance_team_genset', 'controller_hgm6120n'))]))

    def test_neutralize_copy_of_production(self):
        """Копія проду на тесті (``odoo-bin neutralize`` / відновлення з neutralize): стандартний механізм Odoo
        знаходить ``data/neutralize.sql``; після нього опитування й команди вимкнено на всіх генераторах, токена немає,
        cron модуля неактивні; адреса API лишається."""
        own = list(get_neutralization_queries(['td_genset']))     # td_genset/data/neutralize.sql, як у neutralize_database
        self.assertEqual(len(own), 1)
        self.assertIn('UPDATE td_genset', own[0])
        second = self._new_genset().sudo()
        second.write({'relay_enabled': True, 'commands_allowed': True})
        self.env.flush_all()
        self.env.cr.execute(own[0])
        self.env.invalidate_all()
        self.env.registry.clear_cache()
        for genset in (self.genset, second):
            self.assertFalse(genset.sudo().relay_enabled)
            self.assertFalse(genset.sudo().commands_allowed)
        icp = self.env['ir.config_parameter'].sudo()
        self.assertFalse(icp.get_param('td_genset.relay_token'))
        self.assertEqual(icp.get_param('td_genset.relay_url'), BASE_URL)
        for xmlid in CRON_XMLIDS:
            self.assertFalse(self.env.ref('td_genset.%s' % xmlid).active, xmlid)
        # стоп-крани діють: cron забору і планувальника генератори пропускають
        self.run_pull()
        self.assertFalse(self.relay.calls)

    # ------------------------------------------------------------------ логи
    def test_logs_quiet_in_normal_work_and_errors_once(self):
        """Знімок без змін — жодного запису INFO+ від модуля; ретранслятор недоступний — WARNING один раз (кроки
        забору й команд щохвилини — DEBUG), нагадування — раз на годину; відновлення — один INFO."""
        with freeze_time(NOW):
            self._online()
            self.push_reading(snapshot())
            with self.assertNoLogs(LOGGER, level='INFO'):
                self.run_pull()       # новий знімок без змін
                self.run_pull()       # нових знімків немає
                self.run_scheduler()
                self.run_commands()
            # команда в роботі: її кроки під час збою пишуть у той самий ключ «ретранслятор» (DEBUG після першого WARNING)
            self.env['td.genset.command']._enqueue(self.genset, 'manual', 'schedule', 'Odoo: розклад')
        self.relay.fail('timeout')
        with self.assertLogs(LOGGER, level='DEBUG') as logs:
            for minute in range(1, 6):
                with freeze_time(NOW + timedelta(minutes=minute)):
                    self.run_pull()
                    self.run_commands()
        self.assertTrue([record for record in logs.records if 'command' in record.getMessage()
                         and record.levelno == logging.DEBUG], 'кроки команди під час збою — DEBUG')
        warnings = self._records(logs, logging.WARNING)
        self.assertEqual(len(warnings), 1, [record.getMessage() for record in warnings])
        self.assertIn('ретранслятор: GET /status', warnings[0].getMessage())
        self.assertNotIn(TOKEN, '\n'.join(logs.output))
        with self.assertLogs(LOGGER, level='DEBUG') as logs:
            with freeze_time(NOW + timedelta(minutes=62)):
                self.run_pull()
            with freeze_time(NOW + timedelta(minutes=63)):
                self.run_pull()
        warnings = self._records(logs, logging.WARNING)
        self.assertEqual(len(warnings), 1)
        self.assertIn('триває 61 хв, повторів:', warnings[0].getMessage())
        self.relay.fail(None)
        with freeze_time(NOW + timedelta(minutes=64)):
            self.push_reading(snapshot())
            with self.assertLogs(LOGGER, level='INFO') as logs:
                self.run_pull()
        infos = self._records(logs, logging.INFO)
        self.assertEqual(len(infos), 1)
        self.assertIn('ретранслятор знову відповідає — після 63 хв помилок (повторів:', infos[0].getMessage())
        self.assertFalse(self._records(logs, logging.WARNING))

    def test_log_dedup_helper(self):
        """``td_logging``: інший код помилки — знову WARNING; ``exc_info`` лише у WARNING; без помилок — тиша."""
        logger = logging.getLogger(LOGGER + '.test')
        with freeze_time(NOW), self.assertLogs(logger, level='DEBUG') as logs:
            self.assertEqual(td_logging.log_failure(logger, self.env, 'k', 500, 'збій %s', 1), logging.WARNING)
            self.assertEqual(td_logging.log_failure(logger, self.env, 'k', 500, 'збій %s', 2, exc_info=True),
                             logging.DEBUG)
            self.assertEqual(td_logging.log_failure(logger, self.env, 'k', 401, 'збій %s', 3), logging.WARNING)
            self.assertTrue(td_logging.log_recovered(logger, self.env, 'k', 'працює'))
            self.assertFalse(td_logging.log_recovered(logger, self.env, 'k', 'працює'))
        self.assertEqual([record.levelno for record in logs.records],
                         [logging.WARNING, logging.DEBUG, logging.WARNING, logging.INFO])
        self.assertFalse(logs.records[1].exc_info)

    def test_maintenance_failure_does_not_stop_readings(self):
        """Збій створення заявки ТО (напр., обмеження іншого модуля на ``maintenance.request``) не відкочує сторінку
        знімків: курсор іде далі, у лог — один WARNING на кілька кроків."""
        genset_cls = type(self.env['td.genset'])
        with freeze_time(NOW), patch.object(genset_cls, '_check_maintenance', side_effect=ValueError('заявка ТО')), \
                self.assertLogs(LOGGER, level='WARNING') as logs:
            for _index in range(3):
                self.push_reading(snapshot())
                self.run_pull()
        self.assertEqual(self.genset.readings_cursor, 3)
        self.assertEqual(self.genset.last_reading_id.relay_id, 3)
        self.assertEqual(len(logs.records), 1)
        self.assertIn('перевірка ТО не вдалася: заявка ТО', logs.records[0].getMessage())

    # ------------------------------------------------------------------ мультикомпанійність (прод — 5 компаній)
    def test_multi_company(self):
        """Друга компанія і користувачі лише в ній: генератор, знімки, події, тривоги видно всім (рішення 1.3, без
        record rules); форма відкривається; заявка ТО генератора компанії B — у компанії B з командою «Генератори»
        (спільна, без компанії), без помилки check_company; майстри надходження і заправки працюють з компанії B;
        блок «Генератори» в Налаштуваннях — для системного адміністратора."""
        company_b = self.env['res.company'].create({'name': 'IT.Artel (тест)'})
        users = self.env['res.users'].with_context(no_reset_password=True)

        def user_b(login, name, group):
            return users.create(dict(self._user_vals(login, name, group), company_id=company_b.id,
                                     company_ids=[Command.set(company_b.ids)]))

        emp_b = user_b('td_user_b_s', 'Співробітник компанії B', self.group_user)
        admin_b = user_b('td_user_b_a', 'Адміністратор компанії B', self.group_admin)
        tech_b = user_b('td_user_b_t', 'Тех. адміністратор компанії B', self.group_tech)
        with freeze_time(NOW - timedelta(minutes=30)):
            self._online()
        with freeze_time(NOW - timedelta(minutes=20)):
            self.push_reading(snapshot(mains_normal=False, low_fuel_warning=True), reason='change')
            self.run_pull()
        with freeze_time(NOW):
            self.push_reading(snapshot(low_fuel_warning=True), reason='change')
            self.run_pull()
        genset_a = self.genset
        self.assertEqual(genset_a.company_id, self.env.ref('base.main_company'))
        for user in (emp_b, admin_b, tech_b):
            env = self.env(user=user)
            self.assertEqual(env.company, company_b)
            self.assertIn(genset_a, env['td.genset'].search([]))
            self.assertTrue(env['td.genset.reading'].search_count([('genset_id', '=', genset_a.id)]))
            self.assertTrue(env['td.genset.event'].search_count([('genset_id', '=', genset_a.id)]))
            self.assertTrue(env['td.genset.alarm'].search_count([('genset_id', '=', genset_a.id)]))
            form = Form(genset_a.with_user(user))
            self.assertEqual(form.name, 'Стенд')
            self.assertTrue(genset_a.with_user(user).get_pult_state()['buttons'])
        # генератор компанії B (створив тех. адміністратор компанії B): обладнання і заявка ТО — у компанії B
        team = self.env.ref('td_genset.maintenance_team_genset')
        self.assertFalse(team.company_id)
        self.assertFalse(self.env.ref('td_genset.equipment_category_genset').company_id)
        genset_b = self._new_genset(user=tech_b)
        self.assertEqual(genset_b.company_id, company_b)
        equipment = genset_b.sudo().equipment_id
        self.assertEqual((equipment.company_id, equipment.maintenance_team_id), (company_b, team))
        genset_b.sudo().write({'run_hours_total': 40.0})
        with freeze_time(NOW):
            genset_b.sudo()._check_maintenance()      # як cron: OdooBot, компанія за замовчуванням — головна
        request = self.env['maintenance.request'].sudo().search([('equipment_id', '=', equipment.id)])
        self.assertEqual(len(request), 1)
        self.assertEqual((request.company_id, request.maintenance_team_id), (company_b, team))
        Form(genset_b.with_user(self.user_t))        # картку генератора компанії B відкриває користувач компанії A
        # майстри палива з компанії B для генератора компанії A
        location = self.env['td.genset.storage.location'].with_user(admin_b).create({'name': 'Щитова B'})
        self.env['td.genset.fuel.receipt.wizard'].with_user(admin_b).create({
            'mode': 'new', 'canister_qty': 1, 'canister_volume_l': 20.0, 'location_id': location.id,
        }).action_confirm()
        canister = self.env['td.genset.canister'].with_user(admin_b).search([('location_id', '=', location.id)])
        self.assertEqual(canister.liters, 20.0)
        self.env['td.genset.refuel.wizard'].with_user(admin_b).create({
            'genset_id': genset_a.id, 'source': 'other', 'source_note': 'АЗС', 'liters': 5.0,
        }).action_confirm()
        self.assertTrue(self.env['td.genset.refuel'].search_count([('genset_id', '=', genset_a.id)]))
        # Налаштування → Генератори: адреса і токен — системному адміністратору
        admin = self.env.ref('base.user_admin')
        arch = self._form_arch(admin, 'res.config.settings')
        self.assertTrue(arch.xpath("//app[@name='td_genset']//field[@name='td_genset_relay_token']"))
        self.assertTrue(arch.xpath("//app[@name='td_genset']//field[@name='td_genset_relay_url']"))

    # ------------------------------------------------------------------ тексти сповіщень (push у мобільний застосунок)
    def test_notification_texts_self_contained(self):
        """Сповіщення ланцюжку (``message_notify`` → вхідні Odoo і push ``mail_mobile``): тема «<генератор>: <тривога>»,
        у тексті — генератор і час виникнення за Києвом; інформаційні події — генератор і час."""
        with freeze_time(NOW):
            alarm = self.env['td.genset.alarm']._raise(
                self.genset, 'link_lost', 'crit', "Немає зв'язку з модулем",
                "Немає зв'язку з модулем з 11:47 (13 хв). Пульт недоступний.")
            self.env['td.genset.alarm']._cron_escalate()
        self.assertEqual(alarm._td_push_subject(), "Стенд: Немає зв'язку з модулем")
        message = self.env['mail.message'].search([('message_type', '=', 'user_notification'),
                                                   ('partner_ids', 'in', self.user_s.partner_id.ids)])
        self.assertEqual(len(message), 1)
        self.assertEqual(message.subject, "Стенд: Немає зв'язку з модулем")
        text = html2plaintext(message.body)
        self.assertIn('Генератор: Стенд · виникла 08.10 о 12:00 · рівень ланцюжка: Черговий', text)
        self.assertIn('з 11:47 (13 хв)', text)
        self.config.notify_info = 'always'
        with freeze_time(NOW + timedelta(minutes=5)):
            self.genset._td_post_info("Зв'язок відновлено після 18 хв без даних.")
        info = self.env['mail.message'].search([('message_type', '=', 'user_notification'),
                                                ('partner_ids', 'in', self.user_s.partner_id.ids),
                                                ('id', '!=', message.id)])
        self.assertEqual(info.subject, 'Стенд')
        self.assertIn('Генератор: Стенд · 08.10 12:05', html2plaintext(info.body))

    # ------------------------------------------------------------------ ретранслятор 1.1.1 (як на сервері зараз)
    def test_relay_111_raw_and_cloud_commands_null(self):
        """1.1.1: «Автоматично» → ``raw=1`` (ключів ``*_sensor_ohm`` немає), оми — з сирого образу;
        ``cloud_commands_seen`` зі старими записами ``command: null`` — історія без подій; новий запис з
        ``command: null`` — подія «Керування не з Odoo: команда (застосунок SmartGen)» без помилок і тривоги."""
        self.set_status(version='1.1.1', cloud_commands_seen=[
            {'time_utc': '2026-10-07T15:07:21Z', 'frame': '00050006FF006DEA', 'format': 'rtu', 'command': None},
            {'time_utc': '2026-10-07T15:40:10Z', 'frame': '00050003FF007DEB', 'format': 'rtu', 'slave': 0,
             'command': 'auto'},
        ])
        with freeze_time(NOW):
            with self.assertNoLogs(LOGGER, level='WARNING'):
                self._online()
            # сторінки знімків (проба курсору ``limit=1`` для «Починати історію з» — без raw)
            readings_calls = [call for call in self.relay.calls
                              if call['path'] == '/readings' and call['params'].get('limit') != '1']
            self.assertTrue(readings_calls)
            self.assertTrue(all(call['params'].get('raw') == '1' for call in readings_calls))
            self.assertEqual(self.genset.relay_version, '1.1.1')
            self.assertTrue(self.genset.fuel_sensor_ohm)
            self.assertFalse(self.env['td.genset.event'].search_count(
                [('genset_id', '=', self.genset.id), ('event_type', '=', 'external_control')]))
        self.set_status(cloud_commands_seen=[
            {'time_utc': '2026-10-07T15:40:10Z', 'frame': '00050003FF007DEB', 'format': 'rtu', 'command': 'auto'},
            {'time_utc': '2026-10-08T09:00:30Z', 'frame': '000500FFFF000000', 'format': 'rtu', 'command': None},
        ])
        with freeze_time(NOW + timedelta(minutes=1)):
            self.push_reading(snapshot())
            with self.assertNoLogs(LOGGER, level='WARNING'):
                self.run_pull()
        event = self.env['td.genset.event'].search([('genset_id', '=', self.genset.id),
                                                    ('event_type', '=', 'external_control')])
        self.assertEqual(len(event), 1)
        self.assertEqual(event.summary, 'команда (застосунок SmartGen)')
        self.assertFalse(self.env['td.genset.alarm'].search_count(
            [('genset_id', '=', self.genset.id), ('code', '=', 'external_control')]))
