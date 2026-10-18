"""R-14 п. 8, CE-03: острів — навантаження й скидання; баланс пропускає години відключення (R-11)."""

from datetime import timedelta

from odoo import fields
from odoo.tests import tagged

from .common import TAGS, F3DEnergyCase
from .test_counter import EnergyMixin

A = "infra/ats/"


@tagged(*TAGS)
class TestIsland(EnergyMixin, F3DEnergyCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Signal = cls.env["td.signal"]
        cls.Outage = cls.env["td.energy.outage"]
        cls.Outage.search([]).unlink()
        cls.T = cls.base_day(cls).replace(hour=10, minute=5)

    def put(self, code, at, text=None, value=None):
        item = {"code": code, "ts": at}
        if text is not None:
            item["text"] = text
        if value is not None:
            item["value"] = value
        self.Signal.with_context(f3d_now=at)._f3d_ingest([item])

    def test_island_load_and_shed(self):
        T = self.T
        self.put("energy/totals/p_now", T - timedelta(seconds=30), value=626.0)
        self.put(A + "src1_state", T, text="under")
        out = self.Outage.search([])
        self.assertEqual(out.load_before_kw, 626.0)
        self.put(A + "position", T + timedelta(seconds=14), text="pos_II")
        self.put("energy/totals/p_now", T + timedelta(seconds=20), value=348.0)
        now = T + timedelta(seconds=21)
        self.Outage.with_context(f3d_now=now)._f3d_ats_tick(now)
        self.assertEqual((out.load_island_kw, out.shed_kw), (348.0, 278.0))
        self.put(A + "src1_state", T + timedelta(seconds=25), text="under")
        self.put("energy/totals/p_now", T + timedelta(seconds=30), value=400.0)
        now = T + timedelta(seconds=31)
        self.Outage.with_context(f3d_now=now)._f3d_ats_tick(now)
        self.assertEqual((out.load_island_kw, out.shed_kw), (400.0, 278.0))

    def test_balance_skips_outage_hour(self):
        hour = (fields.Datetime.now() - timedelta(days=3)).replace(hour=8, minute=0, second=0, microsecond=0)
        self.Outage.create(
            {
                "ts_start": hour + timedelta(minutes=10),
                "ts_end": hour + timedelta(minutes=40),
                "source": "ats",
                "state": "closed",
            }
        )
        rows = self.env["td.energy.balance"]._f3d_balance_hour(hour, hour + timedelta(hours=2))
        first = rows.filtered(lambda r: r.hour == hour)
        self.assertTrue(first)
        self.assertEqual(set(first.mapped("state")), {"skipped"})
        self.assertEqual(set(first.mapped("reason")), {"відключення мережі"})
        second = rows.filtered(lambda r: r.hour == hour + timedelta(hours=1))
        self.assertNotIn("відключення мережі", second.mapped("reason"))
