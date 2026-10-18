"""AC-205…AC-207, AC-210: журнал (дії, події, автоматика), чат."""

from odoo.tests import tagged

from .common import NOW, TAGS, TestControlCommon


@tagged(*TAGS)
class TestJournal(TestControlCommon):
    def test_journal_rows(self):  # AC-205
        a = self.run_action("bess_charge", user=self.u_en1)
        self.finish(a, "done", "BESS: заряд")
        prep = self.ctl(self.u_en1).prepare("light_break")  # prepared — не показується
        b = self.run_action("qs_close", user=self.u_en1)  # awaiting_second
        res = self.ctl(self.u_view).get_journal()
        ids = [r["id"] for r in res["items"]]
        self.assertIn(a.id, ids)
        self.assertIn(b.id, ids)
        self.assertNotIn(prep["action_id"], ids)
        row = next(r for r in res["items"] if r["id"] == a.id)
        self.assertEqual((row["result"], row["result_kind"], row["state"]), ("виконано", "ok", "done"))
        self.assertEqual(row["who"], self.u_en1.name)
        self.assertEqual(row["what"], "Заряд BESS 50 кВт")
        awaiting = next(r for r in res["items"] if r["id"] == b.id)
        self.assertTrue(awaiting["awaiting_second"])
        for i in range(3):
            self.run_action("bess_charge", {"power_kw": 10 + i}, user=self.u_en1)._me()._td_close("done", "ok")
        page = self.ctl(self.u_view).get_journal(limit=2)
        self.assertEqual((len(page["items"]), page["more"]), (2, True))
        nxt = self.ctl(self.u_view).get_journal(limit=2, before_id=page["items"][-1]["id"])
        self.assertFalse({r["id"] for r in nxt["items"]} & {r["id"] for r in page["items"]})
        self.assertLessEqual(len(self.ctl(self.u_view).get_journal(limit=1000)["items"]), 50)

    def test_event_rows(self):  # AC-206
        node = self.env["td.energy.node"].search([("code", "=", "PFC-2")], limit=1)
        sig = self.env["td.signal"].sudo().search([("code", "=", "energy/cells/PFC-2/fault_step")], limit=1)
        ev = self.env["td.energy.event"]._td_log(
            "warn",
            "pfc",
            "PFC-2",
            "PFC-2: ступінь 3 не вмикається",
            ts=NOW,
            node=node,
            signal=sig,
            title="PFC-2: ступінь 3 не вмикається",
        )
        rows = self.ctl(self.u_view).get_journal()["items"]
        row = next(r for r in rows if r["id"] == -ev.id)
        self.assertEqual((row["who"], row["time"]), ("автоматика", "14:20"))
        self.assertIn(row["result"], ("активно", "створено"))
        self.assertIn("ступінь 3", row["detail"])

    def test_auto_events(self):  # AC-207
        ev = {"event_id": "b9" * 16, "ts": "2026-10-17T11:20:00Z", "scenario": "peak", "kind": "auto_step",
              "text": "BESS · розряд 62 кВт", "signal": "energy_control/bess/mode", "value": 2, "result": "виконано"}  # fmt: skip
        self.assertTrue(self.Action._td_log_auto(ev))
        rec = self.Action.search([("idem", "=", ev["event_id"])])
        self.assertEqual(
            (rec.origin, rec.actor_text, rec.summary, rec.result_text),
            ("auto", "сценарій «Пік»", "BESS · розряд", "виконано"),
        )
        self.assertEqual(self.Action._td_log_auto(ev), "duplicate")
        row = next(r for r in self.ctl(self.u_view).get_journal()["items"] if r["id"] == rec.id)
        self.assertEqual((row["who"], row["result"]), ("сценарій «Пік»", "виконано"))

    def test_chatter(self):  # AC-210
        act = self.run_action("bess_charge", user=self.u_en1)
        self.finish(act, "done", "виконано")
        bodies = " ".join(act.message_ids.mapped("body"))
        for word in ("Підготовлено", "Підтверджено", "Результат"):
            self.assertIn(word, bodies)

    def test_auto_event_without_scenario(self):  # події рушія без сценарію не підписуються «Зрізання піку»
        ev = {"event_id": "cd" * 16, "kind": "mode", "text": "Рушій: auto → hold (контролер у місцевому режимі)"}
        self.assertTrue(self.Action._td_log_auto(ev))
        rec = self.Action.search([("idem", "=", ev["event_id"])])
        self.assertEqual((rec.actor_text, rec.kind_code, rec.summary), ("автоматика", "auto_mode", "Режим рушія"))
        self.assertFalse(rec.scenario_id)
        self.assertNotIn("Пік", rec.actor_text + rec.summary)
        row = next(r for r in self.ctl(self.u_view).get_journal()["items"] if r["id"] == rec.id)
        self.assertEqual((row["who"], row["what"]), ("автоматика", "Режим рушія"))
        event = self.env["td.energy.event"].search([("kind", "=", "control"), ("text", "=", ev["text"])])
        self.assertEqual(event.code, "mode")
        scoped = dict(ev, event_id="ef" * 16, scenario="pfc", text="PFC: збій", kind="interlock")
        self.assertTrue(self.Action._td_log_auto(scoped))
        self.assertEqual(self.Action.search([("idem", "=", scoped["event_id"])]).actor_text, "сценарій «PFC»")
