"""AC-17: тренд (R-11) і журнал (R-12): події й команди разом, `ts desc`, пагінація без дублів."""

from datetime import timedelta

from odoo import fields
from odoo.exceptions import UserError
from odoo.tests import tagged

from .common import TAGS, ChpCase, utc_now


@tagged(*TAGS)
class TestTrendJournal(ChpCase):
    def test_trend(self):
        self.idle()
        sig = self.Signal.search([("code", "=", "chp/gen/p_kw")])
        t = fields.Datetime.now()
        rows = [(t - timedelta(minutes=m), 400.0 + m) for m in (1, 2, 3, 40, 70, 600)]
        self.env["td.reading"].create(
            [{"signal_id": sig.id, "ts": ts, "value": v, "quality": "good", "src": "module"} for ts, v in rows]
        )
        d24 = self.pult(self.u_user).get_trend(range_h=24)
        self.assertEqual((d24["range_h"], d24["step_s"]), (24, 300))
        self.assertEqual(set(d24["series"]), {"pel", "qth", "gas"})
        self.assertTrue(all(len(v) == 288 for v in d24["series"].values()))
        # 1–3 хв — один відрізок (середнє 402), 40, 70 і 600 хв — власні
        self.assertEqual(sum(1 for v in d24["series"]["pel"] if v is not None), 4)
        self.assertTrue(all(v is None for v in d24["series"]["qth"]))
        self.assertTrue(d24["t0"].endswith("Z"))
        d1 = self.pult(self.u_user).get_trend(range_h=1)
        self.assertEqual((d1["range_h"], d1["step_s"]), (1, 30))
        self.assertTrue(all(len(v) == 120 for v in d1["series"].values()))
        pel = [v for v in d1["series"]["pel"] if v is not None]
        self.assertEqual(sorted(pel), [401.0, 402.0, 403.0, 440.0])
        with self.assertRaises(UserError):
            self.pult(self.u_user).get_trend(range_h=6)

    def test_journal_merge_and_pagination(self):
        self.idle()
        base = utc_now().replace(microsecond=0) - timedelta(hours=1)
        for i in range(6):
            self.Event._td_log(self.unit, "info", "state", f"подія {i}", ts=base + timedelta(minutes=i), dedup_s=0)
        prep = self.pult(self.u_op1).command(
            "prepare", kind="set_cos", params={"cos": 0.97}
        )  # prepared — у журналі немає
        self.assertNotIn(prep["ref"], [r["ref"] for r in self.pult(self.u_user).get_journal()["items"]])
        self.pult(self.u_op1).command("confirm", ref=prep["ref"], token=prep["token"])
        page1 = self.pult(self.u_user).get_journal(limit=3)
        self.assertEqual(len(page1["items"]), 3)
        self.assertTrue(page1["more"])
        self.assertEqual(page1["items"][0]["type"], "command")  # найновіший
        self.assertEqual(page1["items"][0]["ref"], prep["ref"])
        seen = [(r["type"], r["id"]) for r in page1["items"]]
        before = page1["items"][-1]["ts"]
        while True:
            page = self.pult(self.u_user).get_journal(limit=3, before=before)
            seen += [(r["type"], r["id"]) for r in page["items"]]
            if not page["more"]:
                break
            before = page["items"][-1]["ts"]
        self.assertEqual(len(seen), len(set(seen)))  # без дублів
        events = [s for s in seen if s[0] == "event"]
        self.assertEqual(len(events), len(self.events()))
        full = self.pult(self.u_user).get_journal(limit=50)
        ts_list = [r["ts"] for r in full["items"]]
        self.assertEqual(ts_list, sorted(ts_list, reverse=True))
        self.assertFalse(full["more"])
        self.assertEqual(full["items"][0]["text"], "Команда «Уставка cos φ»: У черзі")
        self.assertEqual(self.pult(self.u_user).get_state()["jr"][0]["ref"], prep["ref"])

    def test_journal_limit_clamped(self):
        self.idle()
        self.assertTrue(self.pult(self.u_user).get_journal(limit=0)["items"] is not None)
        self.assertLessEqual(len(self.pult(self.u_user).get_journal(limit=10_000)["items"]), 200)
