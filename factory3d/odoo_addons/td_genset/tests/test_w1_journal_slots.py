# Part of td_genset (ToDo). Власник файлу: W1. Заготовка: W0.
"""slot_15/is_journal/is_hour/DST (AC-08).

Базовий клас — ``odoo.addons.td_genset.tests.common.TdGensetCase`` (RelayMock, snapshot(), push_reading,
set_status, run_pull/run_commands/run_scheduler). Імена тестів — ``test_acNN_<що>``, AC у докстрингу.
"""
from datetime import date, datetime, timedelta, timezone

from freezegun import freeze_time

from odoo.tests import tagged

from ..models.genset_reading import slot_start, utc_to_kyiv
from ..models.genset_schedule import kyiv_localize
from .common import TdGensetCase, snapshot


@tagged('standard', 'at_install')
class TestW1JournalSlots(TdGensetCase):

    def _payloads(self, start, end, step, first_id=1, reason='interval'):
        values = snapshot()
        payloads, stamp, relay_id = [], start, first_id
        while stamp < end:
            ts = stamp.replace(tzinfo=timezone.utc).timestamp()
            payloads.append({'id': relay_id, 'ts': ts, 'time_utc': stamp.strftime('%Y-%m-%dT%H:%M:%SZ'),
                             'reason': reason, 'values': values})
            stamp += step
            relay_id += 1
        return payloads

    def _store(self, payloads):
        reading_model = self.env['td.genset.reading']
        for index in range(0, len(payloads), 500):
            readings = reading_model._create_from_payload(self.genset, payloads[index:index + 500])
            reading_model._mark_journal(self.genset, set(readings.mapped('slot_15')))

    def _journal(self, start, end):
        return self.env['td.genset.reading'].search([
            ('genset_id', '=', self.genset.id), ('is_journal', '=', True), ('ts', '>=', start), ('ts', '<', end)])

    def test_ac08_journal_96_records_per_day(self):
        """AC-08: 1 440 знімків за добу + 12 за зміною стану → 96 журнальних (останній знімок кожного інтервалу
        00:00–00:15 … 23:45–24:00 за Europe/Kyiv); «Погодинно» лишає 24."""
        day = date(2026, 10, 7)
        start, end = kyiv_localize(day, 0.0), kyiv_localize(day + timedelta(days=1), 0.0)
        self.assertEqual(start, datetime(2026, 10, 6, 21, 0))
        payloads = self._payloads(start, end, timedelta(minutes=1))
        changes = self._payloads(start + timedelta(minutes=7, seconds=30), end, timedelta(hours=2), first_id=5000,
                                 reason='change')
        self.assertEqual((len(payloads), len(changes)), (1440, 12))
        self._store(sorted(payloads + changes, key=lambda item: item['ts']))
        journal = self._journal(start, end)
        self.assertEqual(len(journal), 96)
        self.assertEqual(len(set(journal.mapped('slot_15'))), 96)
        for reading in journal:
            self.assertEqual(utc_to_kyiv(reading.ts).minute % 15, 14)
        self.assertEqual(len(journal.filtered('is_hour')), 24)
        # вставлений пізніше знімок у вже закритий слот стає журнальним, попередній — ні
        late = self._payloads(start + timedelta(minutes=14, seconds=50), start + timedelta(minutes=15), timedelta(
            minutes=1), first_id=9000)
        self._store(late)
        slot = self.env['td.genset.reading'].search([('genset_id', '=', self.genset.id), ('slot_15', '=', start)])
        self.assertEqual(slot.filtered('is_journal').relay_id, 9000)

    def test_ac08_journal_dst_days(self):
        """AC-08: у дні переходу на літній/зимовий час — 92 / 100 журнальних записів (доба 23 / 25 год)."""
        for day, expected, hours in ((date(2026, 3, 29), 92, 23), (date(2026, 10, 25), 100, 25)):
            start, end = kyiv_localize(day, 0.0), kyiv_localize(day + timedelta(days=1), 0.0)
            first_id = 100000 if hours == 23 else 200000
            self._store(self._payloads(start, end, timedelta(minutes=5), first_id=first_id))
            journal = self._journal(start, end)
            self.assertEqual(len(journal), expected, day)
            self.assertEqual(len(journal.filtered('is_hour')), hours, day)

    def test_ac08_slot_start_kyiv(self):
        """AC-08: початок 15-хв інтервалу — за київським часом, збережений в UTC (і в повторну годину 25.10)."""
        self.assertEqual(slot_start(datetime(2026, 10, 7, 9, 44, 59)), datetime(2026, 10, 7, 9, 30))
        self.assertEqual(slot_start(datetime(2026, 10, 25, 0, 50)), datetime(2026, 10, 25, 0, 45))
        self.assertEqual(slot_start(datetime(2026, 10, 25, 1, 5)), datetime(2026, 10, 25, 1, 0))
        self.assertEqual(slot_start(datetime(2026, 10, 7, 9, 44), 60), datetime(2026, 10, 7, 9, 0))

    def test_ac08_pull_marks_journal(self):
        """AC-08, AC-46: забір cron позначає журнальні; за пропуск без знімків записів журналу немає."""
        now = datetime(2026, 10, 7, 12, 0)
        with freeze_time(now):
            for minute in list(range(0, 30)) + list(range(70, 90)):
                self.push_reading(snapshot(), ts=now - timedelta(minutes=90 - minute))
            self.run_pull()
        journal = self.env['td.genset.reading'].search([('genset_id', '=', self.genset.id), ('is_journal', '=', True)])
        gap_start, gap_end = now - timedelta(minutes=60), now - timedelta(minutes=20)
        self.assertFalse(journal.filtered(lambda reading: gap_start <= reading.ts < gap_end))
        self.assertEqual(len(journal), len(set(journal.mapped('slot_15'))))
