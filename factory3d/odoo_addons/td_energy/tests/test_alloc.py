"""AC-37…AC-45, AC-85: розподіл енергії на завдання й пули (R-08, R-09, R-23)."""

from datetime import datetime, timedelta
from unittest.mock import patch

from odoo import Command, fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import tagged

from ..tools import dates
from .common import TAGS, F3DEnergyCase
from .test_counter import EnergyMixin

STEP = timedelta(minutes=1)


class AllocMixin(EnergyMixin):
    """Синтетичні РЦ, вузли, пули, МО (SPEC §13.0). Час `at(h, m)` — від місцевої півночі доби `cls.day`."""

    @classmethod
    def alloc_setup(cls, days_back=3):
        cls.Alloc = cls.env["td.energy.alloc"]
        cls.Node = cls.env["td.energy.node"]
        # заморожений час (демо-годинник 12.10.2026 10:30 Київ): доба тесту лишається до журналів демо-МО (відкриті
        # журнали демо-шаблону тягнуться з 11.10 і перекривали б спільні пули за реальною датою)
        cls.now = datetime(2026, 10, 12, 7, 30)
        cls.day = dates.local_day(cls.now - timedelta(days=days_back))
        cls.d0, cls.d1 = dates.local_day_bounds(cls.day)
        cls.loss = cls.env["mrp.workcenter.productivity.loss"].search([("loss_type", "=", "productive")], limit=1)

    def at(self, h, m=0, s=0):
        return self.d0 + timedelta(hours=h, minutes=m, seconds=s)

    def mk_wc(self, code):
        return self.env["mrp.workcenter"].create({"name": code, "code": code})

    def mk_direct(self, code, p_inst=10.0, lf=0.5, meter=True, max_kw=48.0):
        """Прямий споживач `<code>` з РЦ `<code>` (і лічильником `PM-<code>`)."""
        wc = self.mk_wc(code)
        vals = {"alloc_role": "direct", "workcenter_id": wc.id, "p_inst_kw": p_inst, "load_factor": lf}
        if meter:
            node = self.mk_meter("PM-" + code, max_kw=max_kw).node_id
            node.write(vals)
        else:
            parent = self.Node.search([("code", "=", "SEC-1")])
            node = self.Node.create(
                {"code": code, "name": code, "kind": "consumer", "parent_id": parent.id, "section": 1, **vals}
            )
        return node

    def mk_pool_node(self, code, pool_code, driver, role="shared", max_kw=200.0):
        node = self.mk_meter("PM-" + code, max_kw=max_kw).node_id
        vals = {"alloc_role": role}
        if role == "shared":
            pool = self.env["td.energy.pool"].search([("code", "=", pool_code)]) or self.env["td.energy.pool"].create(
                {"code": pool_code, "name": pool_code, "driver": driver}
            )
            vals["pool_id"] = pool.id
        node.write(vals)
        return node

    def profile(self, node, parts, base=1000.0):
        """Показання лічильника вузла за добу кроком 1 хв: `parts` — [(t0, t1, кВт)], поза ними споживання 0."""
        sig = node.meter_id.e_import_signal_id
        points, e, t = [], base, self.d0
        while t <= self.d1:
            points.append((t, round(e, 6)))
            nxt = t + STEP
            for a, b, kw in parts:
                lo, hi = max(a, t), min(b, nxt)
                if lo < hi:
                    e += kw * (hi - lo).total_seconds() / 3600.0
            t = nxt
        self.feed(sig, points)

    def mk_mo(self, wcs, qty=26.0, categ=None):
        categ = categ or self.env.ref("product.product_category_goods")
        product = self.env["product.product"].create(
            {"name": "KC-B600-T", "is_storable": True, "type": "consu", "categ_id": categ.id}
        )
        bom = self.env["mrp.bom"].create(
            {
                "product_tmpl_id": product.product_tmpl_id.id,
                "product_qty": 1.0,
                "operation_ids": [Command.create({"name": "Op %s" % wc.code, "workcenter_id": wc.id}) for wc in wcs],
            }
        )
        mo = self.env["mrp.production"].create({"product_id": product.id, "bom_id": bom.id, "product_qty": qty})
        mo.action_confirm()
        return mo

    def log(self, wo, start, end):
        return self.env["mrp.workcenter.productivity"].create(
            {
                "workcenter_id": wo.workcenter_id.id,
                "workorder_id": wo.id,
                "loss_id": self.loss.id,
                "date_start": start,
                "date_end": end,
            }
        )

    def run_day(self, now=None):
        return self.Alloc._f3d_alloc_days([self.day], now=now or self.now)

    def rows(self, kind, **dom):
        domain = [("day", "=", self.day), ("kind", "=", kind)] + [(k, "=", v) for k, v in dom.items()]
        return self.Alloc.sudo().search(domain)


