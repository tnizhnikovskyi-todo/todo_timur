"""W3-A: AC-01…AC-07, AC-49, AC-50, AC-52, AC-53, AC-54 — ресурси, ціни, точки, лічильники, сигнали, права, зміни."""

from datetime import date, datetime

from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import file_open, mute_logger

from .. import hooks
from ..tools import shifts
from .common import TAGS, TestW3Common

NEW_SIGNALS = (
    "infra/gas/m3_total", "infra/gas/flow_m3h", "equipment/BOILER/gas_m3h", "air/flow_m3min", "air/m3_total",
    "air/pressure_bar", "infra/water/boiler_m3_total", "infra/water/boiler_flow_m3h", "energy/cells/Q1/kvarh_total",
    "energy/cells/Q2/kvarh_total",
)  # fmt: skip


@tagged(*TAGS)
class TestW3Data(TestW3Common):
    def test_resources_seed(self):  # AC-01
        res = self.Resource.search([])
        self.assertEqual(set(res.mapped("code")), {"el", "gas", "heat", "air", "water"})
        for xmlid in ("el", "gas", "heat", "air", "water"):
            self.assertEqual(self.env.ref("td_energy_resources.resource_" + xmlid).code, xmlid)
        factors = {r.code: r.rate_hour_factor for r in res}
        self.assertEqual(factors, {"el": 1.0, "gas": 1.0, "heat": 1.0, "air": 60.0, "water": 1.0})
        self.assertEqual(self.resource("gas").kwh_per_unit, 10.5)
        self.assertEqual((self.resource("el").co2_kg_per_unit, self.resource("gas").co2_kg_per_unit), (0.37, 1.96))
        self.assertEqual(set(res.filtered("is_derived").mapped("code")), {"heat", "air"})
        self.assertEqual(set(res.filtered("in_energy_cost").mapped("code")), {"el", "gas"})
        self.assertEqual(res.filtered(lambda r: r.list_basis == "qty_day").code, "water")
        self.assertEqual(self.resource("heat").source_note, "з BMS")
        self.assertEqual(self.resource("gas").daily_limit, 1200.0)
        self.assertEqual(self.resource("el").limit_kind, "tariff_contract")
        self.assertFalse(self.resource("heat").show_tab_cost)

    def test_resource_constraints(self):  # AC-02
        vals = {"code": "xx", "name": "X", "uom_label": "од", "rate_label": "од/год"}
        with self.assertRaises(ValidationError):
            self.Resource.create(dict(vals, code="gas"))
        with self.assertRaises(ValidationError):
            self.Resource.create(dict(vals, rate_hour_factor=0))
        with self.assertRaises(ValidationError):
            self.Resource.create(dict(vals, code="Bad Code!"))
        with self.assertRaises(ValidationError):
            self.Resource.create(dict(vals, limit_kind="fixed", rate_limit=0))
        with self.assertRaises(UserError) as cm:
            self.resource("el").unlink()
        self.assertIn("Електрика", str(cm.exception))
        with self.assertRaises(ValidationError) as cm:
            self.Resource.create(dict(vals, code="el"))
        self.assertIn("має бути єдиним", str(cm.exception))
        with self.assertRaises(ValidationError):
            self.resource("el").write({"active": False})
        self.assertEqual(self.Resource.get_by_code("gas").code, "gas")
        self.assertFalse(self.Resource.get_by_code("nope"))
        self.assertEqual(self.resource("air")._td_rate_to_qty(9.8, 0.25), 9.8 * 60 * 0.25)

    def test_price_rules(self):  # AC-03
        el, gas = self.resource("el"), self.resource("gas")
        with self.assertRaises(ValidationError) as cm:
            self.Price.create({"resource_id": el.id, "date_from": "2026-01-01", "price": 8.4})
        self.assertIn("Ціни електрики задаються в тарифі", str(cm.exception))
        with self.assertRaises(ValidationError):  # перетин з демо-ціною 2025-01-01 → …
            self.Price.create({"resource_id": gas.id, "date_from": "2026-01-01", "date_to": "2026-12-31", "price": 20})
        with self.assertRaises(ValidationError):
            self.Price.create({"resource_id": gas.id, "date_from": "2024-03-01", "date_to": "2024-02-01", "price": 20})
        self.assertEqual(self.Price._td_price_at(gas, date(2026, 10, 17)), 19.80)
        self.assertEqual(self.Price._td_price_at("gas", datetime(2026, 10, 17, 9, 0)), 19.80)
        self.assertEqual(self.Price._td_price_at(gas, date(2024, 6, 1)), 0.0)  # поза періодами — 0, не помилка
        self.assertAlmostEqual(self.Price._td_price_at(self.resource("heat"), date(2026, 10, 17)), 2.0722, places=4)
        for code in ("el", "air"):
            self.assertEqual(self.Price._td_price_at(self.resource(code), date(2026, 10, 17)), 0.0)
        self.assertEqual(self.Price._td_price_at(self.resource("water")), 60.0)
        # нова ціна після закриття старої
        old = self.Price.search([("resource_id", "=", gas.id)])
        old.write({"date_to": "2026-09-30"})
        self.Price.create({"resource_id": gas.id, "date_from": "2026-10-01", "price": 22.5})
        self.assertEqual(self.Price._td_price_at(gas, date(2026, 10, 17)), 22.5)
        self.assertEqual(self.Price._td_price_at(gas, date(2026, 9, 1)), 19.80)

    def test_point_constraints(self):  # AC-04
        gas, air = self.resource("gas"), self.resource("air")
        p = self.point("T-P1", "gas")
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError), self.env.cr.savepoint():
            self.point("T-P1", "gas")
        other = self.point("T-P1", "air")  # той самий код в іншому ресурсі — можна
        with self.assertRaises(ValidationError):
            self.point("T-P2", "gas", parent_id=other.id)
        child = self.point("T-P3", "gas", parent_id=p.id)
        with self.assertRaises(ValidationError):
            p.write({"parent_id": child.id})
        node = self.env["td.energy.node"].search([("code", "=", "EDGE-1")], limit=1)
        for vals in (
            {"estimate_method": "load_share", "rate_nominal": 3.0},  # без вузла
            {"estimate_method": "load_share", "node_id": node.id},  # без паспортної швидкості
            {"estimate_method": "schedule", "estimate_params": {"to_h": 16, "rate": 1}},
            {"estimate_method": "residual", "estimate_params": {}},
            {"estimate_method": "residual", "estimate_params": {"from": ["T-P4"]}},  # сама на себе
            {"estimate_method": "gate_loss", "estimate_params": {"loss_kw_per_k": 3.5}},
        ):
            with self.assertRaises(ValidationError, msg=str(vals)):
                self.point("T-P4", "gas", **vals)
        ok = self.point("T-P5", "air", estimate_method="load_share", node_id=node.id, rate_nominal=3.0)
        self.assertEqual(ok.estimate_method, "load_share")
        self.assertEqual(self.Point._td_bind_extra(), {})
        self.assertTrue(gas and air)

    def test_meter_default_el_migration(self):  # AC-05
        Meter = self.env["td.energy.meter"]
        electric = Meter.search([("resource_id.code", "=", "el")])
        self.assertTrue(len(electric) >= 67)
        self.assertFalse(Meter.search([("resource_id", "=", False)]))
        self.assertEqual(set(electric.mapped("mode")), {"counter"})
        non_el = Meter.search([("resource_id.code", "!=", "el")])
        self.assertEqual(len(non_el), 16)
        self.assertEqual(set(non_el.mapped("role")), {"resource"})
        self.assertEqual(self.Point.search_count([]), 16)
        self.assertEqual(self.Price.search_count([]), 2)
        self.assertFalse(non_el.mapped("node_id"))
        before = self.env["td.energy.interval"].search_count([])
        self.env.cr.execute("UPDATE td_energy_meter SET resource_id = NULL WHERE code = 'PM-Q1'")
        Meter.invalidate_model()
        self.assertEqual(hooks._set_el_on_meters(self.env), 1)
        self.assertEqual(Meter.search([("code", "=", "PM-Q1")]).resource_id.code, "el")
        self.assertEqual(hooks._set_el_on_meters(self.env), 0)  # повтор — без змін
        self.assertEqual(self.env["td.energy.interval"].search_count([]), before)
        stats = hooks._seed_points_meters(self.env)  # повторне завантаження демо — без дублів
        self.assertEqual((stats["points"], stats["meters"]), (0, 0))
        react = Meter.search([("e_react_signal_id", "!=", False)])
        self.assertEqual(set(react.mapped("code")), {"PM-Q1", "PM-Q2"})

    def test_meter_binding(self):  # AC-06
        Meter = self.env["td.energy.meter"]
        gas_point = self.point("T-G", "gas")
        node = self.env["td.energy.node"].search([("code", "=", "COMPRESSOR")], limit=1)
        sig_counter = self.signal("energy/t3/gas_total", "counter", "м³")
        sig_flow = self.signal("energy/t3/gas_flow")
        el_sig = self.Signal.search([("code", "=", "energy/cells/Q1/kwh_total")], limit=1)
        el = self.resource("el")
        cases = [
            ("електричний без вузла", {"code": "T-M1", "name": "x", "resource_id": el.id, "role": "consumer"}),
            ("не-el без точки", {"code": "T-M2", "name": "x", "resource_id": self.resource("gas").id, "mode": "counter",
                                 "qty_signal_id": sig_counter.id}),
            ("не-el з електричним сигналом", {"code": "T-M3", "name": "x", "resource_id": gas_point.resource_id.id,
                                              "point_id": gas_point.id, "qty_signal_id": sig_counter.id,
                                              "e_import_signal_id": el_sig.id}),
            ("counter без сигналу", {"code": "T-M4", "name": "x", "resource_id": gas_point.resource_id.id,
                                     "point_id": gas_point.id, "mode": "counter"}),
            ("flow без сигналів", {"code": "T-M5", "name": "x", "resource_id": gas_point.resource_id.id,
                                   "point_id": gas_point.id, "mode": "flow_integrate"}),
            ("estimate без методу", {"code": "T-M6", "name": "x", "resource_id": gas_point.resource_id.id,
                                     "point_id": gas_point.id, "mode": "estimate"}),
            ("react на фідері", {"code": "T-M7", "name": "x", "resource_id": el.id, "node_id": node.id,
                                 "role": "feeder", "e_react_signal_id": sig_counter.id}),
        ]  # fmt: skip
        for label, vals in cases:
            with self.assertRaises(ValidationError, msg=label):
                Meter.create(vals)
        ok = self.meter("T-M8", gas_point, qty=sig_counter)
        self.assertEqual(
            (ok.role, ok.model, ok.node_id.id, ok.company_id), ("resource", "other", False, self.env.company)
        )
        flow = self.meter("T-M9", self.point("T-G2", "gas"), "flow_integrate", flow=[sig_flow])
        self.assertEqual(flow.flow_signal_ids, sig_flow)
        # автоматична роль/модель для не-el, якщо їх не задано
        auto = Meter.create({"code": "T-M10", "name": "x", "resource_id": gas_point.resource_id.id,
                             "point_id": self.point("T-G3", "gas").id, "qty_signal_id": sig_counter.id})  # fmt: skip
        self.assertEqual((auto.role, auto.model), ("resource", "other"))

    def test_electric_cron_untouched(
        self,
    ):  # AC-05, AC-06: електричні розрахунки W1 не бачать неелектричних лічильників
        from odoo.addons.td_energy.tools import backfill

        sig = self.signal("energy/t3/gas_total2", "counter", "м³")
        meter = self.meter("T-M20", self.point("T-G20", "gas"), qty=sig)
        self.assertNotIn(meter, backfill.Plan(self.env).meters)
        self.assertFalse(meter.e_import_signal_id)
        before = self.Event.search_count([("kind", "=", "meter")])
        self.env["td.energy.meter"].search([("active", "=", True)])._f3d_update_state()  # як cron_td_energy_live
        self.assertEqual(self.Event.search_count([("kind", "=", "meter"), ("code", "=", "T-M20")]), 0)
        self.assertEqual(meter.data_state, "no_data")
        self.assertGreaterEqual(self.Event.search_count([("kind", "=", "meter")]), before)
        self.fresh("energy/t3/gas_total2", 100.0)
        meter._f3d_update_state()
        self.assertEqual(meter.data_state, "ok")
        self.stale("energy/t3/gas_total2", minutes=33)
        meter._f3d_update_state()
        self.assertEqual(meter.data_state, "stale")
        self.assertEqual(self.Event.search_count([("kind", "=", "meter"), ("code", "=", "T-M20")]), 0)  # A-14
        self.assertEqual(self.env["td.energy.interval"].search_count([("meter_id", "=", meter.id)]), 0)
        self.env["td.energy.interval"]._cron_build()
        self.assertEqual(self.env["td.energy.interval"].search_count([("meter_id", "=", meter.id)]), 0)

    def test_signals_ensure(self):  # AC-54
        Signal = self.Signal.with_context(active_test=False)
        sigs = Signal.search([("code", "in", list(NEW_SIGNALS))])
        self.assertEqual(set(sigs.mapped("code")), set(NEW_SIGNALS))
        self.assertEqual(set(sigs.mapped("module")), {"energy"})
        by = {s.code: s for s in sigs}
        self.assertEqual(by["air/flow_m3min"].address["scale"], 0.01)
        self.assertEqual(by["air/m3_total"].address["addr"], 2)
        self.assertEqual(by["infra/gas/m3_total"].address["type"], "u32")
        self.assertEqual(by["air/pressure_bar"].warn_low, 5.8)
        self.assertTrue(by["air/pressure_bar"].warn_low_on)
        self.assertEqual(by["air/pressure_bar"].min_duration_s, 300)
        self.assertFalse(by["air/pressure_bar"].create_request)
        self.assertEqual(by["infra/gas/flow_m3h"].derived_from_id, by["infra/gas/m3_total"])
        self.assertEqual(by["infra/gas/flow_m3h"].derive_rule, "rate_h")
        self.assertEqual(by["infra/water/boiler_flow_m3h"].derived_from_id, by["infra/water/boiler_m3_total"])
        self.assertFalse(Signal.search_count([("code", "=", "air/setpoint_bar")]))  # власник сигналу — W2
        self.assertFalse(Signal.search_count([("code", "=", "energy_control/air/setpoint_bar")]))
        sources = (
            self.env["td.source"]
            .with_context(active_test=False)
            .search([("code", "in", ["MB-U74-GAS-MAIN", "MB-U75-AIR-MAIN"])])
        )
        self.assertEqual(len(sources), 2)
        self.assertEqual({s.params["unit"] for s in sources}, {74, 75})
        self.assertFalse(any(s.write_enabled for s in sources))
        # повтор — без змін
        by["air/flow_m3min"].decimals = 5
        total = Signal.search_count([])
        self.assertEqual(hooks._ensure_resource_signals(self.env), {"sources": 0, "signals": 0})
        self.assertEqual(Signal.search_count([]), total)
        self.assertEqual(by["air/flow_m3min"].decimals, 5)

    def test_tariff_react(self):  # AC-52
        Tariff = self.env["td.energy.tariff"]
        tariff = Tariff.search([], limit=1)
        for vals in ({"tg_phi_limit": -0.1}, {"react_rate": -1}, {"react_rate": 0.24, "tg_phi_limit": 0}):
            with self.assertRaises(ValidationError, msg=str(vals)):
                tariff.write(vals)
        tariff.write({"tg_phi_limit": 0.30, "react_rate": 0.24})
        self.assertEqual(tariff._td_react_penalty(100), 24.0)
        self.assertAlmostEqual(tariff._td_react_penalty(628.8), 150.91, places=2)
        self.assertEqual(tariff._td_react_penalty(-5), 0.0)
        tariff.write({"react_rate": 0, "tg_phi_limit": 0})
        self.assertEqual(tariff._td_react_penalty(100), 0.0)
        user = self.u_view  # група «Перегляд» без «Вартість» не бачить поля
        with self.assertRaises(AccessError):
            tariff.with_user(user).tg_phi_limit  # noqa: B018

    def test_security(self):  # AC-49
        gas = self.resource("gas")
        for model, vals in (
            ("td.energy.resource", {"name": "Х"}),
            ("td.energy.price", {"note": "x"}),
            ("td.energy.point", {"name": "x"}),
        ):
            rec = self.env[model].search([], limit=1)
            with self.assertRaises(AccessError, msg=model):
                rec.with_user(self.u_view).write(vals)
        self.assertTrue(self.Resource.with_user(self.u_view).search([]))  # читання — так
        self.resource("gas").with_user(self.u_eng).write({"rate_limit": 90})  # менеджер правило ресурсу
        self.Price.search([("resource_id", "=", gas.id)]).with_user(self.u_eng).write({"date_to": "2029-12-31"})
        self.Price.with_user(self.u_eng).create({"resource_id": gas.id, "date_from": "2030-01-01", "price": 30})
        with self.assertRaises(AccessError):
            self.Resource.with_user(self.u_eng).create({"code": "zz", "name": "Z", "uom_label": "a", "rate_label": "b"})
        self.Point.with_user(self.u_eng).create({"resource_id": gas.id, "code": "T-SEC", "name": "x"})
        row = self.res_interval(
            self.env["td.energy.meter"].search([("resource_id.code", "!=", "el")], limit=1), self.now, 1
        )
        with self.assertRaises(AccessError):
            row.with_user(self.u_eng).write({"qty": 2})
        row.with_user(self.u_admin).write({"qty": 2})
        self.assertEqual(self.ResInterval.with_user(self.u_view).search_count([("id", "=", row.id)]), 1)
        with self.assertRaises(AccessError):
            self.env["td.energy.usage"].with_user(self.u_plain).search([])

    def test_neutralize_and_uninstall(self):  # AC-50
        with file_open("td_energy_resources/data/neutralize.sql") as f:
            self.env.cr.execute(f.read())
        self.env["ir.cron"].invalidate_model()
        crons = self.env["ir.model.data"].search([("module", "=", "td_energy_resources"), ("model", "=", "ir.cron")])
        self.assertTrue(len(crons) >= 2)
        self.assertFalse(any(self.env["ir.cron"].browse(crons.mapped("res_id")).mapped("active")))
        sources = (
            self.env["td.source"]
            .with_context(active_test=False)
            .search([("code", "in", ["MB-U74-GAS-MAIN", "MB-U75-AIR-MAIN"])])
        )
        self.assertFalse(any(sources.mapped("read_enabled")))
        # uninstall_hook: електричне ціле, неелектричні видалені, node_id знову NOT NULL
        Meter = self.env["td.energy.meter"]
        n_el = Meter.search_count([("resource_id.code", "=", "el")])
        n_iv = self.env["td.energy.interval"].search_count([])
        n_sig = self.Signal.with_context(active_test=False).search_count([])
        hooks.uninstall_hook(self.env)
        Meter.invalidate_model()
        self.assertEqual(Meter.search_count([("resource_id.code", "!=", "el")]), 0)
        self.assertEqual(Meter.search_count([("resource_id.code", "=", "el")]), n_el)
        self.assertFalse(Meter.search([("e_react_signal_id", "!=", False)]))
        self.assertEqual(self.env["td.energy.interval"].search_count([]), n_iv)
        self.assertEqual(self.Signal.with_context(active_test=False).search_count([]), n_sig)
        self.env.cr.execute(
            "SELECT is_nullable FROM information_schema.columns"
            " WHERE table_name = 'td_energy_meter' AND column_name = 'node_id'"
        )
        self.assertEqual(self.env.cr.fetchone()[0], "NO")
        self.assertFalse(self.env["ir.config_parameter"].sudo().search([("key", "=like", "td.energy\\_resources.%")]))

    def test_shifts(self):  # AC-53
        Param = self.env["ir.config_parameter"].sudo()
        Param.set_param("td.energy.shift_calendar_id", "0")
        win = shifts.load_windows(self.env)  # календар не заданий — умолчання макета
        tue = datetime(2026, 10, 13)
        self.assertEqual(win.shift_of(tue.replace(hour=15, minute=59)), "Зміна 1")
        self.assertEqual(win.shift_of(tue.replace(hour=16)), "Зміна 2")
        self.assertIsNone(win.shift_of(tue.replace(hour=23)))
        self.assertIsNone(win.shift_of(datetime(2026, 10, 17, 10, 0)))  # субота
        self.assertTrue(win.is_shift(tue.replace(hour=8)))
        self.assertEqual(win.windows_for(date(2026, 10, 17)), [])
        names = [w[0] for w in win.windows_for(date(2026, 10, 13))]
        self.assertEqual(names, ["Зміна 1", "Зміна 2"])
        # два блоки «Зміна 1» + «Зміна 2» в календарі
        calendar = self.env["resource.calendar"].create(
            {
                "name": "T3 зміни",
                "attendance_ids": [
                    (
                        0,
                        0,
                        {
                            "name": "Зміна 1",
                            "dayofweek": str(d),
                            "hour_from": 7,
                            "hour_to": 12,
                            "day_period": "morning",
                        },
                    )
                    for d in range(5)
                ]
                + [
                    (
                        0,
                        0,
                        {
                            "name": "Зміна 1",
                            "dayofweek": str(d),
                            "hour_from": 13,
                            "hour_to": 16,
                            "day_period": "afternoon",
                        },
                    )
                    for d in range(5)
                ]
                + [
                    (
                        0,
                        0,
                        {
                            "name": "Зміна 2",
                            "dayofweek": str(d),
                            "hour_from": 16,
                            "hour_to": 23,
                            "day_period": "afternoon",
                        },
                    )
                    for d in range(5)
                ],
            }
        )
        Param.set_param("td.energy.shift_calendar_id", str(calendar.id))
        win = shifts.load_windows(self.env)
        self.assertEqual(win.shift_of(tue.replace(hour=15, minute=59)), "Зміна 1")
        self.assertEqual(win.shift_of(tue.replace(hour=16)), "Зміна 2")
        self.assertEqual(win.shift_of(tue.replace(hour=23)), None)
        # стандартні імена рядків — одна зміна «Зміна» 08:00–17:00 (демо-календар)
        Param.set_param("td.energy.shift_calendar_id", "1")
        std = shifts.load_windows(self.env)
        self.assertEqual(std.shift_of(tue.replace(hour=12, minute=30)), "Зміна")  # обід усередині вікна
        self.assertIsNone(std.shift_of(tue.replace(hour=17)))
        # ніч, що закінчується вранці дня; DST: перехід 25.10.2026 (доба 25 год)
        night = win.night_window(date(2026, 10, 17))
        self.assertEqual(night, (datetime(2026, 10, 16, 20, 0), datetime(2026, 10, 17, 3, 30)))
        dst = win.windows_for(date(2026, 10, 26))  # понеділок після переходу: Київ UTC+2
        self.assertEqual(dst[0][1], datetime(2026, 10, 26, 5, 0))
        summer = win.windows_for(date(2026, 10, 19))
        self.assertEqual(summer[0][1], datetime(2026, 10, 19, 4, 0))
