"""W4-C: API-H1…H5 і журнал: AC-H12, AC-H13, AC-H14, AC-H16, AC-H22, AC-H23 (ТП-H1, ТП-H2)."""

import json
import time
from datetime import timedelta

from odoo.exceptions import AccessError
from odoo.tests import tagged

from odoo.addons.td_energy.tools import dates

from ..tools import schedule
from .common import T1, TAGS, TestWHCommon, utc


@tagged(*TAGS)
class TestWHApi(TestWHCommon):
    def test_ac_h12_mobile_payload(self):
        rnd = self._round(self.slot1)
        eng = self.R(user=self.u_eng)
        for item in rnd.item_ids[:2]:
            eng.action_toggle_item(item.id, True)
        for i in range(5):  # п'ять закритих — у history ≤ 3
            day = self.now - timedelta(days=i + 1)
            self._round(self.slot1, state="done" if i % 2 else "missed", now=day)
        data = eng.get_mobile()
        round_ = data["round"]
        self.assertEqual(
            (round_["done_count"], round_["total_count"], round_["progress_pct"]), (2, 6, 33)
        )
        self.assertEqual((round_["can_finish"], round_["finish_blocked"]), (False, "залишилось 4"))
        self.assertEqual([i["code"] for i in round_["items"]], ["t1", "t2", "swb", "pfc", "dgu", "bess"])
        self.assertTrue(round_["performer"]["is_me"])
        self.assertEqual((round_["title"], round_["slot"], round_["due_local"]), ("Обхід ТП і ГРЩ · зміна 1", "Зміна 1", "16:00"))
        self.assertEqual(round_["state"], "in_progress")
        self.assertEqual(len(data["history"]), 3)
        self.assertEqual(data["history"][0]["state"], "missed")  # новіші першими
        self.assertIn("19.10", data["history"][0]["title"])  # дата — лише для не сьогоднішніх
        self.assertLess(len(json.dumps(data)), 10240)
        for bad in ("cost", "price", "tariff"):
            self.assertNotIn(bad, json.dumps(data))
        self.assertEqual(data["meta"], {"now_local": "14:20", "refresh_s": 30, "can_edit": True})
        self.assertIsNone(data["next"])
        t1 = round_["items"][0]
        self.assertEqual((t1["node_code"], t1["can_3d"], t1["done"], t1["result"]), ("T1", True, True, "ok"))
        # 6/6: finish_blocked = None, can_finish = True
        for item in rnd.item_ids[2:]:
            eng.action_toggle_item(item.id, True)
        round_ = eng.get_mobile()["round"]
        self.assertEqual((round_["can_finish"], round_["finish_blocked"], round_["progress_pct"]), (True, None, 100))
        # round_id: конкретний обхід, зокрема закритий
        closed = self.Round.search([("state", "=", "done")], limit=1)
        self.assertEqual(eng.get_mobile(round_id=closed.id)["round"]["id"], closed.id)
        self.assertFalse(eng.get_mobile(round_id=closed.id)["round"]["can_edit"])

    def test_ac_h13_no_open_round(self):
        eng = self.R((2026, 10, 20, 14, 20), self.u_eng)
        data = eng.get_mobile()
        self.assertIsNone(data["round"])
        self.assertEqual(data["next"], {"slot": "Зміна 2", "starts_local": "16:00"})
        self.assertEqual(data["history"], [])
        self.assertEqual(self.R((2026, 10, 20, 6, 0), self.u_eng).get_mobile()["next"], {"slot": "Зміна 1", "starts_local": "07:00"})
        self.assertIsNone(self.R((2026, 10, 20, 23, 30), self.u_eng).get_mobile()["next"])  # слотів більше немає
        self.assertIsNone(self.R((2026, 10, 17, 10, 0), self.u_eng).get_mobile()["next"])  # субота
        # історія: останні закриті
        done = self._round(self.slot1, state="done")
        data = eng.get_mobile()
        self.assertEqual([h["id"] for h in data["history"]], [done.id])
        self.assertEqual(data["history"][0]["finished_at_local"], "14:20")

    def test_ac_h13_two_open_rounds(self):
        r1, r2 = self._round(self.slot1), self._round(self.slot2)
        self.assertEqual(self.R((2026, 10, 20, 14, 20), self.u_eng).get_mobile()["round"]["id"], r1.id)
        self.assertEqual(self.R((2026, 10, 20, 16, 30), self.u_eng).get_mobile()["round"]["id"], r2.id)
        # жоден слот не містить now — найранніший
        self.assertEqual(self.R((2026, 10, 20, 23, 30), self.u_eng).get_mobile()["round"]["id"], r1.id)

    def test_ac_h14_roles(self):
        rnd = self._round(self.slot1, state="in_progress", performer=self.u_eng)
        with self.assertRaises(AccessError):
            self.R(user=self.u_plain).get_mobile()
        viewer = self.R(user=self.u_view).get_mobile()
        self.assertEqual((viewer["meta"]["can_edit"], viewer["round"]["can_edit"]), (False, False))
        own = self.R(user=self.u_eng).get_mobile()["round"]
        self.assertEqual((own["can_edit"], own["performer"]["is_me"]), (True, True))
        other = self.R(user=self.u_eng2).get_mobile()
        self.assertEqual(other["meta"]["can_edit"], True)
        self.assertEqual(other["round"]["can_edit"], False)  # банер «Обхід виконує …»
        self.assertEqual(other["round"]["performer"], {"id": self.u_eng.id, "name": self.u_eng.name, "is_me": False})
        self.assertTrue(self.R(user=self.u_chief).get_mobile()["round"]["can_edit"])
        rnd.write({"performer_id": False, "state": "open"})
        self.assertTrue(self.R(user=self.u_eng2).get_mobile()["round"]["can_edit"])  # виконавця немає

    def test_ac_h16_journal(self):
        today = self._round(self.slot1, state="in_progress", performer=self.u_eng, done=2)
        missed = self._round(self.slot1, state="missed", now=self.now - timedelta(days=1))
        dev = self._round(self.slot1, state="done", now=self.now - timedelta(days=2))
        dev.item_ids[0].write({"done": True, "result": "deviation"})
        for xml in ("list", "form", "search", "pivot"):
            views = self.R(user=self.u_view).get_views([(False, xml)])
            self.assertTrue(views["views"][xml]["arch"], xml)
        for xmlid in ("view_td_energy_round_list", "view_td_energy_round_form"):  # запис — лише методами
            arch = self.env.ref("td_energy_mobile." + xmlid).arch
            for attr in ('create="0"', 'edit="0"', 'delete="0"'):
                self.assertIn(attr, arch, xmlid)
        R = self.R(user=self.u_eng)
        self.assertEqual(R.search([("date", "=", dates.local_day(self.now))]), today)
        self.assertEqual(R.search([("performer_id", "=", self.u_eng.id)]), today)
        self.assertEqual(R.search([("state", "=", "missed")]), missed)
        self.assertEqual(R.search([("deviation_count", ">", 0)]), dev)
        journal = R.get_journal(limit=2, offset=0)
        self.assertEqual((len(journal["items"]), journal["total"]), (2, 3))
        self.assertEqual(R.get_journal(limit=20, offset=2)["items"][0]["id"], dev.id)
        row = journal["items"][0]
        self.assertEqual(set(row), {"id", "name", "date", "state", "performer", "finished_at_local", "done_count", "total_count", "deviation_count"})
        with self.assertRaises(AccessError):
            self.R(user=self.u_plain).get_journal()
        # видалення — лише admin
        for user in (self.u_view, self.u_eng, self.u_chief):
            with self.assertRaises(AccessError):
                today.with_user(user).unlink()
        today.with_user(self.u_admin).unlink()
        self.assertFalse(today.exists())

    def test_ac_h22_settings(self):
        self._round(self.slot1, state="done", now=self.now - timedelta(days=1))
        self._round(self.slot2, state="done", now=self.now - timedelta(days=1))
        eng = self.R(user=self.u_eng)
        self.assertEqual(len(eng.get_mobile()["history"]), 2)
        # стандартний екран налаштувань відкривається лише `base.group_system`: значення записує `set_values`
        settings = self.env["res.config.settings"].create(
            {"td_energy_mobile_history_limit": 1, "td_energy_mobile_value_fresh_s": 600, "td_energy_mobile_keep_days": 100,
             "td_energy_mobile_missed_event": False}
        )  # fmt: skip
        settings.set_values()
        icp = self.env["ir.config_parameter"].sudo()
        self.assertEqual(icp.get_param("td.energy_mobile.history_limit"), "1")
        self.assertEqual(icp.get_param("td.energy_mobile.value_fresh_s"), "600")
        self.assertEqual(icp.get_param("td.energy_mobile.keep_days"), "100")
        self.assertEqual(len(eng.get_mobile()["history"]), 1)
        # `value_fresh_s` — вікно свіжості: сигнал 5 хв тому свіжий за 600 с, несвіжий за 120 с
        self._round(self.slot1)
        self._signal(T1, 58.0, ts=self.now - timedelta(minutes=5))
        hint = lambda: eng.get_mobile()["round"]["items"][0]["hint"]  # noqa: E731
        self.assertEqual(hint(), "норма до 85 °C · зараз 58 °C")
        icp.set_param("td.energy_mobile.value_fresh_s", "120")
        self.assertEqual(hint(), "норма до 85 °C · зараз —")
        # прапорець «подія для не виконаного» знятий → події немає
        rnd = self._round(self.slot2, state="open", now=self.now - timedelta(days=3))
        self.R((2026, 10, 20, 17, 0))._cron_close()
        self.assertEqual(self._event_count("ROUND-%s" % rnd.id), 0)

    # --- ТП-H1, ТП-H2 (AC-H23) --------------------------------------------------------------------------
    def _bulk_rounds(self, days=730):
        """≈ 520 обходів/рік × 6 пунктів: 2 слоти × 5 буднів на добу, закриті."""
        vals = []
        slots = (self.slot1, self.slot2)
        for back in range(1, days + 1):
            day_utc = self.now - timedelta(days=back)
            day = dates.local_day(day_utc)
            if day.weekday() > 4:
                continue
            for slot in slots:
                starts_at, due_at = schedule.slot_bounds(day, slot.time_from, slot.time_to)
                items = [
                    (0, 0, {"code": i.code, "title": i.title, "sequence": i.sequence, "done": True, "result": "ok"})
                    for i in self.tpl.item_ids
                ]
                vals.append(
                    {
                        "template_id": self.tpl.id, "slot_id": slot.id, "slot_name": slot.name, "date": day,
                        "starts_at": starts_at, "due_at": due_at, "state": "done", "finished_at": due_at,
                        "item_ids": items,
                    }
                )  # fmt: skip
        self.Round.with_context(mail_create_nolog=True).create(vals)
        return len(vals)

    def test_ac_h23_performance(self):
        total = self._bulk_rounds()
        self.assertGreater(total, 1000)
        rnd = self._round(self.slot1)
        eng = self.R(user=self.u_eng)
        eng.get_mobile()  # прогрів кешів ORM
        started = time.perf_counter()
        with self.assertQueryCount(15):
            data = eng.get_mobile()
        elapsed = time.perf_counter() - started
        self.assertEqual(len(data["round"]["items"]), 6)
        self.assertLess(elapsed, 0.25, "get_mobile %.0f мс" % (elapsed * 1000))
        item = rnd.item_ids[0]
        started = time.perf_counter()
        eng.action_toggle_item(item.id, True)
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 0.15, "action_toggle_item %.0f мс" % (elapsed * 1000))
        for other in rnd.item_ids[1:]:
            eng.action_toggle_item(other.id, True)
        started = time.perf_counter()
        eng.action_finish(rnd.id)
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 0.3, "action_finish %.0f мс" % (elapsed * 1000))
        # ротація: старші за keep_days (730) видаляються пакетами за ≤ 10 с
        self.env["ir.config_parameter"].sudo().set_param("td.energy_mobile.keep_days", "365")
        before = self.Round.search_count([])
        started = time.perf_counter()
        deleted = self.R()._cron_rotate()
        self.assertLess(time.perf_counter() - started, 10)
        self.assertGreater(deleted, 100)
        self.assertEqual(self.Round.search_count([]), before - deleted)
        self.assertEqual(self.Round.search_count([("due_at", "<", self.now - timedelta(days=365))]), 0)
