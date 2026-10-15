"""AC-55…AC-58, AC-60, AC-62: АВР і відключення мережі (R-14). Час — ключ контексту `f3d_now`."""

from datetime import timedelta

from odoo.exceptions import ValidationError
from odoo.tests import tagged

from ..tools import ats
from .common import TAGS, F3DEnergyCase
from .test_counter import EnergyMixin

A = "infra/ats/"
INCOMERS = ("energy/cells/Q1/p_now", "energy/cells/Q2/p_now", "energy/cells/Q1/i_now", "energy/cells/Q2/i_now")


@tagged(*TAGS)
class TestAts(EnergyMixin, F3DEnergyCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Signal = cls.env["f3d.signal"]
        cls.Outage = cls.env["f3d.energy.outage"]
        cls.Event = cls.env["f3d.energy.event"]
        cls.T = cls.base_day(cls).replace(hour=10, minute=5)
        cls.Outage.search([]).unlink()

    def put(self, code, at, text=None, value=None):
        item = {"code": code, "ts": at}
        if text is not None:
            item["text"] = text
        if value is not None:
            item["value"] = value
        self.Signal.with_context(f3d_now=at)._f3d_ingest([item])

    def sig(self, code):
        return self.Signal.search([("code", "=", code)])

    def test_pure(self):
        self.assertTrue(ats.is_fresh("ok", 15, 5))
        self.assertFalse(ats.is_fresh("ok", 16, 5))
        self.assertFalse(ats.is_fresh("stale", 1, 5))
        self.assertEqual(
            (ats.amf_master("remote"), ats.amf_master("auto"), ats.amf_master("x")), ("hgm", "ats", "unknown")
        )
        self.assertEqual(ats.grid_state("under", None, []), (False, "ats"))
        self.assertEqual(ats.grid_state(None, 3, []), (False, "ats"))
        self.assertEqual(ats.grid_state(None, 2, []), (True, "ats"))
        self.assertEqual(ats.grid_state(None, None, [(0.2, 0.0), (0.0, 0.5)]), (False, "incomers"))
        self.assertTrue(ats.grid_state(None, None, [(0.2, 0.0), (30.0, 5.0)])[0])
        self.assertEqual(ats.shed(626, 348), 278)

    def test_src_ok_derived(self):  # AC-55
        T = self.T
        self.put(A + "src1_state", T, text="available")
        self.assertEqual((self.sig(A + "src1_ok").last_value, self.sig(A + "src1_ok").last_ts), (1, T))
        self.put(A + "src1_state", T + timedelta(seconds=5), text="under")
        self.assertEqual(self.sig(A + "src1_ok").last_value, 0)
        self.put(A + "position", T, text="pos_II")
        self.assertEqual((self.sig(A + "position").last_value, self.sig(A + "position").last_text), (3, "pos_II"))

    def test_outage_cycle_variant_a(self):  # AC-56
        T = self.T
        self.put(A + "mode", T, text="remote")
        self.put(A + "src1_state", T, text="under")
        out = self.Outage.search([])
        self.assertEqual((len(out), out.state, out.amf_master, out.source, out.ts_start), (1, "open", "hgm", "ats", T))
        self.assertTrue(out.name.startswith("Відключення"))
        with self.assertRaises(ValidationError):
            self.Outage.create({"ts_start": T, "source": "ats"})
        self.put(A + "position", T + timedelta(seconds=14), text="pos_II")
        self.assertEqual((out.transfer_s, out.gen_started), (14, True))
        self.put(A + "src1_state", T + timedelta(seconds=600), text="available")
        self.assertEqual((out.state, out.grid_back_at), ("open", T + timedelta(seconds=600)))
        self.put(A + "position", T + timedelta(seconds=660), text="pos_I")
        self.assertEqual((out.state, out.return_s, out.duration_min), ("closed", 60, 11.0))
        events = out.event_ids.sorted("ts")
        texts = events.mapped("text")
        self.assertEqual(len(texts), 3, texts)
        self.assertTrue(texts[0].startswith("Зникла напруга мережі"))
        self.assertEqual(texts[1], "АВР: переключено на генератор за 14 с.")
        self.assertEqual(
            texts[2], "Мережу відновлено, АВР повернув живлення від мережі через 60 с; відключення тривало 11 хв."
        )
        self.assertEqual(events[0].level, "bad")

    def test_fail_start_variant_b(self):  # AC-57
        T = self.T
        self.put(A + "mode", T, text="auto")
        self.put(A + "src1_state", T, text="under")
        self.put(A + "gen_start", T + timedelta(seconds=1), text="on")
        out = self.Outage.search([])
        self.assertEqual((out.amf_master, out.gen_start_at), ("ats", T + timedelta(seconds=1)))
        self.put(A + "src1_state", T + timedelta(seconds=15), text="under")
        self.put(A + "src2_state", T + timedelta(seconds=20), text="under")
        self.assertFalse(out.fail_start)
        self.put(A + "src1_state", T + timedelta(seconds=35), text="under")  # АВР опитується кожні 5 с
        self.put(A + "src2_state", T + timedelta(seconds=40), text="under")
        self.assertTrue(out.fail_start)
        self.assertEqual(self.sig(A + "fail_start").last_value, 1)
        ev = out.event_ids.filtered(lambda e: e.kind == "ats")
        self.assertEqual((ev.level, ev.text), ("bad", "АВР: генератор не запустився за 35 с (FAIL START)."))
        self.put(A + "src2_state", T + timedelta(seconds=50), text="available")
        self.assertEqual(self.sig(A + "fail_start").last_value, 0)

    def test_no_fail_start_variant_a(self):  # AC-58
        T = self.T
        self.put(A + "mode", T, text="remote")
        self.put(A + "src1_state", T, text="under")
        self.put(A + "src2_state", T + timedelta(seconds=61), text="under")
        out = self.Outage.search([])
        self.assertFalse(out.fail_start)
        self.assertEqual(out.amf_master, "hgm")
        self.assertNotEqual(self.sig(A + "fail_start").last_value, 1)

    def test_incomer_fallback(self):  # AC-60
        T = self.T
        for code in INCOMERS:
            self.put(code, T, value=0.0)
        out = self.Outage.search([])
        self.assertEqual((len(out), out.source, out.state), (1, "incomers", "open"))
        self.put("energy/cells/Q1/p_now", T + timedelta(seconds=10), value=120.0)
        self.assertEqual((out.state, out.return_s), ("closed", 0))

    def test_bridge_mismatch_event(self):  # AC-62
        T = self.T
        self.env["ir.config_parameter"].sudo().set_param("factory3d.genset.amf_master", "hgm")
        self.put(A + "mode", T, text="auto")
        self.put(A + "mode", T + timedelta(seconds=10), text="auto")
        self.put(A + "position", T + timedelta(seconds=20), value=2)
        ev = self.Event.search([("level", "=", "warn"), ("text", "like", "не відповідає налаштуванню моста")])
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev.text, "Режим АВР «Авто» не відповідає налаштуванню моста генератора «hgm».")
