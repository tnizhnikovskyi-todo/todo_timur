# Part of td_genset (ToDo). Власник файлу: W4 «Паливо і ТО».
"""Обладнання, авто-заявка, закриття ТО (AC-53, AC-54).

Базовий клас — ``TdGensetCase``. Мотогодини генератора (``run_hours_total`` копіює з останнього знімка W1)
задаються напряму; ``_raise``/``_clear`` тривог (W1) перехоплюються ``patch.object`` (``AlarmSpyMixin``).
"""
from dateutil.relativedelta import relativedelta
from freezegun import freeze_time
from lxml import etree

from odoo import fields
from odoo.tests import tagged

from .common import TdGensetCase
from .test_w4_fuel import AlarmSpyMixin

FIRST_REQUEST = 'ТО-1 після обкатки (30 мотогодин)'


@tagged('standard', 'at_install')
class TestW4Maintenance(AlarmSpyMixin, TdGensetCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.team = cls.env.ref('td_genset.maintenance_team_genset')
        cls.category = cls.env.ref('td_genset.equipment_category_genset')
        cls.activity_check = cls.env.ref('td_genset.activity_check')
        cls.stage_done = cls.env.ref('maintenance.stage_3')     # Repaired (done)
        cls.stage_scrap = cls.env.ref('maintenance.stage_4')    # Scrap (done)

    def setUp(self):
        super().setUp()
        self._spy_alarms()
        self.requests = self.env['maintenance.request']

    def _set_hours(self, hours, genset=None):
        (genset or self.genset).sudo().run_hours_total = hours

    def _genset_requests(self, open_only=False):
        domain = [('equipment_id', '=', self.genset.equipment_id.id)]
        if open_only:
            domain.append(('stage_id.done', '=', False))
        return self.requests.search(domain, order='id')

    def _close_first_request(self, hours=31.2):
        self._set_hours(30.0)
        self.genset._check_maintenance()
        request = self._genset_requests()
        self._set_hours(hours)
        request.with_user(self.user_t).write({'stage_id': self.stage_done.id})
        return request

    # ------------------------------------------------------------------ AC-53
    def test_ac53_equipment_and_auto_request(self):
        """AC-53: генератор (перше ТО 30 год), мотогодини 29,9 → 30,0 → обладнання «Генератор · …» категорії
        «Генератори»; заявка ТО (превентивна, команда «Генератори», виконавець — відповідальний, опис із
        чек-листом), попередження «Термін ТО» і активність; друга заявка не створюється, поки перша відкрита."""
        genset = self.genset
        equipment = genset.equipment_id
        self.assertTrue(equipment)
        self.assertEqual(equipment.name, 'Генератор · Стенд')
        self.assertEqual((equipment.category_id, equipment.maintenance_team_id), (self.category, self.team))
        self.assertEqual((equipment.technician_user_id, equipment.td_genset_id), (self.user_t, genset))
        self.assertEqual(genset.maint_first_hours, 30)

        self._set_hours(29.9)
        genset._check_maintenance()
        self.assertFalse(self._genset_requests())
        self.assertEqual((genset.maint_hours_left, genset.maint_state), (0.1, 'due'))
        self.assertFalse(self._calls(self.raised, 'maintenance_due'))

        self._set_hours(30.0)
        genset._check_maintenance()
        request = self._genset_requests()
        self.assertEqual(len(request), 1)
        self.assertEqual(request.name, FIRST_REQUEST)
        self.assertEqual(request.maintenance_type, 'preventive')
        self.assertEqual(request.maintenance_team_id, self.team)
        self.assertEqual(request.user_id, self.user_t)
        self.assertIn('Замінити оливу і масляний фільтр', request.description)
        self.assertEqual(request.td_genset_id, genset)
        self.assertFalse(request.td_partner_id)
        self.assertFalse(request.stage_id.done)
        self.assertEqual(request.request_date, fields.Date.context_today(request))
        self.assertTrue(request.schedule_date)
        warnings = self._calls(self.raised, 'maintenance_due')
        self.assertEqual(len(warnings), 1)
        self.assertEqual((warnings[0]['genset'], warnings[0]['level'], warnings[0]['source']), (genset, 'warn', request))
        self.assertEqual(warnings[0]['name'], 'Термін ТО: перше 30 год. Створено заявку «%s».' % FIRST_REQUEST)
        activities = genset.activity_ids.filtered(lambda activity: activity.activity_type_id == self.activity_check)
        self.assertEqual(len(activities), 1)
        self.assertEqual((activities.user_id, activities.summary), (self.user_t, 'Термін ТО'))
        genset.invalidate_recordset()
        self.assertEqual((genset.maint_hours_left, genset.maint_state, genset.maint_progress), (0.0, 'overdue', 100.0))

        # друга заявка не створюється, поки перша відкрита (cron і знімки викликають перевірку повторно)
        self._set_hours(35.0)
        genset._check_maintenance()
        self.env['td.genset']._check_maintenance()
        self.assertEqual(len(self._genset_requests()), 1)
        self.assertEqual(len(self._calls(self.raised, 'maintenance_due')), 1)

    def test_ac53_maintenance_data_in_install_company(self):
        """AC-53 (DoD W4): категорія обладнання і команда ТО «Генератори» (data) — у компанії встановлення;
        налаштування посилаються на команду; обладнання — в компанії генератора."""
        company = self.env.ref('base.main_company')
        self.assertEqual(self.env.company, company)
        self.assertEqual(self.team.company_id, company)
        self.assertEqual(self.category.company_id, company)
        self.assertEqual(self.config.maint_team_id, self.team)
        self.assertEqual(self.genset.equipment_id.company_id, self.genset.company_id)

    def test_ac53_equipment_follows_genset(self):
        """AC-53 / ТР 2.9: обладнання синхронізується з карткою — назва, відповідальний, архів разом з генератором;
        у режимі догону авто-заявка не створюється."""
        genset = self.genset
        equipment = genset.equipment_id
        genset.with_user(self.user_t).write({'name': 'Садова вулиця', 'user_id': self.user_a.id})
        self.assertEqual((equipment.name, equipment.technician_user_id), ('Генератор · Садова вулиця', self.user_a))
        genset.with_user(self.user_t).action_archive()
        self.assertFalse(equipment.active)
        genset.with_user(self.user_t).action_unarchive()
        self.assertTrue(equipment.active)
        self.assertEqual(genset.equipment_id, equipment)

        other = self.env['td.genset'].with_user(self.user_t).create({
            'name': 'Другий', 'controller_model_id': self.controller_model.id, 'power_kw': 10.0})
        self.assertEqual(other.equipment_id.name, 'Генератор · Другий')
        self.assertNotEqual(other.equipment_id, equipment)

        genset.sudo().catchup_mode = True
        self._set_hours(40.0)
        genset._check_maintenance()
        self.assertFalse(self._genset_requests())
        genset.sudo().catchup_mode = False
        genset._check_maintenance()
        self.assertEqual(len(self._genset_requests()), 1)

    # ------------------------------------------------------------------ AC-54
    def test_ac54_close_request_new_countdown(self):
        """AC-54: заявка в стадії «Виконано» на 31,2 мотогодин, інтервал 250 год / 12 міс. → «До ТО: 250 год»,
        дата наступного ТО через 12 місяців, попередження знято; «Підрядник» — контакт без доступу до системи."""
        genset = self.genset
        self._set_hours(30.0)
        genset._check_maintenance()
        request = self._genset_requests()
        contractor = self.env['res.partner'].create({'name': 'СервісГен', 'is_company': True})
        request.with_user(self.user_t).td_partner_id = contractor
        self.assertFalse(contractor.user_ids)
        arch = etree.fromstring(self.requests.with_user(self.user_t).get_view(view_type='form')['arch'])
        self.assertTrue(arch.xpath("//field[@name='td_partner_id']"), 'поле «Підрядник» у формі заявки')

        self._set_hours(31.2)
        request.with_user(self.user_t).write({'stage_id': self.stage_done.id})
        today = fields.Date.context_today(request)
        self.assertEqual(request.td_run_hours_at_close, 31.2)
        self.assertEqual(request.close_date, today)
        genset.invalidate_recordset()
        self.assertEqual(genset.maint_hours_left, 250.0)
        self.assertEqual(genset.maint_next_hours, 281.2)
        self.assertEqual(genset.maint_due_date, today + relativedelta(months=12))
        self.assertEqual(genset.maint_state, 'ok')
        cleared = self._calls(self.cleared, 'maintenance_due')
        self.assertEqual(len(cleared), 1)
        self.assertEqual(cleared[0]['genset'], genset)
        self.assertFalse(genset.activity_ids.filtered(lambda activity: activity.activity_type_id == self.activity_check))
        self.assertTrue(genset.message_ids.filtered(lambda message: 'ТО виконано' in (message.body or '')))

        # перехід між стадіями «виконано» не перезаписує мотогодини закриття
        self._set_hours(40.0)
        request.with_user(self.user_t).write({'stage_id': self.stage_scrap.id})
        self.assertEqual(request.td_run_hours_at_close, 31.2)
        genset._check_maintenance()
        self.assertFalse(self._genset_requests(open_only=True))

        # наступний цикл — через 250 мотогодин після закриття
        self._set_hours(281.2)
        genset._check_maintenance()
        second = self._genset_requests(open_only=True)
        self.assertEqual(second.name, 'ТО-2: кожні 250 мотогодин')
        self.assertEqual(self._calls(self.raised, 'maintenance_due')[-1]['name'],
                         'Термін ТО: кожні 250 год. Створено заявку «ТО-2: кожні 250 мотогодин».')

    def test_ac54_next_maintenance_by_months(self):
        """AC-54 / ФВ-35: «або раз на 12 міс.» — що настане раніше: за 30 днів до дати — «Скоро ТО», у дату —
        прострочено і нова заявка; до першого закриття відлік місяців — від введення в експлуатацію."""
        genset = self.genset
        request = self._close_first_request()
        due_date = request.close_date + relativedelta(months=12)
        with freeze_time(due_date - relativedelta(days=10)):
            genset.invalidate_recordset()
            self.assertEqual(genset.maint_state, 'due')
        with freeze_time(due_date):
            genset.invalidate_recordset()
            self.assertEqual(genset.maint_state, 'overdue')
            genset._check_maintenance()
            second = self._genset_requests(open_only=True)
            self.assertEqual(second.name, 'ТО-2: раз на 12 міс.')
            self.assertEqual(self._calls(self.raised, 'maintenance_due')[-1]['name'],
                             'Термін ТО: 12 міс. Створено заявку «ТО-2: раз на 12 міс.».')

        other = self.env['td.genset'].create({
            'name': 'Другий', 'controller_model_id': self.controller_model.id, 'power_kw': 10.0,
            'commissioning_date': fields.Date.context_today(genset) - relativedelta(months=13)})
        self.assertEqual(other.maint_state, 'overdue')
        self.assertEqual(other.maint_hours_left, 30.0)
        other._check_maintenance()
        first = self.requests.search([('equipment_id', '=', other.equipment_id.id)])
        self.assertEqual(first.name, 'ТО-1: раз на 12 міс.')
