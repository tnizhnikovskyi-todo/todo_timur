"""W4-C: розклад і крони (R-H1, R-H2): AC-H03, AC-H04, AC-H05, AC-H26 + чисті функції `tools/schedule.py`."""

from datetime import date, datetime

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from ..tools import schedule
from .common import TAGS, TestWHCommon, utc


@tagged(*TAGS)
class TestWHScheduleTools(TransactionCase):
    def test_weekdays(self):
        self.assertEqual(schedule.parse_weekdays("0,1,2,3,4"), [0, 1, 2, 3, 4])
        for bad in ("", "0,0", "7", "a", "0,,1", None, "0,10"):
            self.assertIsNone(schedule.parse_weekdays(bad), bad)

    def test_fmt_and_bounds(self):
        self.assertEqual(schedule.fmt_hhmm(7.0), "07:00")
        self.assertEqual(schedule.fmt_hhmm(16.5), "16:30")
        # звичайна доба: Київ = UTC+3 у жовтні до 25.10
        self.assertEqual(
            schedule.slot_bounds(date(2026, 10, 20), 16.0, 23.0), (datetime(2026, 10, 20, 13, 0), datetime(2026, 10, 20, 20, 0))
        )
        self.assertEqual(schedule.local_hhmm(datetime(2026, 10, 20, 11, 40)), "14:40")

    def test_next_slot(self):
        slots = [("Зміна 1", 7.0, "0,1,2,3,4"), ("Зміна 2", 16.0, "0,1,2,3,4")]
        self.assertEqual(schedule.next_slot_today(utc(2026, 10, 20, 14, 20), slots), ("Зміна 2", "16:00"))
        self.assertIsNone(schedule.next_slot_today(utc(2026, 10, 20, 17, 0), slots))
        self.assertEqual(schedule.next_slot_today(utc(2026, 10, 20, 5, 0), slots), ("Зміна 1", "07:00"))
        self.assertIsNone(schedule.next_slot_today(utc(2026, 10, 17, 5, 0), slots))  # субота


