from datetime import datetime
from unittest import mock

from freezegun import freeze_time

from odoo.tests import tagged
from odoo.tools import mute_logger

from ..tools import schedule
from .common import F3DBmsLightCase, F3DBmsRulesMixin


def at(hour, minute, day=14):
    """UTC naive: 14.10.2026 (вт); Київ = UTC+3."""
    return datetime(2026, 10, day, hour, minute)


class RulesCase(F3DBmsRulesMixin, F3DBmsLightCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_rules()
        cls.cut = cls.mk_group("LT-CUT", "Z-CUT", "woodworking_machine", cls.lp2, 27)
        cls.sheets = cls.mk_group(
            "LT-SHEETS", "Z-SHEETS", "storage_floor", cls.lp1, 12, level_design=0.8, control_mode="presence"
        )
        cls.level = cls.define("lighting/groups/LT-CUT/level")
        cls.faults = cls.define(
            "lighting/groups/LT-CUT/faults",
            "LT-CUT",
            alarm_high=0.0,
            alarm_high_on=True,
            alarm_title="Аварія світильників LT-CUT: несправних {value} шт. при нормі {threshold}",
            decimals=0,
        )
        cls.faulty = cls.define("lighting/groups/LT-CUT/faulty", kind="state")
        cls.check_sig = cls.define(
            "lighting/groups/LT-CUT/check",
            "LT-CUT",
            states=[
                "норма",
                "поза робочим часом",
                "вимкнено в робочий час",
                "нижче норми",
                "немає даних",
                "немає мережі (живлення від резерву)",
            ],
            alarm_states=["вимкнено в робочий час", "нижче норми"],
        )
        cls.cut.write(
            {
                "level_signal_id": cls.level.id,
                "faults_signal_id": cls.faults.id,
                "faulty_signal_id": cls.faulty.id,
                "check_signal_id": cls.check_sig.id,
                "equipment_id": cls.eq("LT-CUT").id,
            }
        )
        s_level = cls.define("lighting/groups/LT-SHEETS/level")
        s_check = cls.define("lighting/groups/LT-SHEETS/check", "LT-SHEETS", states=["норма"], alarm_states=[])
        cls.sheets.write({"level_signal_id": s_level.id, "check_signal_id": s_check.id})
        cls.s_level, cls.s_check = s_level, s_check

    def step(self, hour, minute, day=14):
        """Прогін крона о `hour:minute` UTC."""
        with freeze_time(at(hour, minute, day)):
            self.run_check()
        return self.check_sig.last_text


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestSchedule(RulesCase):
    def test_work_interval(self):
        wi = lambda dt: schedule.work_interval_at(self.cal, dt)  # noqa: E731
        self.assertEqual(wi(at(7, 0)), (at(4, 0), at(8, 30)))
        self.assertIsNone(wi(at(8, 45)))  # 11:45 Київ — обід
        self.assertIsNone(wi(at(12, 31)))  # 15:31 Київ
        self.assertIsNone(wi(at(7, 0, day=18)))  # субота
        self.env["resource.calendar.leaves"].create(
            {
                "name": "Свято",
                "company_id": self.env.company.id,
                "date_from": datetime(2026, 10, 14, 21, 0),
                "date_to": datetime(2026, 10, 15, 20, 59),
            }
        )
        self.assertIsNone(wi(at(7, 0, day=15)))
        self.assertIsNotNone(wi(at(7, 0, day=16)))
        self.assertIsNone(schedule.work_interval_at(self.env["resource.calendar"], at(7, 0)))


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestLightRules(RulesCase):
    def test_off_in_work_delay(self):
        self.push(self.level.code, at(6, 55), 0)
        self.assertEqual(self.cut.off_since, at(6, 55))
        self.assertEqual(self.step(7, 4), "норма")
        self.assertEqual(self.step(7, 5), "вимкнено в робочий час")
        self.assertEqual(self.check_sig.status, "alarm")
        reqs = self.requests(self.check_sig)
        self.assertEqual(len(reqs), 1)
        last = self.check_sig.last_ts
        self.step(7, 6)
        self.assertEqual(self.check_sig.last_ts, last)  # без зміни тексту — без показання
        self.assertEqual(len(self.requests(self.check_sig)), 1)
        self.push(self.level.code, at(7, 20), 100)
        self.assertFalse(self.cut.off_since)
        self.assertEqual(self.step(7, 21), "норма")

    def test_off_since_yesterday(self):
        self.push(self.level.code, at(15, 0, day=13), 0)
        self.assertEqual(self.step(4, 9), "норма")
        self.assertEqual(self.step(4, 10), "вимкнено в робочий час")
        self.assertEqual(self.step(8, 40), "поза робочим часом")

    def test_lunch_and_after_shift(self):
        self.push(self.level.code, at(5, 0), 0)
        self.assertEqual(self.step(8, 40), "поза робочим часом")  # обід
        self.assertEqual(self.step(13, 0), "поза робочим часом")  # після зміни

    def test_check_off_false(self):
        self.cut.check_off = False
        self.push(self.level.code, at(6, 55), 0)
        self.assertEqual(self.step(7, 30), "норма")

    def test_below_norm(self):
        self.push(self.level.code, at(7, 0), 60)
        self.assertEqual(self.cut.low_since, at(7, 0))
        self.assertEqual(self.step(7, 9), "норма")
        self.assertEqual(self.step(7, 10), "нижче норми")  # ≈ 305 < 475
        self.push(self.level.code, at(7, 11), 95)
        self.assertFalse(self.cut.low_since)
        self.assertEqual(self.step(7, 12), "норма")  # ≈ 484 ≥ 475

    def test_tolerance_zero(self):
        self.env["ir.config_parameter"].sudo().set_param("td.bms.light_norm_tolerance_pct", "0")
        self.push(self.level.code, at(7, 0), 98)
        self.assertEqual(self.step(7, 10), "нижче норми")  # 498,6 < 500

    def test_presence_not_checked(self):
        self.push(self.s_level.code, at(7, 0), 50)
        self.assertFalse(self.sheets.check_norm)
        with freeze_time(at(7, 30)):
            self.run_check()
        self.assertEqual(self.s_check.last_text, "норма")
        self.sheets.check_norm = True
        with freeze_time(at(7, 40)):
            self.run_check()
        self.assertEqual(self.s_check.last_text, "нижче норми")  # 57 < 95

    def test_no_data(self):
        self.assertEqual(self.step(7, 30), "немає даних")
        self.assertFalse(self.requests(self.check_sig))

    def test_mains_suppression(self):
        mains = self.define("infra/ats/src1_ok")
        self.push(mains.code, at(7, 0), 0)
        self.push(self.level.code, at(7, 0), 0)
        self.assertEqual(self.step(7, 30), "немає мережі (живлення від резерву)")
        self.assertFalse(self.cut.off_since)
        self.push(mains.code, at(7, 30), 1)
        self.assertEqual(self.step(7, 31), "норма")
        self.assertEqual(self.step(7, 40), "норма")
        self.assertEqual(self.step(7, 41), "вимкнено в робочий час")


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestIngestHook(RulesCase):
    CHECK = "odoo.addons.td_bms.models.td_bms_check.F3dBmsCheck._f3d_bms_on_ingest"

    def test_since_from_reading_ts(self):
        with freeze_time(at(7, 30)):
            self.push(self.level.code, at(6, 55, 14), 0)
            self.assertEqual(self.cut.off_since, at(6, 55))
            self.push(self.level.code, at(7, 0), 0)
            self.assertEqual(self.cut.off_since, at(6, 55))
            self.push(self.level.code, at(7, 1), 60)
            self.assertFalse(self.cut.off_since)
            self.assertEqual(self.cut.low_since, at(7, 1))

    def test_internal_context_skips(self):
        with freeze_time(at(7, 30)), mock.patch(self.CHECK) as hook:
            self.env["td.signal"].with_context(f3d_bms_internal=True).sudo()._f3d_ingest(
                [{"code": self.level.code, "ts": at(7, 1), "value": 0.0}], src="module"
            )
            hook.assert_not_called()
            self.push(self.level.code, at(7, 2), 1)
            hook.assert_called_once()

    def test_exception_isolated(self):
        with (
            freeze_time(at(7, 30)),
            mute_logger("odoo.addons.td_bms.models.td_signal"),
            mock.patch(self.CHECK, side_effect=RuntimeError("boom")),
        ):
            res = self.push(self.level.code, at(7, 1), 40)
        self.assertGreater(res["accepted"], 0)
        self.assertEqual(self.level.last_value, 40)

    def test_read_disabled_skips(self):
        self.env["ir.config_parameter"].sudo().set_param("td.bms.read_enabled", "False")
        with freeze_time(at(7, 30)), mock.patch(self.CHECK) as hook:
            self.push(self.level.code, at(7, 1), 40)
            hook.assert_not_called()


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestDerivedSource(RulesCase):
    def test_local_source(self):
        self.assertEqual(self.derived.type, "f3d_bms")
        self.assertFalse(self.derived.collector_id)
        self.assertIn("f3d_bms", self.env["td.source"]._f3d_local_types())

    def test_not_stale_by_telemetry(self):
        self.push(self.level.code, at(7, 0), 100)
        self.step(7, 1)
        self.assertEqual(self.check_sig.status, "ok")
        with freeze_time(at(10, 0)):
            self.env["td.signal"]._cron_stale()
        self.assertEqual(self.check_sig.status, "ok")

    def test_foreign_push_rejected(self):
        col = self.env["td.collector"].create({"code": "COL-BMS-T", "name": "Колектор (тест)"})
        with freeze_time(at(7, 30)):
            res = (
                self.env["td.signal"]
                .sudo()
                ._f3d_ingest(
                    [{"code": self.check_sig.code, "ts": at(7, 1), "text": "норма"}], src="collector", collector=col
                )
            )
        self.assertEqual(res["rejected"][0]["reason"], "foreign_signal")

    def test_heartbeat(self):
        self.push(self.level.code, at(7, 0), 100)
        self.step(7, 5)
        self.assertEqual(self.check_sig.last_ts, at(7, 5))
        self.step(7, 6)
        self.assertEqual(self.check_sig.last_ts, at(7, 5))
        self.step(7, 15)
        self.assertEqual(self.check_sig.last_ts, at(7, 15))
        self.assertEqual(self.derived.state, "online")
