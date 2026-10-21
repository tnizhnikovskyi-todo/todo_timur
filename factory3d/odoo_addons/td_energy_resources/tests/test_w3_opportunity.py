"""W3-B: AC-32, AC-33, AC-40…AC-43 — правила, життєвий цикл резервів, дії (C-32), заявки ТО, права, API-02/06."""

from datetime import timedelta
from unittest.mock import patch

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged

from ..tools.detectors import DETECTORS, common
from .common import NOW, TAGS, TestW3Common

CORE = {"vent_offshift", "idle_machines", "air_leaks", "air_pressure", "react_section", "pv_export"}
RULES = {  # код: (ресурс, вікно, мін. економія, пороги, намір керування)
    "vent_offshift": ("el", 7, 1000.0, {"group": "vent", "ratio_min": 0.35, "target_ratio": 0.30}, "vent_night_mode"),
    "idle_machines": ("el", 7, 1000.0, {"idle_share_min": 0.05, "recoverable": 0.40}, False),
    "air_leaks": ("air", 7, 1000.0, {"ratio_min": 0.10, "min_flow": 0.2, "reducible": 0.65}, False),
    "air_pressure": ("air", 7, 1000.0, {"margin_bar": 0.3, "k_per_bar": 0.07, "min_save_bar": 0.2},
                     "air_pressure_setpoint"),
    "react_section": ("el", 7, 500.0, {"cos_target": 0.92, "min_hours_day": 2.0}, False),
    "pv_export": ("el", 7, 500.0, {"min_export_kw": 10.0, "capture": 0.40}, "pv_self_consumption"),
}  # fmt: skip


def finding(key="vent_offshift:*", saving=5000.0, qty=600.0, **extra):
    item = {
        "dedup_key": key, "title": "Тестова знахідка", "text": "Текст знахідки", "est_saving_month": saving,
        "est_qty_month": qty, "evidence": {"n": 1}, "node_code": None, "point_code": None,
    }  # fmt: skip
    item.update(extra)
    return item