@tagged(*TAGS)
class TestWHSchedule(TestWHCommon):
    def test_ac_h03_cron_open(self):
        before = self.Round.search_count([])
        rec = self.R((2026, 10, 20, 16, 20))  # вівторок
        self.assertEqual(rec._cron_open(), 1)
        rnd = self.Round.search([], limit=1)
        self.assertEqual(self.Round.search_count([]), before + 1)
        self.assertEqual(rnd.name, "Обхід ТП і ГРЩ · Зміна 2 · 20.10")
        self.assertEqual(rnd.state, "open")
        self.assertEqual(rnd.slot_id, self.slot2)
        self.assertEqual(rnd.due_at, datetime(2026, 10, 20, 20, 0))  # 23:00 Київ
        self.assertEqual(rnd.starts_at, datetime(2026, 10, 20, 13, 0))
        self.assertEqual(rnd.item_ids.mapped("code"), ["t1", "t2", "swb", "pfc", "dgu", "bess"])
        # повторний прогін — без дубля
        self.assertEqual(rec._cron_open(), 0)
        self.assertEqual(self.Round.search_count([]), before + 1)
        # правка шаблона не змінює створений обхід (знімок)
        self.tpl.item_ids[0].title = "Змінено"
        self.tpl.item_ids[0].norm_max = 70.0
        self.assertEqual(rnd.item_ids[0].title, "T1: огляд, температура масла")
        self.assertEqual(rnd.item_ids[0].norm_max, 85.0)

    def test_ac_h03_windows(self):
        self.assertEqual(self.R((2026, 10, 17, 14, 20))._cron_open(), 0)  # субота
        self.assertEqual(self.R((2026, 10, 20, 6, 59))._cron_open(), 0)  # до зміни 1
        self.assertEqual(self.R((2026, 10, 20, 23, 0))._cron_open(), 0)  # слот 2 уже закінчився
        self.assertEqual(self.R((2026, 10, 20, 7, 0))._cron_open(), 1)  # межа початку слота
        self.assertEqual(self.Round.search([], limit=1).slot_id, self.slot1)
        # крон не працює, якщо `read_enabled` вимкнено
        self.env["ir.config_parameter"].sudo().set_param("td.energy.read_enabled", "False")
        self.assertEqual(self.R((2026, 10, 21, 8, 0))._cron_open(), 0)

    def test_ac_h04_cron_close(self):
        rnd = self._round(self.slot1, state="in_progress", done=3, performer=self.u_eng)
        self.assertEqual(rnd.done_count, 3)
        # ще в межах слота — не чіпає
        self.assertEqual(self.R((2026, 10, 20, 15, 59))._cron_close(), 0)
        late = self.R((2026, 10, 20, 16, 30))
        self.assertEqual(late._cron_close(), 1)
        self.assertEqual((rnd.state, rnd.finished_at, rnd.done_count), ("missed", rnd.due_at, 3))
        code = "ROUND-%s" % rnd.id
        events = self.Event.search([("kind", "=", "round"), ("code", "=", code)])
        self.assertEqual((len(events), events.level), (1, "warn"))
        self.assertIn("Виконано 3/6", events.detail)
        self.assertEqual(late._cron_close(), 0)  # повтор без дублів
        self.assertEqual(self._event_count(code), 1)
        # done / cancelled не переглядаються
        done = self._round(self.slot2, state="done")
        self.assertEqual(self.R((2026, 10, 20, 23, 30))._cron_close(), 0)
        self.assertEqual(done.state, "done")

    def test_ac_h04_without_event(self):
        self.env["ir.config_parameter"].sudo().set_param("td.energy_mobile.missed_event", "0")
        rnd = self._round(self.slot1, state="open")
        self.assertEqual(self.R((2026, 10, 20, 17, 0))._cron_close(), 1)
        self.assertEqual(rnd.state, "missed")
        self.assertEqual(self._event_count("ROUND-%s" % rnd.id), 0)

    def test_ac_h05_dst(self):
        tpl = self.Template.create(
            {
                "name": "Нічний",
                "code": "T-DST",
                "slot_ids": [(0, 0, {"name": "Ніч", "time_from": 1.0, "time_to": 6.0, "weekdays": "6"})],
            }
        )
        # неділя 29.03.2026: перехід на літній час о 03:00 → слот 01:00–06:00 триває 4 години
        spring = self.R((2026, 3, 29, 2, 0))
        self.assertEqual(spring._cron_open(), 1)
        rnd = self.Round.search([("template_id", "=", tpl.id)])
        self.assertEqual((rnd.starts_at, rnd.due_at), (datetime(2026, 3, 28, 23, 0), datetime(2026, 3, 29, 3, 0)))
        self.assertTrue(rnd.name.endswith("· 29.03"), rnd.name)
        # неділя 25.10.2026: перехід на зимовий час о 04:00 → слот триває 6 годин; назва — київська дата
        self.assertEqual(self.R((2026, 10, 25, 2, 0))._cron_open(), 1)
        rnd = self.Round.search([("template_id", "=", tpl.id)], limit=1)
        self.assertEqual((rnd.starts_at, rnd.due_at), (datetime(2026, 10, 24, 22, 0), datetime(2026, 10, 25, 4, 0)))
        self.assertTrue(rnd.name.endswith("· 25.10"), rnd.name)

    def test_ac_h26_manual_start(self):
        now = utc(2026, 10, 20, 14, 20)
        rec = self.R((2026, 10, 20, 14, 20), self.u_eng)
        rid = rec.action_start(self.tpl.id)
        rnd = self.Round.browse(rid)
        self.assertEqual((rnd.state, rnd.slot_name, rnd.slot_id.id), ("open", "поза розкладом", False))
        self.assertEqual((rnd.starts_at, rnd.due_at), (now, datetime(2026, 10, 20, 13, 20)))
        self.assertEqual(len(rnd.item_ids), 6)
        with self.assertRaisesRegex(UserError, "Обхід уже відкритий"):
            rec.action_start(self.tpl.id)
        with self.assertRaises(AccessError):
            self.R((2026, 10, 20, 14, 20), self.u_view).action_start(self.tpl.id)
        # після закриття можна запустити знову (слот не заданий — UNIQUE не заважає)
        rnd.write({"state": "cancelled"})
        self.assertTrue(rec.action_start(self.tpl.id))
        # V-H4: server action «Запустити обхід зараз»
        rnd2 = self.Round.search([("state", "=", "open")], limit=1)
        rnd2.write({"state": "done"})
        action = rec.action_start_now()
        self.assertEqual((action["res_model"], action["type"]), ("td.energy.round", "ir.actions.act_window"))
