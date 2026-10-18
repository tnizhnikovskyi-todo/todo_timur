from datetime import datetime
from freezegun import freeze_time

from odoo.tests import tagged

from .common import F3DBmsCase, F3DBmsHvacMixin, F3DBmsRulesMixin

CHECK_STATES = [
    "норма",
    "поза робочим часом",
    "не працює в робочий час",
    "холодно в зоні",
    "немає даних",
    "зупинено пожежною сигналізацією",
    "немає мережі (живлення від резерву)",
]


def at(hour, minute, day=14):
    return datetime(2026, 10, day, hour, minute)  # вт 14.10.2026; Київ = UTC+3


class HvacRulesCase(F3DBmsRulesMixin, F3DBmsHvacMixin, F3DBmsCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_hvac_fixtures()
        cls._setup_rules()
        cls.zone_hvac.name = "Склад плит"
        cls.unit_signals(cls.rv["RV-05"], "Установка RV-05")
        cls.unit_signals(cls.rv["RV-07"], "Дахова установка RV-07")
        cls.rv5 = cls.rv["RV-05"]
        cls.rv7 = cls.rv["RV-07"]

    @classmethod
    def unit_signals(cls, unit, eq_name):
        cls.env["maintenance.equipment"].create({"name": eq_name})
        base = "ventilation/units/%s/" % unit.code
        unit.write(
            {
                "airflow_signal_id": cls.define(base + "airflow_m3h").id,
                "state_signal_id": cls.define(base + "state", eq_name, kind="state").id,
                "mode_signal_id": cls.define(base + "mode", kind="state").id,
                "indoor_signal_id": cls.define(base + "indoor_c").id,
                "heat_signal_id": cls.define(base + "heat_kw").id,
                "check_signal_id": cls.define(
                    base + "check",
                    eq_name,
                    states=CHECK_STATES,
                    alarm_states=["не працює в робочий час", "холодно в зоні"],
                ).id,
            }
        )

    def step(self, unit, hour, minute, day=14):
        with freeze_time(at(hour, minute, day)):
            self.run_check()
        return unit.check_signal_id.last_text

    def put(self, unit, hour, minute, state=None, mode=None, indoor=None, airflow=None, day=14):
        base = "ventilation/units/%s/" % unit.code
        with freeze_time(at(hour, minute, day)):
            if state is not None:
                self.push(base + "state", at(hour, minute, day), text=state)
            if mode is not None:
                self.push(base + "mode", at(hour, minute, day), text=mode)
            if indoor is not None:
                self.push(base + "indoor_c", at(hour, minute, day), value=indoor)
            if airflow is not None:
                self.push(base + "airflow_m3h", at(hour, minute, day), value=airflow)

    def _setup_deficit(self):
        bal = self.balance
        sig = self.define("ventilation/heat_plant/check", "BOILER", states=["норма", "дефіцит тепла", "немає даних"])
        sig.alarm_states = ["дефіцит тепла"]
        bal.write(
            {
                "check_signal_id": sig.id,
                "chp_heat_signal_id": self.define("infra/totals/chp_heat_kw").id,
                "boiler_state_signal_id": self.define("equipment/BOILER/state", kind="state").id,
            }
        )
        self.push("infra/totals/chp_heat_kw", at(7, 0), 497.0)
        self.push("equipment/BOILER/state", at(7, 0), text="fault")
        units = self.env["f3d.bms.hvac.unit"].search([("kind", "in", ("roofvent", "ahu"))])
        for unit in units:
            unit.heat_signal_id = self.define("ventilation/units/%s/heat_kw" % unit.code)
            self.push("ventilation/units/%s/heat_kw" % unit.code, at(7, 0), 23.0 if unit != units[-1] else 25.0)
        return sig


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestUnitRules(HvacRulesCase):
    def test_not_running(self):
        self.put(self.rv5, 6, 50, state="stopped", mode="ST", airflow=0.0)
        self.assertEqual(self.rv5.off_since, at(6, 50))
        self.assertEqual(self.step(self.rv5, 6, 59), "норма")
        self.assertEqual(self.step(self.rv5, 7, 0), "не працює в робочий час")
        self.assertEqual(self.rv5.check_signal_id.status, "alarm")
        self.assertEqual(len(self.requests(self.rv5.check_signal_id)), 1)

    def test_vel_ok(self):
        self.put(self.rv5, 6, 50, state="running", mode="VEL", airflow=2000.0)
        self.assertFalse(self.rv5.off_since)
        self.assertEqual(self.step(self.rv5, 7, 0), "норма")

    def test_fault_separate(self):
        self.put(self.rv5, 6, 50, state="fault", mode="ST", airflow=0.0)
        self.assertFalse(self.rv5.off_since)
        self.assertEqual(self.step(self.rv5, 7, 0), "норма")

    def test_fans_no_check(self):
        self.assertFalse(self.ef_elec.check_signal_id)
        self.run_check()  # без помилок

    def test_cold_work(self):
        self.put(self.rv5, 6, 30, state="running", mode="AQ", indoor=15.5, airflow=8000.0)
        self.assertEqual(self.rv5.cold_since, at(6, 30))
        self.assertEqual(self.step(self.rv5, 6, 59), "норма")
        self.assertEqual(self.step(self.rv5, 7, 0), "холодно в зоні")

    def test_cold_off_hours(self):
        self.put(self.rv5, 19, 20, state="running", mode="AQ", indoor=15.0, airflow=8000.0)
        self.assertEqual(self.step(self.rv5, 19, 25), "поза робочим часом")  # 22:25 Київ, 15 °C
        self.put(self.rv5, 19, 26, indoor=9.0)
        self.assertEqual(self.rv5.cold_off_since, at(19, 26))
        self.assertEqual(self.step(self.rv5, 19, 55), "поза робочим часом")
        self.assertEqual(self.step(self.rv5, 19, 56), "холодно в зоні")

    def test_fire_suppression_signal(self):
        fire = self.define("fire/totals/system_state", kind="state")
        self.put(self.rv7, 6, 50, state="stopped", mode="ST", airflow=0.0)
        self.push(fire.code, at(7, 0), text="test")
        self.assertEqual(self.step(self.rv7, 7, 0), "зупинено пожежною сигналізацією")
        self.assertFalse(self.rv7.off_since)
        self.assertFalse(self.requests(self.rv7.check_signal_id))
        self.push(fire.code, at(7, 5), text="normal")
        self.assertEqual(self.step(self.rv7, 7, 5), "норма")
        self.assertEqual(self.step(self.rv7, 7, 14), "норма")
        self.assertEqual(self.step(self.rv7, 7, 15), "не працює в робочий час")

    def test_mains(self):
        mains = self.define("infra/ats/src1_ok")
        self.push(mains.code, at(7, 0), 0)
        self.put(self.rv5, 6, 50, state="stopped", mode="ST", airflow=0.0)
        self.assertEqual(self.step(self.rv5, 7, 30), "немає мережі (живлення від резерву)")


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestThresholds(HvacRulesCase):
    def alarm_request(self, code, ts, value=None, text=None):
        with freeze_time(at(7, 30)):
            self.push(code, ts, value=value, text=text)
        return self.requests(self.env["f3d.signal"].search([("code", "=", code)]))

    def test_filter_supply_rv05(self):
        sig = self.define(
            "ventilation/units/RV-05/filter_dp_pa",
            "RV-05",
            alarm_high=250.0,
            alarm_high_on=True,
            hysteresis=5.0,
            decimals=0,
            unit="Па",
            alarm_title="Заміна фільтрів: перепад тиску {value} Па при нормі до {threshold}",
        )
        self.rv5.filter_signal_id = sig
        reqs = self.alarm_request(sig.code, at(7, 1), 285.2)
        self.assertEqual(len(reqs), 1)
        self.assertEqual(reqs.name, "Заміна фільтрів: перепад тиску 285 Па при нормі до 250")
        self.assertEqual(reqs.f3d_bms_rule, "filter_supply")
        self.alarm_request(sig.code, at(7, 2), 248.0)
        self.assertEqual(sig.status, "alarm")
        self.alarm_request(sig.code, at(7, 3), 244.0)
        self.assertEqual(sig.status, "ok")

    def test_filter_extract(self):
        sig = self.define(
            "ventilation/units/RV-05/filter_extract_dp_pa",
            "RV-05",
            alarm_high=350.0,
            alarm_high_on=True,
            hysteresis=10.0,
            decimals=0,
            alarm_title="Заміна фільтрів витяжки: перепад тиску {value} Па при нормі до {threshold}",
        )
        reqs = self.alarm_request(sig.code, at(7, 1), 360.0)
        self.assertEqual(reqs.name, "Заміна фільтрів витяжки: перепад тиску 360 Па при нормі до 350")
        self.assertEqual(reqs.f3d_bms_rule, "filter_extract")

    def test_unit_fault_frost(self):
        sig = self.rv7.state_signal_id
        sig.write({"states": ["running", "stopped", "fault", "frost"], "alarm_states": ["fault", "frost"]})
        sig.alarm_title = "{equipment}: аварія установки (стан «{text}»)"
        reqs = self.alarm_request(sig.code, at(7, 1), text="fault")
        self.assertEqual(reqs.name, "Дахова установка RV-07: аварія установки (стан «fault»)")
        self.assertEqual(reqs.f3d_bms_rule, "unit_fault")

    def test_ef_chg_charging(self):
        sig = self.define(
            "ventilation/units/EF-CHG/state",
            "EF-CHG",
            kind="state",
            states=["running", "stopped", "stopped_charging"],
            alarm_states=["stopped_charging"],
            alarm_title="Витяжка зарядної станції (Ex): не працює під час заряджання — водень!",
        )
        reqs = self.alarm_request(sig.code, at(7, 1), text="stopped_charging")
        self.assertEqual(reqs.f3d_bms_rule, "charging_vent")

    def test_ef_elec_overheat(self):
        sig = self.define(
            "ventilation/units/EF-ELEC/indoor_c",
            "EF-ELEC",
            alarm_high=35.0,
            alarm_high_on=True,
            hysteresis=1.0,
            min_duration_s=600,
            decimals=0,
            alarm_title="Електрощитова: температура {value} °C при нормі до {threshold}",
        )
        self.assertFalse(self.alarm_request(sig.code, at(7, 0), 36.2))
        self.assertFalse(self.alarm_request(sig.code, at(7, 9), 36.2))
        reqs = self.alarm_request(sig.code, at(7, 10), 36.2)
        self.assertEqual(reqs.name, "Електрощитова: температура 36 °C при нормі до 35")
        self.assertEqual(reqs.f3d_bms_rule, "overheat")

    def test_ahu_pressure(self):
        sig = self.define(
            "ventilation/units/AHU-1/room_pressure_pa",
            "AHU-1",
            alarm_high=0.0,
            alarm_high_on=True,
            hysteresis=1.0,
            min_duration_s=300,
            decimals=0,
            alarm_title="Дільниця фасадів: тиск {value} Па при нормі до {threshold} (має бути розрідження)",
        )
        self.assertFalse(self.alarm_request(sig.code, at(7, 0), 2.0))
        reqs = self.alarm_request(sig.code, at(7, 5), 2.0)
        self.assertEqual(reqs.f3d_bms_rule, "pressure")

    def test_boiler_fault(self):
        sig = self.define(
            "equipment/BOILER/state",
            "BOILER",
            kind="state",
            states=["standby", "K1", "K1+K2", "fault"],
            alarm_states=["fault"],
            alarm_title="{equipment}: аварія котельні (стан «{text}»)",
        )
        reqs = self.alarm_request(sig.code, at(7, 1), text="fault")
        self.assertEqual(reqs.f3d_bms_rule, "boiler_fault")

    def test_heat_deficit(self):
        sig = self._setup_deficit()
        with freeze_time(at(7, 1)):
            self.run_check()
        self.assertEqual(self.balance.deficit_since, at(7, 1))
        with freeze_time(at(7, 30)):
            self.run_check()
        self.assertEqual(sig.last_text, "норма")
        with freeze_time(at(7, 31)):
            self.run_check()
        self.assertEqual(sig.last_text, "дефіцит тепла")
        self.assertEqual(self.balance.deficit_kw, 103.0)

    def test_heat_no_data(self):
        sig = self._setup_deficit()
        units = self.env["f3d.bms.hvac.unit"].search([("kind", "in", ("roofvent", "ahu"))])
        for unit in units[:14]:
            unit.heat_signal_id.sudo().status = "unknown"
        with freeze_time(at(7, 1)):
            self.run_check()
        self.assertEqual(sig.last_text, "немає даних")