@tagged(*TAGS)
class TestW3Opportunity(TestW3Common):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Rule = cls.env["td.energy.opportunity.rule"]
        cls.Opp = cls.env["td.energy.opportunity"]
        cls.rule_vent = cls.env.ref("td_energy_resources.rule_vent_offshift")
        cls.rule_idle = cls.env.ref("td_energy_resources.rule_idle_machines")
        cls.rule_air = cls.env.ref("td_energy_resources.rule_air_leaks")
        cls.u_ecost = cls._mk_user("w3b_ecost", ["td_energy.group_td_energy_cost"])

    # --- допоміжне --------------------------------------------------------------------------------------
    def run_rule(self, rule, findings, env=None):
        """`action_run` правила з підміненим детектором (`DETECTORS` — реєстр ядра)."""
        fake = findings if callable(findings) else (lambda env, rule, now: findings)
        with patch.dict(DETECTORS, {rule.code: fake}):
            return rule.with_env(env or self.env).action_run()

    def open_opp(self, rule=None, key="vent_offshift:*", **kw):
        rule = rule or self.rule_vent
        self.run_rule(rule, [finding(key, **kw)])
        return self.Opp.search([("dedup_key", "=", key), ("state", "=", "open")])

    def later(self, days):
        return self.env(context=dict(self.env.context, f3d_now=NOW + timedelta(days=days)))

    # --- AC-32 -------------------------------------------------------------------------------------------
    def test_rules_data(self):  # AC-32
        rules = self.Rule.search([("code", "in", sorted(CORE))])
        self.assertEqual(set(rules.mapped("code")), CORE)
        for rule in rules:
            res, days, saving, params, intent = RULES[rule.code]
            self.assertTrue(rule.enabled, rule.code)
            self.assertEqual(
                (rule.resource_id.code, rule.lookback_days, rule.min_saving_uah, rule.control_intent or False),
                (res, days, saving, intent), rule.code,
            )  # fmt: skip
            self.assertEqual(rule.params, params, rule.code)
            self.assertEqual(common.check_params(rule.params_schema, rule.params), [], rule.code)
            self.assertEqual({i["key"] for i in rule.params_schema}, {k for k in params if k != "group"}, rule.code)
            self.assertTrue(
                all({"key", "label", "type", "min", "max", "unit", "default"} <= set(i) for i in rule.params_schema)
            )
        self.assertEqual(self.rule_idle.actions[0]["params"]["xmlid"], "td_energy.action_td_energy_alloc_pivot")
        self.assertEqual(self.rule_air.actions[0]["kind"], "ticket")
        self.assertEqual(self.rule_air.actions[0]["params"]["node_code"], "COMPRESSOR")
        self.assertEqual(
            self.rule_vent.fallback_action["params"]["xmlid"], "td_energy_resources.action_td_energy_opportunity"
        )

    def test_rule_constraints(self):  # AC-32
        rule = self.rule_vent
        good = dict(rule.params)
        for bad in ({"ratio_min": 5.0}, {"ratio_min": -1.0}, {"ratio_min": "x"}, {"target_ratio": True}):
            with self.assertRaisesRegex(ValidationError, "Параметр"):
                rule.write({"params": dict(good, **bad)})
        with self.assertRaisesRegex(ValidationError, "очікується float у діапазоні 0.05…1.0"):
            rule.write({"params": dict(good, ratio_min=0.0)})
        rule.write({"params": dict(good, ratio_min=0.4)})  # у межах
        for bad in (
            [{"code": "x", "label": "Y", "kind": "bad"}],
            [{"code": "BAD CODE", "label": "Y", "kind": "link"}],
            [{"code": "ok", "label": "Я" * 49, "kind": "link"}],
            ["не словник"],
        ):
            with self.assertRaises(ValidationError):
                rule.write({"actions": bad})
        with self.assertRaises(ValidationError):
            rule.write({"lookback_days": 0})
        with self.assertRaises(ValidationError):
            rule.write({"lookback_days": 61})

    # --- AC-33 -------------------------------------------------------------------------------------------
    def test_lifecycle(self):  # AC-33
        rule = self.rule_vent
        stats = self.run_rule(rule, [finding(saving=5000.0, qty=600.0)])
        self.assertEqual((stats["found"], stats["created"], stats["expired"]), (1, 1, 0))
        self.assertIn("seconds", stats)
        opp = self.Opp.search([("dedup_key", "=", "vent_offshift:*")])
        self.assertEqual((opp.state, opp.in_plan, opp.est_saving_month, opp.found_at), ("open", False, 5000.0, NOW))
        self.assertEqual((rule.last_count, rule.last_error, rule.last_run), (1, False, NOW))
        self.assertEqual(opp.resource_id.code, "el")
        opp.with_user(self.u_eng).action_plan_toggle()
        stats = self.run_rule(rule, [finding(saving=7000.0, qty=800.0, title="Новий заголовок")], self.later(1))
        self.assertEqual((stats["found"], stats["created"], stats["expired"]), (1, 0, 0))
        opp.invalidate_recordset()
        self.assertEqual((opp.est_saving_month, opp.est_qty_month, opp.title), (7000.0, 800.0, "Новий заголовок"))
        self.assertTrue(opp.in_plan)  # in_plan і plan_* зберігаються
        self.assertEqual(opp.plan_user_id, self.u_eng)
        self.assertEqual(opp.last_seen_at, NOW + timedelta(days=1))
        stats = self.run_rule(rule, [], self.later(2))
        self.assertEqual((stats["found"], stats["created"], stats["expired"]), (0, 0, 1))
        opp.invalidate_recordset()
        self.assertEqual((opp.state, opp.resolved_at, opp.in_plan), ("expired", NOW + timedelta(days=2), True))
        self.assertEqual(rule.last_count, 0)

    def test_min_saving_filter(self):  # AC-33
        stats = self.run_rule(self.rule_vent, [finding(saving=999.0)])
        self.assertEqual((stats["found"], stats["created"]), (0, 0))
        self.assertFalse(self.Opp.search([("dedup_key", "=", "vent_offshift:*")]))
        self.rule_vent.min_saving_uah = 100.0
        self.assertEqual(self.run_rule(self.rule_vent, [finding(saving=999.0)])["created"], 1)

    def test_dismiss_and_done_suppress_repeat(self):  # AC-33
        rule = self.rule_vent
        opp = self.open_opp()
        opp.with_user(self.u_eng).action_dismiss()
        self.assertEqual(opp.state, "dismissed")
        self.assertEqual(self.run_rule(rule, [finding()], self.later(10))["created"], 0)  # < dismiss_days (30)
        self.assertEqual(self.run_rule(rule, [finding()], self.later(31))["created"], 1)
        second = self.Opp.search([("dedup_key", "=", "vent_offshift:*"), ("state", "=", "open")])
        self.assertNotEqual(second, opp)
        second = second.with_env(self.later(31)).with_user(self.u_eng)
        second.action_done("Налаштовано")
        self.assertEqual((second.state, second.result_note, second.resolved_by), ("done", "Налаштовано", self.u_eng))
        self.assertEqual(self.run_rule(rule, [finding()], self.later(31 + 5))["created"], 0)  # < cooldown_days (14)
        self.assertEqual(self.run_rule(rule, [finding()], self.later(31 + 15))["created"], 1)

    def test_detector_failure_isolated(self):  # AC-33
        self.Rule.search([]).write({"enabled": False})
        (self.rule_vent | self.rule_idle).write({"enabled": True})

        def boom(env, rule, now):
            raise RuntimeError("boom")

        fake = {"vent_offshift": boom, "idle_machines": lambda env, rule, now: [finding("idle_machines:*", 3000.0)]}
        keep = self.open_opp(key="vent_offshift:*")  # відкритий резерв збоєм не закривається
        with patch.dict(DETECTORS, fake), self.assertLogs("odoo.addons.td_energy_resources", level="ERROR"):
            self.Opp._cron_detect()
        self.assertEqual(self.rule_vent.last_error, "boom")
        self.assertFalse(self.rule_idle.last_error)
        self.assertEqual(self.rule_idle.last_count, 1)
        self.assertTrue(self.Opp.search([("dedup_key", "=", "idle_machines:*")]))
        self.assertEqual(keep.state, "open")

    def test_detector_note_and_missing(self):  # AC-33, AC-38: DetectorNote → last_error, резерви правила закриваються
        opp = self.open_opp()

        def note(env, rule, now):
            raise common.DetectorNote("Немає параметрів доплати в тарифі")

        stats = self.run_rule(self.rule_vent, note)
        self.assertEqual((stats["found"], stats["expired"]), (0, 1))
        self.assertEqual(self.rule_vent.last_error, "Немає параметрів доплати в тарифі")
        self.assertEqual(opp.state, "expired")
        rule = self.Rule.create({"code": "no_detector", "name": "Без детектора", "resource_id": self.resource("el").id})
        self.assertEqual(rule.action_run()["found"], 0)
        self.assertEqual(rule.last_error, "Детектор недоступний")

    def test_cron_respects_read_enabled(self):
        self.env["ir.config_parameter"].sudo().set_param("td.energy.read_enabled", "False")
        with patch.dict(DETECTORS, {"vent_offshift": lambda env, rule, now: [finding()]}):
            self.assertFalse(self.Opp._cron_detect())
        self.assertFalse(self.Opp.search([("dedup_key", "=", "vent_offshift:*")]))

    def test_single_open_per_key(self):  # частковий унікальний індекс dedup_key WHERE state = 'open'
        opp = self.open_opp()
        self.assertEqual(self.run_rule(self.rule_vent, [finding(), finding()])["created"], 0)
        self.assertEqual(self.Opp.search_count([("dedup_key", "=", opp.dedup_key), ("state", "=", "open")]), 1)

    # --- AC-40: дії -----------------------------------------------------------------------------------------
    def test_actions_control_and_fallback(self):  # AC-40
        opp = self.open_opp()
        self.assertEqual(opp.actions[-1]["code"], "control")
        self.assertEqual(opp.actions[-1]["params"], {"intent": "vent_night_mode"})
        item = self.Opp.get_list("el")["items"][0]
        if "td.energy.control" in self.env:  # W2 встановлено: керування доступне, запасне «Відкрити» не додається
            self.assertEqual([(a["kind"], a["enabled"]) for a in item["actions"]], [("control", True)])
            return
        control, fallback = item["actions"]
        self.assertEqual((control["kind"], control["enabled"]), ("control", False))  # немає td_energy_control
        self.assertEqual((fallback["code"], fallback["kind"], fallback["enabled"]), ("open", "link", True))
        self.assertEqual(
            fallback["params"], {"xmlid": "td_energy_resources.action_td_energy_opportunity", "res_id": opp.id}
        )
        advice = type(self.env["td.energy.advice"])
        with patch.object(advice, "_td_control_available", lambda self: True):
            actions = self.Opp.get_list("el")["items"][0]["actions"]
        self.assertEqual([(a["kind"], a["enabled"]) for a in actions], [("control", True)])

    def test_actions_ticket_tag(self):  # AC-40
        opp = self.open_opp(self.rule_air, "air_leaks:*", node_code="COMPRESSOR")
        ticket = opp.actions[0]
        self.assertEqual((ticket["kind"], ticket["params"]["node_code"]), ("ticket", "COMPRESSOR"))
        self.assertIn("[OPP-%d]" % opp.id, ticket["params"]["description"])
        self.assertEqual(opp.node_id.code, "COMPRESSOR")
        self.run_rule(self.rule_air, [finding("air_leaks:*", saving=9000.0)])  # оновлення зберігає тег
        opp.invalidate_recordset()
        self.assertIn("[OPP-%d]" % opp.id, opp.actions[0]["params"]["description"])
        self.assertEqual(self.Opp.get_list("air")["items"][0]["actions"][0]["enabled"], True)

    def test_actions_from_finding(self):  # AC-38: дії знахідки (динамічні) замінюють `rule.actions`
        link = {"code": "open_request", "label": "Відкрити заявку", "kind": "link", "class": None,
                "params": {"xmlid": "maintenance.hr_equipment_request_action", "res_id": 5}}  # fmt: skip
        opp = self.open_opp(self.rule_air, "air_leaks:*", actions=[link])
        self.assertEqual(opp.actions, [link])

    # --- AC-41: заявки ---------------------------------------------------------------------------------------
    def test_link_requests(self):  # AC-41
        opp = self.open_opp(self.rule_air, "air_leaks:*", node_code="COMPRESSOR")
        Stage = self.env["maintenance.stage"]
        stage_new, stage_done = (
            Stage.search([("done", "=", False)], limit=1),
            Stage.search([("done", "=", True)], limit=1),
        )
        self.assertTrue(stage_new and stage_done)
        request = self.env["maintenance.request"].create(
            {
                "name": "Витоки повітря", "stage_id": stage_new.id, "user_id": self.u_eng.id,
                "description": "Пошук витоків стисненого повітря [OPP-%d]" % opp.id,
            }
        )  # fmt: skip
        other = self.env["maintenance.request"].create({"name": "Без тегу", "stage_id": stage_done.id})
        self.assertTrue(self.Opp._td_link_requests())
        opp.invalidate_recordset()
        self.assertEqual((opp.request_id, opp.state), (request, "open"))
        self.assertNotEqual(other, opp.request_id)
        self.assertEqual(self.Opp.get_list("air")["items"][0]["request_id"], request.id)
        request.stage_id = stage_done
        self.Opp._td_link_requests()
        opp.invalidate_recordset()
        self.assertEqual((opp.state, opp.result_note, opp.resolved_by), ("done", "Заявку закрито", self.u_eng))
        self.assertEqual(opp.resolved_at, NOW)
        self.assertEqual(self.Opp._td_link_requests(), 0)  # нічого нового

    # --- AC-42: права ---------------------------------------------------------------------------------------
    def test_manager_only_actions(self):  # AC-42
        opp = self.open_opp()
        view = opp.with_user(self.u_view)
        for call in (lambda: view.action_plan_toggle(), lambda: view.action_dismiss(), lambda: view.action_done("x")):
            with self.assertRaisesRegex(AccessError, "Керувати резервами може лише енергетик."):
                call()
        self.assertEqual((opp.state, opp.in_plan), ("open", False))
        manager = opp.with_user(self.u_eng)
        self.assertTrue(manager.action_plan_toggle())
        self.assertEqual((opp.in_plan, opp.plan_user_id, opp.plan_date), (True, self.u_eng, NOW.date()))
        self.assertTrue(manager.action_plan_toggle())
        self.assertEqual((opp.in_plan, opp.plan_user_id.id, opp.plan_date), (False, False, False))
        self.assertTrue(manager.action_plan_toggle(plan=True))
        self.assertTrue(manager.action_plan_toggle(plan=True))  # явне значення не інвертує
        self.assertTrue(opp.in_plan)
        bodies = " ".join(opp.message_ids.mapped("body"))
        self.assertIn("Додано до плану", bodies)
        self.assertIn("Прибрано з плану", bodies)
        self.assertTrue(manager.action_done("Готово"))
        self.assertIn("Виконано", " ".join(opp.message_ids.mapped("body")))
        self.assertTrue(opp.in_plan)  # `done` план не скидає
        for call in (manager.action_plan_toggle, manager.action_dismiss, manager.action_done):
            with self.assertRaisesRegex(UserError, "Резерв уже закрито."):
                call()
        with self.assertRaises(AccessError):
            opp.with_user(self.u_view).write({"title": "Інший"})  # користувач групи — лише читання
        dismissed = self.open_opp(key="vent_offshift:2")
        dismissed.with_user(self.u_eng).action_dismiss()
        self.assertIn("Відхилено", " ".join(dismissed.message_ids.mapped("body")))
        self.assertFalse(dismissed.in_plan)

    def test_run_rule_access(self):  # API-05
        with self.assertRaises(AccessError):
            self.rule_vent.with_user(self.u_view).action_run()
        stats = self.run_rule(self.rule_vent, [finding()], self.env(user=self.u_eng.id))  # менеджер створює через sudo
        self.assertEqual((stats["found"], stats["created"]), (1, 1))
        self.assertEqual(set(stats), {"found", "created", "expired", "seconds"})

    # --- AC-43: список й підсумки ---------------------------------------------------------------------------
    def test_get_list_and_summary(self):  # AC-43
        a = self.open_opp(key="vent_offshift:a", saving=6900.0, qty=348.5)
        b = self.open_opp(self.rule_air, "air_leaks:*", saving=33787.0, qty=4022.2)
        c = self.open_opp(self.rule_idle, "idle_machines:*", saving=1500.0)
        a.with_user(self.u_eng).action_plan_toggle()
        closed = self.open_opp(self.env.ref("td_energy_resources.rule_pv_export"), "pv_export:*", saving=99999.0)
        closed.with_user(self.u_eng).action_dismiss()
        cost = self.Opp.with_user(self.u_ecost)
        data = cost.get_list()
        self.assertEqual([i["id"] for i in data["items"]], [a.id, b.id, c.id])  # in_plan, потім економія
        self.assertEqual((data["plan_sum"], data["all_sum"]), (6900, 6900 + 33787 + 1500))
        first = data["items"][0]
        self.assertEqual(
            (first["code"], first["resource"], first["save_uah_month"], first["est_qty_month"], first["in_plan"]),
            ("vent_offshift", "el", 6900, 348.5, True),
        )
        self.assertEqual(first["state"], "open")
        self.assertEqual(first["found_at"], NOW.isoformat())
        self.assertIsNone(first["request_id"])
        self.assertEqual([i["id"] for i in cost.get_list("air")["items"]], [b.id])
        self.assertEqual(cost.get_list("air")["all_sum"], 33787)
        self.assertEqual([i["state"] for i in cost.get_list(states=("dismissed", "expired"))["items"]], ["dismissed"])
        self.assertEqual(
            cost.get_plan_summary(), {"plan_sum": 6900, "all_sum": 42187, "plan_count": 1, "open_count": 3}
        )
        view = self.Opp.with_user(self.u_view)  # без групи вартості — ключів сум і вартості немає
        plain = view.get_list()
        self.assertEqual(set(plain), {"items"})
        self.assertTrue(all("save_uah_month" not in i for i in plain["items"]))
        self.assertEqual(len(plain["items"]), 3)
        self.assertEqual(view.get_plan_summary(), {"plan_count": 1, "open_count": 3})
        with self.assertRaises(AccessError):
            self.Opp.with_user(self.u_plain).get_list()
        with self.assertRaises(AccessError):
            self.Opp.with_user(self.u_plain).get_plan_summary()
        with self.assertRaisesRegex(UserError, "Невідомий ресурс: xx."):
            cost.get_list("xx")
        with self.assertRaises(UserError):
            cost.get_list(states=("bogus",))
