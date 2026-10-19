from odoo.exceptions import UserError, ValidationError
from odoo.tests import tagged

from ..tools import hvac
from .common import F3DBmsCase, F3DBmsHvacMixin


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestNominals(F3DBmsHvacMixin, F3DBmsCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_hvac_fixtures()

    def test_nominals(self):
        none = lambda key: None  # noqa: E731
        self.assertEqual(
            hvac.nominals("roofvent", 1, none), {"airflow_nom": 8000, "heat_nom_kw": 60.0, "p_inst_kw": 4.0}
        )
        self.assertEqual(hvac.nominals("ahu", 1, none)["airflow_nom"], 20000)
        spec = {"airflow_m3h": 7060.0, "power_kw": 0.42}.get
        res = hvac.nominals("fan", 2, spec)
        self.assertEqual((res["airflow_nom"], res["p_inst_kw"]), (14120.0, 0.84))
        res = hvac.nominals("exfan", 1, none)
        self.assertEqual((res["airflow_nom"], res["p_inst_kw"], res["required_m3h"]), (644, 0.18, 160))
        # без паспорта computed-номінали беруться з умовчань R-10 і перекриваються вручну
        unit = self.env["td.bms.hvac.unit"].create(
            {"code": "RV-90", "name": "Тест", "kind": "roofvent", "zone_id": self.zone_hvac.id, "mode_design": "VE"}
        )
        self.assertEqual((unit.airflow_nom, unit.heat_nom_kw, unit.p_inst_kw), (8000, 60.0, 4.0))
        unit.airflow_nom = 9000
        self.assertEqual(unit.airflow_nom, 9000)
        self.assertEqual(self.ef_elec.fan_count, 2)
        self.assertEqual(self.ef_chg.required_m3h, 158.4)

    def test_coordinates(self):
        rv5 = self.rv["RV-05"]
        rv5.write({"x": 21.5, "y": 33.5})
        self.assertEqual((rv5.x, rv5.y), (21.5, 33.5))

    def test_constraints(self):
        Unit = self.env["td.bms.hvac.unit"]
        base = {"name": "Тест", "kind": "roofvent", "zone_id": self.zone_hvac.id, "mode_design": "VE"}
        with self.assertRaises(ValidationError), self.cr.savepoint():
            Unit.create({**base, "code": "RV-5"})
        col = self.env["td.collector"].create({"code": "COL-HV", "name": "Колектор (тест)"})
        src = self.env["td.source"].create(
            {
                "code": "BAC-HV-105",
                "name": "BAC 105",
                "type": "bacnet_ip",
                "collector_id": col.id,
                "params": {"host": "iot-sim", "device": 105},
            }
        )
        with self.assertRaises(ValidationError), self.cr.savepoint():
            Unit.create({**base, "code": "RV-91", "source_id": src.id, "bacnet_device": 106})
        Unit.create({**base, "code": "RV-92", "source_id": src.id, "bacnet_device": 105})
        with self.assertRaises(ValidationError), self.cr.savepoint():
            Unit.create({**base, "code": "RV-93", "mode_design": "thermostat"})


@tagged("post_install", "-at_install", "f3d", "f3d_bms")
class TestState(F3DBmsHvacMixin, F3DBmsCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls._setup_hvac_fixtures()

    def _live(self, unit):
        unit.invalidate_recordset()
        return unit

    def test_mode_labels_states(self):
        ml, st = hvac.mode_label, hvac.unit_state
        self.assertEqual((ml("roofvent", "AQ", "AQ", True), st("roofvent", "running", "AQ")), ("Рекуперація", "on"))
        self.assertEqual(
            (ml("roofvent", "ST", "AQ", False), st("roofvent", "stopped", "ST")), ("Очікування", "standby")
        )
        self.assertEqual((ml("roofvent", "Off", "AQ", False), st("roofvent", "stopped", "Off")), ("Вимкнено", "off"))
        self.assertEqual(st("roofvent", "frost", "VE"), "fault")
        self.assertEqual(ml("ahu", "VE", "VE", True), "Приплив під витяжку фарбувальних камер")
        self.assertEqual(
            (ml("fan", None, "thermostat", True, 2), st("fan", "running")), ("Увімкнено 2 з 2 (термостат)", "on")
        )
        self.assertEqual(
            (ml("fan", None, "thermostat", False, 1), st("fan", "stopped")), ("Чекає (термостат)", "standby")
        )
        self.assertEqual(
            ml("exfan", None, "charging", True, 1, 158.4), "Безперервно під час заряджання, не менше 158 м³/год"
        )
        self.assertEqual(st("exfan", "stopped_charging"), "fault")
        # через модель
        rv5 = self.rv["RV-05"]
        rv5.state_signal_id = self.make_signal("ventilation/units/RV-05/state", text="running", kind="state")
        rv5.mode_signal_id = self.make_signal("ventilation/units/RV-05/mode", text="AQ", kind="state")
        self._live(rv5)
        self.assertEqual((rv5.state, rv5.mode_label, rv5.mode_code), ("on", "Рекуперація", "AQ"))
        self.ef_chg.state_signal_id = self.make_signal(
            "ventilation/units/EF-CHG/state", text="stopped_charging", kind="state"
        )
        self.assertEqual(self._live(self.ef_chg).state, "fault")

    def test_fallback_formulas(self):
        f = hvac.fallback_heat("roofvent", 0.72, "AQ", 9.0)
        self.assertAlmostEqual(f["heat"], 6.88, 2)
        self.assertEqual((round(f["heat"], 1), f["valve"], f["p_now"]), (6.9, 0.06, 3.31))
        f = hvac.fallback_heat("roofvent", 0.68, "VE", 9.0)
        self.assertEqual((round(f["heat"], 2), f["valve"]), (17.33, 0.15))
        self.assertAlmostEqual(hvac.fallback_heat("roofvent", 0.45, "REC", 9.0)["heat"], 11.47, 2)
        self.assertEqual(hvac.fallback_heat("roofvent", 0.72, "ST", 9.0)["heat"], 0)
        self.assertAlmostEqual(
            hvac.fallback_heat("ahu", 0.85, "VE", 9.0, airflow=17000.0, p_inst=15.0)["heat"], 68.0, 1
        )
        self.assertAlmostEqual(hvac.fallback_heat("roofvent", 0.72, "AQ", -10.0)["heat"], 21.4, 1)
        self.assertEqual(hvac.fallback_power("fan", 1.0, 0.84, True), 0.84)
        self.assertEqual(hvac.fallback_power("fan", 0.0, 0.84, False), 0)

    def test_live_precedence(self):
        rv5 = self.rv["RV-05"]
        static = {"RV-05": {"airflow_m3h": 5912.6, "heat_kw": 6.9, "filter_dp_pa": 287.2, "state": "on"}}
        rv5 = rv5.with_context(f3d_bms_static_units=static)
        self.assertEqual((rv5.airflow_m3h, rv5.heat_kw, rv5.filter_dp_pa, rv5.stale), (5912.6, 6.9, 287.2, True))
        rv5.airflow_signal_id = self.make_signal("ventilation/units/RV-05/airflow_m3h", 6000.0, unit="м³/год")
        self._live(rv5)
        self.assertEqual((rv5.airflow_m3h, rv5.heat_kw, rv5.stale), (6000.0, 7.2, False))
        rv5.heat_signal_id = self.make_signal("ventilation/units/RV-05/heat_kw", 8.1, unit="кВт")
        rv5.valve_signal_id = self.make_signal("ventilation/units/RV-05/valve_pct", 12.0, unit="%")
        self._live(rv5)
        self.assertEqual((rv5.heat_kw, rv5.heating_valve), (8.1, 0.12))

    def test_heat_now_contract(self):
        res = self.env["td.bms.hvac.unit"]._td_bms_heat_now()
        self.assertEqual(len(res), 26)
        self.assertNotIn("EF-ELEC", res)
        self.assertIn("AHU-1", res)
        static = {code: {"heat_kw": 322 / 26} for code in res}
        self.env.invalidate_all()
        res = self.env["td.bms.hvac.unit"].with_context(f3d_bms_static_units=static)._td_bms_heat_now()
        self.assertAlmostEqual(sum(res.values()), 322, delta=0.5)

    def test_command_refused_for_fans(self):
        with self.assertRaises(UserError):
            self.ef_elec.action_open_command()
