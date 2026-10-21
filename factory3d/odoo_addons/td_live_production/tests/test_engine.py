"""Інтеграційні тести двигуна: генерація доби, диспетчер у «віртуальному» часі, догнати минуле, підготовка компанії."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from psycopg2 import errors as pg_errors

from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from ..tools import clock, pricing

DAY = date(2026, 11, 2)  # понеділок, після переведення годинника: Київ UTC+2
SHIFT = (7.0, 15.5)
T0 = clock.shift_window(DAY, SHIFT)[0]  # 07:00 Київ = 05:00 UTC
P = "td.live_production."


def mins(n):
    return timedelta(minutes=n)


@tagged("post_install", "-at_install", "td_live")
class TestLive(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        cls.engine = env["td.live.engine"]
        icp = env["ir.config_parameter"].sudo()
        for key, value in {
            "orders_per_day": "2",
            "downtime_pct": "20",
            "hot_section": "Присадка",
            "hot_factor": "2.5",
            "workdays": "0123456",
            "enabled": "True",
        }.items():
            icp.set_param(P + key, value)
        tag = env["mrp.workcenter.tag"].create({"name": "Присадка"})
        attendance = [  # як у демо: 07:00–11:30 і 12:00–15:30 (обід — поза плановим часом)
            (0, 0, {"name": name, "dayofweek": str(d), "hour_from": a, "hour_to": b, "day_period": period})
            for d in range(7)
            for name, a, b, period in (("Ранок", 7.0, 11.5, "morning"), ("День", 12.0, 15.5, "afternoon"))
        ]
        cls.cal = env["resource.calendar"].create(
            {"name": "Зміна 1 (тест)", "tz": "Europe/Kyiv", "attendance_ids": [(5, 0, 0)] + attendance}
        )
        WC = env["mrp.workcenter"]

        def wc(name, code, tags=()):
            return WC.create(
                {
                    "name": name,
                    "td_code": code,
                    "time_efficiency": 100,
                    "costs_hour": 600.0,
                    "resource_calendar_id": cls.cal.id,
                    "tag_ids": [(6, 0, [t.id for t in tags])],
                }
            )

        cls.wcs = {
            "SAW-T": wc("Розкрій (тест)", "SAW-T"),
            "EDGE-T": wc("Крайка (тест)", "EDGE-T"),
            "CNC-T1": wc("Присадка 1 (тест)", "CNC-T1", tag),
            "CNC-T2": wc("Присадка 2 (тест)", "CNC-T2", tag),
            "ASM-T": wc("Збирання (тест)", "ASM-T"),
            "PACK-T": wc("Пакування (тест)", "PACK-T"),
        }
        for rec in cls.wcs.values():
            env["td.machine"].create({"workcenter_id": rec.id, "protocol": "manual"})
        Product = env["product.product"]
        cls.board = Product.create(
            {
                "name": "ДСП тест",
                "default_code": "DSP16-T",
                "is_storable": True,
                "tracking": "lot",
                "standard_price": 0.0,
            }
        )
        cls.hinge = Product.create(
            {"name": "Завіса тест", "default_code": "FUR-HG-T", "is_storable": True, "standard_price": 140.0}
        )
        cls.fg = Product.create(
            {"name": "Тумба тест", "default_code": "OF-T", "is_storable": True, "list_price": 5600.0}
        )
        cls.boms = {}
        for key, cnc in (("A", "CNC-T1"), ("B", "CNC-T2")):
            ops = [
                ("Розкрій", "SAW-T"),
                ("Крайка", "EDGE-T"),
                ("Присадка", cnc),
                ("Збирання", "ASM-T"),
                ("Пакування", "PACK-T"),
            ]
            cls.boms[key] = env["mrp.bom"].create(
                {
                    "product_tmpl_id": cls.fg.product_tmpl_id.id,
                    "product_qty": 1,
                    "code": "лінія %s" % key,
                    "bom_line_ids": [
                        (0, 0, {"product_id": cls.board.id, "product_qty": 0.3}),
                        (0, 0, {"product_id": cls.hinge.id, "product_qty": 2}),
                    ],
                    "operation_ids": [
                        (
                            0,
                            0,
                            {
                                "name": n,
                                "workcenter_id": cls.wcs[c].id,
                                "time_mode": "manual",
                                "time_cycle_manual": 1.0,
                            },
                        )
                        for n, c in ops
                    ],
                }
            )
        partner = env["res.partner"].create({"name": "Клієнт шаблонний (тест)"})
        template = env["sale.order"].create(
            {"partner_id": partner.id, "order_line": [(0, 0, {"product_id": cls.fg.id, "product_uom_qty": 1})]}
        )
        template.action_confirm()
        cls.template_so = template
        cls.partner = partner

    # --- допоміжні -----------------------------------------------------------------------------------
    def at(self, minutes):
        return self.engine.with_context(td_live_now=T0 + mins(minutes))

    def run_jobs(self, now=None, limit=300):
        """Запуски крона-виконавця з нульовим бюджетом: одна порція за запуск. Повертає кількість запусків."""
        self.env["ir.config_parameter"].sudo().set_param(P + "job_budget_s", "0")
        eng = self.engine.with_context(td_live_now=now or T0 - mins(120))
        Job = self.env["td.live.job"]
        calls = 0
        with patch.object(type(Job), "_td_wake"):
            while Job.search_count([("state", "in", ("queued", "running"))]) and calls < limit:
                Job.with_context(**eng.env.context)._cron_td_live_jobs()
                calls += 1
        return calls

    def generate(self):
        return self.engine.with_context(td_live_now=T0 - mins(120)).td_generate_day(DAY)

    def fake_sim(self):
        fake = MagicMock()
        fake._td_push_machine_targets.return_value = {"ok": 1, "unknown": []}
        return fake

    # --- LP-02: генерація доби -----------------------------------------------------------------------
    def test_generate_day(self):
        day = self.generate()
        self.assertEqual(day.date, DAY)
        self.assertEqual(day.order_count, 2)
        self.assertTrue(4 <= day.production_count <= 6)
        for so in day.order_ids:
            self.assertEqual(so.state, "sale")
            self.assertTrue(so.picking_ids)
        shift_start, shift_end = clock.shift_window(DAY, SHIFT)
        for mo in day.production_ids:
            self.assertEqual(mo.state, "confirmed")
            self.assertIn(mo.origin, day.order_ids.mapped("name"))
            wos = mo.workorder_ids.sorted("id")
            self.assertEqual(len(wos), 5)
            for wo in wos:
                self.assertGreaterEqual(wo.date_start, shift_start)
            for prev, nxt in zip(wos, wos[1:], strict=False):
                self.assertLessEqual(prev.date_finished, nxt.date_start)  # наряди МО послідовно
        self.assertEqual(day.hot_section, "Присадка")
        self.assertTrue(day.hot_load_pct > 0)

    def test_generate_is_idempotent(self):
        first = self.generate()
        n_so = self.env["sale.order"].search_count([("td_live_day_id", "=", first.id)])
        again = self.engine.td_generate_day(DAY)
        self.assertEqual(first, again)
        self.assertEqual(self.env["sale.order"].search_count([("td_live_day_id", "=", first.id)]), n_so)

    def test_hot_section_slowdown_and_finite_capacity(self):
        day = self.generate()
        hot = day.production_ids.workorder_ids.filtered(lambda w: w.workcenter_id.td_code.startswith("CNC"))
        for wo in hot:
            self.assertAlmostEqual(wo.duration_expected, wo.production_id.product_qty * 1.0 * 2.5, places=1)
        by_wc = {}
        for wo in day.production_ids.workorder_ids:
            by_wc.setdefault(wo.workcenter_id.id, []).append((wo.date_start, wo.date_finished))
        for spans in by_wc.values():
            spans.sort()
            for (_s1, e1), (s2, _e2) in zip(spans, spans[1:], strict=False):
                self.assertLessEqual(e1, s2)

    def test_margin_plan_in_band(self):
        day = self.generate()
        self.assertTrue(25.0 <= day.margin_plan_pct <= 40.0, day.margin_plan_pct)
        self.assertEqual(self.board.standard_price, 0.0)  # без LP-07 собівартість дошки нульова: маржа з решти
        for so in day.order_ids:
            for line in so.order_line:
                qty = line.product_uom_qty
                hot = {self.wcs["CNC-T1"].id, self.wcs["CNC-T2"].id}
                unit_cost = self.engine._td_line_cost(self.boms["A"], qty, hot, 2.5) / qty
                self.assertTrue(25.0 <= pricing.margin_pct(line.price_unit, unit_cost) <= 40.0)

    def test_hot_section_default_and_off(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(P + "hot_section", False)  # параметр не заданий: за замовчуванням «Присадка»
        self.assertEqual(self.generate().hot_section, "Присадка")
        icp.set_param(P + "hot_section", "-")
        self.assertEqual(self.engine._td_params()["hot_section"], "")
        icp.set_param(P + "hot_section", "Розкрій")
        self.assertEqual(self.engine._td_params()["hot_section"], "Розкрій")

    def test_throttle_when_backlog_grows(self):
        self.generate()
        next_release = clock.shift_window(DAY + timedelta(days=1), SHIFT)[0]
        self.assertEqual(self.engine._td_throttle(8, next_release)[0], 8)  # черга менша за 1,5 доби
        long_ago = clock.shift_window(DAY - timedelta(days=6), SHIFT)[0]
        orders, backlog = self.engine._td_throttle(8, long_ago)
        self.assertTrue(1 <= orders < 8, orders)
        self.assertGreater(backlog, 5)
        self.assertEqual(self.engine._td_throttle(1, long_ago)[0], 1)

    def test_no_templates_message(self):
        self.template_so.action_cancel()
        with self.assertRaisesRegex(UserError, "Немає шаблонів"):
            self.engine.td_generate_day(DAY + timedelta(days=30))

    # --- LP-03: диспетчер ----------------------------------------------------------------------------
    def test_dispatcher_30_minutes(self):
        """Генерація → тики щохвилини 30 хв «віртуального» часу → наряди стартують і закриваються, МО закрито,
        простій має причину, цілі емулятору (C-LP-01) — правильні."""
        day = self.generate()
        fake = self.fake_sim()
        codes = {wc.td_code for wc in self.wcs.values()}
        with patch.object(type(self.engine), "_td_sim_device", return_value=fake):
            for k in range(0, 31):
                self.at(k).td_dispatch()
        wos = day.production_ids.workorder_ids
        self.assertTrue(wos.filtered(lambda w: w.state == "done"))
        self.assertTrue(day.production_ids.filtered(lambda m: m.state == "done"), "жодну МО не закрито за 30 хв")
        for wo in wos.filtered(lambda w: w.state in ("progress", "done")):
            timers = wo.time_ids
            self.assertEqual(len(timers), 1, "подвійний запис часу %s" % wo.display_name)
            self.assertGreaterEqual(timers.date_start, T0)  # час із плану, а не реальне «зараз»
            self.assertLessEqual(timers.date_start, T0 + mins(31))
            if wo.state == "done":
                self.assertTrue(timers.date_end)
                self.assertLessEqual(timers.date_end, T0 + mins(31))
                self.assertEqual(wo.date_finished, timers.date_end)
        # простій з причиною: td.downtime (демо) з причиною, не «Не вказано»
        unknown = self.env.ref("td_machine_connect.loss_unknown")
        downtimes = self.env["td.downtime"].search([("reason_source", "=", "demo")])
        live = day.downtime_ids
        self.assertTrue(live)
        self.assertTrue(live.filtered(lambda d: d.state in ("active", "done")), "простій не відкрито за 30 хв")
        self.assertTrue(downtimes)
        for dt in downtimes:
            self.assertNotEqual(dt.loss_id, unknown)
            self.assertEqual(dt.reason_state, "confirmed")
        # C-LP-01: цілі — коди наших верстатів, стан working/idle/down, until — ISO UTC у майбутньому
        calls = fake._td_push_machine_targets.call_args_list
        self.assertTrue(calls)
        seen = set()
        for k, call in enumerate(calls):
            targets = call.args[0]
            for tg in targets:
                self.assertIn(tg["code"], codes)
                self.assertIn(tg["state"], ("working", "idle", "down"))
                self.assertRegex(tg["until"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
                until = tg["until"].replace("T", " ").rstrip("Z")
                self.assertGreater(until, str(T0 + mins(k))[:19])  # ціль живе довше за момент тику
                seen.add(tg["state"])
                if tg["state"] == "idle":
                    self.assertTrue(tg["reason"])
                if tg["state"] == "working":
                    self.assertIsNone(tg["reason"])
        self.assertIn("working", seen)
        self.assertIn("idle", seen)

    def test_dispatcher_full_day_closes_everything(self):
        day = self.generate()
        res = self.at(600).td_dispatch()
        self.assertEqual(res["closed"], day.production_count)
        self.assertTrue(all(mo.state == "done" for mo in day.production_ids))
        self.assertTrue(all(wo.state == "done" for wo in day.production_ids.workorder_ids))
        for mo in day.production_ids:
            self.assertEqual(mo.qty_produced, mo.product_qty)
            self.assertTrue(all(m.state == "done" for m in mo.move_raw_ids))
            self.assertTrue(T0 <= mo.date_finished <= T0 + mins(600))
        for so in day.order_ids:
            self.assertTrue(so.picking_ids)
            self.assertTrue(all(p.state == "done" for p in so.picking_ids), so.name)
        self.assertTrue(all(d.state == "done" for d in day.downtime_ids if d.state != "skipped"))
        for dt in self.env["td.downtime"].search([("reason_source", "=", "demo")]):
            self.assertTrue(dt.date_end)
        self.assertEqual(day.state, "done")
        # повторний тик — нічого нового (ідемпотентність)
        again = self.at(600).td_dispatch()
        self.assertEqual((again["started"], again["finished"], again["closed"], again["shipped"]), (0, 0, 0, 0))

    def test_start_unblocks_work_center_with_stale_loss(self):
        """Верстат заблоковано старим відкритим записом втрат (як у демо) — диспетчер його закриває й стартує наряд."""
        saw = self.wcs["SAW-T"]
        stale = self.env["mrp.workcenter.productivity"].create(
            {
                "workcenter_id": saw.id,
                "loss_id": self.env.ref("mrp.block_reason0").id,
                "date_start": T0 - timedelta(days=9),
            }
        )
        self.assertEqual(saw.working_state, "blocked")
        self.generate()
        self.at(1).td_dispatch()
        self.assertTrue(stale.date_end)
        self.assertLessEqual(stale.date_end, T0 + mins(1))
        self.assertTrue(self.env["mrp.workorder"].search([("workcenter_id", "=", saw.id), ("state", "=", "progress")]))

    def test_tick_event_limit_catches_up_in_parts(self):
        day = self.generate()
        first = self.at(600).td_dispatch(limit=3)
        self.assertLessEqual(first["started"] + first["finished"] + first["closed"] + first["shipped"], 3)
        self.assertEqual(first["pushed"], {})  # частковий такт цілі не надсилає
        for _i in range(200):
            self.at(600).td_dispatch(limit=20)
            if day.state == "done" and all(p.state == "done" for o in day.order_ids for p in o.picking_ids):
                break
        self.assertEqual(day.state, "done")
        self.assertTrue(all(p.state == "done" for o in day.order_ids for p in o.picking_ids))

    def test_tick_catch_up_equals_minute_ticks(self):
        """Один тик після паузи дає ті самі часи, що й тики щохвилини."""
        day = self.generate()
        self.at(90).td_dispatch()
        one = {wo.id: (wo.state, wo.date_start, wo.date_finished) for wo in day.production_ids.workorder_ids}
        self.assertTrue(any(v[0] == "done" for v in one.values()))
        self.at(90).td_dispatch()
        two = {wo.id: (wo.state, wo.date_start, wo.date_finished) for wo in day.production_ids.workorder_ids}
        self.assertEqual(one, two)

    def test_compatible_with_machine_autostart(self):
        """Наряд уже запустив автостарт верстата — диспетчер не створює другий таймер і не стартує вдруге."""
        day = self.generate()
        wo = day.production_ids.workorder_ids.sorted(lambda w: (w.date_start, w.id))[0]
        machine = wo.workcenter_id.td_machine_ids[:1]
        machine._td_start_at(wo, self.env["hr.employee"], T0 + mins(1))
        machine._td_set_active(wo)
        wo.time_ids.write({"date_start": T0 + mins(1)})  # у бою таймер стартує «зараз»; у тесті «зараз» віртуальне
        self.assertEqual(wo.state, "progress")
        before = wo.time_ids
        self.at(1).td_dispatch()
        self.assertEqual(wo.time_ids, before)
        self.assertEqual(len(wo.time_ids), 1)
        # автостоп (завершення верстатом) — диспетчер не завершує вдруге
        wo.time_ids.write({"date_end": T0 + mins(5)})
        tech_wo = wo.with_env(machine._td_tech_env())
        tech_wo.write({"qty_produced": wo.qty_production})
        tech_wo.button_finish()
        self.assertEqual(wo.state, "done")
        stop = wo.date_finished
        self.at(20).td_dispatch()
        self.assertEqual(wo.state, "done")
        self.assertEqual(wo.date_finished, stop)
        self.assertEqual(len(wo.time_ids), 1)

    def test_no_emulator_fallback(self):
        """Без td_iot_sim (чи без методу C-LP-01) такт працює, цілі не надсилаються."""
        self.generate()
        with patch.object(type(self.engine), "_td_sim_device", return_value=None):
            res = self.at(5).td_dispatch()
        self.assertEqual(res["pushed"]["ok"], 0)
        self.assertTrue(res["targets"])

    def test_emulator_failure_does_not_break_tick(self):
        self.generate()
        fake = MagicMock()
        fake._td_push_machine_targets.side_effect = RuntimeError("немає зв'язку")
        with patch.object(type(self.engine), "_td_sim_device", return_value=fake):
            res = self.at(5).td_dispatch()
        self.assertEqual(res["pushed"]["ok"], 0)
        self.assertTrue(res["started"])

    def test_disabled_cron_does_nothing(self):
        day = self.generate()
        self.env["ir.config_parameter"].sudo().set_param(P + "enabled", "False")
        self.assertEqual(self.at(60).td_dispatch()["started"], 0)
        self.at(60)._cron_td_live_tick()
        self.assertFalse(
            day.production_ids.workorder_ids.filtered(lambda w: w.state != "blocked" and w.state != "ready")
        )

    def test_generate_today_first_run_closes_elapsed(self):
        """Перший запуск посеред зміни: операції, що за планом мали закінчитись, закриваються одразу."""
        res = self.at(180).td_generate_today()
        self.assertIn("Диспетчер", res)
        day = self.env["td.live.day"].search([("date", "=", DAY)])
        self.assertTrue(day)
        self.assertTrue(day.production_ids.workorder_ids.filtered(lambda w: w.state == "done"))
        for wo in day.production_ids.workorder_ids.filtered(lambda w: w.state == "done"):
            self.assertLessEqual(wo.date_finished, T0 + mins(180))

    # --- LP-06: запуск / зупинка -----------------------------------------------------------------------
    def test_start_stop_switches_clock_and_crons(self):
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("td.viewer.demo_clock", "2026-10-12 10:30")
        icp.set_param(P + "enabled", "False")
        self.generate()  # план на сьогодні (DAY) готовий: запуск одразу
        msg = self.at(0).td_start()
        self.assertIn("запущено", msg)
        self.assertEqual(icp.get_param(P + "enabled"), "True")
        self.assertFalse(icp.get_param("td.viewer.demo_clock"))
        for xmlid in ("td_live_production.cron_td_live_tick", "td_live_production.cron_td_live_nightly"):
            self.assertTrue(self.env.ref(xmlid).active)
        night = self.env.ref("td_live_production.cron_td_live_nightly")
        local = clock.to_local(night.nextcall)
        self.assertEqual((local.hour, local.minute), (2, 0))  # 02:00 Europe/Kyiv
        self.engine.td_stop()
        self.assertEqual(icp.get_param(P + "enabled"), "False")
        self.assertEqual(icp.get_param("td.viewer.demo_clock"), "2026-10-12 10:30")
        self.assertFalse(self.env.ref("td_live_production.cron_td_live_tick").active)

    def test_settings_buttons_and_save(self):
        """Кнопки налаштувань повертають повідомлення, а збереження форми не скидає вимикач і зберігає параметри."""
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param(P + "enabled", "False")
        self.generate()
        Settings = self.env["res.config.settings"].with_context(td_live_now=T0)
        action = Settings.create({}).action_td_live_start()
        self.assertEqual(action["tag"], "display_notification")
        self.assertTrue(Settings.create({}).td_live_enabled)
        stale = Settings.create({"td_live_orders": 5, "td_live_hot_factor": 3.0})
        stale.execute()  # форма відкрита до запуску: застаріле значення вимикача не має його скинути
        self.assertEqual(icp.get_param(P + "enabled"), "True")
        self.assertEqual(icp.get_param(P + "orders_per_day"), "5")
        self.assertEqual(self.engine._td_params()["hot_factor"], 3.0)
        self.assertEqual(Settings.create({}).action_td_live_stop()["tag"], "display_notification")
        self.assertEqual(icp.get_param(P + "enabled"), "False")

    def test_stop_deactivates_crons(self):
        self.engine.td_stop()
        self.assertFalse(self.env.ref("td_live_production.cron_td_live_tick").active)
        self.assertFalse(self.env.ref("td_live_production.cron_td_live_nightly").active)

    def test_nightly_queues_generation_of_today_and_tomorrow(self):
        with patch.object(type(self.engine), "_td_now", return_value=T0 - mins(300)):
            with patch.object(type(self.env["td.live.job"]), "_td_wake"):
                self.engine._cron_td_live_nightly()
        jobs = self.env["td.live.job"].search([("kind", "=", "generate_day")])
        self.assertEqual(sorted(jobs.mapped("day_date")), [DAY, DAY + timedelta(days=1)])
        self.run_jobs()
        days = self.env["td.live.day"].search([("generated", "=", True)]).mapped("date")
        self.assertIn(DAY, days)
        self.assertIn(DAY + timedelta(days=1), days)

    # --- LP-04: догнати минуле ---------------------------------------------------------------------------
    def make_old_mo(self, start, qty=3):
        so = self.env["sale.order"].create(
            {"partner_id": self.partner.id, "order_line": [(0, 0, {"product_id": self.fg.id, "product_uom_qty": qty})]}
        )
        so.action_confirm()
        mo = self.env["mrp.production"].create(
            {
                "product_id": self.fg.id,
                "product_qty": qty,
                "bom_id": self.boms["A"].id,
                "origin": so.name,
            }
        )
        mo.action_confirm()
        t = start
        for wo in mo.workorder_ids.sorted("id"):
            wo.with_context(bypass_duration_calculation=True).write({"date_start": t, "date_finished": t + mins(30)})
            t += mins(30)
        return so, mo

    def test_catch_up_past_by_plan_dates_deletes_nothing(self):
        past = T0 - timedelta(days=9)
        so, mo = self.make_old_mo(past)
        first = mo.workorder_ids.sorted("id")[0]
        first.button_start()  # «в роботі» з минулого: таймер і дати як у демо (фактичний початок, плановий кінець)
        first.time_ids.write({"date_start": past})
        first.with_context(bypass_duration_calculation=True).write(
            {"date_start": past, "date_finished": past + mins(30)}
        )
        self.assertEqual(mo.state, "progress")
        _so2, fresh = self.make_old_mo(T0 + mins(60))  # план на сьогодні: чіпати не можна
        n_mo = self.env["mrp.production"].search_count([])
        n_so = self.env["sale.order"].search_count([])
        msg = self.at(60).td_catch_up()
        self.assertIn("Догнати минуле", msg)
        self.assertEqual(mo.state, "done")
        wos = mo.workorder_ids.sorted("id")
        self.assertTrue(all(w.state == "done" for w in wos))
        for k, wo in enumerate(wos):
            self.assertEqual(wo.date_finished, past + mins(30 * (k + 1)))
        self.assertEqual(mo.date_finished, past + mins(150))
        self.assertTrue(all(p.state == "done" for p in so.picking_ids))
        self.assertEqual(fresh.state, "confirmed")  # сьогоднішнє не чіпали
        self.assertEqual(self.env["mrp.production"].search_count([]), n_mo)  # нічого не видалено
        self.assertEqual(self.env["sale.order"].search_count([]), n_so)
        self.assertTrue(first.time_ids)  # журнал часу лишився
        again = self.at(60).td_catch_up()  # ідемпотентно
        self.assertIn("закрито МО 0", again)

    # --- сервер: послідовності, працівник Enterprise, контроль якості, причини невдач ---------------------
    def test_generation_with_names_ahead_of_sequences(self):
        """Імена документів попереду послідовностей (демо створювало їх явно): генерація не падає на унікальності."""
        env, company = self.env, self.env.company
        mo_type = env["stock.picking.type"].search(
            [("code", "=", "mrp_operation"), ("company_id", "=", company.id)], limit=1
        )
        out_type = env["stock.picking.type"].search(
            [("code", "=", "outgoing"), ("company_id", "=", company.id)], limit=1
        )
        mo_seq, out_seq = mo_type.sequence_id, out_type.sequence_id
        so_seq = env["ir.sequence"].search([("code", "=", "sale.order")], limit=1)
        prefix, _suffix = mo_seq._get_prefix_suffix()

        def name(n):
            return "%s%0*d" % (prefix, mo_seq.padding, n)

        for n in (1, 40):  # зайняті «демо» номери
            env["mrp.production"].create(
                {"product_id": self.fg.id, "product_qty": 1, "bom_id": self.boms["A"].id, "name": name(n)}
            )
        for seq in (mo_seq, out_seq, so_seq):
            seq.number_next_actual = 1
        fixed = self.engine.td_sequences_ahead()
        self.assertTrue(fixed)
        self.assertEqual(mo_seq.number_next_actual, 41)
        self.assertGreater(so_seq.number_next_actual, 1)  # S00001 — шаблонне замовлення
        self.assertGreater(out_seq.number_next_actual, 1)  # відвантаження шаблонного замовлення
        self.assertEqual(self.engine.td_sequences_ahead(), [])  # ідемпотентно
        for seq in (mo_seq, out_seq, so_seq):
            seq.number_next_actual = 1
        day = self.generate()  # сама підсуває послідовності
        names = day.production_ids.mapped("name")
        self.assertEqual(len(set(names)), len(names))
        self.assertFalse({name(1), name(40)} & set(names))
        self.assertIn("Послідовності", day.note)

    def test_employee_fallback_for_work_centers_without_operators(self):
        """Enterprise не стартує наряд без працівника: на РЦ без операторів береться запасний; у CE — не потрібен."""
        wo = self.generate().production_ids.workorder_ids[:1]
        machine = self.engine._td_machine_of(wo)
        employee = self.env["hr.employee"].create({"name": "Оператор запасний (тест)"})
        no_emp = patch.object(type(machine), "_td_pick_employee", return_value=self.env["hr.employee"])
        with no_emp:
            self.assertFalse(self.engine._td_employee(wo, machine))  # CE: `start_employee` немає
            with patch.object(type(wo), "start_employee", create=True):
                got = self.engine._td_employee(wo, machine)
        self.assertTrue(got)
        self.assertTrue(got == self.env.user.employee_id or got == employee or got.exists())
        assigned = self.env["hr.employee"].create({"name": "Оператор РЦ (тест)"})
        with patch.object(type(machine), "_td_pick_employee", return_value=assigned):
            with patch.object(type(wo), "start_employee", create=True):
                self.assertEqual(self.engine._td_employee(wo, machine), assigned)  # призначений має перевагу

    def test_quality_checks_passed_by_standard_do_pass(self):
        mo = self.generate().production_ids[:1]
        check = MagicMock(title="Контроль збирання")
        with patch.object(type(self.engine), "_td_quality_checks", return_value=[check]) as found:
            self.assertEqual(self.engine._td_pass_quality(production=mo), ["Контроль збирання"])
        check.do_pass.assert_called_once_with()
        domain = found.call_args.args[0]
        self.assertIn(("production_id", "in", mo.ids), domain)
        self.assertIn(("quality_state", "=", "none"), domain)
        self.assertEqual(self.engine._td_pass_quality(), [])  # немає ні МО, ні наряду
        self.assertEqual(self.engine._td_pass_quality(production=mo), [])  # `quality` не встановлено: нічого

    def test_catch_up_reports_top_reasons_and_notes_mo(self):
        past = T0 - timedelta(days=9)
        mos = [self.make_old_mo(past + mins(k))[1] for k in range(4)]
        orig = type(self.engine)._td_catch_up_mo
        errors = {
            mos[0].id: UserError("Вам досі потрібно перевірити якість!"),
            mos[1].id: UserError("Вам досі потрібно перевірити якість!"),
            mos[2].id: pg_errors.SerializationFailure("could not serialize access"),
        }

        def fake(engine, mo, wos):
            if mo.id in errors:
                raise errors[mo.id]
            return orig(engine, mo, wos)

        with patch.object(type(self.engine), "_td_catch_up_mo", new=fake):
            msg = self.at(60).td_catch_up()
        self.assertIn("закрито МО 1", msg)
        self.assertIn("не вдалось 3", msg)
        self.assertIn("Вам досі потрібно перевірити якість! — 2", msg)
        self.assertIn("конкурентне оновлення даних", msg)
        self.assertEqual(mos[3].state, "done")
        self.assertEqual([m.state for m in mos[:3]], ["confirmed"] * 3)  # невдалі лишились як були
        notes = mos[0].message_ids.mapped("body")
        self.assertTrue(any("Догнати минуле не вдалось" in str(n) for n in notes))

    def test_concurrency_error_is_not_swallowed_by_tick(self):
        """Конкурентне оновлення піднімається: Odoo повторить запит, крон — наступний такт, крок не губиться."""
        self.generate()
        with patch.object(type(self.engine), "_td_wo_start", side_effect=pg_errors.SerializationFailure("x")):
            with self.assertRaises(pg_errors.SerializationFailure):
                self.at(5).td_dispatch()

    # --- C-LP-01: ціль кожному верстату ---------------------------------------------------------------------
    def add_machines(self, n):
        """Довести кількість верстатів демо до 35: окремі РЦ з `td_code` і `td.machine`."""
        env = self.env
        total = env["td.machine"].search_count([("active", "=", True)])
        for i in range(max(0, n - total)):
            wc = env["mrp.workcenter"].create(
                {
                    "name": "Верстат демо %02d" % i,
                    "td_code": "DEMO-%02d" % i,
                    "costs_hour": 600.0,
                    "resource_calendar_id": self.cal.id,
                }
            )
            env["td.machine"].create({"workcenter_id": wc.id, "protocol": "manual"})
        return env["td.machine"].search_count([("active", "=", True)])

    def test_every_machine_gets_a_target_each_tick(self):
        """3 активні наряди й 35 верстатів: у емулятор іде 35 цілей, у 32 — `idle` «Немає завдання»."""
        self.assertEqual(self.add_machines(35), 35)
        day = self.generate()
        mos = day.production_ids.sorted("id")
        for mo, name in ((mos[0], "EDGE-T"), (mos[1], "ASM-T")):  # два наряди вже в роботі на різних верстатах
            wo = mo.workorder_ids.filtered(lambda w, name=name: w.workcenter_id.td_code == name)
            self.assertTrue(self.engine._td_wo_start(wo, T0))
        fake = self.fake_sim()
        with patch.object(type(self.engine), "_td_sim_device", return_value=fake):
            self.at(0).td_dispatch()  # перший наряд на SAW-T стартує тактом
        payload = fake._td_push_machine_targets.call_args.args[0]
        self.assertEqual(len(payload), 35)
        self.assertEqual(len({t["code"] for t in payload}), 35)
        states = [t["state"] for t in payload]
        self.assertEqual((states.count("working"), states.count("idle")), (3, 32))
        for tg in payload:
            if tg["state"] == "idle":
                self.assertEqual(tg["reason"], "Немає завдання")
            self.assertRegex(tg["until"], r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")

    def test_targets_pushed_even_without_any_work_when_enabled(self):
        """Диспетчер увімкнено, а роботи немає: кожному верстату ціль «Немає завдання», а не «нічого не слати»."""
        total = self.add_machines(35)
        fake = self.fake_sim()
        with patch.object(type(self.engine), "_td_sim_device", return_value=fake):
            self.at(5).td_dispatch()
        payload = fake._td_push_machine_targets.call_args.args[0]
        self.assertEqual(len(payload), total)
        self.assertEqual({t["state"] for t in payload}, {"idle"})
        # поза зміною — «Поза зміною»
        fake.reset_mock()
        with patch.object(type(self.engine), "_td_sim_device", return_value=fake):
            self.at(60 * 12).td_dispatch()  # 17:00 Київ
        self.assertEqual({t["reason"] for t in fake._td_push_machine_targets.call_args.args[0]}, {"Поза зміною"})

    def test_disabled_dispatcher_does_not_push_idle_targets(self):
        self.add_machines(35)
        self.env["ir.config_parameter"].sudo().set_param(P + "enabled", "False")
        fake = self.fake_sim()
        with patch.object(type(self.engine), "_td_sim_device", return_value=fake):
            self.at(5).td_dispatch(force=True)  # задачі «Згенерувати»/«Догнати» не гасять верстати до запуску
        fake._td_push_machine_targets.assert_not_called()

    # --- причини простоїв «Немає завдання» / «Поза зміною» ---------------------------------------------------
    def follow_targets(self, res, minute):
        """Емулятор + машинний шар: верстат стає в стан цілі (`_td_commit_state` відкриває/закриває простої)."""
        by_wc = {m.workcenter_id.id: m for m in self.env["td.machine"].search([("active", "=", True)])}
        states = {"working": "working", "idle": "idle", "down": "fault"}
        for tg in res["targets"]:
            machine = by_wc[tg["wc"]]
            new = states[tg["state"]]
            if machine.state != new:
                machine._td_commit_state(new, T0 + mins(minute))

    def tick(self, minute):
        fake = self.fake_sim()
        with patch.object(type(self.engine), "_td_sim_device", return_value=fake):
            res = self.at(minute).td_dispatch()
        self.follow_targets(res, minute)
        return res

    def test_idle_downtimes_get_reason_at_once_and_do_not_multiply(self):
        """3 наряди з 35 верстатів, 30 хв усередині зміни: «Потребує причини» = 0, «Немає завдання» є з тривалістю й ₴,
        повторні такти нових записів не плодять."""
        env = self.env
        self.add_machines(35)
        env["ir.config_parameter"].sudo().set_param(P + "downtime_pct", "0")  # лише «Немає завдання»
        day = self.generate()
        mos = day.production_ids.sorted("id")
        busy = self.env["mrp.workorder"]
        for mo, name in ((mos[0], "SAW-T"), (mos[0], "EDGE-T"), (mos[1], "ASM-T")):  # три активні наряди на 2 години
            wo = mo.workorder_ids.filtered(lambda w, name=name: w.workcenter_id.td_code == name)
            wo.duration_expected = 120.0
            self.assertTrue(self.engine._td_wo_start(wo, T0))
            busy |= wo
        counts = []
        for minute in range(0, 31):
            self.tick(minute)
            if minute in (5, 20):
                counts.append(env["td.downtime"].search_count([]))
        Downtime = env["td.downtime"]
        self.assertEqual(Downtime.search_count([("reason_state", "=", "to_classify")]), 0)
        no_task = env.ref("td_live_production.loss_no_task")
        episodes = Downtime.search([("loss_id", "=", no_task)])
        idle_machines = env["td.machine"].search([("state", "=", "idle")])
        self.assertEqual(len(idle_machines), 32)  # 35 верстатів, 3 працюють
        self.assertEqual(env["td.machine"].search_count([("state", "=", "working")]), 3)
        self.assertEqual(episodes.machine_id, idle_machines)  # кожен вільний верстат — «Немає завдання»
        self.assertEqual(len(episodes), 32)  # і рівно один простій на верстат: без дублів
        self.assertFalse(Downtime.search([("machine_id", "in", busy.workcenter_id.td_machine_ids.ids)]))
        self.assertEqual(counts[0], counts[1])  # такти 5 і 20: стан не змінився — нових записів немає
        self.assertEqual({d.reason_state for d in episodes}, {"confirmed"})
        self.assertEqual({d.reason_source for d in episodes}, {"demo"})
        self.assertTrue(all(d.date_start == T0 for d in episodes))
        self.assertEqual(
            no_task.loss_id, env.ref("mrp.category_availability")
        )  # втрата доступності, не плановий простій
        self.assertFalse(no_task.td_planned)
        # закриття: тривалість і ₴ (ставка 600 ₴/год × 30 хв)
        machine = idle_machines[0]
        machine._td_commit_state("working", T0 + mins(30))
        closed = Downtime.search([("machine_id", "=", machine.id)])
        self.assertEqual(len(closed), 1)
        self.assertAlmostEqual(closed.duration_min, 30.0, places=1)
        self.assertAlmostEqual(closed.cost, 300.0, places=1)
        self.assertEqual(closed.loss_id, no_task)

    def test_off_shift_idle_is_not_a_downtime(self):
        """Поза зміною простою з ₴ немає: «Немає завдання» закривається о кінці зміни, новий не відкривається."""
        env = self.env
        self.add_machines(35)
        env["ir.config_parameter"].sudo().set_param(P + "downtime_pct", "0")
        end = 510  # 15:30 Київ
        for minute in (0, 60, 500):
            self.tick(minute)
        Downtime = env["td.downtime"]
        self.assertTrue(Downtime.search([("date_end", "=", False)]))
        res = self.tick(520)  # зміна скінчилась
        self.assertEqual({t["reason"] for t in res["targets"]}, {"Поза зміною"})
        machines = env["td.machine"].search([("active", "=", True)])
        now = T0 + mins(520)
        for machine in machines:  # штатна межа робочого дня td_machine_connect
            machine._td_day_boundary(now)
            machine._td_reopen_after_boundary(now)
        self.assertFalse(Downtime.search([("date_end", "=", False)]))  # відкритих простоїв (з ₴ наживо) немає
        self.assertEqual(Downtime.search([("date_end", ">", T0 + mins(end))]), Downtime.browse())
        self.assertEqual(Downtime.search_count([("date_start", ">=", T0 + mins(end))]), 0)
        # верстат закінчив роботу після зміни й став `idle`: простій не відкривається
        machine = machines[0]
        machine._td_commit_state("working", T0 + mins(530))
        before = Downtime.search_count([])
        machine._td_commit_state("idle", T0 + mins(540))
        self.assertEqual(Downtime.search_count([]), before)
        self.assertFalse(machine.current_downtime_id)

    def test_lunch_break_is_off_shift_and_idle_resumes_after(self):
        """Обід (11:30–12:00) — поза плановим часом: «Немає завдання» закривається о 11:30 і відкривається з 12:00."""
        env = self.env
        self.add_machines(35)
        env["ir.config_parameter"].sudo().set_param(P + "downtime_pct", "0")
        self.tick(0)
        Downtime = env["td.downtime"]
        machines = env["td.machine"].search([("active", "=", True)])
        self.assertEqual(Downtime.search_count([("date_end", "=", False)]), 35)
        lunch_start, lunch_end = 270, 300  # 11:30 і 12:00 Київ
        res = self.tick(lunch_start + 10)
        self.assertEqual({t["reason"] for t in res["targets"]}, {"Поза зміною"})
        self.assertFalse(Downtime.search([("date_end", "=", False)]))
        self.assertEqual({d.date_end for d in Downtime.search([])}, {T0 + mins(lunch_start)})
        res = self.tick(lunch_end + 1)
        self.assertEqual({t["reason"] for t in res["targets"]}, {"Немає завдання"})
        for machine in machines:  # штатне повторне відкриття td_machine_connect з початку наступного інтервалу
            machine._td_reopen_after_boundary(T0 + mins(lunch_end + 1))
        reopened = Downtime.search([("date_end", "=", False)])
        self.assertEqual(len(reopened), 35)
        self.assertEqual({d.date_start for d in reopened}, {T0 + mins(lunch_end)})
        self.assertEqual({d.reason_state for d in reopened}, {"confirmed"})
        self.assertEqual({d.loss_id for d in reopened}, {env.ref("td_live_production.loss_no_task")})

    def test_open_downtime_without_label_is_classified_next_tick(self):
        """Гонка: машинний шар відкрив простій раніше за мітку — наступний такт дає причину, а не «без причини»."""
        self.add_machines(35)
        machine = self.env["td.machine"].search([("active", "=", True)], limit=1)
        machine._td_commit_state("idle", T0)  # мітки ще немає
        dt = machine.current_downtime_id
        self.assertEqual(dt.reason_state, "to_classify")
        self.tick(1)
        self.assertEqual((dt.reason_state, dt.loss_id), ("confirmed", self.env.ref("td_live_production.loss_no_task")))

    def test_dispatcher_planned_reason_is_label_for_machine_layer(self):
        """Причина запланованого простою (наладка, поломка) стає міткою верстата: машинний шар запише її одразу."""
        loss = self.engine._td_loss("fault")
        target = {"wc": 1, "state": "down", "reason": "Поломка", "until": T0, "kind": "downtime", "dt": 7}
        got, off = self.engine._td_target_label(target, {7: loss})
        self.assertEqual((got, off), (loss, False))
        no_loss, off = self.engine._td_target_label({"wc": 1, "kind": "off"}, {})
        self.assertEqual((bool(no_loss), off), (False, True))

    # --- фонові задачі: кнопки лише ставлять у чергу, виконавець працює порціями ----------------------------
    def test_generate_button_queues_and_runs_in_portions(self):
        Job = self.env["td.live.job"]
        eng = self.engine.with_context(td_live_now=T0 - mins(120))
        with patch.object(type(Job), "_td_wake") as wake:
            msg = eng.td_queue_generate(0)
            again = eng.td_queue_generate(0)  # повторне натискання під час роботи
        self.assertIn("у фоні", msg)
        self.assertIn("вже виконується", again)
        wake.assert_called_once()  # виконавця розбуджено один раз
        job = Job.search([("kind", "=", "generate_day")])
        self.assertEqual(len(job), 1)  # без дубля
        self.assertEqual(job.state, "queued")
        self.assertFalse(self.env["td.live.day"].search([("date", "=", DAY)]))  # кнопка нічого важкого не робить
        self.env["ir.config_parameter"].sudo().set_param(P + "job_budget_s", "0")
        with patch.object(type(Job), "_td_wake"):
            Job.with_context(td_live_now=T0 - mins(120))._cron_td_live_jobs()  # одна порція
        job.invalidate_recordset()
        self.assertEqual(job.state, "running")
        day = self.env["td.live.day"].search([("date", "=", DAY)])
        self.assertTrue(day)
        self.assertFalse(day.generated)  # план ще не готовий
        self.assertIn("замовлення", job.progress_text)
        # диспетчер не чіпає МО доби, поки план не готовий
        self.assertEqual(self.at(600).td_dispatch()["started"], 0)
        calls = self.run_jobs()
        self.assertGreater(calls, 4)  # кілька порцій, а не одна важка транзакція
        job.invalidate_recordset()
        self.assertEqual(job.state, "done")
        self.assertTrue(day.generated)
        self.assertEqual(day.order_count, 2)
        self.assertIn("Доба", job.message)
        self.assertEqual(job.day_id, day)
        self.assertEqual(self.engine.with_context(td_live_now=T0 - mins(120)).td_queue_generate(0)[:6], "План н")
        self.assertIn(job, day.job_ids)

    def test_generate_job_dispatches_elapsed_time_for_today(self):
        """Генерація сьогоднішньої доби у фоні доганяє мине час: наряди, що за планом мали закінчитись, закриті."""
        eng = self.engine.with_context(td_live_now=T0 + mins(180))
        with patch.object(type(self.env["td.live.job"]), "_td_wake"):
            eng.td_queue_generate(0)
        self.run_jobs(now=T0 + mins(180))
        day = self.env["td.live.day"].search([("date", "=", DAY)])
        self.assertTrue(day.generated)
        self.assertTrue(day.production_ids.workorder_ids.filtered(lambda w: w.state == "done"))
        job = day.job_ids
        self.assertIn("Диспетчер", job.message)

    def test_catch_up_job_reports_progress_and_top_reasons(self):
        past = T0 - timedelta(days=9)
        mos = [self.make_old_mo(past + mins(k))[1] for k in range(4)]
        orig = type(self.engine)._td_catch_up_mo
        errors = {
            mos[0].id: UserError("Вам досі потрібно перевірити якість!"),
            mos[1].id: UserError("Вам досі потрібно перевірити якість!"),
            mos[2].id: UserError("Вам потрібно зв’язати користувача зі співробітником"),
        }

        def fake(engine, mo, wos):
            if mo.id in errors:
                raise errors[mo.id]
            return orig(engine, mo, wos)

        Job = self.env["td.live.job"]
        with patch.object(type(Job), "_td_wake"):
            self.assertIn("у фоні", self.at(60).td_queue_catch_up())
            self.assertIn("вже виконується", self.at(60).td_queue_catch_up())
        self.assertEqual(Job.search_count([("kind", "=", "catch_up")]), 1)
        job = Job.search([("kind", "=", "catch_up")])
        with patch.object(type(self.engine), "_td_catch_up_mo", new=fake):
            self.run_jobs(now=T0 + mins(60))
        job.invalidate_recordset()
        self.assertEqual(job.state, "done")
        self.assertEqual((job.done_count, job.failed_count), (1, 3))
        self.assertGreaterEqual(job.total, 4)
        self.assertIn("закрито 1 з", job.message)
        self.assertIn("Вам досі потрібно перевірити якість! — 2", job.message)
        self.assertEqual(job.top_reasons().count(" — "), 2)  # топ-3 → тут дві різні причини
        self.assertEqual(mos[3].state, "done")
        self.assertEqual([m.state for m in mos[:3]], ["confirmed"] * 3)
        self.assertTrue(any("Догнати минуле не вдалось" in str(n) for n in mos[0].message_ids.mapped("body")))

    def test_catch_up_requeues_item_on_conflicts(self):
        job = self.env["td.live.job"].create({"kind": "catch_up", "phase": "mos", "total": 2, "state": "running"})
        job.queue = "[[11, 0], [12, 0]]"
        job._td_on_conflict()
        self.assertEqual(job._json("queue", []), [[12, 0], [11, 1]])  # відкладено в кінець
        job.queue = "[[11, 1]]"
        job._td_on_conflict()
        self.assertEqual(job._json("queue", []), [[11, 2]])
        job._td_on_conflict()  # третя поразка: МО вважається невдалою
        self.assertEqual(job.state, "done")  # черга порожня
        self.assertEqual(job.failed_count, 1)
        self.assertIn("конкурентне оновлення", job.top_reasons())

    def test_job_error_marks_failed_not_loops(self):
        Job = self.env["td.live.job"]
        with patch.object(type(Job), "_td_wake"):
            self.engine.with_context(td_live_now=T0).td_queue_generate(0)
        with patch.object(type(self.engine), "_td_gen_plan", side_effect=UserError("Немає шаблонів")):
            self.run_jobs(now=T0, limit=5)
        job = Job.search([("kind", "=", "generate_day")])
        self.assertEqual(job.state, "failed")
        self.assertIn("Немає шаблонів", job.error)
        self.assertIn("помилка", job.progress_text)

    def test_start_without_plan_chains_jobs_and_activates_after(self):
        """«Запустити» без плану на сьогодні не вмикає диспетчер: у фоні догнати минуле → план → запуск."""
        icp = self.env["ir.config_parameter"].sudo()
        icp.set_param("td.viewer.demo_clock", "2026-10-12 10:30")
        icp.set_param(P + "enabled", "False")
        self.make_old_mo(T0 - timedelta(days=9))
        Job = self.env["td.live.job"]
        with patch.object(type(Job), "_td_wake"):
            msg = self.at(0).td_start()
        self.assertIn("Плану на сьогодні ще немає", msg)
        self.assertEqual(icp.get_param(P + "enabled"), "False")
        self.assertEqual(icp.get_param("td.viewer.demo_clock"), "2026-10-12 10:30")  # годинник поки не чіпаємо
        self.assertFalse(self.env.ref("td_live_production.cron_td_live_tick").active)
        kinds = Job.search([], order="id").mapped("kind")
        self.assertEqual(kinds, ["catch_up", "generate_day"])
        status = self.env["res.config.settings"].create({}).td_live_jobs  # блок «Фонові задачі» у налаштуваннях
        self.assertIn("Згенерувати добу", status)
        self.assertIn("Догнати минуле", status)
        self.run_jobs(now=T0 - mins(120))
        self.assertEqual(icp.get_param(P + "enabled"), "True")  # запуск після завершення задач
        self.assertFalse(icp.get_param("td.viewer.demo_clock"))
        self.assertTrue(self.env.ref("td_live_production.cron_td_live_tick").active)
        self.assertTrue(self.env["td.live.day"].search([("date", "=", DAY), ("generated", "=", True)]))

    def test_stop_cancels_pending_start(self):
        Job = self.env["td.live.job"]
        with patch.object(type(Job), "_td_wake"):
            self.at(0).td_start()
        job = Job.search([("kind", "=", "generate_day")])
        self.assertTrue(job.then_start)
        self.at(0).td_stop()
        self.assertFalse(job.then_start)

    def test_dispatch_budget_returns_pending_and_applied(self):
        day = self.generate()
        res = self.at(600).td_dispatch(budget_s=0)  # бюджет вичерпано одразу: нічого не виконано, усе в черзі
        self.assertEqual((res["applied"], res["started"]), (0, 0))
        self.assertGreater(res["pending"], 0)
        self.assertEqual(res["pushed"], {})
        done = self.at(600).td_dispatch()
        self.assertEqual(done["pending"], 0)
        self.assertEqual(day.state, "done")

    def test_catch_up_does_not_touch_live_machine_rows(self):
        """Історія не чіпає стан верстата: менше блокувань і конфліктів із кроном верстатів."""
        past = T0 - timedelta(days=9)
        _so, mo = self.make_old_mo(past)
        machines = mo.workorder_ids.workcenter_id.td_machine_ids
        before = {m.id: (m.write_date, m.active_workorder_id.id) for m in machines}
        self.at(60).td_catch_up()
        self.assertEqual(mo.state, "done")
        self.assertEqual({m.id: (m.write_date, m.active_workorder_id.id) for m in machines}, before)
        for move in mo.move_raw_ids | mo.move_finished_ids:
            self.assertEqual(move.date, mo.date_finished)  # дати рухів — момент закриття МО
        lines = (mo.move_raw_ids | mo.move_finished_ids).move_line_ids
        self.assertTrue(lines)
        self.assertEqual({line.date for line in lines}, {mo.date_finished})

    def test_zonal_tariff_starts_yesterday_and_shifts_existing(self):
        """Зонний тариф з учорашньої доби; створений раніше «з сьогодні» зсувається (потрібен td_energy)."""
        if "td.energy.tariff" not in self.env:
            self.skipTest("td_energy не встановлено")
        company = self.env.company
        Tariff = self.env["td.energy.tariff"]
        today = self.engine._td_today()
        yesterday = today - timedelta(days=1)
        self.engine._td_prepare_tariff(company)
        zonal = Tariff.search([("name", "=", "Зонний тариф (демо-підприємство)")])
        self.assertEqual(zonal.date_from, yesterday)
        zonal.date_from = today  # як на сервері до виправлення
        self.assertIn("зсунуто", self.engine._td_prepare_tariff(company))
        self.assertEqual(zonal.date_from, yesterday)
        self.assertEqual(self.engine._td_prepare_tariff(company), "")

    # --- LP-07: підготовка компанії ----------------------------------------------------------------------
    def test_prepare_company(self):
        company = self.env.company
        uah = self.env.ref("base.UAH")
        so_before = self.template_so.order_line.price_unit
        report = self.engine.td_prepare_company()
        self.assertEqual(company.name, "Меблеве підприємство")
        self.assertEqual(company.currency_id, uah)
        self.assertTrue(uah.active)
        self.assertEqual(self.template_so.currency_id, uah)
        self.assertEqual(self.template_so.order_line.price_unit, so_before)  # суми не перераховано
        self.assertEqual(self.board.with_company(company).standard_price, pricing.guess_unit_cost("DSP16-T"))
        self.assertEqual(self.hinge.with_company(company).standard_price, 140.0)  # задану не чіпаємо
        self.assertIn("Меблеве підприємство", report)
        self.assertEqual(self.engine.td_prepare_company(), "")  # ідемпотентно: нічого не змінилось

    def test_prepare_company_blocked_currency_explains(self):
        company = self.env.company
        company.currency_id = self.env.ref("base.USD")
        company.name = "Інша назва"
        line_model = type(self.env["account.move.line"])
        with patch.object(line_model, "search_count", return_value=3):
            with self.assertRaises(UserError) as err:
                self.engine.td_prepare_company()
        self.assertIn("3 проводок", str(err.exception))
        self.assertIn("UAH", str(err.exception))
        self.assertEqual(company.name, "Інша назва")  # перевірка — до будь-яких змін
        self.assertEqual(company.currency_id, self.env.ref("base.USD"))
