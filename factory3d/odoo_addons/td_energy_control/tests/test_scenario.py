"""AC-159…AC-164, AC-169: сценарії автоматики, чипи, версія конфігурації."""

from datetime import timedelta

from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged

from ..tools import kinds
from .common import NOW, TAGS, TestControlCommon


@tagged(*TAGS)
class TestScenario(TestControlCommon):
    def sc(self, code):
        return self.Scenario.search([("code", "=", code)])

    def test_seed(self):  # AC-159
        self.assertEqual(self.Scenario.search([]).mapped("code"), ["peak", "self", "pfc", "night", "backup", "chp"])
        enabled = {s.code: s.enabled for s in self.Scenario.search([])}
        self.assertEqual(enabled, dict(peak=True, self=False, pfc=True, night=True, backup=True, chp=False))
        self.assertIn("спершу розряд BESS", self.sc("peak").description)
        with self.assertRaises(AccessError):
            self.Scenario.with_user(self.u_en1).create({"code": "peak", "name": "x", "description": "x"})
        with self.assertRaises(AccessError):
            self.sc("peak").with_user(self.u_en1).unlink()

    def test_params_validation(self):  # AC-160
        peak, night = self.sc("peak"), self.sc("night")
        for rec, params in (
            (peak, {"limit_kw": 50}),
            (night, {"from": "25:00"}),
            (peak, {"nope": 1}),
            (night, {"days": [0, 8]}),
        ):
            with self.assertRaises(ValidationError, msg=str(params)), self.cr.savepoint():
                rec.sudo().with_context(td_energy_control_internal=True).write({"params": params})
        for rec in self.Scenario.search([]):
            _clean, errors = kinds.validate(kinds.SCENARIO_PARAMS[rec.code], rec._td_params())
            self.assertFalse(errors, rec.code)

    def test_state_text(self):  # AC-161
        peak = self.sc("peak")
        peak.sudo().with_context(td_energy_control_internal=True).write(
            {"engine_state": "armed", "engine_facts": {"margin_kw": 402}, "engine_ts": NOW}
        )
        self.assertEqual(peak._td_state_text(), ("Чергування · запас 402 кВт", "arm"))
        peak.sudo().with_context(td_energy_control_internal=True).enabled = False
        self.assertEqual(peak._td_state_text(), ("Вимкнено", "off"))
        pfc = self.sc("pfc")
        pfc.sudo().with_context(td_energy_control_internal=True).write(
            {"engine_state": "warn", "engine_facts": {"fault": "PFC-2 ступінь 3"}, "engine_ts": NOW}
        )
        self.assertEqual(pfc._td_state_text(), ("Збій: PFC-2 ступінь 3", "warn"))
        night = self.sc("night")
        night.sudo().with_context(td_energy_control_internal=True).write(
            {"engine_state": "armed", "engine_facts": {"next_run": "23:00"}, "engine_ts": NOW}
        )
        self.assertEqual(night._td_state_text()[0], "Наступний запуск о 23:00")
        slf = self.sc("self")
        slf.sudo().with_context(td_energy_control_internal=True).write(
            {"enabled": True, "engine_state": "active", "engine_facts": {"bess_kw": 26}, "engine_ts": NOW}
        )
        self.assertEqual(slf._td_state_text()[0], "Активний · заряд BESS 26 кВт")
        backup = self.sc("backup")
        backup.sudo().with_context(td_energy_control_internal=True).write(
            {"engine_state": "armed", "engine_facts": {"fuel_pct": 78}, "engine_ts": NOW}
        )
        self.assertEqual(backup._td_state_text()[0], "Готовий · паливо 78 %")
        stale = NOW - timedelta(seconds=300)
        backup.sudo().with_context(td_energy_control_internal=True).engine_ts = stale
        self.assertEqual(backup._td_state_text(), ("Немає даних від рушія", "off"))

    def test_chips(self):  # AC-162
        chips = {s.code: s._td_chips() for s in self.Scenario.search([])}
        self.assertEqual(chips["peak"], ["уставка 760 кВт · 95 %", "прогноз 15 хв"])
        self.assertEqual(chips["self"], ["експорт ≤ 20 кВт", "BESS до 95 %"])
        self.assertEqual(chips["pfc"], ["ціль cos φ 0,95", "крок 35 квар"])
        self.assertEqual(chips["night"], ["23:00–06:30", "RoofVent 30 %", "16 °C"])
        self.assertEqual(chips["backup"], ["АВР → ДГУ", "критичні 180 кВт"])
        self.assertEqual(chips["chp"], ["мін. робота 2 год", "ціна газу 25,00 ₴/м³"])

    def test_toggle_flow(self):  # AC-163
        peak = self.sc("peak")
        with self.assertRaises(AccessError):
            peak.with_user(self.u_en1).write({"enabled": False})
        act = self.run_action("scenario_toggle", {"scenario": "peak", "enabled": False}, user=self.u_chief)
        self.assertEqual(act.state, "done")
        self.assertFalse(peak.enabled)
        self.assertEqual(peak.config_version, self.State.get().config_version)
        self.assertEqual(peak.changed_by, self.u_chief)
        self.assertEqual(act.result_text, "збережено, очікує збирач")
        self.assertTrue(act.undo_available)
        prep = self.ctl(self.u_chief).undo(act.id)
        self.ctl(self.u_chief).confirm(prep["token"])
        self.assertTrue(peak.enabled)

    def test_bump_and_version(self):  # AC-164
        state = self.State.get()
        v0 = state.config_version
        self.State.bump()
        self.State.bump()
        state.invalidate_recordset()
        self.assertEqual(state.config_version, v0 + 2)
        etag0 = state.config_etag
        self.sc("peak").sudo()._td_apply_change({"params": {**self.sc("peak")._td_params(), "limit_kw": 700}})
        state.invalidate_recordset()
        self.assertEqual(state.config_version, v0 + 3)
        self.assertNotEqual(state.config_etag, etag0)
        self.sc("peak").sudo().with_context(td_energy_control_internal=True).write(
            {"engine_facts": {"x": 1}, "engine_ts": NOW}
        )
        state.invalidate_recordset()
        self.assertEqual(state.config_version, v0 + 3)  # факти рушія версію не змінюють

    def test_applied(self):  # AC-169
        act = self.run_action("scenario_toggle", {"scenario": "pfc", "enabled": False}, user=self.u_chief)
        pfc = self.sc("pfc")
        self.assertFalse(pfc.applied)
        self.assertFalse(act.applied)
        state = self.State.get()
        res = self.State._td_report({"collector": "X", "config_version_applied": pfc.config_version})
        self.assertEqual(res["accepted_actions"], 0)
        pfc.invalidate_recordset(["applied"])
        act.invalidate_recordset(["applied"])
        self.assertTrue(pfc.applied)
        self.assertTrue(act.applied)
        self.State._td_report({"collector": "X", "config_version_applied": 1})
        state.invalidate_recordset()
        self.assertGreaterEqual(state.applied_version, pfc.config_version)
