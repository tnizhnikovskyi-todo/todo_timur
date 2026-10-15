# Part of td_genset (ToDo). Власник файлу: W1. Заготовка: W0.
"""чистка, архів винятків (AC-58).

Базовий клас — ``odoo.addons.td_genset.tests.common.TdGensetCase`` (RelayMock, snapshot(), push_reading,
set_status, run_pull/run_commands/run_scheduler). Імена тестів — ``test_acNN_<що>``, AC у докстрингу.
"""
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from freezegun import freeze_time

from odoo.tests import tagged

from .common import TdGensetCase, snapshot

NOW = datetime(2026, 10, 7, 9, 0, 0)


@tagged('standard', 'at_install')
class TestW1Cleanup(TdGensetCase):

    def _create_history(self, days=120):
        """На кожен день: сирий interval (:00), change (:03) і журнальний interval (:10) в одному 15-хв слоті."""
        reading_model = self.env['td.genset.reading']
        values = snapshot()
        payloads, relay_id = [], 1
        for day in range(days):
            base = NOW - timedelta(days=days - day)
            for minutes, reason in ((0, 'interval'), (3, 'change'), (10, 'interval')):
                stamp = base + timedelta(minutes=minutes)
                payloads.append({'id': relay_id, 'ts': stamp.replace(tzinfo=timezone.utc).timestamp(),
                                 'reason': reason, 'values': values})
                relay_id += 1
        readings = reading_model._create_from_payload(self.genset, payloads)
        reading_model._mark_journal(self.genset, set(readings.mapped('slot_15')))
        return readings

    def test_ac58_cleanup_raw_readings(self):
        """AC-58: термін 90 днів, знімки за 120 днів → видалено сирі старші за 90 днів (не журнальні й не change);
        журнальні, change, події, тривоги, команди — на місці; знімок, на який посилається подія, лишається."""
        readings = self._create_history()
        self.assertEqual(len(readings), 360)
        self.assertEqual(len(readings.filtered('is_journal')), 120)
        old_raw = readings.filtered(lambda reading: not reading.is_journal and reading.reason == 'interval'
                                    and reading.ts < NOW - timedelta(days=90))
        self.assertEqual(len(old_raw), 30)
        referenced = old_raw[0]
        event = self.env['td.genset.event'].create({
            'genset_id': self.genset.id, 'event_type': 'gap', 'date_start': referenced.ts,
            'date_end': referenced.ts + timedelta(minutes=5), 'reading_start_id': referenced.id})
        alarm = self.env['td.genset.alarm'].create({'genset_id': self.genset.id, 'code': 'old', 'level': 'warn',
                                                    'name': 'Стара тривога', 'date_raised': NOW - timedelta(days=100)})
        command = self.env['td.genset.command'].create({'genset_id': self.genset.id, 'command': 'auto',
                                                        'source': 'button', 'state': 'done'})
        progress = []

        def notify(cron, **kwargs):
            progress.append((kwargs['done'], kwargs['remaining']))

        with freeze_time(NOW), patch.object(type(self.env['ir.cron']), '_notify_progress', notify):
            self.assertIsNone(self.env['td.genset.reading']._cron_cleanup())
        self.assertEqual(progress, [(29, 0)])
        remaining = self.env['td.genset.reading'].search([('genset_id', '=', self.genset.id)])
        self.assertEqual(len(remaining), 331)
        self.assertFalse((old_raw - referenced) & remaining)
        self.assertIn(referenced, remaining)
        self.assertEqual(len(remaining.filtered('is_journal')), 120)
        self.assertEqual(len(remaining.filtered(lambda reading: reading.reason == 'change')), 120)
        self.assertTrue(event.exists() and alarm.exists() and command.exists())
        self.assertEqual(event.reading_start_id, referenced)

    def test_ac58_cleanup_batches_and_disabled(self):
        """AC-58: партіями (``_notify_progress`` з залишком); термін 0 — не чистити."""
        self._create_history(days=100)
        reading_model = self.env['td.genset.reading']
        self.config.reading_retention_days = 0
        with freeze_time(NOW):
            reading_model._cron_cleanup()
        self.assertEqual(reading_model.search_count([('genset_id', '=', self.genset.id)]), 300)
        self.config.reading_retention_days = 90
        progress = []

        def notify(cron, **kwargs):
            progress.append((kwargs['done'], kwargs['remaining']))

        with freeze_time(NOW), patch.object(type(self.env['ir.cron']), '_notify_progress', notify), \
                patch('odoo.addons.td_genset.models.genset_reading.CLEANUP_BATCH', 4):
            reading_model._cron_cleanup()
            reading_model._cron_cleanup()
            reading_model._cron_cleanup()
        self.assertEqual(progress, [(4, 1), (4, 1), (2, 0)])
        self.assertEqual(reading_model.search_count([('genset_id', '=', self.genset.id)]), 290)

    def test_ac58_archive_old_exceptions(self):
        """ФВ-19, ТР 2.12: дні-винятки старші за 30 днів архівуються щоденною чисткою."""
        exception_model = self.env['td.genset.schedule.exception']
        old = exception_model.create({'genset_id': self.genset.id, 'date': date(2026, 8, 20), 'action': 'skip'})
        recent = exception_model.create({'genset_id': self.genset.id, 'date': date(2026, 9, 30), 'action': 'skip'})
        with freeze_time(NOW):
            self.env['td.genset.reading']._cron_cleanup()
        self.assertFalse(old.active)
        self.assertTrue(recent.active)
