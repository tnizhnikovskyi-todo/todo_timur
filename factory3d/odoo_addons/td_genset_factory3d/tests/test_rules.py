import json
from unittest import mock

from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import AccessError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from odoo.addons.td_factory3d.tests.common import F3DCase

from ..adapters import telemetry

TD = "odoo.addons.td_genset_factory3d.adapters.td_genset"
STATE_MAP = {
    "standby": 1,
    "mains abnormal": 2,
    "starting": 3,
    "safety on": 4,
    "warming": 5,
    "running": 6,
    "cooling": 8,
    "stopping": 9,
    "alarm": 10,
}
MODE_MAP = {"stop": 0, "manual": 1, "auto": 2, "test": 3}
BREAKER_MAP = {"none": 0, "mains": 1, "generator": 2}
SERVICE_DEFAULT = {
    "hours_now": 1213.0,
    "interval_h": 250.0,
    "next_service_hours": 1250.0,
    "last_service_hours": 1000.0,
    "last_service_date": None,
    "due": False,
    "hours_left": 37.0,
}
SNAP_LOADED = {
    "online": True,
    "state_raw": "running",
    "mode_raw": "auto",
    "mains_ok": False,
    "breaker_raw": "generator",
    "p_kw": 348.0,
    "u_v": 400.2,
    "f_hz": 50.0,
    "i_a": 628.0,
    "pf": 0.8,
    "kwh": 61255.3,
    "fuel_pct": 82.0,
    "fuel_l": None,
    "hours": 1213.0,
    "starts": 185,
    "coolant_c": 84.1,
    "oil_bar": 4.4,
    "batt_v": 25.3,
    "charger_v": 27.6,
    "rpm": 1502,
    "alarms": [],
    "mains_u_v": 0.0,
    "mains_f_hz": 0.0,
}


