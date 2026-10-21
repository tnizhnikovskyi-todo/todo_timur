"""Інтеграційні тести двигуна: генерація доби, диспетчер у «віртуальному» часі, догнати минуле, підготовка компанії."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

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
        WC = env["mrp.workcenter"]

        def wc(name, code, tags=()):
            return WC.create(
                {
                    "name": name,
                    "td_code": code,
                    "time_efficiency": 100,
                    "costs_hour": 600.0,
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
        msg = self.engine.td_start()
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
        Settings = self.env["res.config.settings"]
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

    def test_nightly_generates_tomorrow(self):
        with patch.object(type(self.engine), "_td_now", return_value=T0 - mins(300)):
            self.engine._cron_td_live_nightly()
        days = self.env["td.live.day"].search([]).mapped("date")
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
