"""W4-C: відмітка пунктів, завершення, події (R-H3, R-H5): AC-H07, AC-H09, AC-H10, AC-H11, AC-H24."""

from unittest.mock import patch

from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from .common import T1, T2, TAGS, TestWHCommon, utc


@tagged(*TAGS)
class TestWHRound(TestWHCommon):
    def _mark_all(self, rnd, user=None, skip=()):
        eng = self.R(user=user or self.u_eng)
        for item in rnd.item_ids:
            if item.code not in skip:
                eng.action_toggle_item(item.id, True)

    def test_ac_h07_performer_lock(self):
        rnd = self._round(self.slot1)
        first, other = rnd.item_ids[0], rnd.item_ids[1]
        a, b, chief = self.u_eng, self.u_eng2, self.u_chief
        res = self.R(user=a).action_toggle_item(first.id, True)
        self.assertEqual((rnd.state, rnd.performer_id), ("in_progress", a))
        self.assertTrue(rnd.started_at)
        self.assertEqual(res["round"]["performer"], {"id": a.id, "name": a.name, "is_me": True})
        with self.assertRaises(UserError) as cm:
            self.R(user=b).action_toggle_item(other.id, True)
        self.assertEqual(str(cm.exception), "Обхід виконує %s." % a.name)
        self.assertFalse(other.done)
        self.R(user=chief).action_toggle_item(other.id, True)  # chief перехоплює без помилки
        self.assertTrue(other.done)
        self.assertEqual(other.done_by, chief)
        self.assertEqual(rnd.performer_id, a)  # виконавець лишається першим
        with self.assertRaises(AccessError):
            self.R(user=self.u_view).action_toggle_item(first.id, False)
        with self.assertRaises(AccessError):
            self.R(user=self.u_plain).action_toggle_item(first.id, False)
        rnd.write({"state": "done"})
        with self.assertRaisesRegex(UserError, "Обхід уже закрито."):
            self.R(user=a).action_toggle_item(first.id, False)

    def test_ac_h09_untoggle(self):
        self._signal(T1, 90.0)
        rnd = self._round(self.slot1)
        eng = self.R(user=self.u_eng)
        t1 = rnd.item_ids[0]
        eng.action_toggle_item(t1.id, True, comment="гарячий")
        self.assertEqual(
            (t1.result, t1.value, t1.value_text, rnd.deviation_count, rnd.done_count),
            ("deviation", 90.0, "90 °C", 1, 1),
        )
        res = eng.action_toggle_item(t1.id, False)
        self.assertEqual((t1.done, t1.result, t1.value, t1.value_text, t1.done_at), (False, "pending", 0.0, "", False))
        self.assertFalse(t1.event_id)  # події — лише при завершенні
        self.assertEqual((rnd.done_count, rnd.progress_pct, rnd.deviation_count), (0, 0, 0))
        self.assertEqual(res["round"]["done_count"], 0)
        self._mark_all(rnd)
        self.R(user=self.u_eng).action_finish(rnd.id)
        with self.assertRaisesRegex(UserError, "Обхід уже закрито."):
            eng.action_toggle_item(t1.id, False)

    def test_ac_h10_finish(self):
        rnd = self._round(self.slot1)
        eng = self.R(user=self.u_eng)
        self._mark_all(rnd, skip=("bess",))
        with self.assertRaisesRegex(UserError, r"Позначте всі пункти обходу: залишилось 1\."):
            eng.action_finish(rnd.id)
        self.assertEqual(rnd.state, "in_progress")
        eng.action_toggle_item(rnd.item_ids[-1].id, True)
        with patch("odoo.addons.td_energy.tools.bus.tick") as tick:
            res = eng.action_finish(rnd.id, note="усе гаразд")
        self.assertEqual(res, {"finished_at_local": "14:20", "deviation_count": 0})
        self.assertEqual((rnd.state, rnd.finished_at, rnd.note), ("done", self.now, "усе гаразд"))
        self.assertIn("state", [c.args[1] for c in tick.call_args_list])
        self.assertTrue(any("Обхід завершено: 6/6, відхилень 0" in (m.body or "") for m in rnd.message_ids))
        with self.assertRaisesRegex(UserError, "Обхід уже закрито."):
            eng.action_finish(rnd.id)

    def test_ac_h10_optional_item(self):
        tpl = self.Template.create(
            {
                "name": "Опц.",
                "code": "T-OPT",
                "slot_ids": [(0, 0, {"name": "Д", "time_from": 0.0, "time_to": 24.0, "weekdays": "0,1,2,3,4,5,6"})],
                "item_ids": [
                    (0, 0, {"code": "a", "title": "A", "sequence": 1}),
                    (0, 0, {"code": "b", "title": "B", "sequence": 2, "required": False}),
                ],
            }
        )
        rnd = self._round(template=tpl)
        eng = self.R(user=self.u_eng)
        eng.action_toggle_item(rnd.item_ids[0].id, True)
        self.assertEqual(eng.action_finish(rnd.id)["deviation_count"], 0)  # необов'язковий не блокує
        self.assertEqual((rnd.state, rnd.done_count, rnd.total_count), ("done", 1, 2))

    def test_ac_h10_finish_as_form_button(self):
        rnd = self._round(self.slot1)
        self._mark_all(rnd)
        self.assertTrue(rnd.with_user(self.u_chief).action_finish_form())
        self.assertEqual(rnd.state, "done")
        # `action_finish` приймає й список `ids` (кнопка форми)
        rnd2 = self._round(self.slot2)
        self._mark_all(rnd2)
        self.assertEqual(self.R(user=self.u_eng).action_finish([rnd2.id])["deviation_count"], 0)

    def test_ac_h11_deviation_events(self):
        self._signal(T1, 87.0)
        self._signal(T2, 90.0)
        rnd = self._round(self.slot1)
        self._mark_all(rnd)
        self.assertEqual(rnd.deviation_count, 2)
        res = self.R(user=self.u_eng).action_finish(rnd.id)
        self.assertEqual(res["deviation_count"], 2)
        events = self.Event.search([("kind", "=", "round")])
        self.assertEqual(sorted(events.mapped("code")), ["ROUND-%s-t1" % rnd.id, "ROUND-%s-t2" % rnd.id])
        self.assertEqual(set(events.mapped("level")), {"warn"})
        items = {i.code: i for i in rnd.item_ids}
        self.assertEqual(items["t1"].event_id.code, "ROUND-%s-t1" % rnd.id)
        self.assertEqual(items["t1"].event_id.node_id.code, "T1")
        self.assertIn("поза нормою (87 °C)", items["t1"].event_id.text)
        self.assertFalse(items["swb"].event_id)
        with self.assertRaises(UserError):  # повторне завершення неможливе
            self.R(user=self.u_eng).action_finish(rnd.id)
        # dedup_min захищає від дублів
        again = self.Event._td_log("warn", "round", "ROUND-%s-t1" % rnd.id, items["t1"].event_id.text, dedup_min=1440)
        self.assertFalse(again)

    def test_ac_h11_no_deviation_no_events(self):
        rnd = self._round(self.slot1)
        self._mark_all(rnd)
        self.R(user=self.u_eng).action_finish(rnd.id)
        self.assertEqual(self.Event.search_count([("kind", "=", "round")]), 0)

    def test_ac_h24_local_time(self):
        rnd = self._round(self.slot1)
        self._mark_all(rnd)
        res = self.R((2026, 10, 20, 14, 40), self.u_eng).action_finish(rnd.id)
        self.assertEqual(res["finished_at_local"], "14:40")
        self.assertEqual(rnd.finished_at, utc(2026, 10, 20, 14, 40))  # 11:40 UTC
        self.assertEqual(rnd.finished_at.hour, 11)
        journal = self.R(user=self.u_view).get_journal()
        self.assertEqual(journal["items"][0]["finished_at_local"], "14:40")
        mobile = self.R((2026, 10, 20, 14, 45), self.u_view).get_mobile()
        self.assertEqual(mobile["history"][0]["finished_at_local"], "14:40")
        self.assertEqual(mobile["meta"]["now_local"], "14:45")
