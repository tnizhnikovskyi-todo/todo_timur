"""AC-14: верифікація виконання (R-09), зворотний хук td.command (R-08 п. 5), крон прострочення."""

from odoo.tests import tagged

from .common import TAGS, ChpCase


@tagged(*TAGS)
class TestCommandVerify(ChpCase):
    def setUp(self):
        super().setUp()
        self.skip_if_bridge()
        self.idle()

    def queued(self, kind="start", params=None):
        """Команда в черзі: chief виконує одноосібно."""
        prep = self.pult(self.u_chief).command("prepare", kind=kind, params=params)
        self.pult(self.u_chief).command("confirm", ref=prep["ref"], token=prep["token"])
        rec = self.Command.browse(prep["action_id"])
        self.assertEqual(rec.state, "queued")
        return rec

    def test_ack_accepted(self):
        rec = self.queued()
        rec.command_id.write({"state": "sent"})
        self.assertEqual(rec.state, "sent")
        rec.command_id.write({"state": "done", "done_at": self.later(-1).context["td_chp_now"]})
        self.assertEqual(rec.state, "executing")
        self.put({"ctl/ack": 0})  # «немає результату» — чекаємо
        self.assertEqual(rec.state, "executing")
        self.put({"ctl/ack": 1})
        self.assertEqual((rec.state, rec.result_text), ("done", "Контролер прийняв команду"))
        self.assertTrue(rec.finished_at)
        row = [r for r in self.pult(self.u_user).get_journal()["items"] if r["type"] == "command"][0]
        self.assertEqual((row["state"], row["text"], row["level"]), ("done", "Команда «Пуск»: Виконано", "info"))

    def test_ack_rejected_with_reason(self):
        rec = self.queued()
        self.ack_flow(rec, 2, reason=2)
        self.assertEqual(rec.state, "failed")
        self.assertEqual(rec.error, "Контролер відхилив команду: тиск газу нижче мінімуму")
        row = [r for r in self.pult(self.u_user).get_journal()["items"] if r["type"] == "command"][0]
        self.assertEqual(row["level"], "warn")

    def test_old_ack_before_done_ignored(self):
        rec = self.queued()
        rec.command_id.write({"state": "sent"})
        rec.command_id.write({"state": "done", "done_at": self.later(60).context["td_chp_now"]})
        self.put({"ctl/ack": 1})  # показання старше за done_at
        self.assertEqual(rec.state, "executing")

    def test_set_value_verified(self):
        rec = self.queued("set_cos", {"cos": 0.97})
        self.assertEqual(rec.expect["signal"], "chp/ctl/cos_set")
        rec.command_id.write({"state": "sent"})
        rec.command_id.write({"state": "done", "done_at": self.later(-1).context["td_chp_now"]})
        self.put({"ctl/cos_set": 0.99})  # інше значення — не підтверджує
        self.assertEqual(rec.state, "executing")
        self.put({"ctl/cos_set": 0.97})
        self.assertEqual(rec.state, "done")

    def test_timeout_fails_and_cancels_queue(self):
        rec = self.queued()
        self.assertEqual(self.later(10)["td.chp.command"]._cron_expire(), 0)
        late = self.later(31)
        self.assertEqual(late["td.chp.command"]._cron_expire(), 1)
        self.assertEqual(rec.state, "failed")
        self.assertEqual(rec.error, "Контролер не підтвердив команду за 30 с")
        self.assertEqual(rec.command_id.state, "cancelled")  # колектор уже не забере команду

    def test_timeout_executing(self):
        rec = self.queued()
        rec.command_id.write({"state": "sent"})
        rec.command_id.write({"state": "done", "done_at": self.later(-1).context["td_chp_now"]})
        self.assertEqual(self.later(31)["td.chp.command"]._cron_expire(), 1)
        self.assertEqual(rec.state, "failed")

    def test_transport_failure(self):
        rec = self.queued()
        rec.command_id.write({"state": "sent"})
        rec.command_id.write({"state": "failed", "error": "Modbus: тайм-аут"})
        self.assertEqual((rec.state, rec.error), ("failed", "Modbus: тайм-аут"))
        rec2 = self.queued("set_cos", {"cos": 0.95})
        rec2.command_id.write({"state": "expired"})
        self.assertEqual(rec2.state, "expired")

    def test_cancel_queued_command(self):
        rec = self.queued()
        rec._td_cancel_record()
        self.assertEqual(rec.state, "cancelled")
        self.assertEqual(rec.command_id.state, "cancelled")
