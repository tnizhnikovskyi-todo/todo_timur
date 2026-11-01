"""td_telemetry 19.0.1.1.6: АВР (R-14) при відкладеному записі `td_signal.last_*` пакетів колектора.

Інші набори енергетики вимикають відкладення (`src="module"`); тут сигнали `infra/ats/*` надходять пакетами колектора
з параметрами за замовчуванням (`last_write_min_s` 15, `min_period_s` 5): вік `last_ts` перед кожним пакетом не виходить
за `ats_fresh_factor · period_s` (15 с), тож відкриті відключення не закриваються «Мережу відновлено» й не відкриваються
знову.
"""

from datetime import timedelta

from odoo.tests import tagged

from .common import TAGS, F3DEnergyCase
from .test_counter import EnergyMixin

A = "infra/ats/"


@tagged(*TAGS)
class TestAtsDeferredLast(EnergyMixin, F3DEnergyCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        icp = cls.env["ir.config_parameter"].sudo()
        icp.set_param("td.telemetry.last_write_min_s", "15")
        icp.set_param("td.telemetry.min_period_s", "5")
        icp.set_param("td.telemetry.last_fresh_s", "30")
        cls.Signal = cls.env["td.signal"]
        cls.Outage = cls.env["td.energy.outage"]
        cls.Event = cls.env["td.energy.event"]
        cls.T = cls.base_day(cls).replace(hour=10, minute=5)
        cls.Outage.search([]).unlink()
        source = cls.Signal.search([("code", "=", A + "src1_state")]).source_id
        cls.col = cls.env["td.collector"].create({"code": "COL-ATS-T", "name": "АВР (тест)", "push_interval_s": 5})
        source.collector_id = cls.col

    def packet(self, at, **texts):
        """Пакет колектора, прийнятий в момент `at`: показання АВР опитано за 3 с до того."""
        ts = at - timedelta(seconds=3)
        items = [{"code": A + code, "ts": ts, "text": text} for code, text in texts.items()]
        self.Signal.with_context(f3d_now=at, f3d_received_at=at)._td_ingest(items, src="collector", collector=self.col)

    def test_open_outage_not_flapping(self):
        T = self.T
        steady = {"mode": "remote", "src1_state": "under", "src2_state": "available", "gen_start": "on"}
        self.packet(T, position="pos_II", **steady)
        outage = self.Outage.search([])
        self.assertEqual((len(outage), outage.state), (1, "open"))
        n_events = self.Event.search_count([])
        for k in range(1, 61):  # 5 хв: незмінні значення, пакет раз на 5 с
            at = T + timedelta(seconds=5 * k)
            # крок автомата перед прийомом пакета (крон `_td_ats_tick`): `last_ts` найстарший саме зараз
            rows = self.Outage._td_ats_read(at)
            for code in ("src1_state", "position", "gen_start", "src2_state"):
                row, fresh = rows[A + code]
                self.assertTrue(fresh, "%s не свіжий на t=%s с: last_ts %s" % (code, 5 * k, row["last_ts"]))
            self.Outage._td_ats_step(at)
            self.packet(at, position="pos_II", **steady)
            self.assertEqual(self.Outage.search([]).mapped("state"), ["open"], "t=%s с" % (5 * k))
        self.assertEqual(self.Event.search_count([]), n_events, "нових подій (закрито/відкрито) бути не має")
        self.assertEqual(len(self.Outage.search([])), 1)
