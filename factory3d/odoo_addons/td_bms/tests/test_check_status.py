"""Крон перевірок: статус джерела BMS-DERIVED пишеться лише за зміни (`last_ok` — із тротлінгом td_telemetry)."""

from datetime import timedelta
from unittest.mock import patch

from freezegun import freeze_time

from odoo import fields
from odoo.tests import tagged
from odoo.tools import mute_logger

from .test_rules_lighting import RulesCase


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestCheckSourceStatus(RulesCase):
    def _run(self, fail=False, minutes=0):
        """Прогін крона через `minutes` хв від поточного часу; повертає кількість записів у джерело."""
        Check = self.env["td.bms.check"]
        src = self.derived
        with (
            mute_logger("odoo.addons.td_bms.models.td_bms_check"),  # крон логує збій, який тест викликає навмисно
            freeze_time(fields.Datetime.now() + timedelta(minutes=minutes)),
            patch.object(type(Check), "_notify_commands", lambda *a, **k: None),
            patch.object(type(Check), "_run_checks", side_effect=RuntimeError("збій") if fail else None),
            patch.object(type(src), "write", autospec=True, side_effect=type(src).write) as spy,
        ):
            Check._cron_check()
        return spy.call_count

    def test_last_ok_throttled(self):
        src = self.derived
        self.assertEqual(self._run(), 1)  # перший прогін: стан/last_ok змінились
        self.assertEqual((src.state, bool(src.last_ok)), ("online", True))
        last_ok = src.last_ok
        self.assertEqual(self._run(minutes=1), 0)  # наступна хвилина: тільки last_ok — запису немає
        self.assertEqual(src.last_ok, last_ok)
        self.assertEqual(self._run(minutes=10), 1)  # інтервал status_touch_s (300 с) минув
        self.assertGreater(src.last_ok, last_ok)
        self.env["ir.config_parameter"].sudo().set_param("td.telemetry.status_touch_s", "0")
        self.assertEqual(self._run(minutes=11), 1)  # 0 — пишемо щоразу, як раніше

    def test_error_and_recovery_written_at_once(self):
        src = self.derived
        self._run()
        self.assertEqual(self._run(fail=True, minutes=1), 1)
        self.assertEqual((src.state, src.last_error), ("error", "збій"))
        self.assertEqual(self._run(fail=True, minutes=2), 0)  # та сама помилка — без запису
        self.assertEqual(self._run(minutes=3), 1)  # одужання: стан змінюється одразу, не чекаючи тротлінгу
        self.assertEqual((src.state, src.last_error), ("online", False))
