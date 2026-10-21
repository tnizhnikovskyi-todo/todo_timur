"""AC-217…AC-222: правила рекомендацій, алиаси W3, баннер «Виконано»."""

from datetime import timedelta

from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import NOW, TAGS, TestControlCommon


@tagged(*TAGS)
class TestAdviceRules(TestControlCommon):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Advice = cls.env["td.energy.advice"]
        cls.env["ir.config_parameter"].sudo().set_param("td.energy.read_enabled", "True")
        cls.Advice.search([]).write({"state": "dismissed"})
        cls._fresh("energy_control/chp/permit", 0)  # CHP-PRICE не заважає іншим правилам

    def readings(self, code, values, step_s=30):
        sig = self.env["td.signal"].sudo().search([("code", "=", code)], limit=1)
        self.env["td.reading"].sudo().search([("signal_id", "=", sig.id)]).unlink()
        for i, value in enumerate(reversed(values)):
            self.env["td.reading"].sudo().create(
                {"signal_id": sig.id, "ts": NOW - timedelta(seconds=i * step_s), "value": value}
            )

    def test_export_rule(self):  # AC-217
        self.readings("infra/totals/export_kw", [26.0] * 12)
        items = self.Advice._td_advice_rule_export_t2(NOW)
        self.assertEqual(len(items), 1)
        item = items[0]
        self.assertEqual(item["title"], "СЕС віддає 26 кВт у мережу через T2.")
        self.assertIn("до 16:00 приблизно 80 кВт·год", item["text"])
        self.assertEqual([a["code"] for a in item["actions"]], ["open_event", "charge_bess", "qs_on"])
        self.assertEqual([a.get("class") for a in item["actions"]], [None, "A", "B"])
        self.Advice._cron_advice()
        got = self.Advice.get_open()
        self.assertEqual(got["code"], "EXPORT-T2")
        self.assertTrue(all(a["enabled"] for a in got["actions"]))  # AC-219
        self.assertEqual({a["class"] for a in got["actions"] if a["kind"] == "control"}, {"A", "B"})
        self._fresh("energy/cells/QS/state", 1, "closed")
        self.assertEqual(self.Advice._td_advice_rule_export_t2(NOW), [])
        self._fresh("energy/cells/QS/state", 0, "open")
        self._fresh("infra/totals/bess_soc", 96)
        acts = self.Advice._td_advice_rule_export_t2(NOW)[0]["actions"]
        self.assertNotIn("charge_bess", [a["code"] for a in acts])
        self.assertTrue(self.Advice._td_control_available())

    def test_peak_and_chp_rules(self):  # AC-218
        peak = self.Scenario.search([("code", "=", "peak")])
        peak.sudo().with_context(td_energy_control_internal=True).enabled = False
        self.readings("infra/totals/grid_kw", [740.0] * 6)
        items = self.Advice._td_advice_rule_peak_risk(NOW)
        self.assertEqual(items[0]["code"], "PEAK-RISK")
        self.assertEqual([a["code"] for a in items[0]["actions"]], ["enable_peak", "discharge_bess"])
        self.readings("infra/totals/grid_kw", [100.0] * 6)
        self.assertEqual(self.Advice._td_advice_rule_peak_risk(NOW), [])
        self.assertEqual(self.Advice._td_advice_rule_chp_price(NOW), [])  # дозволу оператора немає
        self._fresh("energy_control/chp/permit", 1)
        chp = self.Advice._td_advice_rule_chp_price(NOW)
        self.assertEqual(chp[0]["code"], "CHP-PRICE")
        self._fresh("energy_control/chp/permit", 0)
        self.readings("infra/totals/export_kw", [26.0] * 12)
        self.Advice._cron_advice()
        self.assertTrue(self.Advice.search([("dedup_key", "=", "EXPORT-T2"), ("state", "=", "open")]))
        self._fresh("energy/cells/QS/state", 1, "closed")
        self.Advice._cron_advice()
        self.assertFalse(self.Advice.search([("dedup_key", "=", "EXPORT-T2"), ("state", "=", "open")]))

    def test_chp_price_headroom(self):  # AC-218: КГУ заміщує закупівлю лише в межах «навантаження − СЕС»
        self._fresh("energy_control/chp/permit", 1)
        self._fresh("infra/totals/pv_now", 309.0)
        self._fresh("energy/totals/p_now", 400.0)  # запас 91 кВт: решта 709 кВт пішла б у мережу за 3,5 ₴ < газ 6,25 ₴
        self.assertEqual(self.Advice._td_advice_rule_chp_price(NOW), [])
        self._fresh("energy/totals/p_now", 1200.0)  # запас 891 кВт ≥ потужності КГУ: вигідно
        chp = self.Advice._td_advice_rule_chp_price(NOW)
        self.assertEqual(chp[0]["code"], "CHP-PRICE")
        self.assertIn("891", chp[0]["text"].replace("\xa0", "").replace(" ", ""))
        self._fresh("energy_control/chp/permit", 0)

    def test_done_and_aliases(self):  # AC-220
        self.readings("infra/totals/export_kw", [26.0] * 12)
        self.Advice._cron_advice()
        adv = self.Advice.search([("code", "=", "EXPORT-T2"), ("state", "=", "open")])
        prep = self.ctl(self.u_en1).prepare(
            "bess_charge", {"power_kw": 50, "until": "16:00", "soc_limit_pct": 95}, advice_id=adv.id
        )
        self.ctl(self.u_en1).confirm(prep["token"])
        act = self.Action.browse(prep["action_id"]).sudo()
        self.assertEqual(act.origin, "advice")
        self.finish(act, "done", "BESS: заряд 50 кВт")
        self.assertEqual((adv.state, adv.result_note), ("done", "BESS: заряд 50 кВт"))
        self.assertEqual(self.ctl(self.u_en1).prepare("vent_night_mode")["kind"], "scenario_toggle")
        self.assertEqual(self.ctl(self.u_en1).prepare("pv_self_consumption")["kind"], "scenario_toggle")
        air = self.ctl(self.u_en1).prepare("air_pressure_setpoint", {"setpoint_bar": 6.5})
        self.assertEqual(air["kind"], "air_setpoint")
        with self.assertRaisesRegex(UserError, "не підтримується"):
            self.ctl(self.u_en1).prepare("heat_schedule_shift")
        self.assertFalse(self.Action.search([("kind_code", "=", "heat_schedule_shift")]))

    def test_done_banner(self):  # AC-221
        self.readings("infra/totals/export_kw", [26.0] * 12)
        self.Advice._cron_advice()
        adv = self.Advice.search([("code", "=", "EXPORT-T2"), ("state", "=", "open")])
        prep = self.ctl(self.u_en1).prepare("bess_charge", {"power_kw": 50, "until": "16:00"}, advice_id=adv.id)
        self.ctl(self.u_en1).confirm(prep["token"])
        act = self.Action.browse(prep["action_id"]).sudo()
        self.finish(act, "done", "ok")
        banner = self.Advice.get_open()
        self.assertEqual(banner["state"], "done")
        self.assertEqual(banner["title"], "BESS заряджається 50 кВт.")
        self.assertEqual(banner["text"], "Експорт через T2 усунено, до 16:00 накопичиться ≈ 80 кВт·год.")
        self.assertEqual(banner["actions"][0]["code"], "undo")
        later = self.Advice.with_context(f3d_now=NOW + timedelta(minutes=16))
        self.assertFalse(later.get_open())
        back = self.ctl(self.u_en1).undo(act.id)
        self.ctl(self.u_en1).confirm(back["token"])
        self.finish(self.Action.browse(back["action_id"]), "done")
        self.assertFalse(self.Advice.get_open())
