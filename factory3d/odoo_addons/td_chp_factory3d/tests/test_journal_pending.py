"""AC-B04, B06, B08: інваріант «одна команда — один запис» (RB-06), журнал і картка «Очікує 2/2» (RB-03, RB-04)."""

from datetime import timedelta

from odoo.tests import tagged

from .common import RUNNING, TAGS, BridgeCase


@tagged(*TAGS)
class TestJournalPending(BridgeCase):
    def setUp(self):
        super().setUp()
        self.idle()

    def journal(self, user=None, **kw):
        return self.pult(user or self.u_en1).get_journal(**kw)

    def command_rows(self, user=None):
        return [r for r in self.journal(user)["items"] if r["type"] == "command"]

    def full(self, kind, params=None):
        """Повна команда класу B: 1/2 (u_en1) + 2/2 (u_en2) → `queued`, потім звіт збирача `done` (API-25)."""
        prep = self.prepare(kind, params)
        self.confirm(prep)
        self.pult(self.u_en2).command("confirm_second", ref=prep["ref"])
        action = self.Action.sudo().browse(prep["action_id"])
        self.assertEqual(action.state, "queued")
        self.finish(action)
        self.assertEqual(action.state, "done")
        return action

    def test_invariant_one_command_one_record(self):  # AC-B04, RB-06
        start = self.full("start")
        self.put(RUNNING)
        stop = self.full("stop")
        self.assertEqual(self.actions("chp_start"), start)
        self.assertEqual(self.actions("chp_stop"), stop)
        self.assertEqual(self.Command.search_count([]), 0)
        self.assertEqual(self.env["td.command"].sudo().search_count([("origin", "=", "chp")]), 0)
        texts = self.Event.search([("unit_id", "=", self.unit.id)]).mapped("text")
        self.assertFalse([t for t in texts if "Команда" in t or "Пуск" in t.split(":")[0]])
        rows = self.command_rows()
        self.assertEqual(len(rows), 2)
        self.assertEqual({r["ref"] for r in rows}, {f"energy:{start.id}", f"energy:{stop.id}"})
        self.assertEqual({r["state"] for r in rows}, {"done"})

    def test_journal_text_and_level(self):
        action = self.full("start")
        row = next(r for r in self.command_rows() if r["id"] == action.id)
        self.assertEqual(row["text"], f"Команда «Пуск»: Виконано · 1/2 {self.u_en1.name}, 2/2 {self.u_en2.name}")
        self.assertEqual((row["type"], row["level"], row["ack_state"]), ("command", "info", None))
        failed = self.act("estop")
        self.command_done(failed, ack=2, reason=12)
        row = next(r for r in self.command_rows() if r["id"] == failed.id)
        self.assertEqual((row["level"], row["state"]), ("warn", "failed"))
        self.assertEqual(row["text"], "Команда «Аварійний стоп»: Не виконано")

    def test_journal_merges_events_and_commands_desc(self):  # AC-B06
        self.put({"ctl/state": 0})
        self.put({"ctl/state": 1}, ts=None)  # подія стану (R-04)
        a = self.act("set_cos", {"cos": 0.97})
        self.command_done(a, values={"ctl/cos_set": 0.97})
        b = self.act("estop")
        self.command_done(b, ack=1)
        self.put({"alarm/code": 116, "ctl/state": 3})  # подія аварії
        items = self.journal()["items"]
        kinds = [i["type"] for i in items]
        self.assertIn("event", kinds)
        self.assertEqual(kinds.count("command"), 2)
        keys = [(i["ts"], i["id"]) for i in items]
        self.assertEqual(keys, sorted(keys, reverse=True))
        self.assertEqual(len({(i["type"], i["id"]) for i in items}), len(items))  # без дублів

    def test_journal_pagination_before(self):
        for i in range(3):
            action = self.act("set_cos", {"cos": 0.95 + i / 100})
            self.command_done(action, values={"ctl/cos_set": 0.95 + i / 100})
        page = self.journal(limit=2)
        self.assertEqual(len(page["items"]), 2)
        self.assertTrue(page["more"])
        rest = self.journal(limit=50, before=page["items"][-1]["ts"])
        self.assertTrue(all(r["ts"] < page["items"][-1]["ts"] for r in rest["items"]))

    def test_prepared_and_cancelled_are_not_in_journal(self):
        prep = self.prepare("set_cos", {"cos": 0.97})
        self.assertEqual(self.command_rows(), [])
        self.pult(self.u_en1).command("cancel", ref=prep["ref"], token=prep["token"])
        self.assertEqual(self.command_rows(), [])

    def test_blocked_attempt_is_a_journal_row(self):
        self.put({"gas/p_in": 1.15})
        prep = self.prepare("start")
        rows = self.command_rows()
        self.assertEqual([(r["ref"], r["state"], r["level"]) for r in rows], [(prep["ref"], "blocked", "warn")])

    def test_auto_chp_actions_are_included(self):
        node = self.unit.energy_node_id
        auto = (
            self.Action.sudo()
            .with_context(td_energy_control_internal=True)
            .create(
                {
                    "kind_code": "auto_chp_start",
                    "origin": "auto",
                    "state": "done",
                    "summary": "Сценарій «КГУ за графіком»: пуск КГУ",
                    "node_id": node.id,
                    "prepared_at": self.now,
                    "finished_at": self.now,
                }
            )
        )
        row = next(r for r in self.command_rows() if r["id"] == auto.id)
        self.assertEqual(row["text"], "Сценарій «КГУ за графіком»: пуск КГУ")

    def test_foreign_actions_are_not_in_journal(self):
        self.run_foreign = (
            self.Action.sudo()
            .with_context(td_energy_control_internal=True)
            .create(
                {
                    "kind_code": "qs_close",
                    "state": "done",
                    "summary": "QS",
                    "prepared_at": self.now,
                    "finished_at": self.now,
                }
            )
        )
        self.assertNotIn(self.run_foreign.id, [r["id"] for r in self.command_rows()])

    # --- AC-B08: картка «Очікує другого підтвердження» --------------------------------------------------------------
    def test_pending_card_and_can_second(self):
        prep = self.prepare("start")
        self.confirm(prep)
        mine = self.pult(self.u_en1).get_state()["pending"]
        other = self.pult(self.u_en2).get_state()["pending"]
        self.assertEqual(len(mine), 1)
        self.assertEqual(len(other), 1)
        self.assertEqual(
            (mine[0]["ref"], mine[0]["kind"], mine[0]["prepared_by"]), (prep["ref"], "start", self.u_en1.name)
        )
        self.assertEqual(mine[0]["title"], "Пуск КГУ-1")
        self.assertFalse(mine[0]["can_second"])
        self.assertTrue(other[0]["can_second"])
        self.assertTrue(other[0]["second_expires_at"])
        self.assertTrue(self.pult(self.e_chief).get_state()["pending"][0]["can_second"])
        viewer = self.pult(self.u_view).get_state()["pending"]
        self.assertFalse(viewer[0]["can_second"])  # без ролі «Енергетик» другого підтвердження дати не можна
        self.pult(self.u_en2).command("confirm_second", ref=prep["ref"])
        self.assertEqual(self.pult(self.u_en1).get_state()["pending"], [])

    def test_pending_disappears_on_expiry(self):
        prep = self.prepare("start")
        self.confirm(prep)
        action = self.Action.sudo().browse(prep["action_id"])
        action._me().write({"second_expires_at": self.now - timedelta(seconds=1)})
        self.Action._cron_expire()
        self.assertEqual(action.state, "expired")
        self.assertEqual(self.pult(self.u_en2).get_state()["pending"], [])
        self.assertEqual(self.command_rows()[0]["state"], "expired")
