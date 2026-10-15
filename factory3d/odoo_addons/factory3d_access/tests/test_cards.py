from unittest import mock

from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from ..tools import params as P
from ..tools.biostar_client import BioStarError
from .common import AccessCase, FakeBioStar


@tagged('post_install', '-at_install', 'f3d', 'f3d_access')
class TestCards(AccessCase):

    def _card(self, number='11111111', **kw):
        vals = {'number': number, 'server_id': self.server.id, 'holder_type': 'employee',
                'employee_id': self.emp_a.id}
        vals.update(kw)
        return self.env['f3d.access.card'].create(vals)

    def _write(self, enabled):
        P.set_param(self.env, 'write_enabled', 'True' if enabled else 'False')

    def _fake(self, enabled):
        self._write(enabled)
        fake = FakeBioStar()
        fake.write_enabled = enabled
        return fake

    def _visitor(self, **kw):
        vals = {'name': 'Гість', 'host_employee_id': self.emp_a.id, 'server_id': self.server.id}
        vals.update(kw)
        return self.env['f3d.access.visitor'].create(vals)

    def test_constraints(self):  # AC-39
        with self.assertRaisesRegex(ValidationError, 'лише цифри'):
            self._card('AB12')
        self._card('123')
        with self.assertRaises(IntegrityError), mute_logger('odoo.sql_db'):
            self._card('123')
        with self.assertRaisesRegex(ValidationError, 'вкажіть працівника'):
            self._card('124', employee_id=False)
        with self.assertRaisesRegex(ValidationError, 'не прив.язується'):
            self._card('125', holder_type='pool', employee_id=False, visitor_id=self._visitor().id)
        with self.assertRaisesRegex(ValidationError, 'причину блокування'):
            self._card('126', state='blocked')
        with self.assertRaisesRegex(ValidationError, 'вкажіть відвідувача'):
            self._card('127', holder_type='visitor', employee_id=False)

    def test_issue_local(self):  # AC-40
        fake = self._fake(False)
        card = self._card()
        with self.patch_client(fake):
            card.action_issue()
        self.assertEqual((card.state, card.sync_state, card.pending_op), ('active', 'local', 'issue'))
        self.assertIn('стоп-краном', card.message_ids[:1].body)
        self.assertEqual(fake.calls, [])
        self.assertTrue(card.issued_at)

    def test_mark_synced(self):  # AC-40
        fake = self._fake(False)
        card = self._card()
        with self.patch_client(fake):
            card.action_issue()
            card.action_mark_synced()
        self.assertEqual((card.sync_state, card.pending_op), ('synced', False))
        self.assertEqual(fake.calls, [])

    def test_block_synced(self):  # AC-41
        fake = self._fake(True)
        card = self._card(state='active', biostar_card_id='7')
        card.block_reason = 'Звільнення'
        with self.patch_client(fake):
            card.action_block()
        self.assertEqual(fake.calls[-1], ('update_user_cards', 'TSTA1', [{'id': '7', 'is_blocked': 'true'}]))
        self.assertEqual((card.state, card.sync_state, card.pending_op), ('blocked', 'synced', False))
        self.assertIn('Записано в BioStar', card.message_ids[:1].body)

    def test_block_405(self):  # AC-41
        fake = self._fake(True)
        fake.write_status = 405
        card = self._card(state='active', biostar_card_id='7', block_reason='Звільнення')
        with self.patch_client(fake):
            card.action_block()
        self.assertEqual((card.state, card.sync_state, card.sync_attempts), ('blocked', 'error', 1))
        self.assertEqual(card.sync_error, 'Метод не підтримується сервером BioStar (405)')

    def test_no_biostar_user(self):
        fake = self._fake(True)
        card = self._card(employee_id=self.emp_c.id)
        with self.patch_client(fake):
            card.action_issue()
        self.assertEqual(card.sync_state, 'error')
        self.assertEqual(card.sync_error, 'У власника картки немає користувача BioStar.')
        self.assertEqual(fake.calls, [])

    def test_block_without_biostar_id(self):
        fake = self._fake(True)
        card = self._card(state='active', block_reason='Тест')
        with self.patch_client(fake):
            card.action_block()
        self.assertEqual(card.sync_state, 'error')
        self.assertIn('Картку не записано в BioStar', card.sync_error)

    def test_issue_creates_card_once(self):  # AC-42
        fake = self._fake(True)
        card = self._card('12345678')
        with self.patch_client(fake):
            card.action_issue()
        self.assertEqual(fake.calls, [
            ('create_card', '12345678', 0), ('update_user_cards', 'TSTA1', [{'id': '9', 'is_blocked': 'false'}])])
        self.assertEqual((card.biostar_card_id, card.sync_state), ('9', 'synced'))
        second = self._card('22222222', card_type='wiegand')
        fake.next_card_id = '10'
        boom = BioStarError(500, None, 'boom')
        with self.patch_client(fake), mock.patch.object(fake, 'update_user_cards', side_effect=boom):
            second.action_issue()
        self.assertEqual((second.biostar_card_id, second.sync_state), ('10', 'error'))
        self.assertIn(('create_card', '22222222', 1), fake.calls)
        with self.patch_client(fake):
            second.action_retry_sync()
        self.assertEqual(sum(1 for c in fake.calls if c[0] == 'create_card' and c[1] == '22222222'), 1)
        self.assertEqual(fake.calls[-1], ('update_user_cards', 'TSTA1', [
            {'id': '9', 'is_blocked': 'false'}, {'id': '10', 'is_blocked': 'false'}]))
        self.assertEqual(second.sync_state, 'synced')

    def test_return_removes_card(self):
        fake = self._fake(True)
        card = self._card(state='active', biostar_card_id='7')
        other = self._card('333', state='active', biostar_card_id='8')
        with self.patch_client(fake):
            card.action_return()
        self.assertEqual(fake.calls[-1], ('update_user_cards', 'TSTA1', [{'id': '8', 'is_blocked': 'false'}]))
        self.assertEqual((card.state, card.sync_state), ('returned', 'synced'))
        self.assertEqual(other.state, 'active')

    def test_cron_retry_limits(self):  # AC-43
        fake = self._fake(True)
        P.set_param(self.env, 'card_sync_max_attempts', '10')
        first = self._card('501', state='active', biostar_card_id='5', sync_state='error', pending_op='block',
                           sync_attempts=3)
        self._card('502', state='active', biostar_card_id='6', sync_state='error', pending_op='block',
                   sync_attempts=10, employee_id=self.emp_b.id)
        with self.patch_client(fake):
            self.env['f3d.access.card']._cron_card_sync()
        self.assertEqual([c for c in fake.calls if c[0] == 'update_user_cards'],
                         [('update_user_cards', 'TSTA1', [{'id': '5', 'is_blocked': 'false'}])])
        self.assertEqual(first.sync_state, 'synced')

    def test_cron_write_disabled(self):  # AC-43
        fake = self._fake(False)
        self._card('501', state='active', biostar_card_id='5', sync_state='error', pending_op='block',
                   sync_attempts=3)
        with self.patch_client(fake):
            self.env['f3d.access.card']._cron_card_sync()
        self.assertEqual(fake.calls, [])

    def test_retry_requires_write_enabled(self):
        self._write(False)
        card = self._card(sync_state='local', pending_op='issue')
        with self.assertRaisesRegex(UserError, 'стоп-краном'):
            card.action_retry_sync()

    def test_transitions_and_rights(self):
        self._write(False)
        card = self._card()
        with self.assertRaisesRegex(UserError, 'Повернути можна лише'):
            card.action_return()
        card.action_issue()
        with self.assertRaisesRegex(UserError, 'Видати можна лише'):
            card.action_issue()
        with self.assertRaisesRegex(UserError, 'причину'):
            card.action_block()
        card.action_mark_lost()
        self.assertEqual((card.state, card.block_reason), ('lost', 'Втрачена'))
        # охорона не чіпає картки працівників і не блокує
        card2 = self._card('7777')
        with self.assertRaises(AccessError):
            card2.with_user(self.user_security).action_issue()
        pool = self._card('8888', holder_type='pool', employee_id=False)
        with self.assertRaisesRegex(UserError, 'оберіть, кому'):
            pool.with_user(self.user_security).action_issue()
        with self.assertRaises(AccessError):
            pool.with_user(self.user_security).action_block()
