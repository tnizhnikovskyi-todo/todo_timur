"""AC-194, AC-277: виконавець `genset` (тест ДГУ через ADP-12; з імітацією адаптера, якщо міст не встановлений)."""

from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.tests import tagged

from ..tools import genset_link
from .common import TAGS, TestControlCommon


@tagged(*TAGS)
class TestGensetExec(TestControlCommon):
    def fake_adapter(self, start=None):
        class Adapter:
            @staticmethod
            def generators(env):
                return env["res.partner"].browse([1])

            @staticmethod
            def test_facts(gen):
                return {"fuel_pct": 78.0, "running": False, "test_running": False, "island": False, "coolant_c": 42.0}

            @staticmethod
            def start_test(gen, mode, user):
                if start:
                    raise start
                return {
                    "accepted": True,
                    "minutes": 10,
                    "test_end": "2026-10-17T11:30:00Z",
                    "ref": {"model": "td.genset", "id": 7},
                }

        return Adapter

    def test_available_without_bridge(self):  # AC-194
        with patch.object(genset_link, "adapter", return_value=None):
            kind = self.Kind.search([("code", "=", "genset_test")])
            kind.invalidate_recordset(["available", "unavailable_reason"])
            self.assertEqual(kind.unavailable_reason, "Не встановлено міст td_genset_factory3d")
            with self.assertRaises(UserError):
                self.ctl(self.u_chief).prepare("genset_test")

    def test_genset_flow(self):  # AC-277
        with patch.object(genset_link, "adapter", return_value=self.fake_adapter()):
            prep = self.ctl(self.u_en1).prepare("genset_test")
            codes = [c["code"] for c in prep["checks"]]
            self.assertEqual(codes, ["genset_fuel", "genset_heater", "no_island", "genset_idle"])
            self.assertFalse(prep["blocked"])
            self.assertEqual(self.ctl(self.u_en1).confirm(prep["token"])["state"], "awaiting_second")
            res = self.ctl(self.u_en2).confirm_second(prep["action_id"])
            act = self.Action.browse(prep["action_id"])
            self.assertEqual(res["state"], "done")
            self.assertEqual((act.ref_model, act.ref_id), ("td.genset", 7))
            self.assertEqual(act.result_text, "Тест ДГУ прийнято td_genset: 10 хв")
            self.assertFalse(act.command_id)

    def test_genset_error_blocks(self):
        err = UserError("Тест уже йде.")
        with patch.object(genset_link, "adapter", return_value=self.fake_adapter(start=err)):
            act = self.run_action("genset_test", user=self.u_chief)
            self.assertEqual((act.state, act.error), ("blocked", "Тест уже йде."))
