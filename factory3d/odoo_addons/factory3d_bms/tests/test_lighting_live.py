from datetime import datetime

from odoo.tests import tagged

from .common import F3DBmsLightCase


class LiveCase(F3DBmsLightCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cut = cls.mk_group("LT-CUT", "Z-CUT", "woodworking_machine", cls.lp2, 27)
        cls.eb = cls.mk_group("LT-EB", "Z-EB", "woodworking_machine", cls.lp2, 27)
        cls.fac = cls.mk_group("LT-FAC", "Z-FAC", "spraying", cls.lp2, 91)
        cls.sheets = cls.mk_group(
            "LT-SHEETS", "Z-SHEETS", "storage_floor", cls.lp1, 12, level_design=0.8, control_mode="presence"
        )
        cls.cut_sig = {}
        for key, kind in (
            ("level", "gauge"),
            ("p_now", "gauge"),
            ("scene", "gauge"),
            ("faults", "gauge"),
            ("faulty", "state"),
            ("check", "state"),
        ):
            cls.cut_sig[key] = cls.mk_signal("lighting/groups/LT-CUT/" + key, kind)
        cls.cut.write(
            {
                "level_signal_id": cls.cut_sig["level"].id,
                "power_signal_id": cls.cut_sig["p_now"].id,
                "scene_signal_id": cls.cut_sig["scene"].id,
                "faults_signal_id": cls.cut_sig["faults"].id,
                "faulty_signal_id": cls.cut_sig["faulty"].id,
                "check_signal_id": cls.cut_sig["check"].id,
            }
        )


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestLive(LiveCase):
    def test_design_fallback(self):
        g = self.cut
        self.assertEqual((g.level_pct, g.level_source, g.e_now, g.p_now_kw), (100.0, "design", 509, 3.4))
        self.assertEqual((g.stale, g.scene, g.faults, g.faulty), (True, 0, 0, ""))

    def test_live_values(self):
        s = self.cut_sig
        self.ingest(s["level"], 60)
        self.ingest(s["p_now"], 2.04)
        self.ingest(s["scene"], 3)
        self.ingest(s["faults"], 1)
        self.ingest(s["faulty"], text="1.2.1.5")
        g = self.cut
        self.assertEqual((g.level_pct, g.level_source, g.e_now, g.p_now_kw), (60.0, "live", 305, 2.04))
        self.assertEqual((g.scene, g.faults, g.faulty, g.stale, g.plan_state), (3, 1, "1.2.1.5", False, "fault"))
        self.assertTrue(g.live_ts)

    def test_sheets_design(self):
        self.assertEqual(self.sheets.e_now, 92)
        self.assertEqual(self.sheets.p_now_kw, 1.21)

    def test_plan_state_table(self):
        s = self.cut_sig
        g = self.cut
        self.assertEqual(g.plan_state, "nodata")
        self.ingest(s["level"], 100)
        self.assertEqual(g.plan_state, "ok")
        self.ingest(s["level"], 0)
        self.assertEqual(g.plan_state, "off")
        self.ingest(s["level"], 60)
        self.assertEqual(g.plan_state, "low")
        g.check_norm = False
        self.assertEqual(g.plan_state, "ok")
        g.check_norm = True
        self.ingest(s["check"], text="вимкнено в робочий час")
        self.assertEqual((g.deviation, g.plan_state), ("off_in_work", "alarm"))
        self.assertEqual(self.sheets.plan_state, "nodata")


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestPanel(LiveCase):
    def test_design_sums(self):
        self.assertEqual((self.lp2.group_count, self.lp2.n_fixtures, self.lp2.p_inst_kw), (3, 145, 18.3))
        self.assertEqual((self.lp2.p_now_kw, self.lp2.p_source), (18.3, "design"))
        self.assertEqual((self.lp1.p_now_kw, self.lp1.p_source), (1.2, "design"))

    def test_dali_sum(self):
        self.ingest(self.cut_sig["p_now"], 2.0)
        self.assertEqual((self.lp2.p_source, self.lp2.p_now_kw), ("dali", round(2.0 + 3.4 + 11.47, 1)))

    def test_meter_priority(self):
        meter = self.mk_signal("energy/consumers/LP-2/p_now")
        self.ingest(self.cut_sig["p_now"], 2.0)
        self.ingest(meter, 22.7)
        self.assertEqual((self.lp2.p_source, self.lp2.p_now_kw), ("meter", 22.7))

    def test_state(self):
        sig = self.mk_signal("lighting/panels/LP-2/state", "state")
        self.lp2.state_signal_id = sig
        self.assertEqual(self.lp2.state, "unknown")
        self.ingest(sig, text="fault")
        self.assertEqual(self.lp2.state, "fault")
        self.ingest(sig, text="ok")
        self.assertEqual(self.lp2.state, "ok")
        src = self.env["f3d.source"].search([("code", "=", "HN-LP-2")], limit=1)  # джерело з даних модуля (W3)
        if not src:
            col = self.env["f3d.collector"].create({"code": "COL-BMS", "name": "COL-BMS"})
            src = self.env["f3d.source"].create(
                {
                    "code": "HN-LP-2",
                    "name": "HN-LP-2",
                    "type": "helvarnet",
                    "collector_id": col.id,
                    "params": {"host": "iot-sim", "port": 50000},
                }
            )
        self.lp2.source_id = src
        self.cr.execute("UPDATE f3d_source SET state = 'error' WHERE id = %s", [src.id])
        self.env.invalidate_all()
        self.assertEqual(self.lp2.state, "offline")


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestContracts(LiveCase):
    def test_light_power(self):
        self.ingest(self.cut_sig["p_now"], 3.4)
        self.ingest(self.cut_sig["level"], 100)
        res = self.env["f3d.bms.light.group"]._f3d_bms_light_power()
        self.assertEqual(
            res["LT-CUT"], {"zone": "Z-CUT", "panel": "LP-2", "p_now_kw": 3.4, "p_inst_kw": 3.4, "level_pct": 100.0}
        )

    def test_kwh_from_hours(self):
        Hour = self.env["f3d.reading.hour"]
        for i, v in enumerate((3.4, 3.4, 1.7)):
            Hour.create({"signal_id": self.cut_sig["p_now"].id, "hour": datetime(2026, 1, 1, i), "v_avg": v})
        res = self.env["f3d.bms.light.group"]._f3d_bms_kwh(datetime(2026, 1, 1), datetime(2026, 1, 2))
        self.assertEqual(res["LT-CUT"], 8.5)
        self.assertEqual(res["LT-EB"], 0.0)

    def test_search_deviation(self):
        self.ingest(self.cut_sig["check"], text="нижче норми")
        Group = self.env["f3d.bms.light.group"]
        self.assertEqual(Group.search([("deviation", "in", ["off_in_work", "below_norm"])]), self.cut)
        self.assertNotIn(self.cut, Group.search([("deviation", "=", "none")]))