class GensetCase(F3DCase):
    """Фікстури моста (SPEC §13.0): адаптер td_genset замокано, генератор td_genset — res.partner."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        env = cls.env
        Passport, Equipment = env["td.equipment.passport"], env["maintenance.equipment"]
        cls.passport = Passport.search([("role", "=", "genset")], limit=1) or Passport.create(
            {"role": "genset", "manufacturer": "KOHLER-SDMO", "model": "D700"}
        )
        cls.passport_comp = Passport.search([("role", "=", "compressor")], limit=1) or Passport.create(
            {"role": "compressor", "manufacturer": "Atlas Copco", "model": "GA 37 VSD+"}
        )
        cls.genset_eq = Equipment.search([("td_code", "=", "GENSET")], limit=1) or Equipment.create(
            {
                "name": "Дизель-генератор",
                "serial_no": "GENSET",
                "td_code": "GENSET",
                "td_passport_id": cls.passport.id,
            }
        )
        env["td.genset3d.link"].search([]).write({"publish_enabled": False})
        env["td.genset3d.link"].search([("equipment_id", "=", cls.genset_eq.id)]).unlink()
        cls.profile = env.ref("td_genset_factory3d.profile_d700")
        cls.td_gen = env["res.partner"].create({"name": "Генератор td_genset (тест)"})

    def setUp(self):
        super().setUp()
        self.snap_value = {}
        patcher = mock.patch.multiple(
            TD,
            GENSET_MODEL="res.partner",
            STATE_MAP=STATE_MAP,
            MODE_MAP=MODE_MAP,
            BREAKER_MAP=BREAKER_MAP,
            SERVICE_REQUESTS_BY_TD=False,
            generators=mock.MagicMock(return_value=self.td_gen),
            snapshot=mock.MagicMock(side_effect=lambda g: self.snap_value),
            service_info=mock.MagicMock(return_value=SERVICE_DEFAULT),
            open_action=mock.MagicMock(return_value={"type": "ir.actions.act_window"}),
            set_fuel_rate=mock.MagicMock(return_value=True),
        )
        patcher.start()
        self.addCleanup(patcher.stop)
        self.set_param("read_enabled", "True")
        self.set_param("requests_enabled", "True")
        self.set_param("offline_min", "5")
        self.link = self.env["td.genset3d.link"].create(
            {
                "equipment_id": self.genset_eq.id,
                "td_genset_ref": "res.partner,%d" % self.td_gen.id,
                "profile_id": self.profile.id,
            }
        )
        telemetry.ensure_source(self.env, self.link)
        telemetry.ensure_signals(self.env, self.link)
        self.snap()

    def set_param(self, key, value):
        self.env["ir.config_parameter"].sudo().set_param("td.genset." + key, value)

    def snap(self, **over):
        self.snap_value = {"ts": fields.Datetime.now().replace(microsecond=0), **SNAP_LOADED, **over}
        return self.snap_value

    def make_ats(self, position, src1, age_s=0, period_s=10):
        from datetime import timedelta

        Signal = self.env["td.signal"]
        ts = fields.Datetime.now().replace(microsecond=0) - timedelta(seconds=age_s)
        batch = []
        # власні коди: сигнали infra/ats/* з energy мають kind=state і не приймають числа
        self.set_param("ats_position_code", "infra/ats-t/position")
        self.set_param("ats_src1_code", "infra/ats-t/src1_ok")
        for leaf, value in (("position", position), ("src1_ok", src1), ("src2_ok", 1)):
            code = "infra/ats-t/" + leaf
            if not Signal.search([("code", "=", code)]):
                Signal.create(
                    {
                        "code": code,
                        "name": "АВР " + leaf,
                        "kind": "gauge",
                        "period_s": period_s,
                        "store_period_s": 0,
                        "create_request": False,
                    }
                )
            batch.append({"code": code, "ts": ts, "value": float(value), "q": "good"})
        Signal._f3d_ingest(batch, src="module")


@tagged("post_install", "-at_install")
class TestLinkConstraints(GensetCase):
    def test_unique_equipment(self):  # AC-02
        other = self.env["res.partner"].create({"name": "Інший генератор"})
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"), self.cr.savepoint():
            self.env["td.genset3d.link"].create(
                {
                    "equipment_id": self.genset_eq.id,
                    "td_genset_ref": "res.partner,%d" % other.id,
                    "profile_id": self.profile.id,
                }
            )

    def test_bad_equipment(self):  # AC-03
        other = self.env["res.partner"].create({"name": "Інший генератор"})
        Equipment = self.env["maintenance.equipment"]
        nocode = Equipment.create({"name": "Без коду", "td_passport_id": self.passport.id})
        comp = Equipment.create({"name": "Компресор", "td_code": "COMP-T", "td_passport_id": self.passport_comp.id})
        vals = {"td_genset_ref": "res.partner,%d" % other.id, "profile_id": self.profile.id}
        with self.assertRaisesRegex(ValidationError, "не має коду сцени"), self.cr.savepoint():
            self.env["td.genset3d.link"].create({**vals, "equipment_id": nocode.id})
        with self.assertRaisesRegex(ValidationError, "має роль «compressor», потрібна «genset»"), self.cr.savepoint():
            self.env["td.genset3d.link"].create({**vals, "equipment_id": comp.id})


@tagged("post_install", "-at_install")
class TestFuel(GensetCase):
    def test_fuel_curve(self):  # AC-04
        expected = {0: 38.6, 25: 38.6, 50: 71.2, 68.6: 95.5, 75: 103.8, 100: 136.4, 105: 143.0, 110: 149.5, 150: 149.5}
        for load, lph in expected.items():
            self.assertEqual(self.profile.fuel_lph(load), lph, load)

    def test_autonomy(self):  # AC-05
        for fuel, load, hours in ((500, 75, 4.8), (500, 68.6, 5.2), (610, 75, 5.9), (610, 100, 4.5), (0, 75, 0.0)):
            self.assertEqual(self.profile.autonomy_h(fuel, load), hours, (fuel, load))
        with mock.patch.object(type(self.profile), "fuel_lph", return_value=0.0):
            self.assertIsNone(self.profile.autonomy_h(500, 75))

    def test_curve_monotonic(self):  # AC-06
        with self.assertRaisesRegex(ValidationError, "Крива витрати має бути неспадною."):
            self.profile.fuel_lph_50 = 30
        with self.assertRaises(ValidationError):
            self.profile.tank_l = 0


@tagged("post_install", "-at_install")
class TestCodes(GensetCase):
    def codes(self, **over):
        return self.link._state_codes(self.snap(**over))[0]

    def test_state_by_breaker_or_power(self):  # AC-65, DEC-11
        self.assertEqual(self.codes(p_kw=0.0)["state"], 7)  # breaker == generator
        self.assertEqual(self.codes(breaker_raw="mains", p_kw=30.0)["state"], 7)  # ≥ 5 % PRP (25,35 кВт)
        self.assertEqual(self.codes(breaker_raw="mains", p_kw=10.0)["state"], 6)
        self.assertEqual(self.codes(state_raw="standby", mains_ok=False, breaker_raw="mains")["state"], 2)
        self.assertEqual(self.codes(state_raw="standby", mains_ok=True, breaker_raw="mains")["state"], 1)

    def test_load_and_fuel_l(self):
        for p_kw, pct in ((348.0, 68.6), (507.0, 100.0), (0.0, 0.0)):
            self.assertEqual(self.link._compute_values(self.snap(p_kw=p_kw))["load_pct"], pct)
        self.assertEqual(self.link._compute_values(self.snap())["fuel_l"], 500.2)

    def test_unknown_state(self):
        errors = []
        vals = self.link._compute_values(self.snap(state_raw="bogus"), errors)
        self.assertEqual(vals["state"], 0)
        self.assertTrue(errors)

    def test_service_alarms_filtered(self):  # DEC-9
        service = [
            {"code": "link_lost", "severity": "shutdown"},
            {"code": "cmd_unconfirmed", "severity": "warning"},
            {"code": "relay_health", "severity": "warning"},
        ]
        codes = self.codes(alarms=service)
        self.assertEqual((codes["alarm_level"], codes["alarm_count"]), (0, 0))
        codes = self.codes(alarms=service + [{"code": "oil_low_shutdown", "severity": "shutdown"}])
        self.assertEqual((codes["alarm_level"], codes["alarm_count"]), (2, 1))


@tagged("post_install", "-at_install")
class TestIsland(GensetCase):
    def test_ats_priority(self):  # AC-29
        self.make_ats(3, 0, age_s=5)
        res = self.link._island_state(self.snap())
        self.assertEqual((res["island"], res["grid_ok"], res["source"]), (True, False, "ats"))
        self.make_ats(2, 1)
        res = self.link._island_state(self.snap())
        self.assertEqual((res["island"], res["grid_ok"], res["source"]), (False, True, "ats"))

    def test_ats_stale_fallback_hgm(self):
        self.make_ats(3, 0, age_s=31)
        res = self.link._island_state(self.snap())
        self.assertEqual((res["island"], res["grid_ok"], res["source"]), (True, False, "hgm"))

    def test_offline_last_known(self):
        self.link.last_state_json = {"island": True}
        res = self.link._island_state(self.snap(online=False))
        self.assertEqual((res["island"], res["grid_ok"], res["source"]), (True, None, "stale"))

    def test_amf_master_no_effect(self):  # AC-31
        self.set_param("amf_master", "ats")
        self.make_ats(3, 0)
        res = self.link._island_state(self.snap())
        self.assertEqual((res["island"], res["grid_ok"], res["source"]), (True, False, "ats"))


@tagged("post_install", "-at_install")
class TestCritical(GensetCase):
    def _nodes(self):
        Node, Signal = self.env["td.energy.node"], self.env["td.signal"]
        parent = Node.search([("kind", "=", "section")], limit=1)
        if not parent:
            self.skipTest("немає вузла-секції energy")
        Node.search([("is_critical", "=", True)]).write({"is_critical": False})
        specs = (
            ("CR-A", "consumer", "consumers", 12.0),
            ("CR-B", "consumer", "consumers", 10.0),
            ("CR-L", "line", "lines", 100.0),
        )
        self.signals = {}
        for code, kind, folder, value in specs:
            vals = {"code": code, "name": "Вузол " + code, "kind": kind, "parent_id": parent.id, "is_critical": True}
            if kind == "line":
                vals["line_kind"] = "busway"
            self.node = Node.create(vals)
            sig_code = "energy/%s/%s/p_now" % (folder, code)
            self.signals[code] = Signal.create(
                {
                    "code": sig_code,
                    "name": sig_code,
                    "kind": "gauge",
                    "unit": "кВт",
                    "last_value": value,
                    "last_ts": fields.Datetime.now(),
                    "create_request": False,
                }
            )

    def test_sum_and_missing(self):  # AC-32
        self._nodes()
        self.signals["CR-L"].active = False
        total, missing, names = self.link._critical_kw()
        self.assertEqual((total, missing), (22.0, ["energy/lines/CR-L/p_now"]))
        self.assertEqual(len(names), 2)

    def test_fallback_param(self):  # AC-70
        self._nodes()
        self.set_param("critical_codes", "energy/consumers/CR-B/p_now")
        self.assertEqual(self.link._critical_kw()[0], 122.0)  # вузли є — параметр ігнорується
        self.env["td.energy.node"].search([("is_critical", "=", True)]).write({"is_critical": False})
        total, missing, names = self.link._critical_kw()
        self.assertEqual((total, missing, names), (10.0, [], ["CR-B"]))


@tagged("post_install", "-at_install")
class TestProfileExport(GensetCase):
    def test_export_json(self):  # AC-42
        profile = self.profile.with_user(self.user_manager)
        action = profile.action_export_relay_profile()
        att = self.env["ir.attachment"].search(
            [("res_model", "=", "td.genset3d.profile"), ("res_id", "=", self.profile.id)], order="id desc", limit=1
        )
        self.assertEqual(att.mimetype, "application/json")
        self.assertIn(str(att.id), action["url"])
        data = json.loads(att.raw)
        for key in ("profile", "rated", "tank_l", "fuel_lph", "timers", "timers_plant", "sensors", "alarms", "start"):
            self.assertIn(key, data)
        self.assertEqual(data["fuel_lph"]["75"], 103.8)
        self.assertEqual(data["timers"]["mains_abnormal_s"], 5)
        self.assertEqual(data["timers"]["crank_fire_s"], 3)

    def test_apply_to_td(self):  # AC-42, AC-60
        action = self.profile.with_user(self.user_manager).action_apply_to_td()
        message = action["params"]["message"]
        self.assertIn("Записано в td_genset: 1", message)
        self.assertIn("пропущено (крива/поля немає): 0", message)
        import odoo.addons.td_genset_factory3d.adapters.td_genset as td

        args = td.set_fuel_rate.call_args[0]
        self.assertEqual((args[0], args[1]), (self.td_gen, 103.8))
        with self.assertRaises(AccessError):
            self.profile.with_user(self.user_reader).action_apply_to_td()
