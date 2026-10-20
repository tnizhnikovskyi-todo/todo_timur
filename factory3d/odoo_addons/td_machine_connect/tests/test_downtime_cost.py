"""DT-1…DT-4: простої в гривнях — вартість, пересчіт зі зміною ставки, Парето, плитка, payload, демо-ставки."""

from datetime import timedelta

from odoo.tests import tagged

from .. import hooks
from .common import F3DMachineCase, F3DMachineHttpCase, at, kt
from .test_migration import machines_csv, row

DAY2 = F3DMachineCase.D0.replace(day=2)  # дві доби раніше в тому самому місяці, що й D0 (12.10.2026)


class CostMixin:
    def down(self, machine, start, end, loss="mrp.block_reason1", state="to_confirm", day=None, kind="fault"):
        """Закритий простій `start`–`end` (час за Києвом) із причиною `loss`; `end=None` — відкритий."""
        day = day or self.D0
        return self.env["td.downtime"].create(
            {
                "machine_id": machine.id,
                "date_start": kt(start, day),
                "date_end": kt(end, day) if end else False,
                "state_kind": kind,
                "loss_id": self.env.ref(loss).id,
                "reason_state": state,
            }
        )


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestDowntimeCost(CostMixin, F3DMachineCase):
    def test_cost_is_duration_times_rate(self):
        """DT-1: вартість = тривалість (год) × `costs_hour` РЦ верстата; валюта — компанії."""
        self.wc_cnc.costs_hour = 600.0
        dt = self.down(self.m_cnc, "09:00", "09:30")
        self.assertEqual(dt.duration_min, 30.0)
        self.assertEqual(dt.cost, 300.0)
        self.assertEqual(dt.currency_id, self.env.company.currency_id)
        self.assertEqual(dt.shift_date, self.D0)

    def test_zero_rate_zero_cost(self):
        dt = self.down(self.m_cnc, "09:00", "10:00")
        self.assertEqual(dt.cost, 0.0)

    def test_recompute_on_rate_change(self):
        """DT-1: зміна ставки РЦ перераховує збережену вартість усіх його простоїв."""
        self.wc_cnc.costs_hour = 600.0
        a = self.down(self.m_cnc, "09:00", "09:30")
        b = self.down(self.m_cnc, "11:00", "12:00", loss="mrp.block_reason2", kind="setup")
        other = self.down(self.m_ua, "09:00", "10:00")
        self.assertEqual((a.cost, b.cost, other.cost), (300.0, 600.0, 0.0))
        self.wc_cnc.costs_hour = 1200.0
        self.assertEqual((a.cost, b.cost, other.cost), (600.0, 1200.0, 0.0))

    def test_open_downtime_cost_live(self):
        """Відкритий простій: збережена вартість 0, `cost_live` росте з часом; після закриття стає збереженою."""
        self.wc_cnc.costs_hour = 600.0
        with at("09:00"):
            dt = self.down(self.m_cnc, "09:00", None)
        self.assertEqual(dt.cost, 0.0)
        with at("09:30"):
            dt.invalidate_recordset(["cost_live"])
            self.assertEqual(dt.cost_live, 300.0)
        dt.write({"date_end": kt("10:00")})
        self.assertEqual((dt.cost, dt.cost_live), (600.0, 600.0))

    def test_shift_date_is_kyiv_local(self):
        """Зміна = київська доба: 01:30 за Києвом (22:30 UTC попередньої доби) — вже наступна дата."""
        dt = self.down(self.m_cnc, "01:30", "02:00")
        self.assertEqual(str(dt.date_start)[:10], "2026-10-11")
        self.assertEqual(dt.shift_date, self.D0)

    def test_pareto_sorted_by_sum(self):
        """DT-2: Парето за причиною — сума ₴ за спаданням; графік у представленні має `order="DESC"` за `cost`."""
        self.wc_cnc.costs_hour = 600.0
        self.wc_ua.costs_hour = 300.0
        self.down(self.m_cnc, "08:00", "08:30", loss="mrp.block_reason2", kind="setup")  # 300
        self.down(self.m_cnc, "09:00", "11:00", loss="mrp.block_reason1")  # 1200
        self.down(self.m_ua, "09:00", "10:00", loss="mrp.block_reason0", kind="idle")  # 300
        self.down(self.m_ua, "11:00", "12:00", loss="mrp.block_reason0", kind="idle")  # 300
        Downtime = self.env["td.downtime"]
        rows = Downtime._read_group([], ["loss_id"], ["cost:sum"], order="cost:sum desc")
        sums = [(loss.id, total) for loss, total in rows]
        self.assertEqual(sums[0], (self.env.ref("mrp.block_reason1").id, 1200.0))
        self.assertEqual([t for _, t in sums], sorted((t for _, t in sums), reverse=True))
        self.assertEqual(dict(sums)[self.env.ref("mrp.block_reason0").id], 600.0)
        arch = self.env.ref("td_machine_connect.view_td_downtime_cost_graph").arch
        self.assertIn('order="DESC"', arch)
        self.assertIn('<field name="cost" type="measure"/>', arch)
        action = self.env.ref("td_machine_connect.action_td_downtime_cost")
        self.assertEqual(action.view_mode, "graph,pivot,list")
        # зрізи за верстатом і зміною: збережені поля, за якими працює pivot
        by_wc = {wc.id: t for wc, t in Downtime._read_group([], ["workcenter_id"], ["cost:sum"])}
        self.assertEqual((by_wc[self.wc_cnc.id], by_wc[self.wc_ua.id]), (1500.0, 600.0))
        by_shift = Downtime._read_group([], ["shift_date:day"], ["cost:sum"])
        self.assertEqual(sum(t for _, t in by_shift), 2100.0)

    def test_tile_month_total_and_no_reason(self):
        """DT-2: плитка — сума за поточний місяць і «з них без причини» (`to_classify`); минулий місяць не рахується."""
        self.wc_cnc.costs_hour = 600.0
        with at("12:00"):
            self.down(self.m_cnc, "08:00", "09:00", state="confirmed")  # 600
            self.down(self.m_cnc, "10:00", "10:30", state="to_classify", loss="mrp.block_reason0", kind="idle")  # 300
            self.down(self.m_cnc, "08:00", "09:00", day=DAY2)  # 600, той самий місяць
            self.down(self.m_cnc, "08:00", "09:00", day=self.D0.replace(month=9, day=20))  # минулий місяць
            tile = self.env["td.downtime"].td_cost_tile()
        self.assertEqual((tile["total"], tile["no_reason"]), (1500.0, 300.0))
        self.assertEqual(tile["currency_id"], self.env.company.currency_id.id)
        self.assertTrue(tile["symbol"])

    def test_tile_includes_open_live(self):
        self.wc_cnc.costs_hour = 600.0
        with at("10:00"):
            self.down(self.m_cnc, "09:00", None, state="to_classify")
            tile = self.env["td.downtime"].td_cost_tile()
        self.assertEqual((tile["total"], tile["no_reason"]), (600.0, 600.0))

    def test_tile_only_for_manager(self):
        """Вартість — для менеджера «Завод 3D»; звичайний користувач плитки не отримує."""
        self.assertFalse(self.env["td.downtime"].with_user(self.user_f3d).td_cost_tile())
        self.assertTrue(self.env["td.downtime"].with_user(self.user_f3d_manager).td_cost_tile())

    def test_payload_downtime_cost(self):
        """DT-3: `workcenters[code].downtime_cost` — сума за місяць; немає в кіоску й без групи менеджера."""
        self.wc_cnc.costs_hour = 600.0
        with at("12:00"):
            self.down(self.m_cnc, "08:00", "09:00", state="confirmed")
            provider = self.env["td.viewer.provider.machines"]
            payload = {"workcenters": {"CNC-T": {"code": "CNC-T"}, "UA-T": {"code": "UA-T"}}}
            provider._td_viewer_collect(payload, {})
            self.assertEqual(payload["workcenters"]["CNC-T"]["downtime_cost"], 600.0)
            self.assertEqual(payload["workcenters"]["UA-T"]["downtime_cost"], 0.0)
            kiosk = {"workcenters": {"CNC-T": {"code": "CNC-T"}}}
            provider._td_viewer_collect(kiosk, {"kiosk": True})
            self.assertNotIn("downtime_cost", kiosk["workcenters"]["CNC-T"])
            plain = {"workcenters": {"CNC-T": {"code": "CNC-T"}}}
            provider.with_user(self.user_f3d)._td_viewer_collect(plain, {})
            self.assertNotIn("downtime_cost", plain["workcenters"]["CNC-T"])
            delta = {"workcenters": {"CNC-T": {"code": "CNC-T"}}}
            provider._td_viewer_delta(delta, {})
            self.assertEqual(delta["workcenters"]["CNC-T"]["downtime_cost"], 600.0)


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestDemoRates(CostMixin, F3DMachineCase):
    """DT-4: демо-ставки РЦ — лише порожні, лише в демо-базі, ідемпотентно."""

    def _rows(self):
        return [row("SAW-T", "manual", ""), row("CNC-T", "manual", ""), row("XYZ-T", "manual", "")]

    def _mark_demo(self):
        self.down(self.m_cnc, "08:00", "08:30").reason_source = "demo"

    def test_not_demo_base_untouched(self):
        with machines_csv(self._rows()):
            self.assertEqual(hooks.demo_rates(self.env), {"rates_set": 0})
        self.assertEqual((self.wc_saw.costs_hour, self.wc_cnc.costs_hour), (0.0, 0.0))

    def test_sets_only_empty_rates(self):
        self._mark_demo()
        self.wc_cnc.costs_hour = 777.0
        with machines_csv(self._rows()):
            self.assertEqual(hooks.demo_rates(self.env), {"rates_set": 1})
            self.assertEqual(hooks.demo_rates(self.env), {"rates_set": 0})  # ідемпотентна
        self.assertEqual(self.wc_saw.costs_hour, dict(hooks.RATES)["SAW"])
        self.assertEqual(self.wc_cnc.costs_hour, 777.0)  # ненульову не перезаписано

    def test_default_rate_for_unknown_prefix(self):
        self._mark_demo()
        wc = self.env["mrp.workcenter"].create({"name": "Невідомий", "td_code": "XYZ-T"})
        with machines_csv(self._rows()):
            hooks.demo_rates(self.env)
        self.assertEqual(wc.costs_hour, hooks.RATE_DEFAULT)

    def test_rates_make_demo_downtime_cost(self):
        """Після демо-ставок вартість існуючого демо-простою перераховується."""
        self._mark_demo()
        dt = self.env["td.downtime"].search([("machine_id", "=", self.m_cnc.id)], limit=1)
        self.assertEqual(dt.cost, 0.0)
        with machines_csv(self._rows()):
            hooks.demo_rates(self.env)
        self.assertEqual(dt.cost, dict(hooks.RATES)["CNC"] * 0.5)  # 30 хв


@tagged("post_install", "-at_install", "f3d", "f3d_machine_connect")
class TestCostTileTour(CostMixin, F3DMachineHttpCase):
    def test_cost_tile_tour(self):
        """DT-2: плитка в «Огляді верстатів» і клік у «Простої в ₴»."""
        self.wc_cnc.costs_hour = 600.0
        start = self.env["td.downtime"]._td_month_start() + timedelta(hours=1)  # завжди в поточному місяці
        self.env["td.downtime"].create(
            {
                "machine_id": self.m_cnc.id,
                "date_start": start,
                "date_end": start + timedelta(hours=1),
                "state_kind": "idle",
                "loss_id": self.env.ref("td_machine_connect.loss_unknown").id,
            }
        )
        self.start_tour(
            "/odoo/action-td_machine_connect.action_td_machine_dashboard",
            "td_machine_connect_cost_tile",
            login="admin",
            timeout=180,
        )