@tagged(*TAGS)
class TestDirect(AllocMixin, F3DEnergyCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.alloc_setup()

    def test_measured_saw(self):  # AC-37
        node = self.mk_direct("SAW-T")
        mo = self.mk_mo(node.workcenter_id)
        self.log(mo.workorder_ids, self.at(1, 36), self.at(2, 54))
        self.profile(node, [(self.at(1, 36), self.at(2, 54), 13.2)])
        self.run_day()
        row = self.rows("direct", workorder_id=mo.workorder_ids.id)
        self.assertEqual(len(row), 1)
        self.assertAlmostEqual(row.kwh, 17.160, places=3)
        self.assertAlmostEqual(row.minutes, 78.0, places=1)
        self.assertAlmostEqual(row.cost, 144.14, places=2)
        self.assertEqual(row.quality, "measured")
        self.assertAlmostEqual(mo.workorder_ids.td_energy_direct_kwh, 17.160, places=3)

    def test_estimate_mo231(self):  # AC-38
        spec = [("SAW-T", 24, 0.55, 78), ("EDGE-T", 67.5, 0.65, 63), ("CNC-T", 22, 0.5, 74),
                ("SORT-T", 20, 0.45, 29), ("ASMLINE-T", 8, 0.4, 95)]  # fmt: skip
        nodes = [self.mk_direct(c, p, lf, meter=False) for c, p, lf, _m in spec]
        mo = self.mk_mo(self.env["mrp.workcenter"].concat(*[n.workcenter_id for n in nodes]))
        for wo, (_c, _p, _lf, minutes) in zip(mo.workorder_ids.sorted("id"), spec, strict=True):
            self.log(wo, self.at(1), self.at(1) + timedelta(minutes=minutes))
        self.run_day()
        got = {wo.workcenter_id.code: wo.td_energy_direct_kwh for wo in mo.workorder_ids}
        for code, kwh in (("SAW-T", 17.160), ("EDGE-T", 46.069), ("CNC-T", 13.567), ("SORT-T", 4.350),
                          ("ASMLINE-T", 5.067)):  # fmt: skip
            self.assertAlmostEqual(got[code], kwh, places=3, msg=code)
        self.assertEqual(set(self.rows("direct").mapped("quality")), {"estimate"})
        self.assertAlmostEqual(mo.td_energy_kwh, 86.213, places=3)
        self.assertAlmostEqual(mo.td_energy_cost, 724.18, places=2)
        self.assertEqual(mo.td_energy_state, "estimate")
        self.assertAlmostEqual(mo.td_energy_unit_cost, 724.18 / 26, places=3)

    def test_concurrent_split(self):  # AC-39
        node = self.mk_direct("SAW-T")
        mo1, mo2 = self.mk_mo(node.workcenter_id), self.mk_mo(node.workcenter_id)
        for mo in (mo1, mo2):
            self.log(mo.workorder_ids, self.at(10), self.at(10, 20))
        self.profile(node, [(self.at(10), self.at(10, 20), 12.0)])
        self.run_day()
        for mo in (mo1, mo2):
            row = self.rows("direct", workorder_id=mo.workorder_ids.id)
            self.assertAlmostEqual(row.kwh, 2.0, places=3)
            self.assertAlmostEqual(row.minutes, 20.0, places=1)

    def test_idle_row(self):  # AC-40
        node = self.mk_direct("SAW-T")
        mo = self.mk_mo(node.workcenter_id)
        self.log(mo.workorder_ids, self.at(1, 36), self.at(2, 54))
        # за добу +30,0: 17,160 у вікні завдання й 12,840 поза ним
        self.profile(node, [(self.at(1, 36), self.at(2, 54), 13.2), (self.at(5), self.at(6), 12.84)])
        self.run_day()
        idle = self.rows("idle", workcenter_id=node.workcenter_id.id)
        self.assertEqual(len(idle), 1)
        self.assertAlmostEqual(idle.kwh, 12.840, places=3)
        self.assertEqual(idle.node_id, node)
        self.assertFalse(idle.workorder_id)

    def test_machine_connect_path(self):  # AC-41
        node = self.mk_direct("SAW-T")
        mo = self.mk_mo(node.workcenter_id)
        wo = mo.workorder_ids
        self.log(wo, self.at(9), self.at(9, 30))  # журнал часу для підключеного РЦ ігнорується
        self.profile(node, [(self.at(6), self.at(8), 12.18), (self.at(9), self.at(9, 30), 40.0)])
        intervals = {wo.id: [(self.at(6, 55), self.at(7, 25, 48), "working")]}
        with patch.object(type(self.Alloc), "_f3d_machine_intervals", return_value=intervals):
            self.run_day()
        row = self.rows("direct", workorder_id=wo.id)
        self.assertAlmostEqual(row.kwh, 6.253, delta=0.005)
        self.assertAlmostEqual(row.minutes, 30.8, places=1)


@tagged(*TAGS)
class TestPools(AllocMixin, F3DEnergyCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.alloc_setup()

    def setup_slot(self):
        """R-09: слот 02:45–03:00; SAW-T (WO А) 02:45–02:54, EDGE-T (WO Б) 02:48–03:00, DUST-T/LP-T/BOILER-T."""
        self.saw, self.edge = self.mk_direct("SAW-T"), self.mk_direct("EDGE-T", max_kw=60.0)
        self.mo_a, self.mo_b = self.mk_mo(self.saw.workcenter_id), self.mk_mo(self.edge.workcenter_id)
        self.log(self.mo_a.workorder_ids, self.at(2, 45), self.at(2, 54))
        self.log(self.mo_b.workorder_ids, self.at(2, 48), self.at(3))
        self.profile(self.saw, [(self.at(2, 45), self.at(2, 54), 13.2)])
        self.profile(self.edge, [(self.at(2, 48), self.at(3), 43.875)])
        self.dust = self.mk_pool_node("DUST-T", "POOL-DUST-T", "kwh")
        self.lp = self.mk_pool_node("LP-T", "POOL-LIGHT-T", "time")
        self.profile(self.dust, [(self.at(2, 45), self.at(3), 127.5), (self.at(0), self.at(0, 15), 8.0)])
        self.profile(self.lp, [(self.at(2, 45), self.at(3), 23.2)])
        self.pool_dust = self.dust.pool_id
        self.pool_light = self.lp.pool_id

    def shared(self, pool, mo):
        return self.rows("shared", pool_id=pool.id, workorder_id=mo.workorder_ids.id)

    def test_dust_kwh_driver(self):  # AC-42
        self.setup_slot()
        self.run_day()
        a, b = self.shared(self.pool_dust, self.mo_a), self.shared(self.pool_dust, self.mo_b)
        self.assertAlmostEqual(a.kwh, 5.868, places=3)
        self.assertAlmostEqual(a.cost, 49.29, places=2)
        self.assertAlmostEqual(b.kwh, 26.007, places=3)
        self.assertAlmostEqual(b.cost, 218.46, places=2)
        self.assertAlmostEqual(self.mo_a.workorder_ids.td_energy_kwh, 1.98 + 5.868 + 2.486, places=3)

    def test_light_time_driver(self):  # AC-43
        self.setup_slot()
        self.run_day()
        self.assertAlmostEqual(self.shared(self.pool_light, self.mo_a).kwh, 2.486, places=3)
        self.assertAlmostEqual(self.shared(self.pool_light, self.mo_b).kwh, 3.314, places=3)

    def test_unallocated_overhead_conservation(self):  # AC-44
        self.setup_slot()
        boiler = self.mk_pool_node("BOILER-T", None, None, role="overhead")
        self.profile(boiler, [(self.d0, self.d1, 10.0)])
        self.run_day()
        un = self.rows("unallocated", pool_id=self.pool_dust.id)
        self.assertAlmostEqual(un.kwh, 2.0, places=3)  # 8 кВт × 15 хв = 2,0 (нічний слот без завдань)
        ov = self.rows("overhead", node_id=boiler.id)
        self.assertAlmostEqual(ov.kwh, 240.0, places=2)
        shared = sum(self.rows("shared", pool_id=self.pool_dust.id).mapped("kwh"))
        total = self.dust.meter_id._f3d_kwh(self.d0, self.d1)[0]
        self.assertAlmostEqual(shared + un.kwh, total, delta=0.003)

    def test_locked_untouched(self):  # AC-45
        self.setup_slot()
        self.run_day()
        a_rows = self.Alloc.sudo().search([("production_id", "=", self.mo_a.id)])
        a_rows.write({"locked": True})
        snap = {r.id: (r.kwh, r.cost, r.write_date) for r in a_rows}
        b_before = self.shared(self.pool_dust, self.mo_b).kwh
        # нові показання: +10 кВт·год аспірації наприкінці слота
        self.env.cr.execute(
            "UPDATE td_reading SET value = value + 10 WHERE signal_id = %s AND ts >= %s",
            (self.dust.meter_id.e_import_signal_id.id, self.at(2, 57)),
        )
        self.env["td.reading"].invalidate_model()
        self.run_day()
        self.assertEqual({r.id: (r.kwh, r.cost, r.write_date) for r in a_rows}, snap)
        b_after = self.shared(self.pool_dust, self.mo_b)
        self.assertNotAlmostEqual(b_after.kwh, b_before, places=3)
        un = self.rows("unallocated", pool_id=self.pool_dust.id)
        pool_total = self.dust.meter_id._f3d_kwh(self.d0, self.d1)[0]
        a_stored = sum(r.kwh for r in a_rows if r.pool_id == self.pool_dust)
        self.assertAlmostEqual(un.kwh, pool_total - a_stored - b_after.kwh, delta=0.003)

    def test_wizard(self):  # AC-85
        Wizard = self.env["td.energy.recompute.wizard"]
        today = fields.Date.context_today(Wizard)
        wiz = Wizard.with_user(self.u_energy).create({"date_from": today - timedelta(days=32), "date_to": today})
        with self.assertRaises(UserError):
            wiz.action_run()
        wiz = Wizard.with_user(self.u_energy).create({"date_from": self.day, "date_to": self.day, "what": "both"})
        wiz.action_run()
        self.assertIn("Інтервалів:", wiz.result)
        self.assertIn("діб розподілу: 1", wiz.result)
        with self.assertRaises(AccessError):
            Wizard.with_user(self.u_master).create({"date_from": self.day, "date_to": self.day}).action_run()
