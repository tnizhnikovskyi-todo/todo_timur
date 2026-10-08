# Part of td_genset (ToDo). Власник файлу: W1. Заготовка: W0.
"""ескалація, тихі години, «Прийняв», тестове сповіщення (AC-42…AC-44, AC-63).

Базовий клас — ``odoo.addons.td_genset.tests.common.TdGensetCase`` (RelayMock, snapshot(), push_reading,
set_status, run_pull/run_commands/run_scheduler). Імена тестів — ``test_acNN_<що>``, AC у докстрингу.
"""
from datetime import datetime, timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo.exceptions import AccessError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import TdGensetCase, snapshot

NIGHT = datetime(2026, 10, 7, 20, 10, 0)      # 23:10 за Києвом
MORNING = datetime(2026, 10, 8, 4, 0, 0)      # 07:00 за Києвом
DAY = datetime(2026, 10, 7, 9, 0, 0)          # 12:00 за Києвом


@tagged('standard', 'at_install')
class TestW1AlarmsEscalation(TdGensetCase):

    def _notified(self, user, subject=None):
        domain = [('message_type', '=', 'user_notification'), ('partner_ids', 'in', user.partner_id.ids)]
        if subject:
            domain.append(('subject', '=', subject))
        return self.env['mail.message'].search(domain)

    def _escalate(self, moment):
        with freeze_time(moment):
            self.env['td.genset.alarm']._cron_escalate()

    def _raise(self, moment, code, level, name):
        with freeze_time(moment):
            return self.env['td.genset.alarm']._raise(self.genset, code, level, name, 'Опис «%s»' % name)

    def test_ac42_escalation_chain_and_quiet_hours(self):
        """AC-42: критична о 23:10 → К. 23:10, Н. 23:20, М. 23:40; повідомлення тривоги в чатері генератора;
        попередження о 23:10 — сповіщення о 07:00; «Лише в чаті» — без сповіщень."""
        self.assertEqual((self.config.notify_crit, self.config.notify_warn, self.config.notify_info),
                         ('always', 'not_quiet', 'chatter'))
        crit = self._raise(NIGHT, 'test_crit', 'crit', 'Аварійна зупинка: тест')
        self.assertEqual((crit.state, crit.escalation_level, crit.next_escalation_at), ('active', 0, NIGHT))
        posted = self.env['mail.message'].search([('model', '=', 'td.genset'), ('res_id', '=', self.genset.id),
                                                  ('subtype_id', '=', self.env.ref('td_genset.mt_alarm').id)])
        self.assertTrue(posted.filtered(lambda message: 'Аварійна зупинка: тест' in message.body))
        self._escalate(NIGHT)
        self.assertEqual(crit.notified_user_ids, self.user_s)
        self.assertEqual(len(self._notified(self.user_s, crit.name)), 1)
        self._escalate(NIGHT + timedelta(minutes=9))
        self.assertEqual(crit.notified_user_ids, self.user_s)
        self._escalate(NIGHT + timedelta(minutes=10))
        self.assertEqual(crit.notified_user_ids, self.user_s | self.user_a)
        self._escalate(NIGHT + timedelta(minutes=29))
        self.assertNotIn(self.user_t, crit.notified_user_ids)
        self._escalate(NIGHT + timedelta(minutes=30))
        self.assertEqual(crit.notified_user_ids, self.user_s | self.user_a | self.user_t)
        self.assertFalse(crit.next_escalation_at)
        self.assertEqual(crit.escalation_level, 3)
        # попередження в тихі години → о 07:00
        warn = self._raise(NIGHT, 'test_warn', 'warn', 'Попередження: тест')
        self._escalate(NIGHT)
        self.assertFalse(warn.notified_user_ids)
        self.assertEqual(warn.next_escalation_at, MORNING)
        self._escalate(MORNING - timedelta(minutes=1))
        self.assertFalse(warn.notified_user_ids)
        self._escalate(MORNING)
        self.assertEqual(warn.notified_user_ids, self.user_s)
        self.assertEqual(warn.next_escalation_at, MORNING + timedelta(minutes=10))
        # «Лише в чаті»: інформація — лише запис у чатер
        info = self._raise(NIGHT, 'test_info', 'info', 'Інформація: тест')
        self._escalate(NIGHT + timedelta(hours=12))
        self.assertFalse(info.notified_user_ids)
        self.assertFalse(info.next_escalation_at)
        self.assertFalse(self._notified(self.user_s, info.name))
        # повторне підняття того самого коду не дублює тривогу
        self.assertEqual(self._raise(NIGHT, 'test_crit', 'crit', 'Аварійна зупинка: тест'), crit)

    def test_d08_quiet_hours_no_follower_notifications(self):
        """D-08 (ТК-09.3): у тихі години тривоги з правилом не «Завжди» — у чатері запис без сповіщень (підписник
        генератора вночі нічого не отримує), о 07:00 — сповіщення підписникам (і ланцюжку), якщо тривога ще активна;
        знята вночі — без ранкового сповіщення, і її «знято» теж без сповіщень; «Долити паливо» — о 07:00;
        критична («Завжди») — як і раніше, одразу з підписниками."""
        alarm_subtype = self.env.ref('td_genset.mt_alarm')
        follower = self.user_x.partner_id
        self.genset.message_subscribe(partner_ids=follower.ids, subtype_ids=alarm_subtype.ids)
        Notification = self.env['mail.notification']

        def notified():
            return Notification.search_count([('res_partner_id', '=', follower.id)])

        def chatter(text):
            return self.env['mail.message'].search([('model', '=', 'td.genset'), ('res_id', '=', self.genset.id),
                                                    ('body', 'ilike', text)])

        warn = self._raise(NIGHT, 'test_warn', 'warn', 'Запас у каністрах нижчий за мінімальний')
        message = chatter('Запас у каністрах нижчий за мінімальний')
        self.assertEqual(len(message), 1)
        self.assertEqual(message.subtype_id, self.env.ref('mail.mt_note'))
        self.assertEqual((notified(), warn.followers_notify_at), (0, MORNING))
        fuel = self._raise(NIGHT, 'low_fuel', 'warn', 'Низький рівень палива: 20 L')
        refuel = self.env.ref('td_genset.activity_refuel')
        self.assertFalse(self.genset.activity_ids.filtered(lambda act: act.activity_type_id == refuel))
        gone = self._raise(NIGHT, 'test_gone', 'warn', 'Попередження, що зникне вночі')
        with freeze_time(NIGHT + timedelta(hours=1)):
            self.env['td.genset.alarm']._clear(self.genset, 'test_gone')
        self.assertEqual(chatter('Попередження, що зникне вночі').subtype_id, self.env.ref('mail.mt_note'))
        self.assertFalse(gone.followers_notify_at)
        self.assertEqual(notified(), 0)
        crit = self._raise(NIGHT, 'test_crit', 'crit', 'Аварійна зупинка: тест')
        self.assertEqual(chatter('Аварійна зупинка: тест').subtype_id, alarm_subtype)
        self.assertFalse(crit.followers_notify_at)
        self.assertEqual(notified(), 1)
        self._escalate(MORNING - timedelta(minutes=1))
        self.assertEqual(notified(), 1)
        self._escalate(MORNING)
        self.assertEqual(notified(), 3)
        self.assertFalse(warn.followers_notify_at or fuel.followers_notify_at)
        morning = self.env['mail.message'].search([('message_type', '=', 'user_notification'),
                                                   ('partner_ids', 'in', follower.ids)])
        self.assertEqual(set(morning.mapped('subject')), {warn.name, fuel.name})
        self.assertIn('у тихі години', morning[0].body)
        self.assertEqual(len(self.genset.activity_ids.filtered(lambda act: act.activity_type_id == refuel)), 1)
        self.assertEqual(warn.notified_user_ids, self.user_s)
        self._escalate(MORNING + timedelta(hours=1))
        self.assertEqual(notified(), 3)

    def test_ac42_quiet_hours_window(self):
        """AC-42: тихі години 22:00–07:00 за Києвом (через північ), кінець — 07:00 наступного ранку."""
        config = self.config
        self.assertTrue(config._quiet_now(NIGHT))
        self.assertFalse(config._quiet_now(DAY))
        self.assertTrue(config._quiet_now(datetime(2026, 10, 8, 3, 59)))
        self.assertFalse(config._quiet_now(MORNING))
        self.assertEqual(config._quiet_end(NIGHT), MORNING)
        self.assertEqual(config._quiet_end(datetime(2026, 10, 8, 1, 0)), MORNING)
        self.assertIsNone(config._quiet_end(DAY))
        config.quiet_enabled = False
        self.assertFalse(config._quiet_now(NIGHT))

    def test_ac42_level_without_user_is_skipped(self):
        """SPEC 5.9: рівень без користувача пропускається з попередженням у логах, наступні — за своїм часом."""
        level_2 = self.config.level_ids.sorted(lambda level: (level.sequence, level.id))[1]
        level_2.user_id = False
        crit = self._raise(DAY, 'test_crit', 'crit', 'Критична: тест')
        self._escalate(DAY)
        with self.assertLogs('odoo.addons.td_genset.models.genset_alarm', level='WARNING'):
            self._escalate(DAY + timedelta(minutes=10))
        self.assertEqual(crit.notified_user_ids, self.user_s)
        self._escalate(DAY + timedelta(minutes=30))
        self.assertEqual(crit.notified_user_ids, self.user_s | self.user_t)

    def test_ac43_ack_stops_escalation(self):
        """AC-43: учасник ланцюжка натискає «Прийняв» → хто/коли, ескалація зупинена, чатер «Прийняв тривогу «…».
        Ескалацію зупинено.»; Співробітник поза ланцюжком кнопки не бачить, виклик → AccessError."""
        crit = self._raise(DAY, 'test_crit', 'crit', 'Критична: тест')
        self._escalate(DAY)
        self.assertFalse(crit.with_user(self.user_x).can_ack)
        with self.assertRaises(AccessError):
            crit.with_user(self.user_x).action_ack()
        self.assertEqual(crit.state, 'active')
        self.assertTrue(crit.with_user(self.user_s).can_ack)
        self.assertTrue(crit.with_user(self.user_t).can_ack)
        with freeze_time(DAY + timedelta(minutes=3)):
            self.assertTrue(crit.with_user(self.user_s).action_ack())
        self.assertEqual((crit.state, crit.acked_user_id, crit.date_acked),
                         ('acked', self.user_s, DAY + timedelta(minutes=3)))
        self.assertFalse(crit.next_escalation_at)
        self._escalate(DAY + timedelta(minutes=40))
        self.assertEqual(crit.notified_user_ids, self.user_s)
        message = self.env['mail.message'].search([('model', '=', 'td.genset'), ('res_id', '=', self.genset.id),
                                                   ('body', 'ilike', 'Ескалацію зупинено')])
        self.assertEqual(len(message), 1)
        self.assertIn('Прийняв тривогу «Критична: тест». Ескалацію зупинено.', message.body)
        self.assertEqual(message.author_id, self.user_s.partner_id)
        # прийнята тривога не дублюється, а коли умова зникає — знімається
        self.assertEqual(self._raise(DAY + timedelta(minutes=5), 'test_crit', 'crit', 'Критична: тест'), crit)
        self.env['td.genset.alarm']._clear(self.genset, 'test_crit')
        self.assertEqual(crit.state, 'cleared')

    def test_ac44_test_notification(self):
        """AC-44: Т у ланцюжку натискає «Надіслати тестове сповіщення» → рівень 1 отримує «Тестове сповіщення
        модуля Генератори»; тривоги й ескалації немає; Адміністратору — AccessError."""
        result = self.config.with_user(self.user_t).action_send_test_notification()
        self.assertEqual(result['params']['type'], 'success')
        notified = self._notified(self.user_s, 'Тестове сповіщення модуля Генератори')
        self.assertEqual(len(notified), 1)
        self.assertFalse(self._notified(self.user_a, 'Тестове сповіщення модуля Генератори'))
        self.assertFalse(self.env['td.genset.alarm'].search([]))
        with self.assertRaises(AccessError):
            self.config.with_user(self.user_a).action_send_test_notification()

    def test_ac63_low_fuel_activity_and_notes(self):
        """AC-63: попередження «низький рівень палива» → активність «Долити паливо» відповідальному (одна);
        Співробітник може «Записати примітку»; підписники бачать повідомлення тривог."""
        with freeze_time(DAY):
            self.push_reading(snapshot(fuel_level=15), ts=DAY - timedelta(seconds=30))
            self.run_pull()
        alarm = self.env['td.genset.alarm'].search([('genset_id', '=', self.genset.id), ('code', '=', 'low_fuel')])
        self.assertEqual((alarm.level, alarm.name), ('warn', 'Низький рівень палива: 22 L'))
        activity_type = self.env.ref('td_genset.activity_refuel')
        activities = self.genset.activity_ids.filtered(lambda act: act.activity_type_id == activity_type)
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities.user_id, self.genset.user_id)
        with freeze_time(DAY + timedelta(minutes=1)):
            self.push_reading(snapshot(fuel_level=14, low_fuel_warning=True), ts=DAY + timedelta(seconds=30))
            self.run_pull()
        self.assertEqual(len(self.genset.activity_ids.filtered(lambda act: act.activity_type_id == activity_type)), 1)
        self.assertTrue(self.env['td.genset.alarm'].search([('genset_id', '=', self.genset.id),
                                                            ('code', '=', 'low_fuel_warning')]))
        note = self.genset.with_user(self.user_s).message_post(body='Перевірив бак', message_type='comment',
                                                               subtype_xmlid='mail.mt_note')
        self.assertTrue(note)
        # долили → тривога знята (з гістерезисом)
        with freeze_time(DAY + timedelta(minutes=2)):
            self.push_reading(snapshot(fuel_level=80), ts=DAY + timedelta(seconds=90))
            self.run_pull()
        self.assertEqual(alarm.state, 'cleared')

    def test_ac42_escalation_cron_never_fails(self):
        """AC-42, А.7: помилка в кроці ескалації однієї тривоги не зупиняє cron і не виходить назовні."""
        crit = self._raise(DAY, 'test_crit', 'crit', 'Критична: тест')
        alarm_class = type(self.env['td.genset.alarm'])
        with patch.object(alarm_class, '_td_notify', side_effect=ValueError('збій сповіщення')), \
                mute_logger('odoo.addons.td_genset.models.genset_alarm'):
            self._escalate(DAY)
        self.assertEqual(crit.escalation_level, 0)
        self._escalate(DAY + timedelta(minutes=1))
        self.assertEqual(crit.notified_user_ids, self.user_s)
